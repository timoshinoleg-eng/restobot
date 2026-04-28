"""Bootstrap a completely fresh local database for the MVP."""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from backend.bootstrap.shared_seed import seed_shared_data
from shared.database import AsyncSessionLocal, close_raw_pool, init_database
from shared.models import Plan


async def main() -> None:
    await init_database()
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Plan).order_by(Plan.id))
        plans = result.scalars().all()
        if not plans:
            await session.begin()
            await seed_shared_data(session)
            await session.commit()
            result = await session.execute(select(Plan).order_by(Plan.id))
            plans = result.scalars().all()

    print("Local bootstrap completed.")
    print(f"Seeded plans: {', '.join(plan.name for plan in plans)}")
    await close_raw_pool()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
