# FastAPI ingress for job submission.
# This layer is intentionally thin: durable job record + stream enqueue + idempotency.

import time
import uuid
from fastapi import FastAPI, Header, HTTPException
from redis.asyncio import Redis

# Ensure redis_schema.py is in the same folder
from redis_schema import job_key, queue_key

app = FastAPI()

# Connect to Redis
r = Redis.from_url("redis://localhost:6379", decode_responses=True)

def now_ms() -> int:
    return int(time.time() * 1000)

@app.post("/submit")
async def submit_job(
    tenant_id: str,
    agent_id: str,
    prompt: str,
    cost_gpu_seconds: float = 5.0,
    idempotency_key: str | None = Header(default=None),
):
    """
    tenant_id: which tenant
    agent_id: which agent configuration/memory pointer to use
    cost_gpu_seconds: how many GPU-seconds we estimate/charge
    idempotency_key: client retry safety
    """
    if cost_gpu_seconds <= 0:
        raise HTTPException(400, "cost_gpu_seconds must be > 0")

    # 1) Idempotency: if caller retries, return the same job_id
    if idempotency_key:
        idem_redis_key = f"t:{tenant_id}:idem:{idempotency_key}"
        existing_job = await r.get(idem_redis_key)
        if existing_job:
            return {"job_id": existing_job, "status": "QUEUED"}

    # 2) Create job record (durable state)
    job_id = str(uuid.uuid4())
    jk = job_key(tenant_id, job_id)
    now = str(now_ms())

    await r.hset(jk, mapping={
        "tenant_id": tenant_id,
        "job_id": job_id,
        "agent_id": agent_id,
        "state": "QUEUED",
        "prompt": prompt,
        "cost_gpu_seconds": str(cost_gpu_seconds),
        "created_ms": now,
        "updated_ms": now,
    })

    # 3) Push only identifiers into the stream (cheap + scalable)
    await r.xadd(queue_key(), {"tenant_id": tenant_id, "job_id": job_id})

    # 4) Persist idempotency mapping for 24h
    if idempotency_key:
        await r.set(idem_redis_key, job_id, ex=24 * 3600)

    return {"job_id": job_id, "status": "QUEUED"}