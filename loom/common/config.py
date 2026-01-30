import os

MIGRATION_UPGRADES = os.path.join(os.path.dirname(__file__), "../", "migrations", "up")

MIGRATION_DOWNGRADES = os.path.join(
    os.path.dirname(__file__), "../", "migrations", "down"
)
DATA_ROOT = ".loom"
DATABASE = os.path.join(DATA_ROOT, "LOG")
