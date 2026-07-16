# mpToolSet Dev Notes

## ngSkinTools2 — moved to a separate installer (resolved 2026-07-16)

**Old problem:** ngSkinTools2 installed automatically as part of the main `install.py`, which caused two recurring issues: Maya's Maya 2025 "untrusted folder" warning (the old `_patch_usersetup` `ngskin_block` manually set `MAYA_PLUG_IN_PATH` and called `loadPlugin('ngSkinTools2')`, which Maya 2025's plugin trust system flags for non-hardcoded locations), and locked-file install failures — reinstalling/updating mpToolSet while ngSkinTools2 was loaded would block on `shutil.rmtree` of the `ApplicationPlugins` folder.

**Fix:** ngSkinTools2 is no longer touched by the main `install.py`/`uninstall.py` at all. It now lives in its own top-level folder, `mpToolSet/ngSkinTools2/`, with its own self-contained `install.py`/`uninstall.py` that students drag in separately, only when they need it. It relies purely on Maya's native `ApplicationPlugins`/`PackageContents.xml` auto-discovery — no `userSetup.py` changes, no `MAYA_PLUG_IN_PATH` hack — which also sidesteps the untrusted-folder warning. Decoupling it from the main installer's manifest/backup system means updating mpRig/mpAnim tools can no longer be blocked by a locked ngSkinTools2 file, and vice versa.
