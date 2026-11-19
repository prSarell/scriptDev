"""
Scout's worker: publishes one render from outside the artist's Maya, in its
own mayapy (renderSub's publish needs Maya's settings: the H drive location,
the artist's login, ShotGrid). The Scout window starts it with a request
file and reads the result file when it's done (scout_api.start_worker).

    mayapy scout_worker.py <request.json>

request: {"action": "publish", "folder", "notes", "result"}
result:  {"ok", "message", "dest", "sg_version_id", "sg_error", "warnings"}
"""

import os
import sys
import json
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def publish(request):
    import scout_api as api
    rs = api.rs
    result = rs.publish({}, request["folder"], request.get("notes", ""),
                        running=api.queued_folders())
    info = rs.read_info(request["folder"]) or {}
    lines = ["%s published: %s" % (info.get("version", ""), result["dest"])]
    if result.get("partial"):
        lines.append("(the frames that finished: %s)" % info.get("status"))
    if result.get("sg_error"):
        lines.append("ShotGrid upload failed: %s\nThe frames are on the H drive; Publish again "
                     "to retry the upload." % result["sg_error"])
    lines += result.get("warnings") or []
    return {"ok": not result.get("sg_error"), "message": "\n".join(lines), "dest": result["dest"],
            "sg_version_id": (result.get("sg_version") or {}).get("id"),
            "sg_error": result.get("sg_error"), "warnings": result.get("warnings") or []}


def main(path):
    with open(path) as f:
        request = json.load(f)
    try:
        import maya.standalone
        maya.standalone.initialize()
        if request.get("action") != "publish":
            raise ValueError("unknown action %r" % request.get("action"))
        out = publish(request)
    except Exception as e:
        import renderSub_api as rs
        known = isinstance(e, rs.PublishError)
        out = {"ok": False, "message": str(e) if known else traceback.format_exc()}
    with open(request["result"] + ".tmp", "w") as f:
        json.dump(out, f, indent=2)
    os.replace(request["result"] + ".tmp", request["result"])
    try:
        os.remove(path)
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
