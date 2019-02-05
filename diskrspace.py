# -*- coding: utf-8 -*-
"""
    start web server
    ~~~~~~~~~~~~~~~~
    powered by bottle.py

    :copyright: 20150720 by raptor.zh@gmail.com.
"""
import os
import logging

from bottle import Bottle, run, static_file

from config import reload_config
from db.common import get_fullname
from web.index import app as index


logger = logging.getLogger(__name__)

config = reload_config()

application = Bottle()
application.mount("{web_path}".format(**config), index)



if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG if config['debug'] else logging.INFO)
    run(application, host=config["web_ip"], port=config["web_port"], debug=config['debug'])
