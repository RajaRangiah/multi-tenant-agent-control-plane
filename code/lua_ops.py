# Atomic Redis Lua scripts for correctness under concurrency.
# These prevent double execution, credit drift, and leaked GPU capacity.

CLAIM_JOB_LUA = r"""
-- KEYS[1] = quota_key (hash)
-- KEYS[2] = job_key (hash)
-- KEYS[3] = reservations_zset (zset)
-- ARGV[1] = job_id
-- ARGV[2] = cost_credits (float)
-- ARGV[3] = now_ms (int)
-- ARGV[4] = lease_ttl_ms (int)
-- ARGV[5] = worker_id (string)

local quota_key = KEYS[1]
local job_key = KEYS[2]
local reservations = KEYS[3]

local job_id = ARGV[1]
local cost = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local ttl = tonumber(ARGV[4])
local worker = ARGV[5]

-- 1) Idempotent claim gate: only QUEUED can be claimed
local state = redis.call("HGET", job_key, "state")
if state ~= "QUEUED" then
  return {0, "JOB_NOT_QUEUED", state}
end

-- 2) Load token bucket fields
local last_ms = tonumber(redis.call("HGET", quota_key, "last_ms") or tostring(now))
local credits = tonumber(redis.call("HGET", quota_key, "credits") or "0")
local rate = tonumber(redis.call("HGET", quota_key, "rate_per_sec") or "0")
local burst = tonumber(redis.call("HGET", quota_key, "burst") or "0")

-- Guard: negative time skew
local dt_ms = now - last_ms
if dt_ms < 0 then dt_ms = 0 end

-- 3) Lazy refill
credits = credits + (rate * (dt_ms / 1000.0))
if credits > burst then credits = burst end

-- 4) Affordability check (persist progress even when failing)
if credits < cost then
  redis.call("HSET", quota_key, "credits", tostring(credits), "last_ms", tostring(now))
  return {0, "INSUFFICIENT_CREDITS", tostring(credits)}
end

-- 5) Deduct credits
credits = credits - cost
redis.call("HSET", quota_key, "credits", tostring(credits), "last_ms", tostring(now))

-- 6) Mark job RUNNING (atomic with charge)
redis.call("HSET", job_key,
  "state", "RUNNING",
  "worker_id", worker,
  "start_ms", tostring(now),
  "updated_ms", tostring(now)
)

-- 7) Create lease in global ZSET
local expiry = now + ttl
redis.call("ZADD", reservations, expiry, job_id)

return {1, "OK", tostring(credits), tostring(expiry)}
"""

RENEW_LEASE_LUA = r"""
-- KEYS[1] = job_key (hash)
-- KEYS[2] = reservations_zset (zset)
-- ARGV[1] = job_id
-- ARGV[2] = now_ms
-- ARGV[3] = extend_ttl_ms
-- ARGV[4] = worker_id

local job_key = KEYS[1]
local reservations = KEYS[2]

local job_id = ARGV[1]
local now = tonumber(ARGV[2])
local extend = tonumber(ARGV[3])
local worker = ARGV[4]

local state = redis.call("HGET", job_key, "state")
if state ~= "RUNNING" then
  return {0, "NOT_RUNNING", state}
end

local curr_worker = redis.call("HGET", job_key, "worker_id")
if curr_worker ~= worker then
  return {0, "NOT_OWNER", curr_worker}
end

local new_expiry = now + extend
redis.call("ZADD", reservations, new_expiry, job_id)
redis.call("HSET", job_key, "updated_ms", tostring(now))

return {1, "OK", tostring(new_expiry)}
"""

FINALIZE_JOB_LUA = r"""
-- KEYS[1] = job_key (hash)
-- KEYS[2] = reservations_zset (zset)
-- ARGV[1] = job_id
-- ARGV[2] = now_ms
-- ARGV[3] = worker_id
-- ARGV[4] = final_state ("COMPLETED" or "FAILED")
-- ARGV[5] = result_or_error (string)

local job_key = KEYS[1]
local reservations = KEYS[2]

local job_id = ARGV[1]
local now = ARGV[2]
local worker = ARGV[3]
local final_state = ARGV[4]
local payload = ARGV[5]

local state = redis.call("HGET", job_key, "state")
if state ~= "RUNNING" then
  return {0, "NOT_RUNNING", state}
end

local curr_worker = redis.call("HGET", job_key, "worker_id")
if curr_worker ~= worker then
  return {0, "NOT_OWNER", curr_worker}
end

redis.call("HSET", job_key,
  "state", final_state,
  "updated_ms", now,
  "payload", payload
)

redis.call("ZREM", reservations, job_id)
return {1, "OK"}
"""