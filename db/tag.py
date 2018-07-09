# -*- coding: utf-8 -*-
"""
    Tag data provider
    ~~~~~~~~~~~~~~~~
    for sqlalchemy

    :copyright: 20180620 by raptor.zh@gmail.com.
"""
import logging

from db.model import FileTag


logger = logging.getLogger(__name__)


def delete_tags(orm, file_id):
    rs = orm.query(FileTag).filter(FileTag.file_id==file_id).all()
    return len([orm.delete(t) for t in rs]) > 0


def add_tags(orm, file_id, tags):
    return len([orm.add(FileTag(file_id=file_id, tag=t[:64])) for t in tags])==len(tags)


def update_tags(orm, file_id, tags):
    tags = set(tags)
    ts = orm.query(FileTag).filter(FileTag.file_id==file_id).all()
    for t in ts:
        if t.tag in tags:
            tags.remove(t.tag)
            continue
        orm.delete(t)
    [orm.add(FileTag(file_id=file_id, tag=t[:64])) for t in tags]
