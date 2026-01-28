import os
from typing import List

from ..common.config import MIGRATION_DOWNGRADES, MIGRATION_UPGRADES
from ..schemas.database import Migration


def get_migrations(direction: str) -> List[Migration]:
    migrations = []
    migration_path = MIGRATION_UPGRADES if direction == "up" else MIGRATION_DOWNGRADES
    files = sorted(os.listdir(migration_path))
    for file in files:
        if file.endswith(".sql"):
            with open(os.path.join(migration_path, file), "r", encoding="utf-8") as f:
                sql = f.read()
            migrations.append(Migration(name=file, sql=sql))
    return migrations


def get_upgrade_migrations() -> List[Migration]:
    return get_migrations("up")


def get_downgrade_migrations() -> List[Migration]:
    return get_migrations("down")
