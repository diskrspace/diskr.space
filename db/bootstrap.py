"""Docker-only first-run defaults for the database-backed settings."""
import os

from db.model import create_session
from db.web import get_setting, set_setting


def main():
    # The image always mounts the user's library at /data. Do not apply this
    # default to local installs; work_dir remains required there.
    if not os.path.isdir("/data"):
        return
    with create_session.begin() as session:
        if not get_setting(session, "work_dir"):
            set_setting(session, "work_dir", "/data")


if __name__ == "__main__":
    main()
