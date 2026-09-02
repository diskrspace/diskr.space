# -*- coding: utf-8 -*-
"""Filesystem scanner with short, explicit database transactions."""
from datetime import datetime
from multiprocessing import Pipe, Process
import hashlib
import logging
import os

from db import api as data_api
from db.common import get_filemd5, get_filesize
from db.model import FileInfo, engine
from db.session import DBSession

logger = logging.getLogger(__name__)
BATCH_SIZE = 256
WRITE_CHUNK = 64


def _transaction(fn, *args, **kwargs):
    with DBSession() as db:
        return fn(db.orm, *args, **kwargs)


def set_progress(progress, cur_path, speed):
    _transaction(data_api.set_progress, {
        "progress": str(int(progress)) if progress is not None else None,
        "cur_path": cur_path,
        "speed": str(int(speed)) if speed is not None else None,
    })


def get_filetime(filename):
    try:
        return datetime.fromtimestamp(os.path.getmtime(filename))
    except OSError:
        return None


def make_fileinfo(fullname, root, linkpath=None):
    relname = os.path.relpath(fullname, root)
    if relname == ".":
        relname = ""
    if linkpath:
        relname = linkpath if relname == "" else os.path.join(linkpath, relname)
    dirname, basename = os.path.split(relname)
    if basename in (".", ""):
        raise ValueError("invalid path: %s" % fullname)
    name, ext = os.path.splitext(basename)
    tags = dirname.split(os.path.sep) + [name, ext, os.path.basename(root)]
    tags = {tag[1:] if tag.startswith(".") else tag for tag in tags}
    tags -= {"", "..", "."}
    realname = fullname
    if os.path.islink(fullname):
        realname = os.path.realpath(fullname)
        if realname.startswith(root + os.path.sep):
            return None
    return {
        "dirname": dirname, "name": basename, "size": get_filesize(realname),
        "ftime": get_filetime(realname), "tags": list(tags), "realname": realname,
    }


def get_elapsed(timer):
    return max((datetime.now() - timer).total_seconds(), 0.001)


class ScanBatch:
    def __init__(self, pid, force=False):
        self.pid = pid
        self.force = force
        self.batch = []
        self.timer = datetime.now()
        self.dirs = []
        self.subdirs = {}
        self.donedirs = []

    def init_dirs(self, root, current, dirs, linkpath=None):
        if not self.dirs and current == root:
            self.dirs = dirs
            return
        relative = os.path.relpath(current, root)
        parts = relative.split(os.path.sep)
        top = linkpath if linkpath and os.path.sep not in linkpath else parts[0]
        if len(parts) == 1 and top in self.dirs and top not in self.subdirs:
            self.subdirs[top] = dirs
        done = top if len(parts) == 1 else os.path.join(parts[0], parts[1])
        if done not in self.donedirs:
            self.donedirs.append(done)

    def get_progress(self):
        child_count = sum(len(value) for value in self.subdirs.values())
        return len(self.donedirs) * 75 / (len(self.dirs) + child_count + 1)

    def save_batch(self):
        if not self.batch:
            return 0
        pending, self.batch = self.batch, []
        return _transaction(data_api.save_batch, pending, self.pid, self.force)

    def add_file(self, fileinfo):
        self.batch.append(fileinfo)
        if len(self.batch) >= BATCH_SIZE:
            count = self.save_batch()
            set_progress(self.get_progress(), os.path.join(fileinfo["dirname"], fileinfo["name"]),
                         count / get_elapsed(self.timer))
            self.timer = datetime.now()


def scan_dir(pid, root, force=False, linkpath=None, batch=None):
    owner = batch is None
    batch = batch or ScanBatch(pid, force)
    try:
        for current, dirs, files in os.walk(root):
            batch.init_dirs(root, current, dirs, linkpath)
            if os.path.islink(current):
                return
            for name in files:
                fileinfo = make_fileinfo(os.path.join(current, name), root, linkpath)
                if fileinfo:
                    fileinfo["ftype"] = "F"
                    batch.add_file(fileinfo)
            for name in dirs:
                if not name:
                    continue
                fullname = os.path.join(current, name)
                fileinfo = make_fileinfo(fullname, root, linkpath)
                if fileinfo is None:
                    continue
                fileinfo["ftype"] = "D"
                batch.add_file(fileinfo)
                if not os.path.islink(fullname):
                    continue
                notexists = _transaction(data_api.get_notexists, fileinfo)
                if root.startswith(fileinfo["realname"]):
                    continue
                if force or notexists:
                    scan_dir(pid, fileinfo["realname"], force,
                             os.path.join(fileinfo["dirname"], fileinfo["name"]), batch)
    finally:
        if owner:
            batch.save_batch()


def generate_checksums(pid, root):
    """Read files with no open DB transaction, then commit small chunks."""
    candidates, quickhash = _transaction(data_api.get_checksum_candidates, pid)
    total, results, timer = len(candidates), [], datetime.now()
    for index, item in enumerate(candidates, 1):
        fullname = os.path.realpath(os.path.join(root, item["dirname"], item["name"]))
        results.append((item["id"], item["size"], get_filemd5(fullname, quickhash)))
        if len(results) >= WRITE_CHUNK:
            _transaction(data_api.apply_checksums, results, quickhash)
            results = []
        if index % WRITE_CHUNK == 0 or index == total:
            set_progress(75 + index * 15 / max(total, 1), item["name"], index / get_elapsed(timer))
    if results:
        _transaction(data_api.apply_checksums, results, quickhash)
    return total


def clean_stale_records():
    stale_ids = _transaction(data_api.get_stale_ids)
    for offset in range(0, len(stale_ids), WRITE_CHUNK):
        _transaction(data_api.delete_stale, stale_ids[offset:offset + WRITE_CHUNK])


def _apply_directory_updates(orm, updates):
    for file_id, size, checksum in updates:
        orm.query(FileInfo).filter(FileInfo.id == file_id).update(
            {FileInfo.size: size, FileInfo.checksum: checksum, FileInfo.quickhash: 0},
            synchronize_session=False)


def update_directory_info():
    """Calculate directory totals from a snapshot and update in short chunks."""
    with DBSession() as db:
        rows = [{"id": r.id, "ftype": r.ftype, "dirname": r.dirname, "name": r.name,
                 "size": r.size, "checksum": r.checksum} for r in db.orm.query(FileInfo).all()]
    children = {}
    for row in rows:
        children.setdefault(row["dirname"], []).append(row)
    directories = sorted((row for row in rows if row["ftype"] == "D"),
                         key=lambda row: os.path.join(row["dirname"], row["name"]).count(os.path.sep),
                         reverse=True)
    updates = []
    for directory in directories:
        path = os.path.join(directory["dirname"], directory["name"])
        size, digest, valid = 0, hashlib.md5(), True
        for child in children.get(path, []):
            size += child["size"]
            if child["size"] > 0:
                if child["checksum"]:
                    digest.update(child["checksum"].encode("ascii"))
                else:
                    valid = False
        directory["size"] = size
        directory["checksum"] = digest.hexdigest() if valid and size > 0 else None
        updates.append((directory["id"], size, directory["checksum"]))
        if len(updates) >= WRITE_CHUNK:
            _transaction(_apply_directory_updates, updates)
            updates = []
    if updates:
        _transaction(_apply_directory_updates, updates)
    return sum(row["size"] for row in children.get("", []))


def scanner(root, force=None, reserved=False):
    engine.dispose(close=False)
    pid, speed, timer = os.getpid(), 0, datetime.now()
    registered = reserved
    succeeded = False
    try:
        if not registered:
            force = _transaction(data_api.set_pid, pid)
            registered = True
        _transaction(data_api.clear_tags)
        set_progress(0, "", 0)
        logger.info("Start scan: %s", root)
        scan_dir(pid, root, force)
        generate_checksums(pid, root)
        count = _transaction(data_api.get_scanned_count)
        speed = int(count / get_elapsed(timer))
        if force:
            clean_stale_records()
        set_progress(90, "", speed)
        update_directory_info()
        succeeded = True
    except Exception:
        logger.exception("Scanner failed")
        if registered:
            set_progress(100, "扫描失败，请查看服务端日志", 0)
        raise
    finally:
        if registered:
            _transaction(data_api.clean_scanner, pid)
            if succeeded:
                _transaction(data_api.update_last_scan, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                set_progress(100, "", speed)


def _run_reserved_scanner(root, receiver):
    try:
        force = receiver.recv()
    finally:
        receiver.close()
    scanner(root, force=force, reserved=True)


def spawn_scanner(root):
    receiver, sender = Pipe(duplex=False)
    process = Process(target=_run_reserved_scanner,
                      args=(os.path.expanduser(root), receiver), daemon=True)
    process.start()
    receiver.close()
    try:
        # Reserve the scanner row and commit before allowing the child to touch
        # the filesystem. This closes the double-click/multi-worker race.
        force = _transaction(data_api.set_pid, process.pid)
        sender.send(force)
    except Exception:
        process.terminate()
        process.join(timeout=2)
        raise
    finally:
        sender.close()
    logger.info("Scanner %s started", process.pid)
    return "Start scanning..."
