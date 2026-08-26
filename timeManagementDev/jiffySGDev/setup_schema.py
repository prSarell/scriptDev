# ------------------------------------------------------------
# setup_schema.py
#
# One-time ShotGrid schema setup for Jiffy SG's project-settings feature
# (solo vs group, group admin). Adds two custom fields to the Project
# entity type, site-wide — not per-project, ShotGrid schema fields apply
# to every Project on the site automatically, including ones created
# later.
#
# Idempotent — safe to re-run. Checks existing fields by display name
# before creating, so running this twice (or against a second site, e.g.
# the real production site replacing the current test site next year)
# never creates duplicates.
#
# Deliberately does NOT go through jiffySG.get_connection()'s normal
# sudo_as_login impersonation: schema changes need the bundled Script
# key's own Admin-tier permission, not the impersonated staff member's
# Producer-tier permission (Producers can't modify site schema). This is
# the one place in Jiffy SG that acts as the tool itself, not as any
# particular student or staff login.
#
# Run via mayapy from this folder:
#   mayapy setup_schema.py
#
# Uses the same jiffySG_config.json as the rest of Jiffy SG (see
# jiffySG.py's module docstring for its location/format) — reuses
# jiffySG._load_config() rather than re-parsing it here.
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

import jiffySG
import shotgun_api3


FIELDS = [
    {
        "display_name": "Jiffy Project Type",
        "data_type": "list",
        "properties": {
            "valid_values": ["Solo", "Group"],
            "description": (
                "Jiffy SG: whether this Project is a solo or group "
                "production. Set from Jiffy SG when the Project is "
                "created; changeable later from Jiffy SG's Project "
                "Settings."
            ),
        },
    },
    {
        "display_name": "Jiffy Admin Login",
        "data_type": "text",
        "properties": {
            "description": (
                "Jiffy SG: ShotGrid login of the group member designated "
                "as admin (can edit shot/asset order, create shots/"
                "assets; other members are read/note/publish-only). "
                "Blank for solo Projects, or group Projects with no "
                "admin chosen yet."
            ),
        },
    },
]


def _admin_connection():
    """A Shotgun connection using the bundled Script key's own identity —
    no sudo_as_login. Schema changes need the Script's own Admin-tier
    permission; impersonating a staff/student login here would apply
    their own (lower) permission instead and likely fail."""
    config = jiffySG._load_config()
    return shotgun_api3.Shotgun(
        config["site_url"],
        script_name=config["script_name"],
        api_key=config["api_key"],
    )


def setup_project_fields():
    sg = _admin_connection()
    existing = sg.schema_field_read("Project")
    existing_by_display_name = {
        info["name"]["value"]: field_name
        for field_name, info in existing.items()
    }

    for field in FIELDS:
        display_name = field["display_name"]
        if display_name in existing_by_display_name:
            print("jiffySG setup_schema: '{0}' already exists as '{1}' — skipped".format(
                display_name, existing_by_display_name[display_name]))
            continue

        field_name = sg.schema_field_create(
            "Project", field["data_type"], display_name, field["properties"]
        )
        print("jiffySG setup_schema: created '{0}' as '{1}'".format(
            display_name, field_name))


def setup_asset_type_values():
    """Ensures Asset.sg_asset_type's valid_values list on the site covers
    everything jiffySG.ASSET_TYPE_VALUES needs. sg_asset_type is a standard
    ShotGrid field, not created here (unlike the custom Project fields
    above) — this only ever appends missing values, never removes existing
    site values, since other projects' assets may already use them."""
    sg = _admin_connection()
    existing = sg.schema_field_read("Asset")
    current_values = existing["sg_asset_type"]["properties"]["valid_values"]["value"]

    missing = [v for v in jiffySG.ASSET_TYPE_VALUES if v not in current_values]
    if not missing:
        print("jiffySG setup_schema: sg_asset_type already has all required values — skipped")
        return

    sg.schema_field_update("Asset", "sg_asset_type", {"valid_values": current_values + missing})
    print("jiffySG setup_schema: added {0} to sg_asset_type valid_values".format(missing))


if __name__ == "__main__":
    setup_project_fields()
    setup_asset_type_values()
