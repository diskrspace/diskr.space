# -*- coding: utf-8 -*-
"""Environment and database-backed application settings."""
import os
from os.path import dirname, abspath, join as pathjoin

from dotenv import load_dotenv


PROJECT_ROOT = dirname(dirname(abspath(__file__)))
load_dotenv(pathjoin(PROJECT_ROOT, ".env"), override=False)
load_dotenv(override=False)


class Config:
    """Only connection/listener settings come from environment variables.

    User-facing scanner settings live in the ``sysinfo`` table.  Defaults are
    kept here so a new database works without a config file or migration.
    ``work_dir`` intentionally has no default and must be configured by the
    user before starting a scan.
    """

    DEFAULTS = {
        "quick_hash_size": "0",
        "scan_interval": "86400",
        "progress": "100",
        "cur_path": "",
        "speed": "0",
    }

    @staticmethod
    def load(name="web", reload=False):
        # Keep the old call signature for modules/extensions; business settings
        # are read from sysinfo by the data layer.
        return {
            "DB_URI": os.environ.get("DISKRSPACE_DB_URI", "sqlite:///~/.diskr.space.dat"),
            "WEB_IP": os.environ.get("DISKRSPACE_WEB_IP", "127.0.0.1"),
            "WEB_PORT": int(os.environ.get("DISKRSPACE_WEB_PORT", "1888")),
            "CORS_ORIGINS": ["http://localhost:5173", "http://127.0.0.1:5173"],
            "DEBUG": False,
        }
