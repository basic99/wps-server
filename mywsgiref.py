"""
#!/bin/bash
#
#wsgiref    This is the init script for starting up the wsgiref Pyton app server
#               server.
#
# chkconfig: 2345 20 95
# description: wsgi web app


export PATH=/usr/local/pythonenvs/ncthreatsenv/bin:$PATH


case "$1" in
	start)
		echo -n "Starting wsgiref services: "
		python /var/www/wsgi/wps-server/mywsgiref.py & > /var/log/httpd/wsgiref_log  2>&1
	;;
	stop)
		echo -n "Shutting down wsgiref services: "
		pkill -f mywsgiref.py
		
	;;

	restart)
		echo -n "restarting wsgiref services "
		$0 stop
		$0 start

	;;

	*)
		echo "Usage:  {start|stop|restart}"
		exit 1
	;;
esac
"""


from wps import app
from wsgiref.simple_server import make_server

httpd = make_server('', 5000, app)
httpd.serve_forever()