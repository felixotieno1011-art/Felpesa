# Next steps

## Done
- Double-entry ledger, wallets, transfers, idempotency (409 on mismatch), audit log
- Pay bill, till, airtime (internal demo merchants, not real fulfilment)
- Transaction PIN with lockout, mandatory by default
- Daraja sandbox top-up with callback, status query and unique receipt
- Provider interface, Daraja adapter, mock provider, `payment_attempts`
- Pending withdrawals with once-only reversal, and a reconciliation job
- Inbox, receipts, live updates over SSE and Redis
- Production compose: non-root images, migrations as a step, startup guard, pinned lock file
- Refresh tokens in an HttpOnly cookie with rotation and reuse detection; access token in memory only
- Scheduled payment reconciliation with a Redis lock; crash-gap retry for unsent withdrawals
- Tests isolated on `felpesa_test` and Redis DB 15
- Auto-logout on 401, Nairobi time in messages
- Redesign: sidebar, bottom bar, balance card, local icons

## Open, in order
1. **Real payout adapter.** Daraja has no payout lookup here, so real payouts stay in manual review.
2. **Scheduled worker** for reconciliation. Today an admin calls the endpoint.
3. **Crash gap.** A withdrawal debited with no payout attempt is only reported, not retried.
4. **Pending-withdrawal wording.** The inbox still says "withdrawn" before the provider confirms.
8. **Push notifications** for closed apps (device tokens, Web Push or FCM).
9. **Operations.** A production compose file (no `--reload`), migrations as a deploy step, a locked dependency set.
10. **Fraud engine.** Risk scoring beyond the two current rules.

12. **Cleanup.** Purge expired and revoked `refresh_tokens` rows.

13. **Production hardening still open:** TLS in front of nginx (the refresh cookie is Secure), database backups, log shipping and monitoring, container resource limits.

## Before any real money
- Find a licensed payment partner and get written terms (safeguarding, settlement, fees).
- Get advice from a Kenyan payments lawyer on CBK authorisation, AML/KYC and data protection.
- Real airtime, bill and withdrawal fulfilment through provider APIs.
- Until then, Felpesa is a portfolio project.
