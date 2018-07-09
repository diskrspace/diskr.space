# -*- coding: utf-8 -*-
"""
    data model
    ~~~~~~~~~~~~~~~~
    for sqlalchemy

    :copyright: 20150720 by raptor.zh@gmail.com.
"""
import os
import logging

from sqlalchemy import engine_from_config
from sqlalchemy import ForeignKey, Column, Integer, BigInteger, String, Unicode, UnicodeText, DateTime
# from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

from config import reload_config, expanduser


logger = logging.getLogger(__name__)

config = reload_config()
engine = engine_from_config({"sqlalchemy.url": "sqlite:///{}".format(expanduser(config['dbpath']))})

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


class FileTag(Base):
    __tablename__ = "filetag"

    file_id = Column(Integer, ForeignKey("fileinfo.id"), primary_key=True)
    # _file = relationship(FileInfo, backref="_tags")
    tag = Column(Unicode(64), nullable=False, primary_key=True)


class SysInfo(Base):
    __tablename__ = "sysinfo"

    name = Column(String(50), primary_key=True)  # e.g. progress, cur_path, speed, last_scan
    value = Column(String(50))


metadata = Base.metadata


if not os.path.exists(expanduser(config['dbpath'])):
    metadata.create_all(engine)
