class ApplicationError(Exception):
    message: str = "Application error"

    def __init__(self, **kwargs):
        super().__init__(self.message)
        self.details = kwargs


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
