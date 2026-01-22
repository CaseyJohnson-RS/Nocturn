class DomainError(Exception):
    message: str = "Domain error"

    def __init__(self, **kwargs):
        super().__init__(self.message)
        self.details = kwargs


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

# User


class UserAlreadyExists(DomainError):
    message = "User already exists"

class EmailAlreadyVerified(DomainError):
    message = "Email already verified"


# Email Tokens


class InvalidToken(DomainError):
    message = "Invalid token"


class TokenAlreadyUsed(DomainError):
    message = "Token already used"


class TokenExpired(DomainError):
    message = "Token expired"


class UserDoesNotMatchToken(DomainError):
    message = "Email does not match token"
