"""model threat """


import logging
import psycopg2
import psycopg2.extras
from flask import g
import os

cwd = os.path.dirname(os.path.realpath(__file__))
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler(cwd + '/logs/logs.log')
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
fh.setFormatter(formatter)
logger.addHandler(fh)


def get_threat(huc12, query):
    """Given huc12 and query string calculate threat

    input
    huc12 - string
    query - werkzeug.datastructures.ImmutableMultiDict
     """
    num_factors = len(query.keys()) - 1
    year = query.get('year')
    threat = 0
    if(query.get('urb', default='off') == 'on'):
        with g.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "select * from nc_urb_mean where huc_12 = %s", (huc12, )
                )
            rec = cur.fetchone()
            try:
                threat += rec["yr" + year]
            except KeyError:
                return 1

    if(query.get('frag', default='off') == 'on'):
        with g.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "select * from data_frag where huc_12 = %s", (huc12, )
                )
            rec = cur.fetchone()
            try:
                threat += rec["yr" + year]
            except KeyError:
                return 1

    with g.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "select * from data_static where huc_12 = %s", (huc12, )
                )
            rec = cur.fetchone()
            if(query.get('polu1', default='off') == 'on'):
                threat += rec['polu1']
            if(query.get('polu2', default='off') == 'on'):
                threat += rec['polu2']
            if(query.get('dise1', default='off') == 'on'):
                threat += rec['dise1']
            if(query.get('dise2', default='off') == 'on'):
                threat += rec['dise2']
            if(query.get('slr', default='off') == 'on'):
                threat += rec['slr']
            if(query.get('frp', default='off') == 'on'):
                threat += rec['frp']
            if(query.get('firs', default='off') == 'on'):
                threat += rec['firs']
            if(query.get('trans', default='off') == 'on'):
                threat += rec['trans']

    try:
        threat = threat / (num_factors * 200) + 1
    except ZeroDivisionError:
        threat = 1
        pass
    if threat == 6:
        threat = 5
    return threat
