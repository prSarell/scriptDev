# Premiere <-> ShotGrid editorial bridge — research notes (2026-09-21)

Findings from a live session building a first Assignment 3 class-cut workflow:
pull the latest submitted shots from ShotGrid, get them into Premiere, and push
a cut back to ShotGrid. Written up as research for whichever `pipeDev` tool
eventually formalizes this — see `timeManagementDev/jiffySG_brief.md`'s
"long-term multi-DCC bridge" section, which already flagged Premiere/AE as
needing their own design pass since they're not Python-native like Maya.

## 1. Pulling the latest submitted shot per Shot

Works cleanly via the API, same connection pattern as `shotSub`
(`pipeDev/shotSubDev/shotgridConnect.py`), run under `mayapy` (no system
Python has `shotgun_api3` — see `reference_shotgrid_setup` memory):

```python
versions = sg.find(
    "Version", [["entity", "is", shot]],
    ["id", "code", "sg_uploaded_movie", "created_at"],
    order=[{"field_name": "created_at", "direction": "desc"}],
)
latest = versions[0]
movie = latest["sg_uploaded_movie"]          # a File/Link field dict
sg.download_attachment(movie, file_path=dest_path)
```

Important: `Version.sg_path_to_frames` (written by `shotSub.upload_playblast`)
is a **local path on the student's own machine** — not fetchable remotely.
The only media ShotGrid actually stores centrally is
`Version.sg_uploaded_movie`, the rvio-encoded review movie. Any "pull the
frames" workflow has to mean pulling that movie, not real per-frame stills.

## 2. Codec incompatibility — the real blocker

`shotSub`'s `_encode_to_mp4()` (`shotgridConnect.py:275`) calls `rvio` with no
explicit `-codec`, which currently defaults to **`mp4v`** (MPEG-4 Part 2, a
legacy codec). Confirmed by hand-parsing the MP4 `stsd` box — see
`mp4_codec.py` pattern below, no ffmpeg needed:

```python
# walk moov/trak/mdia/minf/stbl/stsd, read the 4-byte sample-entry fourcc
# 'mp4v' = MPEG-4 Part 2, 'avc1' = H.264
```

`mp4v` plays fine in RV (bundled ffmpeg decoder, very permissive) but **is
not decodable by Premiere or Windows Media Foundation** without QuickTime,
which Apple deprecated on Windows years ago and which isn't installed on a
typical student/lab machine. This will silently affect *every* student
submission, not just this pull — it only shows up the moment someone tries to
use the footage outside RV/ShotGrid's own player.

**Fix applied for this session (re-encode after the fact):**
`rvio` was already on this machine (`C:\Program Files\Autodesk\RV-2025.1.0\bin\rvio.exe`
— the same binary `shotSub` calls) and supports H.264 output:

```
rvio in.mp4 -o out.mp4 -codec libx264
```

Confirmed via `-formats` that the codec name is `libx264` (not `h264`) for
the `mp4` container. `-outparams` syntax for tuning (profile, crf, etc.) is
`name:type=value` (e.g. `vc:crf:f=18`) — a `name:type` with no `=value`
silently no-ops (`WARNING: MovieFFMpeg: Could not match option`) rather than
erroring, which cost real time to catch.

**Real fix, not yet applied:** change `_encode_to_mp4()` to always pass
`-codec libx264` so every future student submission is Premiere-compatible
from the moment it's published, instead of needing this re-encode step every
time an instructor wants to edit with submitted footage. Deliberately not
done as a side effect of this session — it changes output for all students,
needs explicit sign-off.

## 3. Even re-encoded H.264 wasn't reliably readable on Windows

After re-encoding to `libx264`, Windows (`Media Player`) and Premiere both
still reported "unsupported codec" for some/all files, while RV played them
fine. Hand-verified the file was structurally standard: `avcC` present,
H.264 **High Profile, Level 3.1**, BT.709 `colr` tags, all expected
`stbl` tables (`stsd`/`stts`/`stsz`/`stco`) present and well-formed.

Working theory going in: `libx264`'s default settings use B-frames, which
made `rvio` write an `edts`/`elst` (edit list) box to compensate for
decode/display-order offset, and Windows' Media Foundation MP4 demuxer has a
known history of fragility with edit lists (RV's ffmpeg-based reader doesn't
care either way). **Tested and disproven**: re-encoding with
`-outparams vc:profile=baseline` (correct syntax — no `:type` suffix needed
for an already-typed option; `vc:profile:s=baseline` just silently no-ops,
see the syntax note above) confirmed via box-dump that baseline profile does
drop B-frames (`ctts` — the composition-time-offset table — disappears), but
the `edts`/`elst` box is still there regardless. So B-frames are not what's
causing the edit list, and the edit list (if it's even the real culprit,
which was never confirmed independently) is not a B-frame side effect here.

**Actual cause of the Windows/Premiere "unsupported codec" symptom is still
unknown.** `-codec libx264 -outparams vc:profile=baseline` was applied to
`shotgridConnect._encode_to_mp4()` anyway (2026-09-21) since it's a solid,
confirmed fix for the original `mp4v`-unreadable problem and baseline
profile is the most broadly-compatible H.264 profile regardless — but
whether it *also* resolves the specific Windows playback failure seen this
session is unconfirmed pending the user's own test. If it's still broken,
the edit-list theory needs to be abandoned and the actual cause
re-investigated from scratch (e.g. bisect further `-outparams` combinations,
or compare against a known-good H.264 mp4 from a different encoder entirely
to isolate whether it's an `rvio`/ffmpeg-mov-muxer quirk at all).

Also floated: testing on macOS instead, since AVFoundation is typically far
more permissive of exactly this kind of edit-list/B-frame quirk than Windows
Media Foundation. Not tested this session (no Mac access from this
environment) — worth trying if the Windows-side fix doesn't pan out.

## 4. Getting shots into Premiere: XML linking was unreliable, native import wasn't

Built an FCP7 XML (v5) to pre-populate a Premiere sequence with all clips
already placed in shot order — the interchange format Premiere natively
imports via File > Import. Tried three `pathurl` encodings across the
session, in this order, on Premiere Pro 2026 / Windows:

1. `file://localhost/D%3A/...` (percent-encoded drive colon) — imported the
   sequence structure but every clip came in "Media Offline", no relink
   prompt at all.
2. `file:///D%3A/...` (no `localhost` host segment) — same offline result,
   but this time Premiere *did* prompt Link Media, suggesting this form was
   at least recognized as a file reference worth resolving.
3. `file://localhost/D:/...` (colon left unencoded) — not conclusively
   tested before the session moved on.

None auto-resolved cleanly. **What actually worked**: skip XML-based media
linking entirely.

- Rename each shot's movie to its exact ShotGrid Shot code
  (`NWF_EAP_010.mp4`, etc.) — also incidentally fixes the filename mismatch
  described in `project_a3_editorial_pull` memory.
- Put them all in one flat folder (Premiere's native Import dialog only
  multi-selects within a single folder).
- File > Import that folder directly (plain filesystem read — no path-string
  parsing involved, so nothing to get wrong).
- Sort the Project panel by Name (shot-code filenames sort into correct
  order for free) → select all → **Automate to Sequence**.

This is the version worth building real tooling around: native import +
Automate to Sequence is far more robust than trying to hand-craft a
perfectly-escaped interchange file, and it's one click once the media is
named/organized correctly.

## 5. ShotGrid Cut/CutItem semantics (confirmed against live schema)

- `Cut` is its own entity type, **not** an Asset. `Cut.entity` links to
  exactly one `Sequence` or `Episode` — it cannot span multiple Sequences.
  Assignment 3 has 21 shots across **4** team Sequences
  (`Assignment_3_team_1..4`, via `Shot.sg_sequence`), so "one Cut for
  Assignment 3" isn't representable as a single entity — it has to be 4
  Cuts, one per team.
- `CutItem` key fields (from a live `schema_field_read`, not docs):
  `cut_item_in`/`cut_item_out`/`cut_item_duration` = the **source** range
  used from that shot's media; `edit_in`/`edit_out` = the item's position on
  the **Cut's own timeline**; `cut_order` = simple sequence position;
  `version` links directly to a `Version` entity (lets a CutItem point at
  the exact submitted review that's in the cut). `fps` on `Cut` must be a
  **float**, not an int, or `create()` raises a `Fault`.
- Import is one-directional and inert: importing/creating a Cut never
  touches the local Premiere project, never notifies anyone, never changes
  Shot/Task status, and critically **never produces a playable stitched
  video** — it's pure structural metadata (order/timing/shot links). To get
  something actually playable, a real movie has to be rendered/exported
  separately and uploaded as a `Version`.
- No `shotgun_api3` helper exists for "import this EDL/XML as a Cut" — that
  logic lives in ShotGrid's own web UI (or `tk-multi-importcut`, not
  configured on this site). Built the 4 Assignment 3 Cuts directly via
  `sg.create("Cut", ...)` / `sg.create("CutItem", ...)` instead of the web
  importer — straightforward once the schema is known, and doesn't depend on
  ever having a real edited timeline to export from Premiere.

## 6. Tools confirmed present/absent on this machine ("Bean")

- `mayapy`: `C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe`
- `rvio`: `C:\Program Files\Autodesk\RV-2025.1.0\bin\rvio.exe` — already used
  by `shotSub`, also usable standalone for transcoding/probing.
- No `ffmpeg`, `ffprobe`, `VLC`, or `HandBrake` installed. MP4 duration/codec
  probing was done with small dependency-free Python (parsing `mvhd`/`stsd`
  atoms directly) rather than installing anything new.
- Adobe Media Encoder 2026 is installed alongside Premiere but shares its
  media engine/decoder limitations — doesn't help read `mp4v` either.

## 7. Open items for a future `pipeDev` tool

> **Update 2026-10-13:** item 1 below is out of date. The live encoder
> (`shelfDev/mpAnim/tools/shotgridConnect.py`, `_encode_to_mp4`) now always
> passes `-codec libx264`, with the time slider audio muxed in as PCM, and
> the user confirms Premiere now loads shotSub movies. See
> `filmPipeline_spec.md` §4 "Final publish movie for the edit".

1. **Tried, rolled back (2026-09-21), still needed.** Added
   `-codec libx264 -outparams vc:profile=baseline` to
   `_encode_to_mp4()` and asked the user to test locally first. Testing hit
   an unrelated snag (see below) and ran out of time, so the change was
   reverted rather than left half-verified — both `shotgridConnect.py`
   copies (see the important note just below) are back to git HEAD, no
   codec flag at all, still defaulting to `mp4v`. **This still needs to be
   done** — nothing about the underlying case against `mp4v` changed, the
   attempt just didn't finish being validated.
   - **Important:** `shotSub` graduated to shelf-native — the deployed,
     actually-live source is `shelfDev/mpAnim/tools/shotgridConnect.py`
     (mirrored into `Documents/maya/scripts/` by `mpInstaller.py`), **not**
     `pipeDev/shotSubDev/shotgridConnect.py`. The latter is a stale,
     already-drifted leftover from before the tool graduated out of active
     dev — it isn't deployed anywhere. The first attempt at this fix
     mistakenly edited the stale pipeDev copy, which is why the user's
     first test showed no change at all. Whoever picks this up next: edit
     `shelfDev/mpAnim/tools/shotgridConnect.py`, not the pipeDev one.
   - **Testing gotcha found:** `_encode_to_mp4()` skips re-encoding if a
     `.mp4` already exists in the version folder and is newer than the
     source `.jpg` frames (meant to avoid re-encoding on a notes-only
     republish). Republishing the *same* local version folder to test a
     code change silently reuses the stale pre-fix `.mp4` instead of
     re-running `rvio` — byte-identical output, easy to mistake for "the
     fix didn't work." To actually test a `rvio` invocation change, publish
     a genuinely new local version, or delete the cached `.mp4` in that
     version folder first.
2. Resolve the Windows "H.264 but still unsupported" mystery — the
   edit-list/B-frame theory was tested and disproven (see above), so the
   real cause is still open.
3. If XML-based Premiere ingestion is still wanted (vs. native
   import + Automate to Sequence), the `pathurl` encoding that actually
   auto-links in this Premiere version was never nailed down — needs
   dedicated testing, ideally by someone who can watch Premiere's reaction
   directly rather than iterating blind.
4. A real "push the cut back to ShotGrid" path still needs an actual edited
   Premiere sequence exported to XML/EDL — nothing here tested that leg
   end-to-end, since the sequence never got past offline media this session.
