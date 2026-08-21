# Job Search Agent (France) — simple v1

Local Python agent that discovers roles, scores them against your CV, queues/applies good fits, and tracks status. Designed for a **private GitHub repo** + Actions cron + Pages status report.

## What’s in this simple build

| Piece | Status |
|--------|--------|
| CV parse (markdown / PDF) | Working |
| Matcher (keywords + remote preference + dealbreakers) | Working |
| SQLite tracker | Working |
| **Demo** connector (offline smoke test) | Working |
| **France Travail** search API | Working (needs credentials) |
| LinkedIn / Indeed / WTTJ / APEC | Stubs (login bootstrap ready; apply later) |
| Static HTML report | Working |
| Streamlit local UI | Minimal |
| GitHub Actions + Pages | Workflows included |

France Travail **apply** is manual-queue in v1 (search + score are automated). Browser portals are stubs until you enable them and extend Playwright flows.

## Quick start (local)

**Easiest:** double-click `start.bat` → browser opens → press **START SEARCH**.

Or manually:

```powershell
cd job-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run ui/app.py
```

Your CV (`resume/cv_profile.md` or a PDF) is used to **score** jobs. France Travail does **not** auto-upload/apply the resume yet — good fits are marked `manual` so you open the link and apply yourself.

### France Travail (real search)

1. Register an app at [francetravail.io](https://francetravail.io) with scope `api_offresdemploiv2 o2dsoffre`.
2. Copy `config/.env.example` → `.env` and set `FRANCE_TRAVAIL_CLIENT_ID` / `SECRET`.
3. In `config/config.yaml`: set `demo.enabled: false`, `france_travail.enabled: true`.
4. Run: `python scripts/run_once.py --force`

### Browser portals (later)

```powershell
playwright install chromium
python scripts/login_bootstrap.py linkedin
# saves .auth/linkedin.json — never commit
```

## Config knobs

Edit `config/config.yaml`:

- `kill_switch` — pause all automation
- `matching.threshold` — auto-queue if score ≥ this (default 65)
- `matching.dealbreakers` — skip visa/citizenship blockers
- `portals.*.enabled` / `daily_cap`
- `cv_path` — point at `resume/cv_profile.md` or a PDF

## GitHub deployment (private repo)

```powershell
cd job-agent
git init
git add .
git commit -m "Initial job-agent v1"
# create private repo on GitHub, then:
git remote add origin https://github.com/<you>/<repo>.git
git branch -M main
git push -u origin main
```

Then:

1. **Settings → Secrets**: add `FRANCE_TRAVAIL_CLIENT_ID`, `FRANCE_TRAVAIL_CLIENT_SECRET` (and portal emails later).
2. Enable **Actions**.
3. Enable **Pages** → source: GitHub Actions.
4. Run workflow **Run job agent** manually once.
5. Open the Pages URL for the read-only tracker.

## Layout

```
job-agent/
  config/config.yaml
  connectors/          # france_travail + demo + stubs
  core/                # cv_parser, matcher, tracker, scheduler
  scripts/             # run_once, login_bootstrap, generate_report
  ui/app.py            # local Streamlit
  docs/index.html      # GitHub Pages report
  db/jobs.db           # created on first run
```

## Risk note

LinkedIn/Indeed (and similar) ToS disallow bots. This repo still uses human-like delays, caps, kill switch, and session reuse — but cloud IPs raise ban risk. Prefer local `run_once.py` if a portal starts checkpointing.
