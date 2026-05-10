import json, urllib.request, os, glob

# 1. Get current DB alembic version
with open('/tmp/yc_token.txt') as f:
    token = f.read().strip()

# Use the direct container invoke to run a quick check via admin container
# Actually, let's just check the DB directly using the migration runner's secrets
# We can construct the DATABASE_URL from the .env.prod or use the Lockbox secret

# Read .env.prod to get DB connection info
env_path = '/opt/restobot/.env.prod'
env_vars = {}
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, val = line.strip().split('=', 1)
                env_vars[key] = val

db_url = env_vars.get('DATABASE_URL', '')
print(f"DB URL found: {bool(db_url)}")

if db_url:
    import asyncpg
    import asyncio
    
    async def check():
        try:
            conn = await asyncpg.connect(db_url)
            result = await conn.fetch("SELECT version_num FROM alembic_version")
            await conn.close()
            if result:
                print(f"Current DB version: {result[0]['version_num']}")
            else:
                print("No alembic_version table found")
        except Exception as e:
            print(f"DB check error: {e}")
    
    asyncio.run(check())

# 2. List local migrations
migration_files = sorted(glob.glob('/opt/restobot/migrations/versions/*.py'))
if migration_files:
    latest = migration_files[-1]
    # Extract revision from filename like "2024..._abc123.py"
    rev = os.path.basename(latest).split('_')[-1].replace('.py', '')
    print(f"Latest local migration: {rev}")
