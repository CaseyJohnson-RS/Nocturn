
class RegistrationError(Exception):
    message = "Registration error"

    def __str__(self) -> str:
        return self.message


class UserAlreadyExists(RegistrationError):
    message = "User already exists"

class InvalidEmailToken(RegistrationError):
    message = "Invalid or expired token"

class ExpiredEmailToken(RegistrationError):
    message = "Invalid or expired token"

class EmailDoesNotMatchToken(RegistrationError):
    message = "Email does not match token"
