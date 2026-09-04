from pathlib import Path

import pytest
from fastapi import HTTPException

from db.model import FileInfo, SysInfo, create_session
from db.scan import scanner
from web.index import _remove_file_or_dir, get_duplicates, get_status, search_files


def scan_fixture(root: Path):
    root.mkdir()
    (root / "photo-a.jpg").write_bytes(b"duplicate-content")
    (root / "photo-b.jpg").write_bytes(b"duplicate-content")
    (root / "notes.txt").write_bytes(b"unique-content")
    with create_session.begin() as session:
        session.add(SysInfo(name="work_dir", value=str(root)))
    scanner(str(root))


def test_scan_tags_search_and_duplicates(tmp_path):
    root = tmp_path / "library"
    scan_fixture(root)
    with create_session() as session:
        status = get_status(session)
        assert status["files"] == 3
        assert status["work_dir"] == str(root)
        search = search_files("jpg", 0, session)
        assert {item["name"] for item in search["items"]} == {"photo-a.jpg", "photo-b.jpg"}
        by_name = search_files("photo-a", 0, session)
        assert {item["name"] for item in by_name["items"]} == {"photo-a.jpg"}
        assert len(get_duplicates(0, False, session)["items"]) == 2


def test_delete_removes_disk_file_and_database_record(tmp_path):
    root = tmp_path / "library"
    scan_fixture(root)
    with create_session() as session:
        item = get_duplicates(0, False, session)["items"][0]
        target = root / item["name"]
        assert _remove_file_or_dir(session, item["id"]) == item["name"]
        session.commit()
        assert not target.exists()
        assert session.query(FileInfo).filter(FileInfo.id == item["id"]).count() == 0
        assert get_duplicates(0, False, session)["items"] == []


def test_delete_reports_unavailable_path_without_mutating_database(tmp_path):
    root = tmp_path / "library"
    scan_fixture(root)
    with create_session.begin() as session:
        session.query(SysInfo).filter(SysInfo.name == "work_dir").update(
            {SysInfo.value: str(tmp_path / "not-mounted")}
        )
    with create_session() as session:
        item = get_duplicates(0, False, session)["items"][0]
        with pytest.raises(HTTPException) as error:
            _remove_file_or_dir(session, item["id"])
        assert error.value.status_code == 409
        assert session.query(FileInfo).filter(FileInfo.id == item["id"]).count() == 1
