# Code Reference

This directory contains the reference implementation of the control plane and workers.

## Core Components

* [**redis_schema.py**](./redis_schema.py)
    * **Role:** The Database Schema.
    * **Details:** Defines the Redis key structures (`t:{tenant}:...`) to ensure isolation and consistent naming.

* [**lua_ops.py**](./lua_ops.py)
    * **Role:** The Governance Engine.
    * **Details:** Contains the atomic Lua scripts (`CLAIM`, `RENEW`, `FINALIZE`) that enforce quotas and prevent race conditions.

* [**api_server.py**](./api_server.py)
    * **Role:** The Entry Point.
    * **Details:** A lightweight FastAPI app that handles job submission, durability, and idempotency checks.

* [**worker.py**](./worker.py)
    * **Role:** The Execution Unit.
    * **Details:** A stateless worker that uses the "Lease-Loop" pattern to claim jobs, execute them, and handle heartbeats.

## Background Services

* [**delayed_scheduler.py**](./delayed_scheduler.py)
    * **Role:** Backoff Manager.
    * **Details:** Moves jobs from the "Delayed" queue back to the "Main" queue when their retry timer expires.

* [**pel_reaper.py**](./pel_reaper.py)
    * **Role:** Crash Recovery.
    * **Details:** Scans the Redis Stream Pending Entries List (PEL) for jobs owned by dead workers and re-queues them.