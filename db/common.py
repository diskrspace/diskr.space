# -*- coding: utf-8 -*-
"""
    comm functions

    :copyright: 20160110 by raptor.zh@gmail.com.
"""
from os.path import dirname, abspath, join as joinpath
import json


unit_map = {"K": 1024, "M": 1048576, "G": 1073741824}


def expand_size(s):
    s = s.strip().upper()
    try:
        num = float(s[:-1]) if s[-1] in unit_map.keys() else float(s)
        unit = unit_map.get(s[-1], 1)
        return int(num*unit)
    except ValueError:
        return 0


def format_size(s):
    if not s:
        return 0
    for unit in ['G', 'M', 'K']:
        if s >= unit_map[unit]:
            return "%0.2f%s(%s)" % (s / unit_map[unit], unit, s)
    return s


def get_fulldir(name=__file__):
    return dirname(abspath(name))


def get_fullname(root, *args):
    return joinpath(root, joinpath(*args)) if len(args) > 0 else root


def load_config(config_file, config_default):
    try:
        with open(config_file, "r") as f:
            config = json.loads(f.read())
        config_default.update(config)
        config = config_default
    except IOError:
        config = config_default
    return config


def save_config(config_file, config):
    with open(config_file, "w") as f:
        f.seek(0)
        f.truncate(0)
        f.write(json.dumps(config))