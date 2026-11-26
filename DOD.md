# Definition of Done

A change that touches money is not done until every box is true.

## Code
- [ ] Money amounts use `Decimal`, never floats.
- [ ] Every money endpoint requires an `Idempotency-Key`; key reuse with different
      parameters returns 409.
- [ ] Wallet rows are locked with `FOR UPDATE` in sorted order.
- [ ] The debit and credit entries balance, and no ledger entry is edited or deleted.
- [ ] Ownership and system-wallet rules are checked in the service, not only the router.
- [ ] An audit record is written in the same database transaction.
- [ ] Money endpoints require the transaction PIN where a user spends funds.
- [ ] External payments use `payment_attempts`; uncertain outcomes become `needs_review`.

## Tests
- [ ] New behaviour has tests: success, failure, replay, and a concurrency case where relevant.
- [ ] The full suite passes: `docker compose exec api pytest -o addopts="" -q` (110+).
- [ ] The frontend type-checks: `docker compose exec web npx tsc --noEmit`.

## Safety
- [ ] No simulated money movement is reachable when `APP_ENV=prod`.
- [ ] No secrets in git: `git ls-files | grep -E "(^|/)\.env$"` prints nothing.
- [ ] Sandbox M-Pesa tests use only the Daraja test number.
- [ ] Migration is reversible and was run against a copy of existing data.

## Release
- [ ] Committed and pushed.
- [ ] README and NEXT_STEPS updated if behaviour or limits changed.
