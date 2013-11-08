#!/usr/local/pythonenvs/ncthreatsenv/bin/python

"""
Create virtualenv with needed packages and python version.
Use Supervisor (http://supervisord.org/) to run server.
Configure proxy on web server to forward /wps to server.

"""


from wps import app
from wsgiref.simple_server import make_server

httpd = make_server('', 5000, app)
httpd.serve_forever()