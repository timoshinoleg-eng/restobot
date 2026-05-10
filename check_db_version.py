import asyncpg, os, asyncio, glob

async def check():
    db_url = os.environ.get("DATABASE_URL", "").replace("postgresql+asyncpg", "postgresql")
    conn = await asyncpg.connect(db_url)
    result = await conn.fetch("SELECT version_num FROM alembic_version")
    await conn.close()
    if result:
        print(f"DB alembic version: {result[0]['version_num']}")
    else:
        print("No alembic_version found")

    migration_files = sorted(glob.glob("/app/migrations/versions/*.py"))
    if migration_files:
        latest = migration_files[-1]
        rev = os.path.basename(latest).split("_")[-1].replace(".py", "")
        print(f"Latest local migration: {rev}")
        if result and result[0]["version_num"] == rev:
            print("Migrations: UP TO DATE")
        else:
            print("Migrations: MISMATCH or PENDING")

asyncio.run(check())
