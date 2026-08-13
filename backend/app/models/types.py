from sqlalchemy import String
from sqlalchemy.types import TypeDecorator

from app.security import decrypt_field, encrypt_field


class EncryptedString(TypeDecorator):
    """Transparently AES-256-GCM encrypts a string column at the ORM boundary.

    Stored ciphertext is base64 and roughly ~1.4x the plaintext length plus a
    fixed overhead, so the underlying column is a generously-sized String.
    """

    impl = String(1024)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return encrypt_field(value)

    def process_result_value(self, value, dialect):
        return decrypt_field(value)
