from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep

from db.model import FileInfo, create_session
from db.scan import generate_checksums, scanner
import db.scan as scan_module
from web.index import get_status, search_files


def test_queries_remain_available_during_hash_io(tmp_path, monkeypatch):
    root = tmp_path / "library"
    root.mkdir()
    (root / "a.bin").write_bytes(b"same data")
    (root / "b.bin").write_bytes(b"same data")
    scanner(str(root))
    with create_session.begin() as session:
        session.query(FileInfo).filter(FileInfo.name.in_(["a.bin", "b.bin"])).update(
            {FileInfo.checksum: None, FileInfo.pid: 12345}, synchronize_session=False
        )

    started = Event()
    original_hash = scan_module.get_filemd5

    def slow_hash(filename, quickhash):
        started.set()
        sleep(0.6)
        return original_hash(filename, quickhash)

    monkeypatch.setattr(scan_module, "get_filemd5", slow_hash)

    def query_status():
        with create_session() as session:
            return get_status(session)

    def query_search():
        with create_session() as session:
            return search_files("bin", 0, session)

    with ThreadPoolExecutor(max_workers=2) as pool:
        worker = pool.submit(generate_checksums, 12345, str(root))
        assert started.wait(2)
        begin = monotonic()
        assert query_status()["files"] == 2
        assert len(query_search()["items"]) == 2
        elapsed = monotonic() - begin
        worker.result()

    with create_session.begin() as session:
        session.query(FileInfo).filter(FileInfo.pid == 12345).update(
            {FileInfo.pid: None}, synchronize_session=False
        )
    assert elapsed < 0.5
