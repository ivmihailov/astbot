# AST Bot

`AST Bot` is a MAX bot for navigating production cases in power engineering. The current version is no longer a procurement search bot: it uses a new `case_*` domain layer, stores cases in SQLite, and works as a pilot assistant for finding a relevant case, opening its card, and walking through steps.

## What Works Now

- `/start` and `/help`
- main menu in MAX
- free-text search through seeded cases
- "Popular cases" section
- case card with key details
- basic step-by-step walkthrough
- local SQLite catalog with seeded cases and steps

Legacy procurement files are still in the repository for reference, but the active bot flow now lives in:

- `bot.py`
- `case_models.py`
- `case_repository.py`
- `case_search.py`
- `case_state.py`
- `case_formatters.py`
- `case_handlers.py`

## Local Setup

### 1. Install Python and dependencies

The project is currently configured for Windows and was tested with the local interpreter path used in `run_bot.ps1`.

```powershell
cd c:\Users\ivmih\OneDrive\Desktop\zakupki-bot-main
pip install -r requirements.txt
```

If `pip` resolves to the wrong interpreter on your machine, use your exact Python executable instead:

```powershell
& 'C:\Users\ivmih\AppData\Local\Python\pythoncore-3.14-64\python.exe' -m pip install -r requirements.txt
```

### 2. Create `.env`

Copy `.env.example` to `.env` and fill in at least the MAX token:

```powershell
Copy-Item .env.example .env
```

Required now:

- `MAX_BOT_TOKEN`

Optional for later GigaChat integration:

- `GIGACHAT_CREDENTIALS`
- `GIGACHAT_SCOPE`
- `GIGACHAT_PARSE_MODEL`
- `GIGACHAT_ANSWER_MODEL`

Defaults already work for local pilot storage:

- `SQLITE_PATH=data/cases.db`
- `MEDIA_DIR=storage/photos`

## Running the Bot

### Recommended: run in the current PowerShell window

```powershell
cd c:\Users\ivmih\OneDrive\Desktop\zakupki-bot-main
powershell -ExecutionPolicy Bypass -File .\run_bot.ps1
```

This is the most reliable option on this machine.

### Alternative: start in a separate window

```powershell
cd c:\Users\ivmih\OneDrive\Desktop\zakupki-bot-main
.\start_bot.cmd
```

### Status and stop

```powershell
powershell -ExecutionPolicy Bypass -File .\status_bot.ps1
powershell -ExecutionPolicy Bypass -File .\stop_bot.ps1
```

## Data and Logs

- SQLite database: `data/cases.db`
- Rolling log file: `logs/bot.log`
- runtime stdout/stderr: `logs/runtime.out`, `logs/runtime.err`

The SQLite catalog is initialized automatically on startup. Seed cases are inserted by the repository layer if the database is empty.

## Quick Smoke Test

After launch, open the bot in MAX and try:

1. `/start`
2. `Популярные кейсы`
3. `Найти кейс`
4. A query such as `траншея заливается водой`

## Project Notes

- The rebuild audit and staged migration plan are in `docs/pilot_rebuild_plan.md`.
- Photo upload, persistent run history, analytics, and GigaChat query normalization are the next planned steps.
- `.env`, logs, and local SQLite files are intentionally ignored by git.

## License

This repository is released under `PolyForm Noncommercial 1.0.0`.

That means the code can be used for noncommercial purposes under the license terms, but commercial use is not permitted without separate permission from the copyright holder.
