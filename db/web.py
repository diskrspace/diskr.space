# -*- coding: utf-8 -*-
"""
    Web data provider
    ~~~~~~~~~~~~~~~~
    for sqlalchemy

    :copyright: 20180615 by raptor.zh@gmail.com.
"""
import os
import logging

from sqlalchemy import func, and_, or_
from sqlalchemy.orm import aliased

from db.common import check_pid, format_size
from db.model import FileInfo, FileTag, SysInfo
from db import Config
from db.session import SQLResult, DBSession
from db.tag import delete_tags


logger = logging.getLogger(__name__)


def get_sysinfo(key):
    with DBSession() as db:
        res = db.orm.query(SysInfo.value).filter(SysInfo.name==key).first()
        return res.value if res else None


def set_sysinfo(key, value):
    with DBSession() as db:
        res = db.orm.query(SysInfo).filter(SysInfo.name==key).first()
        if res:
            res.value = value
        else:
            res = SysInfo(name=key, value=value)
            db.orm.add(res)
            db.orm.flush()
            # db.orm.refresh(res)


def get_setting(orm, key):
    """Read a database-backed setting, falling back to its built-in default."""
    row = orm.query(SysInfo.value).filter(SysInfo.name == key).first()
    return row.value if row else Config.DEFAULTS.get(key)


def set_setting(orm, key, value):
    row = orm.query(SysInfo).filter(SysInfo.name == key).first()
    if row:
        row.value = str(value)
    else:
        orm.add(SysInfo(name=key, value=str(value)))


def get_status(orm):
    scanner_pid = orm.query(SysInfo.value).filter(SysInfo.name == "pid").scalar()
    scanning = bool(scanner_pid and check_pid(scanner_pid))
    current_scan_filter = " AND pid IS NOT NULL" if scanning else ""
    sql = f"""SELECT COUNT(id) AS files, SUM(size) AS size
        FROM fileinfo WHERE ftype='F'{current_scan_filter}
    """
    with SQLResult(orm, sql) as res:
        info = res.first()
    sql = f"""SELECT COUNT(id) AS dirs FROM fileinfo WHERE ftype='D'{current_scan_filter}"""
    with SQLResult(orm, sql) as res:
        info['dirs'] = res.first()['dirs']
    r = orm.query(SysInfo).filter(SysInfo.name=="last_scan").first()
    if r and not r.value.startswith("1970-01-01"):
        info['updated'] = r.value
    else:
        info['updated'] = ""
    return info


def get_progress(orm=None):
    if orm is not None:
        qry = orm.query(SysInfo).filter(SysInfo.name.in_(["progress", "cur_path", "speed"]))
        return {item.name: item.value for item in qry.all()}
    with DBSession() as db:
        return get_progress(db.orm)


def format_rec(r):
    return {
        "id": r.id,
        "parent": r.dirname,
        "name": os.path.join(r.dirname, r.name),
        "ftype": r.ftype,
        "fhash": "{}|{}".format(r.checksum, r.quickhash),
        "size": format_size(r.size),
        "ftime": r.ftime.strftime("%Y-%m-%d %H:%M:%S") if r.ftime else None
    }


def _search_query(orm, tags):
    qry = orm.query(FileInfo)
    for t in tags:
        pattern = "%{}%".format(t)
        ft = aliased(FileTag)
        tag_match = orm.query(ft.file_id).filter(
            ft.file_id == FileInfo.id, ft.tag.ilike(pattern)
        ).exists()
        qry = qry.filter(or_(
            FileInfo.name.ilike(pattern),
            FileInfo.dirname.ilike(pattern),
            tag_match,
        ))
    return qry


def get_search_count(orm, tags):
    return _search_query(orm, tags).count()


def get_search(orm, tags, page=0, count=50):
    qry = _search_query(orm, tags)
    page = page if page > 0 else 0
    count = count if count > 0 and count < 100 else 100
    records = qry.order_by(FileInfo.dirname, FileInfo.name).offset(page * count).limit(count).all()
    return [format_rec(r) for r in records]


def get_duplist(orm, since_size=0, count=50, only_dirs=False, page=0):
    since_size = since_size if since_size > 0 else 0
    sq = orm.query(FileInfo.checksum, FileInfo.quickhash).filter(
        FileInfo.checksum!=None, FileInfo.checksum!='-').group_by(FileInfo.checksum, FileInfo.quickhash, FileInfo.size).having(
        func.count()>1).subquery()
    qry = orm.query(FileInfo).join(sq, and_(
        FileInfo.checksum==sq.c.checksum, FileInfo.quickhash==sq.c.quickhash))
    if since_size > 0:
        qry = qry.filter(FileInfo.size<=since_size)
    if only_dirs:
        qry = qry.filter(FileInfo.ftype=='D')
    # Keep duplicate groups together, ordering larger groups first; within a
    # group, show shorter paths first.
    qry = qry.order_by(
        FileInfo.size.desc(), FileInfo.checksum, FileInfo.quickhash,
        func.length(FileInfo.dirname) + func.length(FileInfo.name),
        FileInfo.dirname, FileInfo.name,
    )
    res = []
    dirs = []
    count = count if count > 0 and count <= 200 else 50
    offset = max(page, 0) * count
    rows = qry.offset(offset).limit(count).all()
    if len(rows) == count:
        last = rows[-1]
        next_row = qry.offset(offset + count).first()
        last_key = (last.checksum, last.quickhash, last.size)
        if next_row and (next_row.checksum, next_row.quickhash, next_row.size) == last_key:
            group_total = qry.filter(
                FileInfo.checksum == last.checksum,
                FileInfo.quickhash == last.quickhash,
                FileInfo.size == last.size,
            ).count()
            # Do not expose a partial small group at a page boundary. Large
            # groups are allowed to span pages so they remain usable.
            if group_total <= 10:
                rows = [r for r in rows if (r.checksum, r.quickhash, r.size) != last_key]
    for r in rows:
        if r.ftype == 'D':
            d = os.path.join(r.dirname, r.name)
            if only_dirs:
                # If an ancestor directory is already represented, its
                # descendants add no useful information and are omitted.
                if any(d == parent or d.startswith(parent + os.path.sep) for parent in dirs):
                    continue
                dirs[:] = [parent for parent in dirs if not parent.startswith(d + os.path.sep)]
                res[:] = [item for item in res if not item['name'].startswith(d + os.path.sep)]
            if d not in dirs:
                dirs.append(d)
        rec = format_rec(r)
        if rec['parent'] not in dirs:
            res.append(rec)
    return res


def get_duplist_count(orm, since_size=0, only_dirs=False):
    since_size = since_size if since_size > 0 else 0
    sq = orm.query(FileInfo.checksum, FileInfo.quickhash).filter(
        FileInfo.checksum != None, FileInfo.checksum != '-').group_by(
            FileInfo.checksum, FileInfo.quickhash, FileInfo.size).having(func.count() > 1).subquery()
    qry = orm.query(FileInfo).join(sq, and_(
        FileInfo.checksum == sq.c.checksum, FileInfo.quickhash == sq.c.quickhash))
    if since_size > 0:
        qry = qry.filter(FileInfo.size <= since_size)
    if only_dirs:
        qry = qry.filter(FileInfo.ftype == 'D')
    return qry.count()



def remove_filedir_info(orm, rec):
    sql = """SELECT id FROM fileinfo WHERE id<>:id AND checksum=:checksum AND quickhash=:quickhash"""
    with SQLResult(orm, sql, id=rec.id, checksum=rec.checksum, quickhash=rec.quickhash) as res:
        data = res.all()
        if len(data) == 1:
            id = data[0]['id']
            sql = """UPDATE fileinfo SET checksum=null, quickhash=0 WHERE id=:id"""
            with SQLResult(orm, sql, id=id) as res:
                if res.rowcount != 1:
                    logger.error("Update {} checksum fail!".format(id))
    delete_tags(orm, rec.id)
    orm.delete(rec)


def remove_all_filedir(orm, rec):
    name = os.path.join(rec.dirname, rec.name)
    records = orm.query(FileInfo).filter(
        or_(FileInfo.id == rec.id,
            FileInfo.dirname == name,
            FileInfo.dirname.like("{}{}%".format(name, os.path.sep)))
    ).all()
    # A duplicate directory can be encountered more than once while cleaning
    # a hash group. Deduplicate IDs and skip rows already deleted in this
    # transaction to avoid SQLAlchemy confirm_deleted_rows warnings.
    for item in {item.id: item for item in records}.values():
        if orm.get(FileInfo, item.id) is not None:
            remove_filedir_info(orm, item)
    return name


def remove_dup(orm, id, root):
    rec = orm.query(FileInfo).filter(FileInfo.id==id).first()
    if not rec or not rec.checksum:
        return None
    # remove duplicated files or directories info if they are not exists
    rs = orm.query(FileInfo).filter(FileInfo.checksum==rec.checksum).filter(FileInfo.quickhash==rec.quickhash).filter(
        FileInfo.id!=id).all()
    for r in rs:
        fullname = os.path.join(root, r.dirname, r.name)
        if not os.path.exists(fullname):
            logger.debug("File %s not exists" % fullname)
            remove_all_filedir(orm, r)
    # check this file or directory is still duplicated
    orm.flush()
    orm.refresh(rec)
    logger.debug(str(rec))
    # rec = orm.query(FileInfo).filter(FileInfo.id==id).first()
    if not rec or not rec.checksum:
        logger.debug("File %s now not duplicated" % rec.name)
        return None
    name = remove_all_filedir(orm, rec)
    return name
