# mpToolSet Dev Notes

## ngSkinTools2 — "untrusted folder" warning in Maya 2025

**Problem:** Maya shows an "untrusted folder" warning when loading ngSkinTools2.

**Root cause:** The installer puts ngSkinTools2 in `ApplicationPlugins/` (correct — Maya discovers it automatically via `PackageContents.xml`), but `_patch_usersetup` in `install.py` also writes a `userSetup.py` block that manually sets `MAYA_PLUG_IN_PATH` and calls `loadPlugin('ngSkinTools2')`. Maya 2025's plugin trust system flags plugins loaded via `MAYA_PLUG_IN_PATH` from non-hardcoded locations.

**Fix:** Remove the `MAYA_PLUG_IN_PATH` / `loadPlugin` block from `_patch_usersetup`. Keep only the `sys.path` entry for the ngSkinTools2 scripts folder (so `import ngSkinTools2` works). Maya will handle plugin loading automatically via the `ApplicationPlugins` / `PackageContents.xml` mechanism, which is trusted.

**Files to change:** `mpToolSet/install.py` — `_patch_usersetup()` function, `ngskin_block` (lines ~223–242).
