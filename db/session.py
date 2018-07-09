# -*- coding: utf-8 -*-
"""
    Database session
    ~~~~~~~~~~~~~~~~
    for sqlalchemy

    :copyright: 20180429 by raptor.zh@gmail.com.
"""
from traceback import format_tb
import logging

from sqlalchemy.orm import sessionmaker

from db.model import engine


logger = logging.getLogger(__name__)


class SQLResult(object):
    def __init__(self, orm, sql, exc_params=None, **kwargs):
        exc_params = exc_params if isinstance(exc_params, dict) else {}
        self.result = orm.execute(sql, params=kwargs, **exc_params)
        self.rowcount = self.result.rowcount
        self.lastrowid = self.result.lastrowid

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.result.close()
        if exc_type is not None:
            logger.error(format_tb(exc_tb)[0])

    def close(self):
        self.result.close()

    def all(self):
        return [dict(zip(i.keys(), i.values())) for i in self.result]

    def first(self):
        try:
            rec = self.result.__iter__().__next__()
            return dict(zip(rec.keys(), rec.values()))
        except StopIteration:
            return None

    def scalar(self):
        rec = self.first()
        return rec.values()[0]

    def scalars(self):
        return [i.values()[0] for i in self.result]


class DBSession(object):
    def __init__(self, maker=None, auto_commit=False):
        if maker is None:
            maker = sessionmaker(bind=engine, autocommit=auto_commit)
        self.maker = maker
        self.auto_commit = auto_commit

    def __enter__(self):
        self.orm = self.maker()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.auto_commit:
            self.orm.close()
            return
        if exc_type is None:
            try:
                self.orm.commit()
            except Exception as e:
                self.orm.rollback()
                logger.error("DB Error: %s" % str(e))
            finally:
                self.orm.close()
        else:
            self.orm.rollback()
            self.orm.close()
            logger.error("DBError: \r\n%s" % format_tb(exc_tb)[0])
