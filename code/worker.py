# Stateless worker using Redis Streams consumer groups + atomic Lua claim.
# Lease discipline makes execution recoverable if the worker crashes.

import asyncio
import os
import time
from redis.asyncio import Redis
from redis_schema import (
    job_key, quota_key, agent_pointer_key,
    queue_key, delayed_queue_key, reservations_key
)
from lua_ops import CLAIM_JOB_LUA, RENEW_LEASE_LUA, FINALIZE_JOB_LUA

WORKER_ID = f"worker-{os.getpid()}"
GROUP = "gpu-workers"

LEASE_TTL_MS = 30_000      # initial lease
RENEW_EVERY_MS = 10_000    # renew cadence
DELAY_ON_NO_CREDITS_MS = 5_000  # backoff

def now_ms() -> int:
    return int(time.time() * 1000)

# Mock blob storage for tiered agent state
class BlobStorage:
    async def load_state(self, pointer: str) -> dict:
        await asyncio.sleep(0.01)
        return {"pointer": pointer, "state": "heavy_agent_state"}

    async def save_state(self, data: dict) -> str:
        await asyncio.sleep(0.01)
        return f"s3://bucket/agent_state/{int(time.time())}"

async def ensure_group(r: Redis):
    try:
        await r.xgroup_create(queue_key(), GROUP, id="0-0", mkstream=True)
    except Exception:
        # group exists
        pass

async def execute_agent(prompt: str, agent_state: dict) -> dict:
    # Simulate GPU work
    await asyncio.sleep(1.0)
    agent_state["last_prompt"] = prompt[:80]
    return {"ok": True, "summary": "done"}

async def main():
    r = Redis.from_url("redis://localhost:6379", decode_responses=True)
    storage = BlobStorage()

    claim_sha = await r.script_load(CLAIM_JOB_LUA)
    renew_sha = await r.script_load(RENEW_LEASE_LUA)
    finalize_sha = await r.script_load(FINALIZE_JOB_LUA)

    await ensure_group(r)
    print(f"[{WORKER_ID}] Listening...")

    while True:
        # 1) Block for messages (delivered once into consumer group)
        streams = await r.xreadgroup(
            GROUP, WORKER_ID, {queue_key(): ">"}, count=1, block=2000
        )
        if not streams:
            continue

        _, messages = streams[0]
        msg_id, data = messages[0]

        tenant_id = data["tenant_id"]
        job_id = data["job_id"]

        jk = job_key(tenant_id, job_id)
        qk = quota_key(tenant_id)

        # 2) Fetch job metadata (source of truth)
        job = await r.hgetall(jk)
        if not job:
            await r.xack(queue_key(), GROUP, msg_id)
            continue

        cost = float(job.get("cost_gpu_seconds", "0"))

        # 3) ATOMIC CLAIM (job state + credits + lease)
        res = await r.evalsha(
            claim_sha,
            3,
            qk, jk, reservations_key(),
            job_id, str(cost), str(now_ms()), str(LEASE_TTL_MS), WORKER_ID
        )

        ok = int(res[0])

        if ok == 0 and res[1] == "INSUFFICIENT_CREDITS":
            # Landmine fix: don't poison PEL. ACK and move to delayed queue.
            run_at = now_ms() + DELAY_ON_NO_CREDITS_MS
            await r.xadd(delayed_queue_key(), {
                "tenant_id": tenant_id,
                "job_id": job_id,
                "run_at_ms": str(run_at),
            })
            await r.xack(queue_key(), GROUP, msg_id)
            continue

        if ok == 0:
            # Not queued / already running / etc. Just ACK (someone else owns it)
            await r.xack(queue_key(), GROUP, msg_id)
            continue

        # 4) Tiered state: load pointer from Redis, heavy state from storage
        pointer = await r.get(agent_pointer_key(tenant_id, job["agent_id"]))
        agent_state = await storage.load_state(pointer) if pointer else {}

        # 5) Execute with lease renewal loop
        last_renew = now_ms()
        try:
            for _ in range(3):
                if now_ms() - last_renew >= RENEW_EVERY_MS:
                    await r.evalsha(
                        renew_sha,
                        2,
                        jk, reservations_key(),
                        job_id, str(now_ms()), str(LEASE_TTL_MS), WORKER_ID
                    )
                    last_renew = now_ms()
                await asyncio.sleep(0.5)

            result = await execute_agent(job["prompt"], agent_state)

            # Save heavy state back to blob storage + update pointer
            new_pointer = await storage.save_state(agent_state)
            await r.set(agent_pointer_key(tenant_id, job["agent_id"]), new_pointer)

            # 6) FINALIZE atomically (state + lease release)
            await r.evalsha(
                finalize_sha,
                2,
                jk, reservations_key(),
                job_id, str(now_ms()), WORKER_ID, "COMPLETED", str(result)
            )

            # 7) ACK stream message (remove from PEL)
            await r.xack(queue_key(), GROUP, msg_id)

        except Exception as e:
            await r.evalsha(
                finalize_sha,
                2,
                jk, reservations_key(),
                job_id, str(now_ms()), WORKER_ID, "FAILED", str(e)
            )
            await r.xack(queue_key(), GROUP, msg_id)

if __name__ == "__main__":
    asyncio.run(main())