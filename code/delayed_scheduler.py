# Moves delayed jobs back into the main queue when they become runnable.
# This is a simple "timer wheel" built using Redis Streams.

import asyncio
import time
from redis.asyncio import Redis
from redis_schema import queue_key, delayed_queue_key

GROUP = "delay-scheduler"
CONSUMER = "delay-1"

def now_ms() -> int:
    return int(time.time() * 1000)

async def main():
    r = Redis.from_url("redis://localhost:6379", decode_responses=True)

    try:
        await r.xgroup_create(delayed_queue_key(), GROUP, id="0-0", mkstream=True)
    except Exception:
        pass

    while True:
        streams = await r.xreadgroup(
            GROUP, CONSUMER, {delayed_queue_key(): ">"}, count=10, block=2000
        )
        if not streams:
            continue

        _, messages = streams[0]
        for msg_id, data in messages:
            run_at = int(data["run_at_ms"])
            if run_at > now_ms():
                # Not ready yet: leave pending briefly
                continue

            await r.xadd(queue_key(), {"tenant_id": data["tenant_id"], "job_id": data["job_id"]})
            await r.xack(delayed_queue_key(), GROUP, msg_id)

if __name__ == "__main__":
    asyncio.run(main())