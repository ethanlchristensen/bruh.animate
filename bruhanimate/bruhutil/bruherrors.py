class ScreenResizedError(Exception):
    """Exception raised when the screen is resized."""

    def __init__(self, message="The screen has been resized"):
        self.message = message
        super().__init__(self.message)


class InvalidEffectTypeError(Exception):
    """Exception raised when an invalid effect type is used."""

    def ____init__(self, message="Invalid effect type"):
        self.message = message
        super().__init__(self.message)


class InvalidImageError(Exception):
    """Exception raised when an invalid effect type is used."""

    def ____init__(self, message="Invalid image"):
        self.message = message
        super().__init__(self.message)
