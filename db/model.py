# -*- coding: utf-8 -*-
"""
    data model
    ~~~~~~~~~~~~~~~~
    for sqlalchemy

    :copyright: 20150720 by raptor.zh@gmail.com.
"""
import os
import logging

from sqlalchemy import create_engine, event, \
    ForeignKey, Column, Index, Integer, BigInteger, String, Unicode, UnicodeText, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

from db import Config


logger = logging.getLogger(__name__)

config = Config.load("web")

sqlite = "sqlite:///"
if config['DB_URI'].startswith(f"{sqlite}~"):
    config['DB_URI'] = f"{sqlite}{os.path.expanduser(config['DB_URI'][len(sqlite):])}"

engine_options = {"pool_pre_ping": True, "future": True}
if config['DB_URI'].startswith("sqlite:"):
    engine_options["connect_args"] = {"check_same_thread": False}
engine = create_engine(config['DB_URI'], **engine_options)

if config['DB_URI'].startswith("sqlite:"):
    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, _record):
        # SQLite remains single-writer, but WAL lets the UI read the previous
        # committed snapshot while a scan batch is writing.
        cursor = connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

Base = declarative_base()


class FileInfo(Base):
    __tablename__ = "fileinfo"

    id = Column(Integer, primary_key=True)
    ftype = Column(String(1), default='F')  # D is directory, F is file, L is link
    name = Column(Unicode(255), nullable=False)  # only basename without path
    size = Column(BigInteger, nullable=False)  # -1 is symbol link
    ftime = Column(DateTime)
    checksum = Column(String(33))  # only for same size file
    quickhash = Column(Integer, default=0)
    dirname = Column(UnicodeText(), nullable=False)
    pid = Column(Integer)  # scanner proc id, clean after scan done


Index("idx_fullname", FileInfo.dirname, FileInfo.name)
Index("idx_checksum", FileInfo.checksum, FileInfo.quickhash)


class FileTag(Base):
    __tablename__ = "filetag"

    file_id = Column(Integer, ForeignKey("fileinfo.id"), primary_key=True)
    # _file = relationship(FileInfo, backref="_tags")
    tag = Column(Unicode(64), nullable=False, primary_key=True)


class SysInfo(Base):
    __tablename__ = "sysinfo"

    name = Column(String(50), primary_key=True)  # e.g. progress, cur_path, speed, last_scan
    value = Column(String(1000))


metadata = Base.metadata

create_session = sessionmaker(bind=engine, expire_on_commit=False, future=True)

metadata.create_all(engine)


def initialize_settings():
    with create_session.begin() as session:
        for name, value in Config.DEFAULTS.items():
            if session.get(SysInfo, name) is None:
                session.add(SysInfo(name=name, value=value))


initialize_settings()
