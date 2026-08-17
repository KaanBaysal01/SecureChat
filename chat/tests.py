from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Conversation, Message
from .crypto import encrypt_message, decrypt_message

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
