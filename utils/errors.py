from discord import app_commands
from discord.ext import commands
import discord


def iserror(error: Exception, kind) -> bool:
    if isinstance(kind, (tuple, set, list)):
        return any([error.__class__.__qualname__ == k.__qualname__ for k in kind])

    return error.__class__.__qualname__ == kind.__qualname__


class NotVoiceMember(commands.CommandError):
    def __init__(self, channel: discord.VoiceChannel) -> None:
        self.channel = channel


class PlayerConnectionFailure(commands.CommandError):
    pass


class NoVoiceFound(commands.CommandError):
    pass


class NotYourButton(app_commands.AppCommandError):
    def __init__(self, reason: str = None) -> None:
        self.reason = reason
