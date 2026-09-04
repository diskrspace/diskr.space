# -*- coding: utf-8 -*-
"""
    Scanner API provider
    ~~~~~~~~~~~~~~~~
    for sqlalchemy

    :copyright: 20220408 by raptor.zh@gmail.com.
"""
from datetime import datetime
import logging

from sqlalchemy import func, or_, and_

from db import Config
from db.common import expand_size, check_pid
from db.model import FileInfo, FileTag, SysInfo
from db.session import SQLResult
from db.tag import add_tags, update_tags


logger = logging.getLogger(__name__)

def _setting(orm, name):
    row = orm.query(SysInfo.value).filter(SysInfo.name == name).first()
    return row.value if row else Config.DEFAULTS[name]


def reset_scanner(orm):
    r = orm.query(SysInfo).filter(SysInfo.name=="pid").first()
    if r and check_pid(r.value):
        return "Scanner {} working, please wait...".format(r.value)
    pids = orm.query(FileInfo.pid).filter(FileInfo.pid != None).distinct()
    logger.info(str(pids))
    for p in pids:
        if check_pid(p.pid):
            return "Scanner {} working, please wait...".format(p.pid)
        else:
            sql = """UPDATE fileinfo SET pid=null WHERE pid = :pid"""
            with SQLResult(orm, sql, pid=p.pid) as res:
                if res.rowcount <= 0:
                    logger.error("Reset scanner {} fail!".format(p.pid))


def get_file(orm, id):
    return orm.query(FileInfo).filter(FileInfo.id==id).first()


def get_checksum_candidates(orm, pid):
    """Return hash work without keeping a transaction open during file IO."""
    quickhash = expand_size(_setting(orm, "quick_hash_size"))
    sq = orm.query(FileInfo.size).filter(FileInfo.ftype=='F', FileInfo.size>0).group_by(
        FileInfo.size).having(func.count(FileInfo.size) > 1).subquery()
    qry = orm.query(FileInfo).join(sq, FileInfo.size == sq.c.size).filter(FileInfo.pid == pid).filter(
        or_(FileInfo.checksum==None, and_(FileInfo.quickhash!=0, FileInfo.quickhash!=quickhash)))
    return [{"id": r.id, "dirname": r.dirname, "name": r.name, "size": r.size}
            for r in qry.all()], quickhash


def apply_checksums(orm, results, quickhash):
    for file_id, size, checksum in results:
        r = get_file(orm, file_id)
        if r is None:
            continue
        if checksum == '-':
            orm.delete(r)
        else:
            r.checksum = checksum
            r.quickhash = quickhash if size > quickhash else 0


def add_file(orm, filerec, pid, ftype, dirname, name, size, ftime, tags, **kwargs):
    if not ftime:
        return None
    parsed_time = ftime if isinstance(ftime, datetime) else datetime.strptime(ftime, "%Y-%m-%d %H:%M:%S")
    if filerec:
        #logger.debug("file_id: %d" % filerec.id)
        filerec.ftype = ftype
        filerec.size = size
        filerec.ftime = parsed_time
        filerec.checksum = None
        filerec.quickhash = None
        filerec.pid = pid
        update_tags(orm, filerec.id, tags)
    else:
        filerec = FileInfo(ftype=ftype, name=name, dirname=dirname,
                           size=size, ftime=parsed_time, pid=pid)
        orm.add(filerec)
        orm.flush()
        orm.refresh(filerec)
        #logger.debug("new file_id: %d(%s%s)" % (filerec.id, dirname + "/" if dirname else "", name))
        add_tags(orm, filerec.id, tags)
    return filerec.id


def save_batch(orm, batch, pid, force):
    for fileinfo in batch:
        try:
            _ = str(fileinfo['name']).encode('utf-8')  # test encoding
            filerec = orm.query(FileInfo).filter(FileInfo.dirname == fileinfo['dirname'],
                                                    FileInfo.name == fileinfo['name']).first()
            if force or not filerec:
                add_file(orm, filerec, pid=pid, **fileinfo)
        except UnicodeEncodeError:
            logger.error("Unicode error: {dirname}/{name}".format(**fileinfo))
        except Exception as e:
            logger.error("Error : {dirname}/{name} {error}".format(error=str(e), **fileinfo), exc_info=True)
            raise
    # Hashing is deliberately performed after this transaction commits.  Doing
    # disk IO here used to hold PostgreSQL row locks for minutes.
    return len(batch)


def set_progress(orm, info):
    rs = orm.query(SysInfo).filter(SysInfo.name.in_(info.keys())).all()
    for item in rs:
        value = info.pop(item.name)
        if value is not None:
            item.value = value
    if info:
        for k, v in info.items():
            if v is not None:
                orm.add(SysInfo(name=k, value=v))


def get_notexists(orm, fileinfo):
    notexists = orm.query(FileInfo.id).filter(FileInfo.dirname == fileinfo['dirname'],
                                                 FileInfo.name == fileinfo['name']).first() is None
    return notexists


def get_stale_ids(orm):
    return [row.id for row in orm.query(FileInfo.id).filter(FileInfo.pid == None).all()]


def delete_stale(orm, ids):
    if not ids:
        return
    orm.query(FileTag).filter(FileTag.file_id.in_(ids)).delete(synchronize_session=False)
    orm.query(FileInfo).filter(FileInfo.id.in_(ids)).delete(synchronize_session=False)


def clear_tags(orm):
    sql = """DELETE FROM filetag WHERE file_id NOT IN (SELECT ID FROM fileinfo)"""
    with SQLResult(orm, sql) as res:
        if res.rowcount > 0:
            logger.info("Delete {} tags.".format(res.rowcount))


def get_scanned_count(orm):
    count = orm.query(FileInfo.id).filter(FileInfo.pid != None).count()
    return count


def set_pid(orm, pid):
    r = orm.query(SysInfo).filter(SysInfo.name == "pid").with_for_update().first()
    if r:
        if r.value and str(r.value) != str(pid) and check_pid(r.value):
            raise RuntimeError("Scanner %s is already running" % r.value)
        r.value = str(pid)
    else:
        orm.add(SysInfo(name="pid", value=str(pid)))
    r = orm.query(SysInfo).filter(SysInfo.name == 'last_scan').first()
    force = True
    if r:
        force = (datetime.now() - datetime.strptime(r.value, "%Y-%m-%d %H:%M:%S")
                 ).total_seconds() > int(_setting(orm, "scan_interval"))
    logger.warning("force: {}".format(force))
    return force


def clean_scanner(orm, pid):
    orm.query(FileInfo).filter(FileInfo.pid == pid).update(
        {FileInfo.pid: None}, synchronize_session=False)
    r = orm.query(SysInfo).filter(SysInfo.name == "pid", SysInfo.value == str(pid)).first()
    if r:
        r.value = None


def get_scanner_pid(orm):
    row = orm.query(SysInfo.value).filter(SysInfo.name == "pid").first()
    return row.value if row and row.value else None


def cancel_scanner(orm, pid):
    """Release records left by a scanner that was intentionally stopped."""
    orm.query(FileInfo).filter(FileInfo.pid == pid).update(
        {FileInfo.pid: None}, synchronize_session=False)
    r = orm.query(SysInfo).filter(SysInfo.name == "pid", SysInfo.value == str(pid)).first()
    if r:
        r.value = None
    set_progress(orm, {"progress": "100", "cur_path": "扫描已中断", "speed": "0"})


def update_last_scan(orm, last_scan):
    r = orm.query(SysInfo).filter(SysInfo.name == "last_scan").first()
    if r:
        r.value = last_scan
    else:
        orm.add(SysInfo(name="last_scan", value=last_scan))
