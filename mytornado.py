#!/usr/local/pythonenvs/ncthreatsenv/bin/python

"""Alternative to wsgiref. Install tornado. """

from tornado.wsgi import WSGIContainer
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop
import logging
from wps import app

logging.getLogger('tornado.access').setLevel(logging.INFO)

http_server = HTTPServer(WSGIContainer(app))
http_server.listen(5000)
IOLoop.instance().start()