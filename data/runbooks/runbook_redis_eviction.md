# Runbook: Redis Cache Eviction Spike
**Target Service:** payment-gateway, auth-service
**Error Signature:** `HTTP_503: Service Unavailable - Redis cache eviction threshold exceeded`
**Severity:** High (Tier 2)

## Diagnosis Steps
1. Confirm spike in `HTTP_503` responses alongside high memory eviction warnings.

## Recovery Procedure (Requires Human Approval)
1. Execute the `flush_stale_cache` tool to clear expired session keys.
2. Scale read-replicas if traffic remains elevated.