This architecture is built around one rule:

**Workers execute. The system decides.**

That separation is what makes fairness, retries, and crash recovery reliable at scale.
# Architecture Overview

This system treats GPUs as governed resources.

## System Data Flow

```mermaid
sequenceDiagram
    participant User
    participant API as API (FastAPI)
    participant Redis as Redis (Stream/Hash)
    participant Worker as Worker (Stateless)
    
    User->>API: Submit Job (Budget Check)
    API->>Redis: HSET Job State + XADD Queue
    Redis-->>API: Job ID (Queued)
    API-->>User: 202 Accepted
    
    loop Lease Cycle
        Worker->>Redis: XREADGROUP (Get Job)
        Worker->>Redis: EVAL (Claim + Deduct Credits)
        alt Sufficient Credits
            Redis-->>Worker: OK + Lease
            Worker->>Worker: Execute Agent
            Worker->>Redis: EVAL (Renew Lease)
            Worker->>Redis: EVAL (Finalize + Release Lease)
        else Insufficient Credits
            Redis-->>Worker: DENY
            Worker->>Redis: Move to Delayed Queue
        end
    end
```

## **Two-plane model**
## Control plane (Redis + API)

* owns truth: job state, quotas, leases

* decides who is allowed to run

* ensures retries and crash recovery are safe

## Data plane (Workers)

* stateless executors

* run jobs only while holding a valid lease

* can crash without corrupting global state

## **Key invariants**
* No job runs without paying (quota charge happens inside CLAIM).

* No worker owns a job permanently (execution rights are leased).

* If a worker dies, the system recovers (lease expiry + reaping).

* Fairness is enforced before execution (token bucket at claim time).

This design favors determinism over cleverness.

<script type="module">
  import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
  mermaid.initialize({ startOnLoad: true });
</script>