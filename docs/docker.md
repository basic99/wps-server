# How to use the code with Docker


# get the siteprivate.py file to the . dir

Build:

docker build -t wps-server .


Run:

docker run -it -v /usr/local/pythonenvs/ncthreatsenv/:/usr/local/pythonenvs/ncthreatsenv/ -p5001:5000 --rm wps-server /bin/bash

Run inside

cd /usr/local/pythonenvs/ncthreatsenv/bin
source activate
cd /var/www/wsgi/wps-server
python wps.py

