"""model threat """


import logging
import psycopg2
import psycopg2.extras
from flask import g
import os
import numpy as np

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


def get_threat_report(huc12_str, query):
    col_hdrs = []
    outputType = []
    huc12s = huc12_str.split(", ")
    huc12s.sort()
    for col_hdr in query.keys():
        if col_hdr != 'year':
            col_hdrs.append(col_hdr)
    col_hdrs.sort()
    col_hdrs.append("result")
    col_len = len(huc12s)
    outputType.append(("huc12", "U20"))
    for col_hdr in col_hdrs:
        outputType.append((col_hdr, 'i4'))
    dtype = np.dtype(outputType)
    nparray = np.ones((col_len,), dtype=dtype)

    for idx, row in enumerate(nparray):
        huc12 = huc12s[idx]
        # set huc12 value
        row['huc12'] = huc12
        # now rest of columns
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
                    row['urb'] = rec["yr" + year]
                except KeyError:
                    continue

        if(query.get('frag', default='off') == 'on'):
            with g.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute(
                    "select * from data_frag where huc_12 = %s", (huc12, )
                    )
                rec = cur.fetchone()
                try:
                    threat += rec["yr" + year]
                    row['frag'] = rec["yr" + year]
                except KeyError:
                    continue

        with g.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute(
                    "select * from data_static where huc_12 = %s", (huc12, )
                    )
                rec = cur.fetchone()
                if(query.get('polu1', default='off') == 'on'):
                    threat += rec['polu1']
                    row['polu1'] = rec['polu1']
                if(query.get('polu2', default='off') == 'on'):
                    threat += rec['polu2']
                    row['polu2'] = rec['polu2']
                if(query.get('dise1', default='off') == 'on'):
                    threat += rec['dise1']
                    row['dise1'] = rec['dise1']
                if(query.get('dise2', default='off') == 'on'):
                    threat += rec['dise2']
                    row['dise2'] = rec['dise2']
                if(query.get('slr', default='off') == 'on'):
                    threat += rec['slr']
                    row['slr'] = rec['slr']
                if(query.get('frp', default='off') == 'on'):
                    threat += rec['frp']
                    row['frp'] = rec['frp']
                if(query.get('firs', default='off') == 'on'):
                    threat += rec['firs']
                    row['firs'] = rec['firs']
                if(query.get('trans', default='off') == 'on'):
                    threat += rec['trans']
                    row['trans'] = rec['trans']

        try:
            threat = threat / (num_factors * 200) + 1
        except ZeroDivisionError:
            threat = 1
            pass
        if threat == 6:
            threat = 5
        row['result'] = threat

    return {"res_arr": nparray.tolist(), "col_hdrs": nparray.dtype.names}


