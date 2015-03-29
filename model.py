"""model threat """


import logging
import psycopg2
import psycopg2.extras
from flask import g
import os
import numpy as np
import collections

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


def get_threat_report2(formdata):
    # logger.debug
    formvals = {}
    model_cols = ["huc"]
    model_wts = []

    # create dict w/ key huc12 and val empty list
    hucs_dict = collections.OrderedDict()
    query = "select huc_12 from forest_health order by huc_12"
    with g.db.cursor() as cur:
        cur.execute(query)
        hucs = cur.fetchall()
    for huc in hucs:
        hucs_dict[huc[0]] = []
        hucs_dict[huc[0]].append(huc[0])

    # read formdata into formvals excluding notinclude
    for formval in formdata:
        if formdata[formval] == 'notinclude':
            continue
        formvals[formval] = formdata[formval]

    scenario = formvals['scenario']
    year = formvals['year']
    habitat = formvals['habitat']
    logger.info(formvals)

    # add habitat in in model
    if 'habitat_weight' in formvals:
        query = "select huc_12, %s%srnk from lcscen_%s_rnk" % (
            habitat, year[2:], scenario
        )
        model_wts.append(formvals['habitat_weight'])
        model_cols.append(
            "%s %s - weight(%s)" % (
                habitat, scenario, formvals['habitat_weight'])
            )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                # logger.debug(row)
                hucs_dict[row[0]].append(int(row[1]))

    # add urban growth if included
    if 'urbangrth' in formvals:
        query = "select huc_12, urb%sha_rnk from urban_ha_rnk" % year[2:]
        model_wts.append(formvals['urbangrth'])
        model_cols.append("Urban Growth - weight(%s)" % formvals['urbangrth'])
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                # logger.debug(row)
                hucs_dict[row[0]].append(int(row[1]))

    # add fire suppression
    if 'firesup' in formvals:
        query = "select huc_12, urb%sden_rnk from urban_den_rnk" % year[2:]
        model_wts.append(formvals['firesup'])
        model_cols.append("Fire Suppresion - weight(%s)" % formvals['firesup'])
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                # logger.debug(row)
                hucs_dict[row[0]].append(int(row[1]))

    # add highway
    if 'hiway' in formvals:
        query = "select huc_12, rds%srnk from transportation_rnk" % year[2:]
        model_wts.append(formvals['hiway'])
        model_cols.append("Highway - weight(%s)" % formvals['hiway'])
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                # logger.debug(row)
                hucs_dict[row[0]].append(int(row[1]))

    # add slr up
    if 'slr_up' in formvals:
        query = "select huc_12, up00%srnk from slamm_up_rnk" % year[2:]
        model_wts.append(formvals['slr_up'])
        model_cols.append("Sea Level rise Upland change - weight(%s)" % formvals['slr_up'])
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                # logger.debug(row)
                hucs_dict[row[0]].append(int(row[1]))

    # add sea level land cover
    if 'slr_lc' in formvals:
        query = "select huc_12, lc00%srnk from slamm_lc_rnk" % year[2:]
        model_wts.append(formvals['slr_lc'])
        model_cols.append("Sea Level rise landcover change - weight(%s)" % formvals['slr_lc'])
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                # logger.debug(row)
                hucs_dict[row[0]].append(int(row[1]))

    logger.debug(model_wts)
    for huc in hucs_dict:
        threat = 0
        tot_weight = 0
        for idx, weight in enumerate(model_wts):
            threat += float(hucs_dict[huc][idx + 1]) * float(weight)
            tot_weight += float(weight)
        threat = threat / float(tot_weight)
        hucs_dict[huc].append(threat)

    # res_arr = [hucs_dict[x] for x in hucs_dict]

    return {
        "res_arr": hucs_dict,
        "col_hdrs": model_cols,
        "year": year
        }





