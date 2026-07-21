# ------------------------------------------------------------
# jiffySG.py
#
# ShotGrid connection layer for the Jiffy SG tool.
# See timeManagementDev/jiffySG_brief.md for the full design.
#
# Status: connection/auth layer only. This is deliberately NOT a full
# JiffySchedule fork yet — that's a much bigger follow-on piece (shot
# scheduling UI, Project linking, Note sync, etc.). What's here resolves
# the brief's most immediate blocker: proving the Script API key +
# sudo_as_login auth pattern actually works against a real ShotGrid site
# and a real student account, before building anything on top of it.
#
# Auth model (per the brief): a single Script API key authenticates all
# API calls; sudo_as_login applies the impersonated student's own
# ShotGrid permissions to each call and attributes it to them in the
# event log. The key itself is never hardcoded here or committed to the
# repo — it's read from a local config file created on each machine.
#
# Config file:
#   <Maya userPrefDir>/jiffySG_config.json
#   {
#     "site_url": "https://nfw.shotgrid.autodesk.com",
#     "script_name": "JiffySG_001",
#     "api_key": "<the Application Key from ShotGrid Admin > Scripts>"
#   }
#
# Quick connection test (Script Editor, inside Maya):
#   import jiffySG
#   jiffySG.test_connection()
# ------------------------------------------------------------

import os
import json
import getpass

import maya.cmds as cmds

import shotgun_api3


_CONFIG_FILENAME = "jiffySG_config.json"
_REQUIRED_KEYS = ("site_url", "script_name", "api_key")


def _config_file():
    prefs = cmds.internalVar(userPrefDir=True)
    return os.path.join(prefs, _CONFIG_FILENAME).replace("\\", "/")


def _load_config():
    path = _config_file()
    if not os.path.isfile(path):
        raise RuntimeError(
            "jiffySG: no config file found at {0}\n\n"
            "Create it with:\n"
            '{{\n'
            '  "site_url": "https://nfw.shotgrid.autodesk.com",\n'
            '  "script_name": "<Script Name from ShotGrid Admin > Scripts>",\n'
            '  "api_key": "<Application Key from ShotGrid Admin > Scripts>"\n'
            '}}'.format(path)
        )

    with open(path, "r") as f:
        try:
            config = json.load(f)
        except ValueError as exc:
            raise RuntimeError("jiffySG: config at {0} is not valid JSON — {1}".format(path, exc))

    missing = [key for key in _REQUIRED_KEYS if not config.get(key)]
    if missing:
        raise RuntimeError(
            "jiffySG: config at {0} is missing: {1}".format(path, ", ".join(missing))
        )

    return config


def current_login():
    """The identity to sudo_as_login as. On RMIT lab machines the OS/domain
    username is expected to match the student's ShotGrid login — confirmed
    so far only at the web-login level (both instructor and students were
    able to log into the ShotGrid site with their RMIT credentials), NOT
    yet confirmed that the OS username matches ShotGrid's `login` field
    exactly. Treat results from this as provisional until that's checked
    with RMIT's ShotGrid admin (see jiffySG_brief.md)."""
    return getpass.getuser()


def get_connection(as_login=None):
    """Return an authenticated shotgun_api3.Shotgun connection, impersonating
    as_login (defaults to current_login()) via sudo_as_login."""
    config = _load_config()
    return shotgun_api3.Shotgun(
        config["site_url"],
        script_name=config["script_name"],
        api_key=config["api_key"],
        sudo_as_login=as_login or current_login(),
    )


def test_connection(as_login=None):
    """Proves the Script API key + sudo_as_login combination actually
    authenticates, using a genuinely-authenticated call. Deliberately NOT
    sg.info() — the brief's own testing (2026-07-16) found sg.info() gives
    a false positive, since it doesn't require authentication at all and
    will "succeed" even when the credentials are broken.

    Returns the list of Projects visible to as_login. An empty list is a
    legitimate result (the student's Project may not exist/be shared yet)
    — what matters is that this doesn't raise AuthenticationFault."""
    sg = get_connection(as_login=as_login)
    projects = sg.find("Project", [], ["name"])
    print("jiffySG: connected as '{0}' — {1} visible project(s):".format(
        as_login or current_login(), len(projects)))
    for p in projects:
        print("  {0}".format(p.get("name")))
    return projects


def upload_playblast(shot_name, version_folder, files=None, notes=None):
    """Hand-off target for pbTool's "Send to ShotGrid" button (see
    pbTool.py send_to_shotgrid()). NOT YET IMPLEMENTED — creating a real
    Shot/Task/Version in ShotGrid needs the real Project code and the
    Task status codes set up on it (both still open items in
    jiffySG_brief.md's rollout checklist), plus Jiffy SG's own Project-
    linking logic, which doesn't exist yet. Confirm test_connection()
    works first; this is the next piece after that."""
    raise NotImplementedError(
        "jiffySG.upload_playblast() isn't built yet. Run "
        "jiffySG.test_connection() first to confirm ShotGrid auth works, "
        "then see jiffySG_brief.md for what's still needed before this "
        "can create a real ShotGrid Version."
    )
