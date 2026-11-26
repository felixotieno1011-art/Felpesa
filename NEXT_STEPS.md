# Next steps

## Done
- Double-entry ledger, wallets, transfers, idempotency (409 on mismatch), audit log
- Pay bill, till, airtime (internal demo merchants, not real fulfilment)
- Transaction PIN with lockout, mandatory by default
- Daraja sandbox top-up with callback, status query and unique receipt
- Provider interface, Daraja adapter, mock provider, `payment_attempts`
- Pending withdrawals with once-only reversal, and a reconciliation job
- Inbox, receipts, live updates over SSE and Redis

## Open, in order
1. **Real payout adapter.** Daraja has no payout lookup here, so real payouts stay in manual review.
2. **Scheduled worker** for reconciliation. Today an admin calls the endpoint.
3. **Crash gap.** A withdrawal debited with no payout attempt is only reported, not retried.
4. **Pending-withdrawal wording.** The inbox still says "withdrawn" before the provider confirms.
5. **Separate test database.** The suite runs against the dev database.
6. **Expired token.** Redirect to login on a 401; confirmation messages show UTC, rows show local time.
7. **Token storage.** Move from `localStorage` to refresh tokens in HttpOnly cookies, with revocation.
8. **Push notifications** for closed apps (device tokens, Web Push or FCM).
9. **Operations.** A production compose file (no `--reload`), migrations as a deploy step, a locked dependency set.
10. **Fraud engine.** Risk scoring beyond the two current rules.
11. **Redesign.** The sidebar and icon layout from earlier was never committed and was lost.

## Before any real money
- Find a licensed payment partner and get written terms (safeguarding, settlement, fees).
- Get advice from a Kenyan payments lawyer on CBK authorisation, AML/KYC and data protection.
- Real airtime, bill and withdrawal fulfilment through provider APIs.
- Until then, Felpesa is a portfolio project.
