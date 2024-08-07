from typing import TYPE_CHECKING, Optional

import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from .subclasses import Cog


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
    def __init__(self, reason: Optional[str] = None) -> None:
        self.reason = reason


class ModuleDisabled(commands.CommandError):
    def __init__(self, module: "Cog") -> None:
        self.module = module.qualified_name
