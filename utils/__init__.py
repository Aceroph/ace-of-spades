import json
import pathlib

EMOJIS = json.load(open(pathlib.Path(__file__).parent / "emoji_map.json", "r"))

schooldata = json.load(open(pathlib.Path(__file__).parent / "schoolday.json", "r"))