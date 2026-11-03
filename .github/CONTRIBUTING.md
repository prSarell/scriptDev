# Contributing

Welcome! This repo holds Maya tools for RMIT's 3D animation teaching, and
the group **film pipeline** (`pipeDev/`). You can help by **coding**,
**testing**, or both.

Read these first:
1. `CLAUDE.md`: how the repo is laid out, and where files go.
2. `pipeDev/PIPE_RULES.md`: the pipe's rules. Some things are locked.
3. `pipeDev/pipelineReview_stage2.md`: where the pipe is and where it's
   heading.

## Testing (no coding needed)

1. Get the pipe: download the repo (green **Code** button → Download ZIP),
   or `git clone` it. Then run
   `mayapy pipeDev/pipelineInstaller/build_zip.py` and drag the zip's
   `install.py` into Maya.
2. Ask the project lead for test ShotGrid access and a test H folder.
   Credentials are sent privately and never go in the repo.
3. Work through `pipeDev/handTests.md`. Report each result with
   **Issues → New issue → Hand test result**. Fails are the most useful
   ones.

Found something else? Use **New issue → Bug or problem**.

## Coding

**Setup:** Maya 2025 (2026 must work too), Git, and a GitHub account
added to the repo. Claude Code is welcome; it reads `CLAUDE.md` and the
pipe rules automatically.

**Flow:**
1. Pick or open an issue, and say you're on it.
2. Make a branch: `git switch -c pipe/<short-name>` (or `test/...`,
   `docs/...`).
3. Make the change. Add or update a `test_*_mayapy.py` beside the code
   you changed.
4. Run `mayapy pipeDev/run_tests.py` (or `... run_tests.py publish` for
   one area). Everything must pass.
5. Push the branch and open a pull request. Fill in the template.
6. The project lead reviews and merges. `main` is protected: nobody pushes
   to it directly.

**Testing a branch in Maya:** build the zip from your branch
(`build_zip.py`) and install it, so you're testing exactly what's in the
PR.

## Things that need the project lead

These are code-owned, so a PR touching them waits for the lead's review:
- `mpToolSet/` and `studio4AnimToolset/`: merging these **publishes to
  students**;
- `.github/`;
- `CLAUDE.md` and `pipeDev/PIPE_RULES.md`;
- the files holding the locked department list and Build's dropdowns.

Design decisions belong to the lead too. If your change needs one, ask in
the issue first and label it `needs-decision`.
