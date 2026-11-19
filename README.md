# Disk Declutter

Scans your Windows machine and tells you which apps, files and caches are unused or stale and can be cleared to free space.

- **Read-only scan.** Nothing changes until you run `clean --apply`.
- **Recycle Bin only.** Cleanup never permanently deletes. `clean` is a dry run unless you pass `--apply`.
- **Optional local AI.** `--ai` asks a local Ollama model for a second opinion on borderline items. It sees metadata only (never file contents) and is advisory: it cannot make anything more deletable.

## Quick start

```powershell
pip install -r requirements.txt
python -m declutter scan            # ~seconds; add --ai for Ollama opinions
python -m declutter report --open   # review, tick items, export selection.json
python -m declutter clean           # dry run, shows exactly what would move
python -m declutter clean --apply   # move to Recycle Bin, then empty it yourself
```

Run `scan` from an administrator terminal for accurate "last used" dates for apps (Windows Prefetch needs admin).

## What it looks at

| Scanner | Finds |
|---|---|
| files | Large files untouched for a while (Downloads, Documents, Desktop, Videos, Pictures, Music) and duplicate copies (size, then partial hash, then full hash) |
| apps | Installed programs from the registry with size and best-effort last-used time. Listed with their uninstall command; never removed by the tool |
| caches | Temp folders, browser caches, npm/pip/yarn/pnpm/gradle/NuGet/cargo caches, Windows Update download cache, stale `node_modules` |
| usage | Folder-size breakdown of your profile, drillable in the report |

Useful options: `--min-size-mb 100`, `--stale-days 180`, `--dirs D:\Games E:\Stuff`, `--skip apps usage`, `--model llama3.2`.

## Safety model

- `clean` only acts on paths present in the last `output/scan.json` and flagged deletable. A hand-edited `selection.json` cannot name arbitrary files.
- Windows, Program Files, ProgramData and your profile roots are protected and refused again at clean time.
- A duplicate is only removed if the copy being kept still exists.
- Cache folders are emptied, not removed.
- Items bigger than your Recycle Bin limit are refused (Windows would delete them permanently), and a Bin set to delete immediately aborts the run.
- Every move is logged in `output/cleanup_log.json`.
- Space is only freed once you empty the Recycle Bin.

## Layout

```
declutter/
  cli.py        scan / report / clean commands
  config.py     defaults, protected-path rules, file locations
  models.py     Item / ScanResult
  scan.py       runs scanners, scores, optional AI, writes output/scan.json
  scoring.py    rule-based reason / confidence / risk
  scanners/     files, apps, caches, usage
  fsutil.py     shared walking helpers (skip symlinks and junctions)
  report.py     renders templates/report.html with the scan embedded
  clean.py      validated Recycle Bin cleanup
  ai.py         optional Ollama reasoning
tests/          pytest suite (python -m pytest)
```

Generated files live in `output/` (git-ignored). Duplicate hashes are cached in `output/hash_cache.json` so re-scans only re-read changed files.
