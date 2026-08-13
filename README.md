# KarAI — Tax & TDS Intelligence for Freelancers and Individuals

KarAI detects when a payment triggers a Tax Deducted at Source (TDS) obligation under India's
Income Tax Act 2025 (Section 393), computes the TDS due with a plain-language explanation of
*why*, projects quarterly advance-tax liability, and flags mismatches against your Annual
Information Statement (AIS) — all before the government's own AI-driven scrutiny systems do.

**This is a working prototype, not a certified filing tool.** Every calculation carries an
"AI-assisted, advisory only" disclaimer. Verify with a Chartered Accountant or the current CBDT
notification before filing or making a payment decision on the basis of anything this app shows.

## What's real vs. what's stubbed

The core intelligence — the thing that makes this product different — is fully implemented and
tested:

| Capability | Status |
|---|---|
| Section 393 TDS rule engine (thresholds, rates, per-payee-per-FY tracking) | **Real**, unit-tested |
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

### Docker (recommended)

```bash
cp .env.example .env
# edit .env: set JWT_SECRET and ENCRYPTION_KEY to real random values
#   python3 -c "import secrets; print(secrets.token_urlsafe(48))"
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend API + docs: http://localhost:8000/docs
- Postgres: localhost:5432

> This environment didn't have Docker installed, so `docker compose up` itself was not run
> directly here. Everything it wires together (Postgres 16, the FastAPI backend, the Vite
> frontend) was verified working via the equivalent manual setup below, including the full
> register → ingest → detect → report → delete-account flow end-to-end in a real browser.
> Run `docker compose up --build` yourself to confirm the container wiring; if anything doesn't
> come up, check `docker compose logs`.

### Manual (no Docker)

Backend:
```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL="postgresql+psycopg2://<user>@localhost:5432/karai_dev"
export JWT_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
export ENCRYPTION_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export CORS_ORIGINS="http://localhost:5173"
alembic upgrade head
uvicorn app.main:app --reload
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

### Tests

```bash
cd backend
source .venv/bin/activate
pytest --cov=app --cov-report=term-missing
```

102 tests, 98% coverage, concentrated on the rule engine, TDS detector, advance-tax projector,
and AIS diffing (the parts making the actual tax-correctness claims), plus auth/security and
full API integration tests (row-level isolation, account deletion cascade, rate limiting).

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

- **Tax slabs and Section 393 thresholds are version-stamped but not live-verified.** They mirror
  publicly documented values as of this build and will drift from reality as Finance Bills and
  CBDT circulars are issued. `RULE_TABLE_VERSION` / `SLAB_VERSION` exist specifically so a real
  deployment can track and update them without touching call sites.
- **No surcharge or senior-citizen tax slabs.** Out of scope for this prototype; noted in
  `advance_tax/slabs.py`.
- **No marginal relief edge case beyond the documented 87A cliff logic** — verified against the
  standard formula but not against every historical edge case.
- **Password-reset-via-OTP is not implemented** (account lockout after 5 failed attempts is).
- **No API-key management for third-party ingestion** (Tally/Zoho-style integrations) — the
  `sources/` abstraction supports adding one without touching the detection pipeline.
- **No automated backup scheduling** — see the `pg_dump` note below.

Backup example (run on a schedule in production, e.g. cron):
```bash
docker compose exec db pg_dump -U karai karai > backup-$(date +%F).sql
```