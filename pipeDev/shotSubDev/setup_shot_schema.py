# ------------------------------------------------------------
# setup_shot_schema.py
#
# One-time ShotGrid schema setup: adds a custom "Artist" field to the
# Shot entity, site-wide, so a Shot's assigned student is visible as a
# plain column in ShotGrid's own Shot List view without opening its Task.
#
# ShotGrid has no built-in artist field on Shot -- assignment lives on
# each Shot's own Task (see provision_shotgrid_class.py's
# _find_or_create_task()/artist-assignment step). This custom field
# mirrors that Task assignee for at-a-glance visibility only; kept in
# sync by provision_shotgrid_class.py whenever it assigns a Shot -- not
# meant to be hand-edited independently of the Task assignee.
#
# Idempotent -- safe to re-run, checks by display name first.
#
# Deliberately does NOT go through shotgridConnect.get_connection()'s
# normal sudo_as_login impersonation: schema changes need the bundled
# Script key's own Admin-tier permission, not the impersonated staff
# member's Producer-tier permission (same reasoning as jiffySGDev's own
# setup_schema.py).
#
# Run via mayapy from this folder:
#   mayapy setup_shot_schema.py
#
# After running, add "Artist" as a column in ShotGrid's Shot List page
# yourself (one-time, per saved view) -- a brand-new custom field doesn't
# automatically appear as a visible column until added.
# ------------------------------------------------------------
import sys
import os

_DEV_DIR = os.path.dirname(os.path.abspath(__file__))
if _DEV_DIR not in sys.path:
    sys.path.insert(0, _DEV_DIR)

try:
    import maya.standalone
    maya.standalone.initialize(name="python")
except Exception:
    pass  # already running inside an interactive Maya session

import shotgridConnect
import shotgun_api3


def _admin_connection():
    """A Shotgun connection using the bundled Script key's own identity --
    no sudo_as_login. Schema changes need the Script's own Admin-tier
    permission; impersonating a staff/student login here would apply
    their own (lower) permission instead and likely fail."""
    config = shotgridConnect._load_config()
    return shotgun_api3.Shotgun(
        config["site_url"],
        script_name=config["script_name"],
        api_key=config["api_key"],
    )


def setup_shot_artist_field():
    sg = _admin_connection()
    existing = sg.schema_field_read("Shot")
    existing_by_display_name = {
        info["name"]["value"]: field_name
        for field_name, info in existing.items()
    }

    display_name = "Artist"
    if display_name in existing_by_display_name:
        print("setup_shot_schema: '{0}' already exists as '{1}' — skipped".format(
            display_name, existing_by_display_name[display_name]))
        return existing_by_display_name[display_name]

    field_name = sg.schema_field_create(
        "Shot", "entity", display_name,
        {
            "valid_types": ["HumanUser"],
            "description": (
                "The student (or staff) assigned to this Shot. Mirrors "
                "the Shot's own Task assignee for at-a-glance visibility "
                "in Shot List view -- set by provision_shotgrid_class.py, "
                "not meant to be hand-edited independently."
            ),
        },
    )
    print("setup_shot_schema: created '{0}' as '{1}'".format(display_name, field_name))
    return field_name


if __name__ == "__main__":
    setup_shot_artist_field()
