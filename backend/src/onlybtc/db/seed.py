from __future__ import annotations

from onlybtc.db.repositories import SeedRepository
from onlybtc.db.session import Database, database


def seed_demo_data(db: Database = database) -> dict:
    db.init_schema()
    with db.session() as session:
        return SeedRepository(session).seed_demo()
