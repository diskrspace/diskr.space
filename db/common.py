# -*- coding: utf-8 -*-
"""
    comm functions

    :copyright: 20160110 by raptor.zh@gmail.com.
"""
from os.path import dirname, abspath, exists, islink, isfile, getsize, join as joinpath
import datetime
import decimal
import hashlib
import json
import os


unit_map = {"K": 1024, "M": 1048576, "G": 1073741824, "T": 1099511627776}


MINSIZE = 4096
BUFSIZE = MINSIZE * 16


class JsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            if obj.utcoffset() is not None:
                obj = obj - obj.utcoffset()
            encoded_object = obj.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(obj, datetime.date):
            encoded_object = obj.strftime('%Y-%m-%d')
        elif isinstance(obj, datetime.time):
            encoded_object = obj.strftime('%H:%M:%S')
        elif isinstance(obj, decimal.Decimal):
            encoded_object = float(obj)
        else:
            encoded_object = json.JSONEncoder.default(self, obj)
        return encoded_object


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
    for unit in ['T', 'G', 'M', 'K']:
        if s >= unit_map[unit]:
            return "%0.2f%s(%s)" % (s / unit_map[unit], unit, s)
    return s


def get_fulldir(name=__file__):
    return dirname(abspath(name))


def get_fullname(root, *args):
    return joinpath(root, joinpath(*args)) if len(args) > 0 else root


def get_filesize(fn):
    if not exists(fn):
        return -2
    if islink(fn):
        return -1
    if isfile(fn):
        return getsize(fn)
    else:
        return 0


def get_filemd5(fn, qhs=0):
    try:
        size = get_filesize(fn)
        if size < 0:
            return "-"
        m = hashlib.md5()
        m.update(size.to_bytes(max(1, (size.bit_length() + 7) // 8), "big"))
        with open(fn, "rb") as f:
            if not qhs or size <= qhs:
                while True:
                    block = f.read(BUFSIZE)
                    if not block:
                        break
                    m.update(block)
            else:
                block_count = max(1, (qhs + BUFSIZE - 1) // BUFSIZE)
                for index in range(block_count):
                    position = int(index * max(size - BUFSIZE, 0) / max(block_count - 1, 1))
                    f.seek(position)
                    m.update(f.read(BUFSIZE))
        return m.hexdigest()
    except OSError:
        return "-"


def check_pid(pid):
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
    except OSError:
        return False
    return True
