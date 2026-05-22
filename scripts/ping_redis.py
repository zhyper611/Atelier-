import asyncio
import sys

from redis.asyncio import Redis


async def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else "redis://172.19.134.98:6379/0"
    client = Redis.from_url(url, decode_responses=True)
    try:
        await client.ping()
        print(f"Redis PING ok: {url}")
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
