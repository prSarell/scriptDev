# JiffyPomo shared helpers and default file paths

import os

DEFAULT_LOCAL_DATA_DIR = os.path.join(os.path.expanduser("~"), "jiffyData")
DEFAULT_PROMPTS_FILE = os.path.join(DEFAULT_LOCAL_DATA_DIR, "jiffypomo_prompts.json")
DEFAULT_NOTES_FILE = os.path.join(DEFAULT_LOCAL_DATA_DIR, "jiffypomo_notes.json")


def get_ordinal_suffix(day):
    if 11 <= day % 100 <= 13:
        return "th"
    else:
        suffixes = {1: "st", 2: "nd", 3: "rd"}
        return suffixes.get(day % 10, "th")
