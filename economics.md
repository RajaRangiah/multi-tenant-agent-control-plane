AI doesn’t get expensive because it scales.  
It gets expensive because it scales without enforcement.

This model enforces cost and fairness using GPU-seconds and quota-based scheduling.


# Cost and Fairness Model

GPUs are enforced using **GPU-seconds**, not fractional GPUs.

## Why GPU-seconds

You cannot reliably carve a GPU into fractions for arbitrary workloads.
Instead, fairness is enforced over time:
- Each tenant earns credits at a fixed rate (token bucket).
- Jobs consume credits when claimed.
- If a tenant runs out of credits, the job is delayed (backoff) instead of poisoning the queue.

## ROI & Business Impact

By enforcing strict "GPU-seconds" quotas rather than allocating full GPUs per tenant:

1. **Utilization:** Increases GPU bin-packing density (running small jobs in gaps), reducing idle waste.
2. **Predictability:** Tenants are capped by *spend rate*, eliminating "surprise" cloud bills.
3. **Risk Mitigation:** A runaway recursive agent loop is killed automatically when the token bucket empties, preventing financial leakage.

## What this enforces
- predictable cost per tenant
- controlled bursts (via burst cap)
- prevention of noisy-neighbor monopolies
- budget-safe scaling

This aligns technical execution with financial reality.