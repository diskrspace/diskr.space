# -*- coding: utf-8 -*-
"""
    Storamen web app
    ~~~~~~~~~~~~~~~~
    powered by bottle.py

    :copyright: 20150720 by raptor.zh@gmail.com.
"""
import os
import shutil
import logging

from bottle import Bottle, static_file
from bottle.ext.sqlalchemy import Plugin as SAPlugin

from config import config_name, reload_config
from db import web, scan
from db.common import get_fullname, save_config, format_size
from db.model import engine, metadata
from web.bottle_plugins.auth import AuthPlugin
from web.bottle_plugins.params import ParamsPlugin

logger = logging.getLogger(__name__)
config = reload_config()

app = Bottle()
app.install(SAPlugin(engine, metadata, keyword='db'))
app.install(ParamsPlugin())
app.install(AuthPlugin(dbkeyword='db'))


@app.get("/")
def get_():
    return static_file('index.html', root=get_fullname("static"))


@app.get("/static/<filename:path>")
def get_static(filename):
    return static_file(filename, root=get_fullname("static"))


@app.get("/status")
def get_status(db):
    info = web.get_status(db)
    if info:
        info['work_dir'] = config['work_dir']
        info['size'] = format_size(info['size'])
        info['updated'] = info['updated'][:-7] if info['updated'] else None
    return info


@app.post("/scan")
def post_scan(db):
    msg = scan.reset_scanner(db)
    if msg is None:
        msg = scan.spawn_scanner(config['work_dir'])
    return {"message": msg}


@app.get("/scan/progress")
def get_scan_progress(db):
    msg = scan.reset_scanner(db)
    if msg is None:
        scan.set_progress(100, "", 0)
    return web.get_progress(db)


@app.get("/search")
def get_search(db, tags, page='0'):
    tags = [t.strip() for t in tags.replace(" ", ",").split(",") if t.strip() != ""]
    res = web.get_search(db, tags[:8], int(page))
    return {"searchfiles": res}


@app.get("/duplicated")
def get_duplicated(db, page='0'):
    res = web.get_duplist(db, int(page))
    return {"dupfiles": res}


@app.delete("/duplicated/<id:int>")
def delete_duplicated(db, id):
    name = web.remove_dup(db, id)
    if not name:
        return {"status": "invalid_id"}
    name = os.path.join(os.path.expanduser(config["work_dir"]), name)
    if not config["debug"]:
        logger.warning(name)
        shutil.rmtree(name, ignore_errors=True)
    return {"status": "ok"}


@app.get("/settings")
def get_settings():
    fields = ("work_dir", "quick_hash_size", "scan_interval")
    return {k: config[k] for k in fields}


@app.put("/settings")
def put_settings(**kwargs):
    fields = ("work_dir", "quick_hash_size", "scan_interval")
    for k in fields:
        config[k] = kwargs.get(k, config[k])
    save_config(config_name, config)
    return {}
