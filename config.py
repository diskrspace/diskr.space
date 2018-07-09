# -*- coding: utf-8 -*-
"""
    config

    :copyright: 20150720 by raptor.zh@gmail.com.
"""
from os.path import expanduser

from db.common import load_config

config_name = expanduser("~/.diskr.space.json")


def reload_config():
    config = load_config(config_name, {
        "dbpath":"~/.diskr.space.dat",
        "work_dir":"~/",
        "quick_hash_size": "0", # 0 - no quick hash or quick hash file size
        "scan_interval": 86400,
        "web_path": "diskr.space",
        "web_ip": "127.0.0.1",
        "web_port": 1888,
        # "auth_user": "admin",
        # "auth_pass": "admin",
        "debug": False
    })
    return config
