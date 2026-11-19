# Disk Declutter

Scans your Windows machine and tells you which apps, files and caches are unused or stale and can be cleared to free space.

- **Read-only scan.** Nothing is changed until you run `clean`.
- **Recycle Bin only.** Cleanup never permanently deletes; `clean` is a dry run unless you pass `--apply`.
- **Optional local AI.** `--ai` asks a local Ollama model for a second opinion on borderline items (metadata only, never file contents).

## Usage

```powershell
pip install -r requirements.txt
python -m declutter scan
python -m declutter report --open
python -m declutter clean --apply
```

## Status

Scaffolding only. Scanners, report, clean and AI review are stubs (see `declutter/`).

## Layout

```
declutter/
  cli.py        scan / report / clean commands
  config.py     defaults and protected-path rules
  models.py     Item / ScanResult
  scan.py       runs scanners, scores, writes output/scan.json
  scoring.py    rule-based reason / confidence / risk
  scanners/     files, apps, caches, usage
  report.py     HTML report
  clean.py      Recycle Bin cleanup
  ai.py         optional Ollama reasoning
tests/
```
