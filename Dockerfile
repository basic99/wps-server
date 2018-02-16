FROM ubuntu:trusty

RUN apt-get update -y
RUN apt-get install -y \
    python-psycopg2 \
    python-flask \
    python-numpy \
    python-pip
RUN apt-get clean

RUN pip install statistics

ADD . /var/www/wsgi/wps-server/

RUN mkdir /var/www/wsgi/wps-server/logs

EXPOSE 5000

WORKDIR /var/www/wsgi/wps-server

CMD python wps.py
