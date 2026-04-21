# ai/main.py
"""AI service entry point."""

from shared.database import init_database


async def main() -> None:
    """Start AI service."""
    await init_database()
