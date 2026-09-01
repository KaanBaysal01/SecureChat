from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Conversation, Message
from .crypto import encrypt_message, decrypt_message
import io
import os
import tempfile
from pathlib import Path
from cryptography.exceptions import InvalidTag
from .filecrypto import (
    encrypt_to_file,
    decrypt_from_file,
    MAGIC,
    PREFIX_LEN,
    CHUNK_SIZE,
    TAG_LEN,
)
from django.test import override_settings
from django.urls import reverse

User = get_user_model()


class CryptoTest(TestCase):

    def test_encrypt_decrypt_roundtrip(self):
        original = "gizli mesaj"
        encrypted = encrypt_message(original)
        self.assertEqual(decrypt_message(encrypted), original)

    def test_ciphertext_is_not_plaintext(self):
        original = "gizli mesaj"
        encrypted = encrypt_message(original)
        self.assertNotIn(original, encrypted)

    def test_same_input_gives_different_ciphertext(self):
        a = encrypt_message("aynı metin")
        b = encrypt_message("aynı metin")
        self.assertNotEqual(a, b)
        self.assertEqual(decrypt_message(a), decrypt_message(b))

    def test_turkish_characters(self):
        original = "şğüöçİ ırmak"
        self.assertEqual(decrypt_message(encrypt_message(original)), original)

    def test_invalid_token_returns_placeholder(self):
        self.assertEqual(decrypt_message("bozuk-veri"), "[çözülemedi]")


class MessageModelTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="test12345")
        self.conversation = Conversation.objects.create()
        self.conversation.participants.add(self.user)

    def test_message_stored_encrypted(self):
        plaintext = "veritabanında görünmemeli"
        message = Message.objects.create(
            conversation=self.conversation,
            sender=self.user,
            encrypted_content=encrypt_message(plaintext),
        )
        self.assertNotEqual(message.encrypted_content, plaintext)
        self.assertEqual(message.content, plaintext)

class FileCryptoTest(TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "blob.scf"

    def tearDown(self):
        self.tmp.cleanup()

    def _encrypt(self, data):
        return encrypt_to_file(io.BytesIO(data), self.path)

    def _decrypt(self, wrapped):
        return b"".join(decrypt_from_file(self.path, wrapped))

    def _chunks(self):
        blob = self.path.read_bytes()
        head = len(MAGIC) + PREFIX_LEN
        header, body = blob[:head], blob[head:]
        size = CHUNK_SIZE + TAG_LEN
        return header, [body[i:i + size] for i in range(0, len(body), size)]

    def test_roundtrip_small(self):
        data = b"kucuk bir dosya"
        self.assertEqual(self._decrypt(self._encrypt(data)), data)

    def test_roundtrip_multi_chunk(self):
        data = os.urandom(CHUNK_SIZE * 3 + 123)
        self.assertEqual(self._decrypt(self._encrypt(data)), data)

    def test_roundtrip_empty_file(self):
        self.assertEqual(self._decrypt(self._encrypt(b"")), b"")

    def test_plaintext_not_on_disk(self):
        data = b"MAAS BORDROSU GIZLI" * 100
        self._encrypt(data)
        self.assertNotIn(b"MAAS BORDROSU", self.path.read_bytes())

    def test_each_file_gets_a_different_key(self):
        a = self._encrypt(b"ayni icerik")
        b = self._encrypt(b"ayni icerik")
        self.assertNotEqual(a, b)

    def test_reordered_chunks_rejected(self):
        wrapped = self._encrypt(os.urandom(CHUNK_SIZE * 3))
        header, chunks = self._chunks()
        chunks[0], chunks[1] = chunks[1], chunks[0]
        self.path.write_bytes(header + b"".join(chunks))

        with self.assertRaises(InvalidTag):
            self._decrypt(wrapped)

    def test_truncated_file_rejected(self):
        wrapped = self._encrypt(os.urandom(CHUNK_SIZE * 3))
        header, chunks = self._chunks()
        self.path.write_bytes(header + b"".join(chunks[:-1]))

        with self.assertRaises(InvalidTag):
            self._decrypt(wrapped)

    def test_flipped_byte_rejected(self):
        wrapped = self._encrypt(os.urandom(CHUNK_SIZE * 2))
        blob = bytearray(self.path.read_bytes())
        blob[100] ^= 0xFF
        self.path.write_bytes(bytes(blob))

        with self.assertRaises(InvalidTag):
            self._decrypt(wrapped)

    def test_wrong_key_rejected(self):
        self._encrypt(b"gizli")
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from .crypto import get_fernet
        baska = get_fernet().encrypt(AESGCM.generate_key(bit_length=256))

        with self.assertRaises(InvalidTag):
            self._decrypt(baska)


class FileAccessTest(TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

        patcher = override_settings(SECURE_FILE_ROOT=self.tmp.name)
        patcher.enable()
        self.addCleanup(patcher.disable)

        self.sender = User.objects.create_user(username="gonderen", password="test12345")
        self.member = User.objects.create_user(username="katilimci", password="test12345")
        self.outsider = User.objects.create_user(username="yabanci", password="test12345")

        self.conversation = Conversation.objects.create()
        self.conversation.participants.add(self.sender, self.member)

        self.payload = b"gizli fotograf verisi"
        wrapped = encrypt_to_file(
            io.BytesIO(self.payload),
            Path(self.tmp.name) / "test.scf",
        )

        self.message = Message.objects.create(
            conversation=self.conversation,
            sender=self.sender,
            file_name="tatil.jpg",
            file_size=len(self.payload),
            file_type="image/jpeg",
            file_path="test.scf",
            file_key=wrapped,
        )
        self.url = reverse("chat:file", args=[self.message.id])

    def test_sender_can_download(self):
        self.client.login(username="gonderen", password="test12345")
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), self.payload)

    def test_participant_can_download(self):
        self.client.login(username="katilimci", password="test12345")
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), self.payload)

    def test_outsider_gets_404(self):
        self.client.login(username="yabanci", password="test12345")
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

    def test_blob_deleted_with_message(self):
        blob = Path(self.tmp.name) / "test.scf"
        self.assertTrue(blob.exists())

        self.message.delete()

        self.assertFalse(blob.exists())


class PinTest(TestCase):

    def setUp(self):
        self.ali = User.objects.create_user(username="ali", password="test12345")
        self.ayse = User.objects.create_user(username="ayse", password="test12345")
        self.can = User.objects.create_user(username="can", password="test12345")

        self.chat = Conversation.objects.create()
        self.chat.participants.add(self.ali, self.ayse)

        self.group = Conversation.objects.create(is_group=True, name="Ekip")
        self.group.participants.add(self.ali, self.ayse, self.can)
        self.group.admins.add(self.ali)

        self.message = Message.objects.create(
            conversation=self.chat,
            sender=self.ali,
            encrypted_content=encrypt_message("sabitlenecek mesaj"),
        )

    def _pin(self, conversation, message, user):
        conversation.pinned_message = message
        conversation.pinned_by = user
        conversation.save()

    def test_cannot_unpin_when_nothing_pinned(self):
        self.assertFalse(self.chat.can_unpin(self.ali))

    def test_pinner_can_unpin(self):
        self._pin(self.chat, self.message, self.ali)
        self.assertTrue(self.chat.can_unpin(self.ali))

    def test_other_participant_cannot_unpin_in_direct_chat(self):
        self._pin(self.chat, self.message, self.ali)
        self.assertFalse(self.chat.can_unpin(self.ayse))

    def test_group_admin_can_unpin_someone_elses_pin(self):
        msg = Message.objects.create(
            conversation=self.group,
            sender=self.ayse,
            encrypted_content=encrypt_message("grup mesaji"),
        )
        self._pin(self.group, msg, self.ayse)

        self.assertTrue(self.group.can_unpin(self.ali))
        self.assertFalse(self.group.can_unpin(self.can))

    def test_deleting_pinned_message_keeps_conversation(self):
        self._pin(self.chat, self.message, self.ali)

        self.message.delete()
        self.chat.refresh_from_db()

        self.assertIsNone(self.chat.pinned_message)
        self.assertTrue(Conversation.objects.filter(id=self.chat.id).exists())