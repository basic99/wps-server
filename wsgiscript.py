"""
download mod_wsgi source 
./configure --with-python=/usr/local/ActivePython-2.7/bin/python
LoadModule wsgi_module modules/mod_wsgi.so

http://code.google.com/p/modwsgi/wiki/VirtualEnvironments
/usr/local/ActivePython-2.7/bin/python virtualenv.py --no-site-packages  ncthreatsenv
WSGIPythonHome /usr/local/pythonenvs/ncthreatsenv
some selinux issues with this!!!

http://code.google.com/p/modwsgi/wiki/QuickConfigurationGuide

<Directory /var/www/wsgi>
Order allow,deny
Allow from all
</Directory>

create directory /var/run/wsgi

WSGISocketPrefix /var/run/wsgi
WSGIDaemonProcess ncthreats.com
WSGIProcessGroup ncthreats.com
WSGIScriptAlias /wps /var/www/wsgi/wps-server/wsgiscript.py

"""


import sys
sys.path.append('/var/www/wsgi/wps-server')
from wps import app as application