"""
Asset department Tasks in ShotGrid (staff tool, plain Python 3, no Maya).

DECIDED 2026-10-28: asset publishes have Final publishes too, like shots.
A department's publish is Final when the newest Version on that
department's Task on the Asset is Approved (it gets a green thumbnail
border; no caches). The Publish tool links each asset publish's Version to
its department's Task (publishTool_api.ASSET_TASKS), so every asset needs
those Tasks. This makes the missing ones. It ONLY ADDS: existing Tasks
(any name) are never renamed, edited or removed.

    Character    Model, Rig, Creature, LookDev
    Prop         Model, Rig, LookDev
    Vehicle      Model, Rig, LookDev
    Environment  Model, Environment, LookDev
    Graphic, no type: none (no Maya work)

Run (dry run first; --apply to make them):
    python asset_tasks.py --project 157
    python asset_tasks.py --project 157 --apply

ShotGrid settings and shotgun_api3: found the same way as h_sync.py.
"""

import sys
import argparse

import h_sync

# Same names as publishTool_api.ASSET_TASKS (this script runs without Maya).
TASKS_BY_TYPE = {
    "character": ("Model", "Rig", "Creature", "LookDev"),
    "prop": ("Model", "Rig", "LookDev"),
    "vehicle": ("Model", "Rig", "LookDev"),
    "environment": ("Model", "Environment", "LookDev"),
}
# The pipeline Step each Task sits under (Asset steps, by code).
STEP_OF = {"Model": "Model", "Rig": "Rig", "Creature": "Character FX",
           "LookDev": "Texture", "Environment": "Model"}


def plan_tasks(assets, tasks):
    """[(asset, task name)] still to make. assets: [{id, code, sg_asset_type}];
    tasks: [{content, entity}] already on them. Names match in any case."""
    have = set((t["entity"]["id"], (t["content"] or "").strip().lower()) for t in tasks
               if t.get("entity"))
    todo = []
    for asset in sorted(assets, key=lambda a: a["code"].lower()):
        for name in TASKS_BY_TYPE.get((asset.get("sg_asset_type") or "").lower(), ()):
            if (asset["id"], name.lower()) not in have:
                todo.append((asset, name))
    return todo


def asset_steps(sg):
    """{step code: Step} for the Asset pipeline steps."""
    return dict((s["code"], {"type": "Step", "id": s["id"]})
                for s in sg.find("Step", [["entity_type", "is", "Asset"]], ["code"]))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Make each ShotGrid Asset's department "
                                                 "Tasks. Only adds.")
    parser.add_argument("--project", type=int, required=True, help="ShotGrid project id")
    parser.add_argument("--config", help="ShotGrid settings JSON")
    parser.add_argument("--apply", action="store_true", help="make them (default: just list)")
    args = parser.parse_args(argv)
    sg = h_sync.connect(args.config)
    project = {"type": "Project", "id": args.project}
    assets = sg.find("Asset", [["project", "is", project]], ["code", "sg_asset_type"])
    tasks = sg.find("Task", [["project", "is", project], ["entity", "type_is", "Asset"]],
                    ["content", "entity"])
    todo = plan_tasks(assets, tasks)
    skipped = sorted(a["code"] for a in assets
                     if (a.get("sg_asset_type") or "").lower() not in TASKS_BY_TYPE)
    print("Tasks to make (%d):" % len(todo))
    for asset, name in todo:
        print("  %-24s %s" % (asset["code"], name))
    if skipped:
        print("No department Tasks (Graphic or no asset type): %s" % ", ".join(skipped))
    if not todo:
        print("Nothing to do: every asset has its department Tasks.")
        return
    if not args.apply:
        print("(Dry run: nothing made. Add --apply to make them.)")
        return
    steps = asset_steps(sg)
    batch = []
    for asset, name in todo:
        data = {"project": project, "content": name,
                "entity": {"type": "Asset", "id": asset["id"]}}
        if STEP_OF[name] in steps:
            data["step"] = steps[STEP_OF[name]]
        batch.append({"request_type": "create", "entity_type": "Task", "data": data})
    made = sg.batch(batch)
    print("Made %d Task(s)." % len(made))


if __name__ == "__main__":
    sys.exit(main())
