# Felpesa

A digital wallet API and web app for Kenya: wallets, transfers, pay bill / till,
airtime, PIN-protected payments, an inbox with live updates, and a double-entry ledger.

> **Status: sandbox and portfolio project.** No real customer funds. Deposits and
> withdrawals are simulated, and are switched off when `APP_ENV=prod`. Holding real money
> needs a licensed partner and legal review (see NEXT_STEPS.md).

## Stack

- **API:** FastAPI, SQLAlchemy (async), Alembic, PostgreSQL 17, Redis 7
- **Web:** React 18, TypeScript, Vite
- **Tests:** pytest (110 tests, run against a live Postgres and Redis)

## How it works

    Web app --> FastAPI routers --> services --> PostgreSQL (ledger, wallets, audit)
                                        |
                                        +--> Redis (rate limits, PIN lockout, live events)
                                        |
                                        +--> payments layer --> provider adapters (daraja, mock)

- **Double-entry ledger.** Every transaction has balanced debit and credit entries.
  Entries are never edited or deleted; mistakes are fixed with compensating entries.
- **Safe money movement.** Wallet rows are locked in a fixed order, so concurrent
  transfers cannot deadlock or double-spend.
- **Idempotency.** Every money request needs an `Idempotency-Key`. Replays return the
  original result; reusing a key with different parameters returns 409.
- **Provider-independent payments.** The ledger never calls a provider directly. Providers
  sit behind `app/payments/interfaces.py`. Payments to or from outside the wallet go
  through a `payment_attempts` table with explicit states.
- **Never credit on a guess.** An M-Pesa top-up is credited only after a callback AND a
  confirming status query, once, matched to a unique receipt. Timeouts become
  `needs_review`, never `failed`.
- **Reconciliation.** `POST /admin/reconcile-payments` re-checks stuck attempts. It acts
  only on explicit provider answers and never refunds a payout twice.

## Run it

    cp .env.example .env
    # edit .env: set JWT_SECRET (python3 -c "import secrets;print(secrets.token_urlsafe(48))"),
    # POSTGRES_USER, POSTGRES_PASSWORD and POSTGRES_DB (the DB name must be felpesa_dev)
    docker compose up -d db redis api web
    docker compose exec api alembic upgrade head
    docker compose exec api python -m scripts.seed_merchants
    docker compose exec api pytest -o addopts="" -q

- API docs: http://localhost:8001/docs
- Web app: http://localhost:5173

Never commit `.env`.

## Main endpoints

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/register`, `POST /auth/login` (rate limited) |
| Wallet | `GET /wallets/me`, `GET /wallets/lookup?phone=` (masked name) |
| Money | `POST /transfers`, `POST /payments/paybill`, `POST /payments/till`, `POST /airtime` |
| Cash | `POST /deposits` (dev only), `POST /withdrawals` (dev only) |
| PIN | `GET /pin/status`, `POST /pin` (3 wrong tries lock for 15 minutes) |
| M-Pesa | `POST /mpesa/stk`, `GET /mpesa/status/{id}`, Daraja callback hook |
| History | `GET /transactions`, `GET /transactions/{id}` |
| Inbox | `GET /notifications`, `GET /notifications/stream` (live), read and delete |
| Admin | `POST /admin/reconcile-payments`, plus ledger, reconciliation and audit routes |

Sending, paying, airtime and withdrawing all require the transaction PIN.

## Security decisions

- **Sandbox M-Pesa only the test number.** A Daraja sandbox push once reached a real SIM
  and debited it. `/mpesa/stk` therefore accepts only Safaricom's test number
  (`+254708374149`). Never enter your own number or PIN on a test prompt.
- Simulated deposits and withdrawals return 404 when `APP_ENV=prod`.
- The `mock` payment provider is refused in production.
- JWTs must have `type=access`; Redis outages return a clean 503.
- Wallet ownership and system-wallet rules are enforced inside the services, not just the routers.

## Known limitations

See NEXT_STEPS.md.
