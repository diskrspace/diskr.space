import pytest
from fastapi import HTTPException

from db.model import SysInfo, create_session
from web.index import (
    SettingsUpdate,
    get_scan_progress,
    get_settings,
    health,
    post_scan,
    put_settings,
)


def test_health_and_default_settings():
    assert health()["status"] == "ok"
    with create_session() as session:
        assert get_settings(session) == {
            "work_dir": "", "quick_hash_size": "0", "scan_interval": 86400
        }


def test_settings_are_persisted_and_work_dir_requires_confirmation():
    with create_session() as session:
        assert put_settings(SettingsUpdate(work_dir="/tmp/library"), session) == {"confirm": "required"}
        assert put_settings(SettingsUpdate(work_dir="/tmp/library", quick_hash_size="4M",
                                           scan_interval=3600, confirm=True), session) == {"status": "ok"}
        session.commit()
        values = {row.name: row.value for row in session.query(SysInfo).all()}
    assert values["work_dir"] == "/tmp/library"
    assert values["quick_hash_size"] == "4M"
    assert values["scan_interval"] == "3600"


def test_empty_work_dir_is_rejected():
    with create_session() as session:
        with pytest.raises(HTTPException) as error:
            put_settings(SettingsUpdate(work_dir=""), session)
        assert error.value.status_code == 422


def test_scan_requires_work_dir():
    with create_session() as session:
        with pytest.raises(HTTPException) as error:
            post_scan(session)
        assert error.value.status_code == 400


def test_scan_progress_has_idle_default():
    with create_session() as session:
        progress = get_scan_progress(session)
    assert progress["progress"] == "100"
    assert progress["cur_path"] == ""
