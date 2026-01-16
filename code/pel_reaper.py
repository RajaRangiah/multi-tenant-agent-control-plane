# Reclaims stuck jobs from Redis Stream PEL using XAUTOCLAIM (Redis 6.2+).
# Replays are safe because CLAIM is idempotent and lease-based.

import asyncio
from redis.asyncio import Redis
from redis_schema import queue_key

GROUP = "gpu-workers"
REAPER = "reaper-1"
MIN_IDLE_MS = 30_000  # consider stuck after 30s

async def main():
    r = Redis.from_url("redis://localhost:6379", decode_responses=True)

    while True:
        try:
            next_id, claimed = await r.xautoclaim(
                queue_key(), GROUP, REAPER, MIN_IDLE_MS, "0-0", count=20
            )

            if claimed:
                for msg_id, data in claimed:
                    # Requeue the message and ACK the old pending entry
                    await r.xadd(queue_key(), data)
                    await r.xack(queue_key(), GROUP, msg_id)

            await asyncio.sleep(2.0)

        except Exception:
            await asyncio.sleep(2.0)

if __name__ == "__main__":
    asyncio.run(main())