#!/usr/bin/env bash
# Felpesa end-to-end demo. One command, full money lifecycle.
#
# Requires: the stack is up (`docker compose up -d`).
# Side effects: creates 3 demo users and ~6 transactions in the dev DB.
# Cleans up: nothing — leaves demo data so you can inspect it.
#
# What it demonstrates:
#   1. Users register (atomic: user + wallet)
#   2. Users deposit from an external source (double-entry vs clearing wallet)
#   3. Users transfer to each other (atomic, idempotent)
#   4. Users withdraw back out (double-entry vs clearing wallet)
#   5. Admin proves the ledger balances (reconciliation: ok=true)
#   6. Admin reads the audit trail (every action logged)
#
set -euo pipefail

API="${FELPESA_API:-http://localhost:8001}"
TS="$(date +%s)"

say() { echo -e "\n\033[1;36m▸ $*\033[0m"; }
ok()  { echo "  ✓ $*"; }
val() { echo "  → $*"; }

# --- helpers ---
req() {
  local method="$1" path="$2" body="${3:-}" token="${4:-}" idem="${5:-}" pin="${6:-}"
  local hdr=(-H "Content-Type: application/json")
  [ -n "$token" ] && hdr+=(-H "Authorization: Bearer $token")
  [ -n "$idem" ]  && hdr+=(-H "Idempotency-Key: $idem")
  [ -n "$pin" ]   && hdr+=(-H "X-Pin: $pin")
  if [ -n "$body" ]; then
    curl -sS -X "$method" "${API}${path}" "${hdr[@]}" -d "$body"
  else
    curl -sS -X "$method" "${API}${path}" "${hdr[@]}"
  fi
}

jq_get() { python3 -c "import sys,json; d=json.load(sys.stdin); print(d$1)"; }

# --- 0. health ---
say "Health check"
health=$(curl -sS "${API}/health")
echo "  → $health"
echo "$health" | grep -q '"status":"ok"' && ok "API healthy" || { echo "API not healthy — is docker compose up?"; exit 1; }

# --- 1. register 3 users ---
say "Registering demo users"
declare -A TOKENS WALLETS

for name in alice bob admin; do
  phone="+2547$((RANDOM))$(printf '%04d' "$RANDOM")"
  # keep it short — replace with deterministic-ish phones per run
  phone="+25479$(printf '%08d' $((TS % 100000000)))"
  # Recompute to avoid collision across alice/bob/admin
  case "$name" in
    alice) phone="+25479${TS: -7}1";;
    bob)   phone="+25479${TS: -7}2";;
    admin) phone="+25479${TS: -7}3";;
  esac

  resp=$(req POST /auth/register "{\"phone\":\"$phone\",\"full_name\":\"Demo ${name^}\",\"password\":\"hunter2hunter2\"}")
  if echo "$resp" | grep -q '"wallet_id"'; then
    wallet=$(echo "$resp" | jq_get "['wallet_id']")
    WALLETS[$name]="$wallet"
    val "$name: phone=$phone wallet=$wallet"
  else
    echo "  register failed: $resp"
    exit 1
  fi

  login=$(req POST /auth/login "{\"phone\":\"$phone\",\"password\":\"hunter2hunter2\"}")
  TOKENS[$name]=$(echo "$login" | jq_get "['access_token']")
  ok "$name: logged in"
done

# --- 2. promote admin in DB (so it can hit admin endpoints) ---
say "Promoting admin user"
docker compose exec -T db psql -U felpesa -d felpesa_dev -c \
  "UPDATE users SET role = 'admin' WHERE phone = '+25479${TS: -7}3';" >/dev/null
# Re-login to get token with admin role claim
login_admin=$(req POST /auth/login "{\"phone\":\"+25479${TS: -7}3\",\"password\":\"hunter2hunter2\"}")
TOKENS[admin]=$(echo "$login_admin" | jq_get "['access_token']")
ok "admin role assigned, token refreshed"

# --- 2b. set transaction PINs (required to send, pay and withdraw) ---
say "Setting transaction PINs"
PIN="2468"
for name in alice bob; do
  resp=$(req POST /pin "{\"pin\":\"$PIN\"}" "${TOKENS[$name]}")
  echo "$resp" | grep -q '"ok":true' && ok "$name: PIN set" || { echo "set PIN failed: $resp"; exit 1; }
done

# --- 3. fund Alice and Bob via deposits ---
say "Depositing funds (from clearing wallet — double-entry)"
for name in alice bob; do
  idem="demo-deposit-$name-$TS"
  resp=$(req POST /deposits "{\"amount\":10000.0,\"currency\":\"KES\",\"description\":\"demo seed\"}" "${TOKENS[$name]}" "$idem")
  echo "$resp" | grep -q '"status":"completed"' && ok "$name deposited 10000 KES" || { echo "deposit failed: $resp"; exit 1; }
done

# --- 4. show balances before transfer ---
say "Balances before transfer"
for name in alice bob; do
  w=$(req GET /wallets/me "" "${TOKENS[$name]}")
  bal=$(echo "$w" | jq_get "['balance']")
  val "$name: $bal KES"
done

# --- 5. Alice → Bob transfer ---
say "Transfer: Alice → Bob (2500 KES)"
idem="demo-transfer-$TS"
resp=$(req POST /transfers "{\"to_wallet_id\":\"${WALLETS[bob]}\",\"amount\":2500.0,\"currency\":\"KES\",\"description\":\"demo transfer\"}" "${TOKENS[alice]}" "$idem" "$PIN")
echo "$resp" | grep -q '"status":"completed"' && ok "transfer completed" || { echo "transfer failed: $resp"; exit 1; }

# --- 6. Idempotency demo: send the SAME key again ---
say "Idempotency demo (same Idempotency-Key, no double-send)"
resp2=$(req POST /transfers "{\"to_wallet_id\":\"${WALLETS[bob]}\",\"amount\":2500.0,\"currency\":\"KES\",\"description\":\"demo transfer\"}" "${TOKENS[alice]}" "$idem" "$PIN")
txn_a=$(echo "$resp"  | jq_get "['id']")
txn_b=$(echo "$resp2" | jq_get "['id']")
if [ "$txn_a" = "$txn_b" ]; then
  ok "same Idempotency-Key → same txn id ($txn_a) — no double-send"
else
  echo "  different txns: $txn_a vs $txn_b — IDEMPOTENCY BROKEN"
  exit 1
fi

# --- 7. Bob withdraws ---
say "Withdrawal: Bob → external (500 KES)"
resp=$(req POST /withdrawals "{\"amount\":500.0,\"currency\":\"KES\",\"description\":\"demo withdrawal\"}" "${TOKENS[bob]}" "demo-withdraw-$TS" "$PIN")
echo "$resp" | grep -q '"status":"completed"' && ok "withdrawal completed" || { echo "withdrawal failed: $resp"; exit 1; }

# --- 8. Balances after ---
say "Balances after all operations"
for name in alice bob; do
  w=$(req GET /wallets/me "" "${TOKENS[$name]}")
  bal=$(echo "$w" | jq_get "['balance']")
  val "$name: $bal KES"
done

# --- 9. Reconciliation ---
say "Reconciliation (admin): prove every transaction balances"
rec=$(req GET /reconciliation "" "${TOKENS[admin]}")
echo "$rec" | python3 -m json.tool | head -20
echo "$rec" | grep -q '"ok":true' && ok "LEDGER BALANCES" || { echo "RECONCILIATION FAILED"; exit 1; }

# --- 10. Audit log ---
say "Audit log (admin): every action recorded"
aud=$(req GET "/audit?limit=10" "" "${TOKENS[admin]}")
echo "$aud" | python3 -c "
import sys,json
d = json.load(sys.stdin)
items = d.get('items', [])
print(f'  → {len(items)} recent actions:')
for it in items[:8]:
    print(f\"    [{it['action']}] actor={str(it.get('actor_id','—'))[:8]} at {it['created_at'][:19]}\")
"
ok "audit trail complete"

say "DONE — Felpesa end-to-end demo succeeded."
echo
echo "  Login with any of these to explore the UI at http://localhost:5173:"
echo "    alice: +25479${TS: -7}1 / hunter2hunter2"
echo "    bob:   +25479${TS: -7}2 / hunter2hunter2"
echo "    admin: +25479${TS: -7}3 / hunter2hunter2  (admin — can see /reconciliation and /audit)"
