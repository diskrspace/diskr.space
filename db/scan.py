# -*- coding: utf-8 -*-
"""
    Data provider
    ~~~~~~~~~~~~~~~~
    for sqlalchemy

    :copyright: 20180615 by raptor.zh@gmail.com.
"""
from datetime import datetime
from multiprocessing import Process
import hashlib
import os
import logging

from cProfile import Profile
from sqlalchemy import func, or_

from config import reload_config
from db.common import expand_size
from db.model import FileInfo, SysInfo
from db.session import DBSession, SQLResult
from db.tag import delete_tags, add_tags, update_tags


logger = logging.getLogger(__name__)
config = reload_config()

MINSIZE = 4096
BUFSIZE = MINSIZE * 16


def set_progress(progress, cur_path, speed):
    info = {
        "progress": str(int(progress)) if progress is not None else None,
        "cur_path": cur_path,
        "speed": str(int(speed)) if speed is not None else None,
    }
    with DBSession() as db:
        rs = db.orm.query(SysInfo).all()
        for item in rs:
            if item.name in info.keys():
                value = info.pop(item.name)
                if value is not None:
                    item.value = value
        if info:
            for k, v in info.items():
                if v is not None:
                    db.orm.add(SysInfo(name=k, value=v))


def check_pid(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def get_filesize(fn):
    if not os.path.exists(fn):
        return -2
    if os.path.islink(fn):
        return -1
    if os.path.isfile(fn):
        return os.path.getsize(fn)
    else:
        return 0


def get_filetime(fn):
    if os.path.exists(fn):
        ftime = os.path.getmtime(fn)
        return datetime.fromtimestamp(ftime)
    else:
        return None


def get_filemd5(fn):
    try:
        size = get_filesize(fn)
        qhs = expand_size(config['quick_hash_size'])
        block_count = int((qhs + BUFSIZE / 2) / BUFSIZE
                          if qhs else size / BUFSIZE)
        block_size = size * 1.0 / block_count if qhs \
            else BUFSIZE
        m = hashlib.md5()
        with open(fn, "rb") as f:
            for i in range(block_count):
                pos = int(i * block_size / MINSIZE) * MINSIZE
                f.seek(pos, 0)
                buf = f.read(BUFSIZE)
                m.update(buf)
            remaining = size - f.tell()
            if remaining > 0:
                if qhs and remaining > BUFSIZE:
                    f.seek(size - BUFSIZE, 0)
                    remaining = BUFSIZE
                buf = f.read(remaining)
                m.update(buf)
        return m.hexdigest()
    except:
        return "-"


def add_file(pid, ftype, dirname, name, size, ftime, tags, **kwargs):
    if not ftime:
        return None
    with DBSession() as db:
        orm = db.orm
        r = orm.query(FileInfo).filter(FileInfo.dirname == dirname,
                                       FileInfo.name == name).first()
        if r:
            r.ftype = ftype
            r.size = size
            r.ftime = ftime
            r.checksum = None
            r.quickhash = None
            r.pid = pid
            update_tags(orm, r.id, tags)
        else:
            r = FileInfo(ftype=ftype, name=name, dirname=dirname,
                         size=size, ftime=ftime, pid=pid)
            orm.add(r)
            orm.flush()
            orm.refresh(r)
            add_tags(orm, r.id, tags)
        return r.id


def clean_notexists():
    with DBSession() as db:
        qry = db.orm.query(FileInfo).filter(FileInfo.pid==None)
        for r in qry.all():
            fullname = os.path.join(r.dirname, r.name)
            size = get_filesize(fullname)
            if size >= 0:
                logger.warning("missing %s" % fullname)
                r.size = size
                r.checksum = None
            else:
                delete_tags(db.orm, r.id)
                db.orm.delete(r)


def gen_checksum():
    root = os.path.expanduser(config['work_dir'])
    quickhash = expand_size(config['quick_hash_size'])
    with DBSession() as db:
        sq = db.orm.query(FileInfo.size).filter(FileInfo.ftype=='F', FileInfo.size>0).group_by(
            FileInfo.size).having(func.count(FileInfo.size) > 1).subquery()
        rs = [{"id": r.id, "realname": os.path.realpath(os.path.join(root, r.dirname, r.name))
               } for r in db.orm.query(FileInfo).join(sq, FileInfo.size == sq.c.size).filter(FileInfo.pid!=None).filter(
            or_(FileInfo.checksum==None, FileInfo.quickhash!=quickhash)).all()]
    for r in rs:
        checksum = get_filemd5(r['realname'])
        with DBSession() as db:
            r = get_file(db.orm, r['id'])
            if checksum == '-':
                db.orm.delete(r)
            else:
                r.checksum = checksum
                r.quickhash = quickhash if r.size > quickhash else 0


def update_dirinfo():
    def gen_dirinfo(orm, dirname):
        rs = orm.query(FileInfo).filter(FileInfo.dirname==dirname).all()
        dirsize = 0
        m = hashlib.md5()
        for r in rs:
            if r.ftype == 'D':
                r.size, r.checksum = gen_dirinfo(orm, os.path.join(dirname, r.name))
                r.quickhash = 0
            if m and r.size > 0:
                if r.checksum:
                    m.update(bytes(r.checksum, "ascii"))
                else:
                    m = None
            dirsize += r.size
        return dirsize, m.hexdigest() if m and dirsize > 0 else None

    with DBSession(auto_commit=True) as db:
        gen_dirinfo(db.orm, "")


def clean_scanner(pid):
    with DBSession() as db:
        rs = db.orm.query(FileInfo).filter(FileInfo.pid == pid).all()
        for r in rs:
            r.pid = None


def make_fileinfo(fullname, root, linkpath=None):
    relname = os.path.relpath(fullname, root)
    if relname == '.':
        relname = ""
    if linkpath:
        relname = linkpath if relname == "" else os.path.join(linkpath, relname)
    dirname, basename = os.path.split(relname)
    if basename in ('.', ''):
        logger.error("fullname '%s'" % fullname)
        raise ValueError
    tags = dirname.split(os.path.sep)
    name, ext = os.path.splitext(basename)
    tags.append(name)
    tags.append(ext)
    tags.append(os.path.basename(root))
    tags = [t if not t or t[0] != "." else t[1:] for t in tags]
    tags = set(tags) - set(["", "..", "."])
    realname = fullname
    if os.path.islink(fullname):
        realname = os.path.realpath(fullname)
        if realname.startswith("{}{}".format(root, os.path.sep)):
            return None
    return {"dirname": dirname, "name": basename, "size": get_filesize(realname),
            "ftime": get_filetime(realname), "tags": list(tags), "realname": realname}


def get_elapsed(timer):
    elapsed = (datetime.now() - timer).seconds
    return elapsed + 1


class ScanProgress:
    def __init__(self):
        self.count = 0
        self.dirs = []
        self.dircnt = 0
        self.dircur = ""
        self.timer = datetime.now()

    def set_dirs_once(self, dirs):
        if not self.dirs:
            self.dirs = dirs
            self.dirs.append("")
            self.dircnt = len(self.dirs)

    def update_progress(self, root, rdir, linkpath=None):
        relname = os.path.relpath(rdir, root)
        if relname == '.':
            relname = ''
            cur = ''
        else:
            dirs = relname.split(os.path.sep)
            cur = dirs[1] if dirs[0]=='' else dirs[0]
        if cur != self.dircur:
            try:
                self.dirs.remove(self.dircur)
            except ValueError:
                pass
            self.dircur = cur
            if linkpath:
                relname = os.path.join(linkpath, relname)
            return relname
        return None

    def get_progress(self):
        return int((self.dircnt - len(self.dirs)) * 90 / self.dircnt)

    def step(self, count):
        self.count += count

    def get_speed(self):
        return self.count / ((datetime.now() - self.timer).seconds + 1)


def scan_dir(pid, root, force=False, linkpath=None):
    prog = ScanProgress()
    with DBSession(auto_commit=True) as db:
        for rdir, dirs, files in os.walk(root):
            prog.set_dirs_once(dirs)
            relname = prog.update_progress(root, rdir, linkpath)
            if relname is not None or prog.count % 100 == 0:
                gen_checksum()
                set_progress(prog.get_progress(), relname, prog.get_speed())
            if os.path.islink(rdir):
                logger.warning("link to: %s" % rdir)
                return
            for name in files:
                try:
                    fileinfo = make_fileinfo(os.path.join(rdir, name), root, linkpath)
                    if fileinfo:
                        f = db.orm.query(FileInfo.id).filter(FileInfo.dirname==fileinfo['dirname'],
                                                             FileInfo.name==fileinfo['name']).first()
                        if force or not f:
                            add_file(pid=pid, ftype='F', **fileinfo)
                except UnicodeEncodeError:
                    logger.error("dirname: %s, name: %s" % (rdir, name))
                except:
                    logger.error("dirname: %s, name: %s" % (rdir, name))
                    raise
            for name in dirs:
                if name == '':
                    continue
                try:
                    fullname = os.path.join(rdir, name)
                    fileinfo = make_fileinfo(fullname, root, linkpath)
                    if fileinfo:
                        f = db.orm.query(FileInfo.id).filter(FileInfo.dirname==fileinfo['dirname'],
                                                             FileInfo.name==fileinfo['name']).first()
                        if force or not f:
                            add_file(pid=pid, ftype='D', **fileinfo)
                            if os.path.islink(fullname):
                                count = scan_dir(pid, fileinfo['realname'], force,
                                                 os.path.join(fileinfo['dirname'], fileinfo['name']))
                                prog.step(count)
                except UnicodeEncodeError:
                    logger.error("dirname: %s, name: %s" % (rdir, name))
                except:
                    logger.error("dirname: %s, name: %s" % (rdir, name))
                    raise
            prog.step(1)
    gen_checksum()
    return prog.count


def get_file(orm, id):
    return orm.query(FileInfo).filter(FileInfo.id==id).first()


def scanner(root):
    speed = 0
    logger.info("Scanner started...")
    prof = Profile()
    prof.enable()
    try:
        pid = os.getpid()
        timer = datetime.now()
        with DBSession(auto_commit=True) as db:
            r = db.orm.query(SysInfo).filter(SysInfo.name=="pid").first()
            if r:
                r.value = str(pid)
            else:
                db.orm.add(SysInfo(name="pid", value=str(pid)))
            r = db.orm.query(SysInfo).filter(SysInfo.name=='last_scan').first()
            force = False
            if r:
                force = (datetime.now() - datetime.strptime(r.value, "%Y-%m-%d %H:%M:%S")
                         ).seconds > int(config['scan_interval'])
        set_progress(1, "", speed)
        scan_dir(pid, root, force)
        with DBSession(auto_commit=True) as db:
            count = db.orm.query(FileInfo.id).filter(FileInfo.pid!=None).count()
        speed = int(count / get_elapsed(timer))
        if force:
            clean_notexists()
        set_progress(90, "", speed)
        update_dirinfo()
        clean_scanner(pid)
    finally:
        dt = datetime.now().strftime("%Y-%d-%m %H:%M:%S")
        with DBSession(auto_commit=True) as db:
            r = db.orm.query(SysInfo).filter(SysInfo.name=="last_scan").first()
            if r:
                r.value = dt
            else:
                db.orm.add(SysInfo(name="last_scan", value=dt))
        set_progress(100, "", speed)
        logger.info("Scanner done")
        prof.disable()
        prof.dump_stats(os.path.expanduser("~/Downloads/prof.log"))


def reset_scanner(orm):
    r = orm.query(SysInfo).filter(SysInfo.name=="pid").first()
    if r and check_pid(int(r.value)):
        return "Scanner working, please wait..."
    pids = orm.query(FileInfo.pid).filter(FileInfo.pid != None).distinct()
    for p in pids:
        if check_pid(p.pid):
            return "Scanner working, please wait..."
        else:
            sql = """UPDATE fileinfo SET pid=null WHERE pid = :pid"""
            with SQLResult(orm, sql, pid=p.pid) as res:
                if res.rowcount <= 0:
                    logger.error("Reset scanner {} fail!".format(p.pid))
    return None


def spawn_scanner(root):
    set_progress(0, "", 0)
    p = Process(target=scanner, args=(os.path.expanduser(root),))
    p.start()
    return "Start scanning..."