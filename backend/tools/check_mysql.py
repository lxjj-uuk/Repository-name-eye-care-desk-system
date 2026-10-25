from sqlalchemy import text

from app.config import settings
from app.db import engine


def main():
    print("database:", settings.database_url.split("@")[-1])
    with engine.connect() as connection:
        print("mysql:", connection.execute(text("SELECT VERSION()")).scalar())
        print(
            "devices:",
            connection.execute(text("SELECT COUNT(*) FROM devices")).scalar(),
        )
        print(
            "config:",
            connection.execute(
                text(
                    "SELECT lux_min, lux_max, sit_warn_min, sit_strong_min "
                    "FROM device_configs WHERE device_id = 'hi3861_001'"
                )
            ).fetchone(),
        )


if __name__ == "__main__":
    main()
