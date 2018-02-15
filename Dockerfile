FROM ubuntu:trusty

RUN apt-get update -y
RUN apt-get install -y python python-psycopg2
RUN apt-get clean

# TODO: replace by direct install
VOLUME /usr/local/pythonenvs/ncthreatsenv

ADD . /var/www/wsgi/wps-server/

RUN mkdir /var/www/wsgi/wps-server/logs

EXPOSE 5000

