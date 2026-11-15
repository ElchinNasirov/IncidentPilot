# Runbook: Database Connection Pool Exhaustion
**Target Service:** payment-gateway, user-profile-db
**Error Signature:** `ERR_CONNECTION_REFUSED: Upstream Postgres pool exhausted`
**Severity:** Critical (Tier 1)

## Diagnosis Steps
1. Check active connection counts in the server logs (`status_code == 500` or `503`).
2. Verify if latency spikes exceed 2000ms.

## Recovery Procedure (Requires Human Approval)
1. Execute the `restart_connection_pool` tool targeting the affected service.
2. Monitor latency metrics for 5 minutes to confirm stabilization below 250ms.