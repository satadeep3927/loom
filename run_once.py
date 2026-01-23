from src.core.runner import run_once


async def main():
    await run_once()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
