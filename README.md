# Multi-Tenant Agent Control Plane

This repository is the technical companion to a simple idea:

**AI agents don’t bankrupt you because they scale.  
They bankrupt you because they scale without control.**

At **20 GPUs**, brute force works.  
At **200 GPUs**, finance starts asking questions.  
At **5,000+ GPUs**, lack of governance becomes a systemic business risk.

This is **control-plane code**, not a full product.

---

## The Problem

AI agent platforms fail at scale because:
- GPU usage is uncontrolled
- Concurrency causes double execution and double billing
- Worker crashes leak expensive capacity
- One tenant can silently monopolize the system

At small scale, brute force works.  
At large scale, these are not engineering bugs — they are **financial failure modes**.

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

This separation is what allows cost control, retries, and fairness to hold at scale.

---

## The three failure modes this architecture eliminates

### 1️⃣ The RAM Density Ceiling

Most agent platforms duplicate context per user.  
You hit memory limits long before GPU limits.

**Fix:** Tiered state + execution isolation  
*(enables shared heavy context: model state, RAG indices, tool metadata)*

**Outcome:** Higher agent density per node and slower, more controlled fleet expansion.

📌 At scale, this isn’t thrift — it’s **capacity planning discipline**.

---

### 2️⃣ Race Conditions = Financial Bugs

Concurrency without transactional guarantees causes:
duplicate execution, double billing, retry storms, and silent state corruption.

**Fix:** Strict transactional state transitions enforced by the control plane.

**Outcome:** Idempotent execution, auditable behavior, predictable cost per job.

📌 At 10k GPUs, this isn’t a bug — it’s **financial exposure**.

---

### 3️⃣ The Noisy Neighbor Problem

One runaway agent should never stall the entire system.

**Fix:** Fair-share scheduling with enforceable quotas.

**Outcome:** Predictable latency, enforceable SLAs, controlled blast radius.

📌 This is how hyperscalers avoid **self-inflicted outages**.

---

## What this is (and is not)

This is not an agent framework and not a demo application.  
It is a **governance layer**.

The goal is not to make agents smarter.  
The goal is to make AI systems economically predictable, failure-tolerant,
and safe to operate at scale.

---

## What this repo contains

- **Redis key schema** for tenant isolation and observability
- **Atomic Lua scripts** for:
  - `CLAIM` — charge credits, mark RUNNING, create lease
  - `RENEW` — extend lease with ownership proof
  - `FINALIZE` — complete/fail job and release lease
- **Minimal API layer** for durable job submission and idempotency
- **Stateless workers** with lease discipline and tiered agent-state pointers
- **Delayed queue scheduler** for intentional backoff
- **PEL reaper** for crash recovery in Redis Streams

---

## Repo tour (recommended reading order)

- **Architecture Overview** – core invariants, diagrams, and failure model  
  [`architecture.html`](./architecture.html)

- **Economics & ROI** – fairness and cost governance model  
  [`economics.html`](./economics.html)

- **Code Reference** – reference implementation  
  [`code/`](./code/)

---

## Important note on “shared heavy context”

This repo implements **tiered state + execution isolation**, which enables shared heavy context safely.

The actual in-process shared cache (RAG index, tool registry, etc.) is a follow-on optimization once ownership, isolation, and recovery are correct.

---

## License

MIT
