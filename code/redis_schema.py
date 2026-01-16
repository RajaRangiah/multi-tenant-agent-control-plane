# Redis key schema for a multi-tenant agent control plane.
# Keys are structured to guarantee isolation, observability, and safe recovery.

def job_key(tenant_id: str, job_id: str) -> str:
    # Hash with job metadata/state (tenant-scoped)
    return f"t:{tenant_id}:job:{job_id}"

def quota_key(tenant_id: str) -> str:
    # Hash storing token bucket fields (tenant-scoped)
    return f"t:{tenant_id}:quota:gpu"

def agent_pointer_key(tenant_id: str, agent_id: str) -> str:
    # String pointer to blob storage (tenant-scoped)
    return f"t:{tenant_id}:agent:{agent_id}:pointer"

def queue_key() -> str:
    # Main job queue stream (system-wide)
    return "sys:queue:jobs"

def delayed_queue_key() -> str:
    # Delayed jobs stream (system-wide)
    return "sys:queue:jobs:delayed"

def reservations_key() -> str:
    # Global ZSET: member = job_id, score = expiry_ms (system-wide)
    return "sys:gpu:reservations"

def lease_key(job_id: str) -> str:
    # Optional per-job lease key (system-wide)
    return f"sys:lease:{job_id}"