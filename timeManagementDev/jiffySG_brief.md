# Jiffy SG — design brief

Status: **design only, no code written**. RMIT's single shared ShotGrid site is confirmed; a test site is live now (`https://nfw.shotgrid.autodesk.com`), official site rolling out ~2026-07-23. Not being built yet — this doc captures the plan agreed 2026-07-15, plus auth findings from testing the site 2026-07-16, so the next session can pick it up without re-deriving it.

## What it is

A new tool, forked from JiffySchedule, that adds ShotGrid integration for RMIT's animation course. Not a feature bolted onto JiffySchedule — ShotGrid becomes mandatory and structurally central, which is different enough from JiffySchedule's local-only model to warrant its own tool. JiffySchedule keeps working untouched for as long as it's needed; Jiffy SG eventually replaces it once proven.

Goal: students manage everything — shot scheduling, status, notes — through Jiffy SG's UI. They never need to open ShotGrid directly.

## Context

RMIT gave the course ShotGrid access (2026-07-15). Every student gets their own account. The plan is to recommend RMIT stand up **one single shared site** (not one per staff member) with:
- **Staff** on the "Producer" permission group (stock ShotGrid role) — can create/manage Projects.
- **Students** on the "Artist" permission group, scoped to their own Project only.

Both are built-in ShotGrid permission groups — no custom permission engineering needed.

## Architecture

**Site URL** — one centrally-configured setting, not hardcoded in code (in case the single-site plan changes later) and not stored per-project (unnecessary complexity once it's confirmed as one shared site).

**Auth** — ~~per-student human login (`shotgun_api3`, `login`/`password`)~~ **superseded, see below.**

> ### Auth findings, tested 2026-07-16 against the test site
> **Direct username/password API login does not work.** Site's `user_authentication_method` is `oxygen` (Autodesk Identity/SSO), and it's enforced for real authenticated calls — `shotgun_api3.Shotgun(site_url, login=, password=)` followed by an authenticated call (e.g. `find`) throws `AuthenticationFault: Can't authenticate user`. (A first attempt looked like it succeeded because it only checked `sg.info()`, which doesn't require authentication at all — false positive, don't rely on `info()` as an auth test.)
>
> **Decided replacement: Script API key + `sudo_as_login`.** A single ShotGrid Script API key (site admin → API Script), bundled with Jiffy SG, authenticates all API calls. Per-student identity is applied via `shotgun_api3`'s `sudo_as_login` parameter. Verified from `shotgun_api3`'s own source docstring (`shotgun.py` ~line 561): `sudo_as_login` **applies that user's own permissions** to the action (so ShotGrid's Producer/Artist permission scoping still holds per-student, enforced by ShotGrid itself, not reimplemented in Jiffy SG) and **writes an event-log entry attributed to that student**, with an extra `sudo_actual_user` field noting the script performed it on their behalf. So the only thing actually lost versus true per-student login is *proof of identity at the point of use* — permissions and audit trail both stay correctly scoped to the real student.
>
> **Identity-detection plan (who to `sudo_as_login` as):**
> - **On RMIT lab machines**: auto-detect the current OS/domain username (`getpass.getuser()` / `$env:USERNAME`) and use it to pick the ShotGrid login — relies on RMIT's domain login already being per-student, so spoofing would require being logged into someone else's Windows session. **Needs confirming**: does each student's ShotGrid `login` field match their RMIT domain username/student ID 1:1, or does it need a lookup table? **Partial result, 2026-07-21**: tested against a personal/staff machine and it does *not* hold — `getpass.getuser()` returned a local Windows account name (`'scout'`) that ShotGrid rejected outright (`unknown or retired user`), not even a wrong-but-real login. Untested on an actual RMIT lab machine with real domain login, which is the actual scenario this plan describes — don't treat this as disproving the lab-machine case, just as evidence it can't be assumed to work everywhere without a fallback.
> - **At home (no RMIT domain login)**: possible fallback — a student's Autodesk ID (used to activate their Education Maya license) might be the *same underlying identity* as their ShotGrid account, since both appear to sit on Autodesk's `oxygen` identity system. **Unconfirmed on two counts**: (1) whether it's literally the same account, not just the same auth backend, and (2) whether Maya/RV expose the currently-signed-in Autodesk ID programmatically to a script — needs research before relying on it. Until confirmed, home use likely needs a manual dropdown/override.
> - **Informal supporting signal (2026-07-16, needs formal confirmation)**: today, both the instructor and students logged into the ShotGrid website using the same username/password as their RMIT login — suggests RMIT's identity is unified across systems, but could also just be coincidental password reuse. Confirm properly with RMIT's IT/ShotGrid admin rather than relying on this alone.
>
> ### ⚠️ Security — needs active monitoring, not just at build time
> Bundling one Admin-tier Script API key into a tool distributed to a whole class is a materially different risk profile than per-student passwords: it's a single high-value credential, and if leaked it grants broad access to the entire RMIT site (not just one student's Project) unless carefully constrained. Needs an explicit plan before this ships, not just at final review:
> - Where the key lives at runtime (never committed to the repo; likely fetched from a local config file created by the installer, not hardcoded in `jiffySG.py`).
> - Whether the Script key can be scoped more tightly than full Admin (ShotGrid permission groups for Scripts, if available) while still supporting `sudo_as_login` for every student.
> - A rotation/revocation plan if the key is ever suspected leaked (e.g. found in a student's local files, posted somewhere).
> - Re-confirm real OS-username-based identity detection can't be trivially spoofed by a student on their own lab session (e.g. editing an environment variable) — worth a quick adversarial check once that code exists, not just assuming the OS username is trustworthy.

**Project setup** — 100% manual, done by the instructor directly in ShotGrid: creating each student's Project, adding students/mentors/helpers, both up front and as needed later. Jiffy SG never creates Projects or manages membership via the API.

**Project linking** — student logs into Jiffy SG, which queries which ShotGrid Project(s) that account can see and auto-links if there's exactly one (expected, since the instructor already scoped the Project to just that student). Re-linking uses the identical flow and must stay safely repeatable at any time — covers a site being rebuilt or a student's access changing, with no special-case handling needed.

**Shots/Assets** — created and scheduled entirely in Jiffy SG, pushed to ShotGrid:
| Jiffy SG field | ShotGrid field |
|---|---|
| Stage | `Task.sg_status_list` |
| Due Date | `Task.due_date` |
| Frame Start/End | Shot's built-in cut-in/cut-out fields |
| Artist | `Task.task_assignees` |

**Stage mapping** — no translation table in code. The instructor sets ShotGrid Task status codes to match JiffySchedule's existing stage lists directly:
- Shots: `Previs, Blocking, Primary, Final, Rendered, Omit`
- Assets: `WIP, Testing, Production Ready, Omit`

> ⚠️ Gotcha: ShotGrid's status field stores a short internal *code* separate from the display name shown in the UI. The **code** must match what Jiffy SG writes, not just the display label, or API writes will silently fail to land on the right status.

**Artist dropdown** — read-only pull of ShotGrid project members. Jiffy SG never writes project membership.

**Notes — genuine two-way sync** — uses ShotGrid's native `Note` entity as an append-only feed, not a single overwritable field. A note typed in Jiffy SG posts a new `Note`; a note added directly in ShotGrid (e.g. a mentor reviewing there) appears in Jiffy SG's feed on next pull. Nothing is ever overwritten in place, so there's no conflict-resolution problem to solve — merging two append-only lists just works.

**Packaging** — vendor `shotgun_api3` into `mpToolSet`, the same way ngSkinTools2 is already bundled (`mpToolSet/ngSkinTools2/`). No per-student pip install, no network dependency on lab machines.

## Rollout plan

1. ~~RMIT stands up the single shared site~~ — done; test site live, official site ~2026-07-23.
2. ~~Confirm SSO vs. direct-login~~ — done 2026-07-16: SSO-enforced, direct login doesn't work. Auth plan is now Script API key + `sudo_as_login` (see above).
3. **Auth confirmed working (2026-07-21).** Script `JiffySG_002` + `sudo_as_login=patrick.sarell2@rmit.edu.au` connected successfully via `jiffySG.test_connection()` and returned 17 visible Projects — the Script API key + `sudo_as_login` auth pattern is now proven end-to-end against a real account (staff, not yet a student account specifically). `timeManagementDev/jiffySGDev/jiffySG.py` (connection/auth layer only, not a `jiffySchedule.py` fork yet) and vendored `shotgun_api3` (`timeManagementDev/jiffySGDev/shotgun_api3/`, pulled from the official GitHub repo) are in place. Key lives in `<Maya userPrefDir>/jiffySG_config.json`, never in this doc or committed.
   - **Identity-detection finding**: OS username (`getpass.getuser()` → `'scout'`) does **not** match the ShotGrid `login` field — tested and confirmed failing (`AuthenticationFault: Cannot 'sudo' - unknown or retired user: 'scout'`) for this staff account. The brief's "auto-detect via OS username" plan doesn't hold as-is; `jiffySG.current_login()` still uses it as a provisional default but callers need an explicit override (`test_connection(as_login=...)`) until this is resolved. Needs the RMIT confirmation below regardless — this result is only proven for one staff account, not yet tested against a student login.
   - **Real Project code found**: `VART3575` appeared in the visible-Projects list — almost certainly the actual course Project code the brief needed (the saved-view URL `.../page/5779` wasn't it). `Catherine_Vickery_S4096697` also appeared, suggesting the per-student-Project naming pattern is already seeded on the site. The rest of the 17 (`Start From Scratch`, `Demo: ...`, `... Template`, etc.) are ShotGrid's stock bundled projects, not real ones.
   - Still open: confirm with RMIT's ShotGrid/IT admin — student `login` field ↔ RMIT domain username mapping (now known to *not* be OS-username-based for staff; needs checking separately for students); whether an Admin-tier Script key is obtainable long-term (this one was created fine, but permission scope wasn't specifically checked); whether Autodesk ID is shared between Maya licensing and ShotGrid.
   - Set up custom Task status codes on the `VART3575` Project matching `SHOT_STAGES`/`ASSET_STAGES` (see Stage mapping above) — still needed before `upload_playblast()` can create real Shot/Task/Version entities.
   - Next actual code piece: implement `upload_playblast()` for real (currently `NotImplementedError`) — needs the Task status codes above decided first, plus a decision on Shot/Task lookup (by name match against `VART3575`?) before it can create entities.
4. Pilot with the one existing 3-person team first — lower stakes, easier to debug auth/API rough edges before wider rollout.
5. Roll out to the rest of the class, each with their own ShotGrid Project (cloned from a template if useful, since ShotGrid's project-duplicate feature is admin-console-only and can't be triggered from a student's API session).
6. Once proven, retire JiffySchedule in favour of Jiffy SG.

**Bigger picture (per user, 2026-07-16):** this whole transition — Jiffy SG/ShotGrid, then the shared server, then eventually a render farm — is expected to roll out across the **whole school**, over roughly **3-4 years**. The concrete first slice within that is (a) get Jiffy SG talking to ShotGrid at all, then (b) roll that out to **all staff** before wider expansion — the single 3-student pilot above is the very first step of that, not something that needs to anticipate later stages (render farm, whole-school scale) yet. No rush intended on any of this; prioritize getting the foundations (auth, permissions, path handling) right over moving fast, since mistakes here compound across a much larger rollout later.

## Adjacent and future initiatives (added 2026-07-15)

Captured here so they inform Jiffy SG's design even though most are out of scope for the initial build.

**1. Playblast → Jiffy SG → ShotGrid.** pbTool (shipped RV playblast review launch 2026-07-15) should be able to send a playblast into ShotGrid as a `Version` entity linked to the shot's Task — ShotGrid's standard dailies/review workflow. Rather than pbTool holding its own separate ShotGrid login, it should hand the playblast off to Jiffy SG (same pattern as the existing JiffySchedule → JiffyPomo hand-off: a direct module call, e.g. `import jiffySG; jiffySG.upload_playblast(shot_name, filepath)`), and **Jiffy SG performs the actual upload using the session it already has open** for that student's linked project. This avoids a student needing to log into ShotGrid separately per tool, and keeps ShotGrid auth/session state in one place.

pbTool also needs two things at the point of sending a playblast:
- **A notes field**, so a student can add context to that specific playblast ("blocking pass, ignore the left arm"). Rather than inventing a second, separate notes system, this should feed the *same* append-only `Note`-entity feed already designed for Jiffy SG's shots — a playblast note is just another Note, linked to that Version (and/or the shot's Task), not a parallel concept.
- **Configurable burn-in info** — students should be able to control what text gets baked into the playblast video itself (name, shot, custom text), not just Maya's fixed built-in HUD elements. This is a Maya-technical question more than a ShotGrid one: Maya's native `playblast`/HUD ornaments only expose a fixed set of built-in fields (frame, camera, scene name), so genuinely custom freeform burn-in text needs either scripted custom HUD elements injected before the playblast runs, or a post-process compositing pass (e.g. ffmpeg `drawtext`) over the rendered video. Worth auto-populating the obvious fields (artist, shot name, stage) from Jiffy SG/ShotGrid data by default, with room for the student to type additional custom text on top — consistent with the rest of this design's theme of not making students retype what's already tracked.

> **pbTool's side done (2026-07-21), inert until Jiffy SG exists:** `pbTool.py` now has a "Notes (sent with this playblast)" scroll field, a "Custom Text" burn-in field (drawn bottom-right, since fps/scene/frame/focal already occupy the other three burn-in corners — not yet auto-populated from Jiffy SG/ShotGrid data since there's no session to pull from), and a "Send to ShotGrid" button wired to `send_to_shotgrid()`. That method does exactly the hand-off described above — `import jiffySG; jiffySG.upload_playblast(shot_name, version_folder, files=..., notes=...)` inside a try/except ImportError, same shape as `jiffySchedule.py`'s `_send_to_pomo` — and today always shows "Jiffy SG isn't installed" since `jiffySG.py` doesn't exist yet. `shot_name` is derived from `get_scene_relative_folder_from_scenes()`, and the payload passed is the raw JPEG version folder + file list (no video encoding step exists in pbTool) — whether Jiffy SG wants a pre-encoded movie or the frame sequence path is an open question for whoever builds `upload_playblast()`, not decided here.

**2. Portable drives → central server → render farm.** This ShotGrid rollout is step one of a bigger, multi-stage shift, and the eventual scale is **the whole school**, not just this course: (1) students move off portable/external drives onto (2) a single shared server, then eventually (3) a render farm. Not a Jiffy SG feature itself, but critical context — once there's a real shared server, uploaded playblasts/publishes can reference a consistent server path rather than a portable drive letter that won't resolve on anyone else's machine; further out, render farm job submission would likely tie into the same Task/Version tracking Jiffy SG already owns. Given the whole-school scale this eventually reaches, get the foundational pieces (auth, permissions, path handling) right now rather than retrofitting later — mistakes here compound across many more students down the line.

**3. mpAnim shelf: frame-range button.** A new shelf button that looks up the current shot's frame range (from Jiffy SG and/or ShotGrid) and sets Maya's playback range automatically, instead of an animator typing it in by hand. Needs to resolve "which shot is this" the same way JiffySchedule already infers a shot name from the current scene file. Should call into Jiffy SG's already-authenticated session (same reasoning as #1) rather than re-implementing its own ShotGrid connection.

**4. Long-term: multi-DCC bridge + full asset pipeline.** Vision beyond Maya — bridge ShotGrid to Adobe Premiere, After Effects, DaVinci Resolve, and Houdini, and extend tracking beyond shots to full asset pipeline management. This is a much larger, separate initiative that needs its own design pass when the time comes — not something to spec now. One real constraint worth flagging early: Houdini is Python-native like Maya, so the same connector approach likely extends there directly. Premiere and After Effects are not — they're scripted via JavaScript/ExtendScript/UXP, so bridging them to `shotgun_api3` (Python-only) needs a separate relay mechanism, not a direct port. DaVinci Resolve has its own Python/Lua scripting API, closer to feasible but still a distinct integration path. "Bridge to all four" is not the same amount of work in each case.

**Design implication for the initial build:** because pbTool and the frame-range shelf button both need ShotGrid access independently of Jiffy SG's own UI, **Jiffy SG should own the single ShotGrid session/connection for a given student**, with other tools calling into it rather than each maintaining separate logins and connector code. Worth designing Jiffy SG's connection layer with this in mind from the start, even though only the JiffyPomo-style hand-off exists today.
