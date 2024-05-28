from discord.ext import commands
from typing import Generator
import requests
import discord
import difflib
import zlib
import time
import re
import io

rtfm_cache: dict = None

RTFM_PAGES = {
    ("stable"): "https://discordpy.readthedocs.io/en/stable",
    ("python", "py"): "https://docs.python.org/3/",
    ("wavelink", "wl"): "https://wavelink.dev/en/latest/",
}

literal_rtfm = set()
for src in RTFM_PAGES.keys():
    if isinstance(src, str):
        literal_rtfm.add(src)
    else:
        literal_rtfm.update(src)


class SphinxObjectFileReader:
    BUFFER = 16 * 1024

    def __init__(self, buffer: bytes) -> None:
        self.stream = io.BytesIO(buffer)

    def readline(self) -> str:
        return self.stream.readline().decode()

    def skipline(self) -> None:
        self.stream.readline()

    def read_compressed_chunks(self) -> Generator[bytes, None, None]:
        decompressor = zlib.decompressobj()
        while True:
            chunk = self.stream.read(self.BUFFER)
            if len(chunk) == 0:
                break
            yield decompressor.decompress(chunk)
        yield decompressor.flush()

    def read_compressed_lines(self) -> Generator[str, None, None]:
        buffer = b""
        for chunk in self.read_compressed_chunks():
            buffer += chunk
            position = buffer.find(b"\n")
            while position != -1:
                yield buffer[:position].decode()
                buffer = buffer[position + 1 :]
                position = buffer.find(b"\n")


def parse_object_inv(stream: SphinxObjectFileReader, url: str) -> dict[str, str]:
    # key: URL
    # n.b.: key doesn't have `discord` or `discord.ext.commands` namespaces
    result: dict[str, dict[str, str]] = {}

    # first line is version info
    inv_version = stream.readline().rstrip()

    if inv_version != "# Sphinx inventory version 2":
        raise RuntimeError("Invalid objects.inv file version.")

    # next line is "# Project: <name>"
    # then after that is "# Version: <version>"
    projname = stream.readline().rstrip()[11:]
    _ = stream.readline().rstrip()[11:]

    # next line says if it's a zlib header
    line = stream.readline()
    if "zlib" not in line:
        raise RuntimeError("Invalid objects.inv file, not z-lib compatible.")

    # This code mostly comes from the Sphinx repository.
    entry_regex = re.compile(r"(?x)(.+?)\s+(\S*:\S*)\s+(-?\d+)\s+(\S+)\s+(.*)")
    for line in stream.read_compressed_lines():
        match = entry_regex.match(line.rstrip())
        if not match:
            continue

        name, directive, _, location, dispname = match.groups()
        domain, _, subdirective = directive.partition(":")
        if directive == "py:module" and name in result:
            continue

        if directive == "std:doc":
            subdirective = "label"

        if location.endswith("$"):
            location = location[:-1] + name

        key = name if dispname == "-" else dispname
        prefix = f"{subdirective}:" if domain == "std" else ""

        if projname == "discord.py":
            key = key.replace("discord.ext.commands.", "").replace("discord.", "")

        result[f"{prefix}{key}"] = {
            "url": "/".join((url, location)),
            "type": directive.split(":")[1],
        }

    return result


async def build_rtfm_table():
    # Build cache
    cache: dict[str, dict[str, dict[str, str]]] = {}
    for key, page in RTFM_PAGES.items():
        cache[key] = {}
        # Get objects.inv from docs
        with requests.get(page + "/objects.inv") as resp:
            if resp.status_code != 200:
                raise RuntimeError("Failed")

            stream = SphinxObjectFileReader(resp.content)
            cache[key] = parse_object_inv(stream, page)

    global rtfm_cache
    rtfm_cache = cache


async def do_rtfm(ctx: commands.Context, key: tuple, obj: str = None):
    if obj is None:
        await ctx.send(RTFM_PAGES[key])
        return

    timer = time.time()
    # If no cache
    if not rtfm_cache:
        await ctx.typing()
        await build_rtfm_table()

    # Discard any discord.ext.commands
    obj = re.sub(r"^(?:discord\.(?:ext\.)?)?(?:commands\.)?(.+)", r"\1", obj)

    cache = list(rtfm_cache[key].items())

    # Sort and get the top 6 items
    matches = sorted(
        cache,
        key=lambda c: difflib.SequenceMatcher(None, obj, c[0]).ratio(),
        reverse=True,
    )[:8]

    embed = discord.Embed(
        title=f"RTFM - {'Discord.py' if key == ('stable') else key[0].capitalize()}",
        colour=discord.Colour.blurple(),
    )
    embed.set_footer(
        text=f"Query time : {(time.time()-timer):,.2f}s",
        icon_url=ctx.author.avatar.url,
    )
    if len(matches) == 0:
        return await ctx.send("Could not find anything. Sorry.")

    # Format results
    results = []
    for key, data in matches:
        results.append(f"[`{data['type'][:4]}`] [`{key}`]({data['url']})")

    embed.description = "\n".join(results)
    await ctx.reply(embed=embed, mention_author=False)
