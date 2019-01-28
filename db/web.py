# -*- coding: utf-8 -*-
"""
    Web data provider
    ~~~~~~~~~~~~~~~~
    for sqlalchemy

    :copyright: 20180615 by raptor.zh@gmail.com.
"""
import os
import logging

from sqlalchemy import func, and_
from sqlalchemy.orm import aliased

from db.common import format_size
from db.model import FileInfo, FileTag, SysInfo
from db.session import SQLResult, DBSession
from db.tag import delete_tags


logger = logging.getLogger(__name__)


def get_sysinfo(key):
    with DBSession(auto_commit=True) as db:
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


def get_status(orm):
    sql = """SELECT COUNT(id) AS files, SUM(size) AS size
        FROM fileinfo WHERE ftype='F'
    """
    with SQLResult(orm, sql) as res:
        info = res.first()
    sql = """SELECT COUNT(id) AS dirs FROM fileinfo WHERE ftype='D'"""
    with SQLResult(orm, sql) as res:
        info['dirs'] = res.first()['dirs']
    r = orm.query(SysInfo).filter(SysInfo.name=="last_scan").first()
    if r:
        info['updated'] = r.value
    else:
        info['updated'] = ""
    return info


def get_progress():
    with DBSession(auto_commit=True) as db:
        orm = db.orm
        qry = orm.query(SysInfo).filter(SysInfo.name.in_(["progress", "cur_path", "speed"]))
        prog = {item.name: item.value for item in qry.all()}
        #info = get_status(db.orm)
    #prog['info'] = info
    return prog


def format_rec(r):
    return {
        "id": r.id,
        "parent": r.dirname,
        "name": os.path.join(r.dirname, r.name),
        "ftype": r.ftype,
        "fhash": "{}|{}".format(r.checksum, r.quickhash),
        "size": format_size(r.size),
        "ftime": r.ftime.strftime("%Y-%m-%d %H:%M:%S")
    }


def get_search(orm, tags, page=0, count=50):
    qry = orm.query(FileInfo)
    for t in tags:
        ft = aliased(FileTag)
        qry = qry.join((ft, FileInfo.id==ft.file_id)).filter(ft.tag==t)
    page = page if page > 0 else 0
    count = count if count > 0 and count < 100 else 100
    return [format_rec(r) for r in qry.order_by(FileInfo.dirname).all()[page * count:(page + 1) * count]]


def get_duplist(orm, since_size=0, count=50):
    since_size = since_size if since_size > 0 else 0
    sq = orm.query(FileInfo.checksum, FileInfo.quickhash).filter(FileInfo.checksum!=None,
                                                                 FileInfo.checksum!='-').group_by(
        FileInfo.checksum).having(func.count(FileInfo.checksum)>1).subquery()
    qry = orm.query(FileInfo).join(sq, and_(FileInfo.checksum==sq.c.checksum,
                                           FileInfo.quickhash==sq.c.quickhash)
                                  )
    if since_size > 0:
        qry = qry.filter(FileInfo.size<=since_size)
    qry = qry.order_by(FileInfo.size.desc())
    res = []
    dirs = []
    count = count if count > 0 and count < 100 else 100
    index = 0
    while True:
        if index > qry.count():
            break
        for r in qry.all()[index:index + count]:
            if r.ftype == 'D':
                d = os.path.join(r.dirname, r.name)
                if d not in dirs:
                    dirs.append(d)
            rec = format_rec(r)
            if rec['parent'] not in dirs:
                res.append(rec)
        if len(res) < count:
            index += count
        else:
            break
    return res



def remove_file_or_dir(orm, rec):
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


def remove_dup(orm, id):
    rec = orm.query(FileInfo).filter(FileInfo.id==id).first()
    if not rec or not rec.checksum:
        return None
    name = os.path.join(rec.dirname, rec.name)
    rs = orm.query(FileInfo).filter(FileInfo.dirname == name).all()
    for r in rs:
        remove_file_or_dir(orm, r)
    rs = orm.query(FileInfo).filter(FileInfo.dirname.like("{}{}%".format(name, os.path.sep))).all()
    for r in rs:
        remove_file_or_dir(orm, r)
    remove_file_or_dir(orm, rec)
    return name
