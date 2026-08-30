"""Application configuration loaded from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv


# Direct local entry points load the project-level .env before settings are read.
# Existing process variables keep priority.
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)


class Settings:
    wx_appid = os.getenv("WX_APPID", "")
    wx_secret = os.getenv("WX_SECRET", "")
    database_url = os.getenv("DATABASE_URL", "sqlite://data/db.sqlite3")
    admin_username = os.getenv("ADMIN_USERNAME", "")
    admin_password = os.getenv("ADMIN_PASSWORD", "")
    admin_session_secret = os.getenv("ADMIN_SESSION_SECRET", "")
    admin_session_hours = int(os.getenv("ADMIN_SESSION_HOURS", "12"))
    admin_cookie_secure = os.getenv("ADMIN_COOKIE_SECURE", "false").lower() in {"1", "true", "yes"}
    token_expire_hours = int(os.getenv("TOKEN_EXPIRE_HOURS", "2"))


settings = Settings()


def prepare_sqlite_directory() -> None:
    """Create the parent directory for a file-backed SQLite database."""
    prefix = "sqlite://"
    if settings.database_url.startswith(prefix) and settings.database_url != "sqlite://:memory:":
        database_path = Path(settings.database_url.removeprefix(prefix))
        database_path.parent.mkdir(parents=True, exist_ok=True)


class Miniprogram:
    appid = settings.wx_appid
    secret = settings.wx_secret


class Auth:
    token_expire_hour = settings.token_expire_hours
    token_length = 32
