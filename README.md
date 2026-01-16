# Multi-Tenant Agent Control Plane

This repository demonstrates how to build a **governed AI agent runtime** that prevents GPU waste, enforces fairness, and remains safe under failure.

This is **control-plane code**, not a full product.

---

## The Problem

AI agent platforms fail at scale because:
- GPU usage is uncontrolled
- Concurrency causes double execution and double billing
- Worker crashes leak expensive capacity
- One tenant can silently monopolize the system

At small scale, brute force works.  
At large scale, **lack of governance becomes a financial risk**.

---

## What makes this work

The system separates **decision-making** from **execution**.

A central **control plane** owns:
- job state
- fairness and quotas
- execution ownership
- failure recovery

Workers are **stateless and disposable**.  
They can crash without losing work or leaking GPUs.

---

## What This Repo Contains
- **Redis key schema** for tenant isolation and observability
- **Atomic Lua scripts** for:
  - `CLAIM` (charge + mark RUNNING + lease)
  - `RENEW` (extend lease with ownership proof)
  - `FINALIZE` (complete/fail + release lease)
- **Minimal API layer** for durable job submission + idempotency
- **Stateless workers** with lease discipline and tiered agent state pointers
- **Delayed queue scheduler** for backoff
- **PEL reaper** for crash recovery in Redis Streams

---

## Repo tour (recommended reading order)

* [**Architecture Overview**](./architecture.md) – core invariants, diagrams, and failure model
* [**Economics & ROI**](./economics.md) – fairness and cost governance model
* [**Code Reference**](./code/) – implementation details

---

## Important note on “shared heavy context”

This repo implements **tiered state + execution isolation**, which enables shared heavy context safely.
The actual in-process shared cache (RAG index, tool registry, etc.) is a follow-on optimization once ownership and recovery are correct.

---

## License

MIT