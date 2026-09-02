"""Shared isolated database setup for the backend test suite."""
import os
import sys
import tempfile
from pathlib import Path

# Set this before importing application modules: db.model creates the engine
# and schema at import time. Every test run gets a disposable SQLite database.
_test_dir = tempfile.mkdtemp(prefix="diskrspace-tests-")
os.environ["DISKRSPACE_DB_URI"] = os.environ.get(
    "DISKRSPACE_TEST_DB_URI",
    "sqlite:///" + os.path.join(_test_dir, "index.db"),
)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from db.model import FileInfo, FileTag, SysInfo, create_session


@pytest.fixture(autouse=True)
def clean_database():
    with create_session.begin() as session:
        session.query(FileTag).delete(synchronize_session=False)
        session.query(FileInfo).delete(synchronize_session=False)
        session.query(SysInfo).filter(SysInfo.name.in_(["work_dir", "last_scan", "pid"])).delete(
            synchronize_session=False
        )
    yield
