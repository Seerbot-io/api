# SeerBot Service

## Caching Overview
- Redis-backed middleware caches GET requests registered through `router_cache`.
- `/analysis` endpoints now cache responses until the next 5-minute boundary using `seconds_until_next_interval`.
- If Redis is unavailable, an in-memory TTL cache keeps responses warm using the same expiry rules (per-process only).
- Configure Redis via `.env` (`REDIS_HOST`, `REDIS_PORT`, `REDIS_MAX_CONNECTIONS`, `REDIS_SSL`).

## Extending Cache Coverage
- Call `router_cache(<router>, "<prefix>", "<cache_type>", spec_method="GET")` for additional routers.
- Available cache types include fixed durations (`in-1m`, `in-5m`, `in-30m`, `in-1h`) and dynamic variants (`at-e5m`, `at-eh-m5`, etc.).
- Use `at-e5m` for data feeds that refresh every five minutes to align expiry with upstream updates.

