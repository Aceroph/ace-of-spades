from discord import app_commands

class NotYourButton(app_commands.errors.AppCommandError):
    def __init__(self, reason: str=None) -> None:
        self.reason = reason