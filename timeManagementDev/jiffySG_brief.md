# Jiffy SG — design brief

Status: **design only, no code written**. Blocked on RMIT provisioning a single shared ShotGrid site. Not being built yet — this doc captures the plan agreed 2026-07-15 so the next session can pick it up without re-deriving it.

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

**Auth** — per-student human login (`shotgun_api3`, `login`/`password`), entered once in Jiffy SG, never committed to the repo.
> ⚠️ **Open question, not yet confirmed**: does RMIT's ShotGrid site support direct username/password API login, or is it SSO-only? Needs checking with RMIT's ShotGrid admin before building the login screen — if SSO-only, the simple login form approach won't work and a token-based flow is needed instead.

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

1. RMIT stands up the single shared site; staff get Producer, students get Artist permissions.
2. Confirm SSO vs. direct-login with RMIT's ShotGrid admin.
3. Build Jiffy SG in `timeManagementDev/jiffySGDev/`, forked from `jiffyScheduleDev/jiffySchedule.py` — most of the UI (row widgets, thumbnail capture, drag-reorder, notes box, artist dropdown, stage badges) carries over directly; only the data layer underneath is new.
4. Pilot with the one existing 3-person team first — lower stakes, easier to debug auth/API rough edges before wider rollout.
5. Roll out to the rest of the class, each with their own ShotGrid Project (cloned from a template if useful, since ShotGrid's project-duplicate feature is admin-console-only and can't be triggered from a student's API session).
6. Once proven, retire JiffySchedule in favour of Jiffy SG.

## Adjacent and future initiatives (added 2026-07-15)

Captured here so they inform Jiffy SG's design even though most are out of scope for the initial build.

**1. Playblast → Jiffy SG → ShotGrid.** pbTool (shipped RV playblast review launch 2026-07-15) should be able to send a playblast into ShotGrid as a `Version` entity linked to the shot's Task — ShotGrid's standard dailies/review workflow. Rather than pbTool holding its own separate ShotGrid login, it should hand the playblast off to Jiffy SG (same pattern as the existing JiffySchedule → JiffyPomo hand-off: a direct module call, e.g. `import jiffySG; jiffySG.upload_playblast(shot_name, filepath)`), and **Jiffy SG performs the actual upload using the session it already has open** for that student's linked project. This avoids a student needing to log into ShotGrid separately per tool, and keeps ShotGrid auth/session state in one place.

pbTool also needs two things at the point of sending a playblast:
- **A notes field**, so a student can add context to that specific playblast ("blocking pass, ignore the left arm"). Rather than inventing a second, separate notes system, this should feed the *same* append-only `Note`-entity feed already designed for Jiffy SG's shots — a playblast note is just another Note, linked to that Version (and/or the shot's Task), not a parallel concept.
- **Configurable burn-in info** — students should be able to control what text gets baked into the playblast video itself (name, shot, custom text), not just Maya's fixed built-in HUD elements. This is a Maya-technical question more than a ShotGrid one: Maya's native `playblast`/HUD ornaments only expose a fixed set of built-in fields (frame, camera, scene name), so genuinely custom freeform burn-in text needs either scripted custom HUD elements injected before the playblast runs, or a post-process compositing pass (e.g. ffmpeg `drawtext`) over the rendered video. Worth auto-populating the obvious fields (artist, shot name, stage) from Jiffy SG/ShotGrid data by default, with room for the student to type additional custom text on top — consistent with the rest of this design's theme of not making students retype what's already tracked.

**2. Portable drives → central server.** This ShotGrid rollout is step one of a bigger shift: RMIT moving students off portable/external drives onto a single shared server. Not a Jiffy SG feature itself, but relevant context for file-path handling — once there's a real shared server, uploaded playblasts/publishes can reference a consistent server path rather than a portable drive letter that won't resolve on anyone else's machine. Worth keeping in mind whenever pbTool's upload path handling gets built.

**3. mpAnim shelf: frame-range button.** A new shelf button that looks up the current shot's frame range (from Jiffy SG and/or ShotGrid) and sets Maya's playback range automatically, instead of an animator typing it in by hand. Needs to resolve "which shot is this" the same way JiffySchedule already infers a shot name from the current scene file. Should call into Jiffy SG's already-authenticated session (same reasoning as #1) rather than re-implementing its own ShotGrid connection.

**4. Long-term: multi-DCC bridge + full asset pipeline.** Vision beyond Maya — bridge ShotGrid to Adobe Premiere, After Effects, DaVinci Resolve, and Houdini, and extend tracking beyond shots to full asset pipeline management. This is a much larger, separate initiative that needs its own design pass when the time comes — not something to spec now. One real constraint worth flagging early: Houdini is Python-native like Maya, so the same connector approach likely extends there directly. Premiere and After Effects are not — they're scripted via JavaScript/ExtendScript/UXP, so bridging them to `shotgun_api3` (Python-only) needs a separate relay mechanism, not a direct port. DaVinci Resolve has its own Python/Lua scripting API, closer to feasible but still a distinct integration path. "Bridge to all four" is not the same amount of work in each case.

**Design implication for the initial build:** because pbTool and the frame-range shelf button both need ShotGrid access independently of Jiffy SG's own UI, **Jiffy SG should own the single ShotGrid session/connection for a given student**, with other tools calling into it rather than each maintaining separate logins and connector code. Worth designing Jiffy SG's connection layer with this in mind from the start, even though only the JiffyPomo-style hand-off exists today.
