"""Project-level configuration and path helpers."""

from pathlib import Path
from typing import Union

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "03_data"
LOGS_DIR = PROJECT_ROOT / "04_logs"
DEFAULT_DB_PATH = DATA_DIR / "team_assistant.db"
DEFAULT_LOG_PATH = LOGS_DIR / "app.log"

DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)


PathLike = Union[str, Path]


def resolve_db_path(env_value: PathLike | None = None) -> PathLike:
    """Resolve DATABASE_URL to an absolute path."""
    if not env_value:
        return DEFAULT_DB_PATH

    if str(env_value) == ":memory:":
        return ":memory:"

    candidate = Path(env_value)
    return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate
