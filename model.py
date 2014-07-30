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
    '%(asctime)s - %(name)s, %(lineno)s - %(levelname)s - %(message)s',
    datefmt='%m/%d %H:%M:%S'
    )
fh.setFormatter(formatter)
logger.addHandler(fh)

col_names = {
    'polu1': 'Pollution 1',
    'polu2': 'Pollution 2',
    'dise1': 'Disease 1',
    'dise2': 'Disease 2',
    'slr': 'Sea Level Rise',
    'firp': 'Fire Probability',
    'firs': 'Fire Suppresion',
    'tran': 'Transportation Corridors',
    'frag': 'Fragmentation Index',
    'urb': 'Urban Percentage',
    'huc12': 'HUC12',
    'result': 'Result'
}


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
    # logger.debug(col_hdr)

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
                if(query.get('firp', default='off') == 'on'):
                    threat += rec['firp']
                    row['firp'] = rec['firp']
                if(query.get('firs', default='off') == 'on'):
                    threat += rec['firs']
                    row['firs'] = rec['firs']
                if(query.get('tran', default='off') == 'on'):
                    threat += rec['tran']
                    row['tran'] = rec['tran']

        try:
            threat = threat / (num_factors * 200) + 1
        except ZeroDivisionError:
            threat = 1
            pass
        if threat == 6:
            threat = 5
        row['result'] = threat

    col_disp = []
    for col in nparray.dtype.names:
        col_disp.append(col_names[col])

    return {
        "res_arr": nparray.tolist(),
        "col_hdrs": col_disp,
        "year": year
        }

