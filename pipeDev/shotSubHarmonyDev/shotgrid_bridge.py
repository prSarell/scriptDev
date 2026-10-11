# ------------------------------------------------------------
# shotgrid_bridge.py
#
# External Python entry point shelled out to by shotSub_harmony.js.
# Harmony's JS scripting can't import Python modules directly -- see
# shotSub_harmony_design.md's "Architecture" section -- so the JS tool
# writes a small input JSON describing one publish request, launches this
# script as a subprocess (Process2), and reads back a result JSON this
# script writes before exiting.
#
# This is the only place Harmony-side logic touches ShotGrid at all --
# everything else is shotgridConnect.py, imported unmodified (dual-copy
# mirrored from pipeDev/shotSubDev/shotgridConnect.py; keep both in sync).
#
# Usage:
#     <python> shotgrid_bridge.py <input_json_path> <output_json_path>
#
# Input JSON:
#     {
#         "entity_type": "Shot" | "Asset",
#         "entity_id": <int>,
#         "movie_path": "<absolute path to the rendered .mov>",
#         "notes": "<string or null>",
#         "fps": <float or null>
#     }
#
# Output JSON, always written even on failure so the JS side never hangs
# waiting on a result that never comes:
#     {"success": true, "sg_version_id": <int or null>}
#     or
#     {"success": false, "error": "<message>"}
#
# No rvio/RV involvement at all here -- unlike the Maya tool, the movie
# file already exists (produced directly by Harmony's own Write node, see
# the design doc's workflow section), so this bridge only ever uploads it
# via upload_playblast()'s movie_path parameter, which skips the
# frame-sequence/thumbnail/encode path entirely.
# ------------------------------------------------------------

from __future__ import print_function

import os
import sys
import json

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import shotgridConnect


def _write_result(output_path, success, sg_version_id=None, error=None):
    result = {"success": success}
    if success:
        result["sg_version_id"] = sg_version_id
    else:
        result["error"] = error
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)


def main(input_path, output_path):
    try:
        with open(input_path, "r") as f:
            request = json.load(f)
    except (ValueError, OSError) as exc:
        _write_result(output_path, False, error="Could not read input file: {0}".format(exc))
        return 1

    movie_path = request.get("movie_path")
    if not movie_path or not os.path.isfile(movie_path):
        _write_result(output_path, False, error="Movie file not found: {0}".format(movie_path))
        return 1

    version_folder = os.path.dirname(movie_path)

    try:
        result = shotgridConnect.upload_playblast(
            request["entity_type"],
            request["entity_id"],
            version_folder,
            notes=request.get("notes") or None,
            fps=request.get("fps"),
            movie_path=movie_path,
        )
    except Exception as exc:
        _write_result(output_path, False, error=str(exc))
        return 1

    sg_version_id = result.get("id") if isinstance(result, dict) else None
    _write_result(output_path, True, sg_version_id=sg_version_id)
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.stderr.write("Usage: shotgrid_bridge.py <input_json_path> <output_json_path>\n")
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))
