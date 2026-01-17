import enum


class EmailType(str, enum.Enum):
    VERIFY_EMAIL = "verify_email"