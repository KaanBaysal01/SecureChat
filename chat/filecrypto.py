import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from .crypto import get_fernet

MAGIC = b"SCF1"
PREFIX_LEN = 4
CHUNK_SIZE = 64 * 1024
TAG_LEN = 16


def _nonce(prefix, index):
    return prefix + index.to_bytes(8, "big")


def _aad(is_last):
    return b"\x01" if is_last else b"\x00"


def encrypt_to_file(fileobj, destination_path):
    data_key = AESGCM.generate_key(bit_length=256)
    aesgcm = AESGCM(data_key)
    prefix = os.urandom(PREFIX_LEN)

    with open(destination_path, "wb") as out:
        out.write(MAGIC + prefix)

        index = 0
        current = fileobj.read(CHUNK_SIZE)

        while True:
            nxt = fileobj.read(CHUNK_SIZE)
            is_last = not nxt

            out.write(aesgcm.encrypt(_nonce(prefix, index), current, _aad(is_last)))

            if is_last:
                break

            current = nxt
            index += 1

    return get_fernet().encrypt(data_key)


def decrypt_from_file(path, wrapped_key):
    data_key = get_fernet().decrypt(bytes(wrapped_key))
    aesgcm = AESGCM(data_key)

    with open(path, "rb") as f:
        header = f.read(len(MAGIC) + PREFIX_LEN)

        if header[: len(MAGIC)] != MAGIC:
            raise ValueError("Bilinmeyen dosya biçimi.")

        prefix = header[len(MAGIC) :]

        index = 0
        current = f.read(CHUNK_SIZE + TAG_LEN)

        while True:
            nxt = f.read(CHUNK_SIZE + TAG_LEN)
            is_last = not nxt

            yield aesgcm.decrypt(_nonce(prefix, index), current, _aad(is_last))

            if is_last:
                return

            current = nxt
            index += 1