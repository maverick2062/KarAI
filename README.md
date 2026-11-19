# KarAI — Tax & TDS Intelligence for Freelancers and Individuals

KarAI is a prototype for exploring Tax Deducted at Source (TDS) event detection, plain-language
calculation explanations, advance-tax projections, and Annual Information Statement (AIS)
discrepancy checks for Indian individuals and freelancers.

**This is a working prototype, not a certified filing tool.** Every calculation carries an
"AI-assisted, advisory only" disclaimer. Verify with a Chartered Accountant or the current CBDT
notification before filing or making a payment decision on the basis of anything this app shows.

## What's real vs. what's stubbed

The product flows are implemented and tested as prototype behavior:

| Capability | Status |
|---|---|
| Section 393 TDS rule engine (advisory thresholds/rates, per-payee-per-FY tracking) | **Prototype**, unit-tested; not a complete or verified implementation of current law |
| TDS event detection from a transaction stream | **Real**, unit-tested |
| Plain-language explanation of every computation | **Real** |
| Advance-tax quarterly projection + old/new regime comparator + 234B/234C interest | **Real**, unit-tested |
| AIS-mirror discrepancy detection | **Real**, unit-tested |
| PDF / Excel audit report generation | **Real** |
| Auth, row-level data isolation, rate limiting, field encryption | **Real**, tested |
| CSV upload / manual entry / synthetic demo feed | **Real** |
| **Live bank/UPI feed** (RBI Account Aggregator) | **Stubbed** — needs an AA partnership (Finvu/OneMoney/Perfios); see `app/sources/account_aggregator_stub.py` for the exact integration spec |
| **Auto e-filing** (ERI) | **Stubbed** — needs e-Return Intermediary registration with the Income Tax Dept; see `app/filing/` |
| **Real AIS pull** (IT portal OAuth) | **Stubbed** — see `app/ais_mock/oauth_stub.py` for the integration spec |

Nothing here pretends to have these integrations. Each stub raises `NotImplementedError` with a
docstring describing exactly what a real integration needs to implement, so plugging one in later
is additive, not a rewrite.

For PAN handling, manual entry lets you record whether the payee furnished PAN; CSV imports may
include an optional `party_pan` column. A blank value in that column means PAN was not furnished,
while omitting the column means PAN status is unknown. Supplied PANs are format-checked, not
verified against a government database. Where PAN is explicitly recorded as not furnished, the
TDS engine uses the higher of 20% or the scheduled rule rate and labels the event.

## Architecture

```
karai/
  backend/   FastAPI + SQLAlchemy + PostgreSQL (Python 3.12)
  frontend/  React + TypeScript + Vite
```

Backend modules (`backend/app/`):

- `rule_engine/` — the Section 393 TDS table and pure evaluation functions. This is the core IP.
- `tds_detector/` — per-vendor-per-FY cumulative tracking + the ingestion pipeline that ties
  a `TransactionSource` to the rule engine to explainability to persistence.
- `advance_tax/` — FY2026-27 tax slabs (old & new regime), quarterly installment schedule,
  Section 234B/234C interest estimation.
- `explainability/` — template-based plain-language rendering of every rule-engine decision
  (deliberately not ML/SHAP — the underlying logic is deterministic, so explaining it is
  templating, not approximating a model).
- `ais_mock/` — synthetic AIS generation, CSV upload parsing, and the discrepancy diffing engine.
- `sources/` / `filing/` — the adapter interfaces described above.
- `security.py` — JWT, bcrypt, AES-256-GCM field encryption, rate limiting.
- `reports/` — PDF (ReportLab) and Excel (openpyxl) report generation.
- `audit/` — hashing + audit-log helpers used by every state-changing operation.

## Running it

### Windows setup with Docker (recommended)

Prerequisites:

- Install Docker Desktop for Windows and make sure the Linux engine is running.
- Install Git for Windows if you are cloning the repository.

Open PowerShell in the repository root:

```powershell
Set-Location "C:\your_directory\karai\karai"
Copy-Item .env.example .env
notepad .env
```

In `.env`, replace `JWT_SECRET` and `ENCRYPTION_KEY` with long random values. You can generate
them in PowerShell with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

TDS email alerts are sent to the account email after an ingestion run finds TDS due. To enable
outbound email, configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM_EMAIL`, and (if required by your
provider) `SMTP_USERNAME`/`SMTP_PASSWORD` in `.env`. The app uses STARTTLS by default. Without
SMTP settings, no email is sent and the backend logs a warning.

Start the complete application:

```powershell
docker compose up --build
```

The backend automatically runs the Alembic database migration before starting, so the PostgreSQL
tables are created on the first run. To run it in the background instead:

```powershell
docker compose up -d --build
docker compose ps
```

To stop the application containers:

```powershell
docker compose down
```

- Frontend: http://localhost:5173
- Backend API + docs: http://localhost:8000/docs
- Postgres: localhost:5432

If a service does not start, inspect its logs:

```powershell
docker compose logs backend --tail=100
docker compose logs db --tail=100
docker compose logs frontend --tail=100
```

### Manual Windows setup (no Docker)

This option requires PostgreSQL 16 running locally, with a database and user matching the
`DATABASE_URL` value. Open two PowerShell terminals.

Backend:
```powershell
Set-Location "C:\your_directory\karai\karai\backend"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:DATABASE_URL="postgresql+psycopg2://<user>:<password>@localhost:5432/karai"
$env:JWT_SECRET = (python -c "import secrets; print(secrets.token_urlsafe(48))")
$env:ENCRYPTION_KEY = (python -c "import secrets; print(secrets.token_urlsafe(32))")
$env:CORS_ORIGINS="http://localhost:5173"
alembic upgrade head
uvicorn app.main:app --reload
```

Frontend:
```powershell
Set-Location "C:\your_directory\karai\karai\frontend"
npm install
npm run dev
```

### Tests

```powershell
Set-Location "C:\your_directory\karai\karai\backend"
.\.venv\Scripts\Activate.ps1
pytest --cov=app --cov-report=term-missing
```

Tests cover the rule engine, TDS detector, advance-tax projector, AIS diffing, auth/security, and
API integration behavior. Run the command above for the current test and coverage results.

## Try it in 60 seconds

1. Register an account, log in.
2. Go to **Transactions** → **Simulate bank feed**. This generates a year of realistic recurring
   payments to a handful of vendors.
3. Go to **TDS Events** — see which payments crossed a Section 393 threshold, with a
   plain-language explanation and filing deadline for each.
4. Go to **Advance Tax** — enter an income estimate, compare old vs. new regime, see the
   quarterly installment schedule.
5. Go to **Dashboard** → **Check against AIS** — see a simulated AIS-mismatch check.
6. Go to **Reports** → generate and download a PDF or Excel audit report.
7. Go to **Settings** to delete your account and all associated data at any time.

## Known limitations / honest gaps

- **Tax slabs and Section 393 rules are advisory and not a complete or current-law-verified
  implementation.** In particular, the TDS engine does not yet model all payer/payee categories,
  monthly rent periods, asset-specific rates, property stamp-duty valuation, or conditional
  threshold exceptions (including dividend and VDA cases). Do not rely on its results to decide withholding.
  Have a Chartered Accountant validate the applicable law and taxpayer facts before changing rule
  values or using them for compliance. `RULE_TABLE_VERSION` / `SLAB_VERSION` identify the
  calculation versions; they do not imply legal verification.
- **Automatic description classification is only a heuristic.** Text that matches multiple TDS
  categories is left unclassified; select the correct category explicitly rather than relying on
  an ambiguous description.
- **No surcharge or senior-citizen tax slabs.** Out of scope for this prototype; noted in
  `advance_tax/slabs.py`.
- **Advance-tax rules are also advisory.** The 87A marginal-relief and Section 234C installment
  calculations need validation against the applicable tax year and current law before use.
- **Password-reset-via-OTP is not implemented** (account lockout after 5 failed attempts is).
- **No API-key management for third-party ingestion** (Tally/Zoho-style integrations) — the
  `sources/` abstraction supports adding one without touching the detection pipeline.
- **No automated backup scheduling** — see the `pg_dump` note below.

Backup example (run on a schedule in production, e.g. cron):
```bash
docker compose exec db pg_dump -U karai karai > backup-$(date +%F).sql
```
