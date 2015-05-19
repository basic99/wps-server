"""model threat """


import logging
import psycopg2
import psycopg2.extras
from flask import g
import os
import numpy as np
import collections
import statistics
import copy

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

col_names = {
    'x': 'Baseline',
    'a': 'Biofuel A',
    'b': 'Biofuel B',
    'c': 'Biofuel C',
    'd': 'Biofuel D',
    'e': 'Biofuel E',
    'frst': 'Forest',
    'ftwt': 'Wet forest',
    'open': 'Open',
    'shrb': 'Scrub',
    'hbwt': 'Wet herbaceous'
}


def get_threat_report2(id, formdata, mode='state'):
    # logger.debug
    formvals = {}
    model_cols = ["huc"]
    model_wts = []

    logger.debug(id)
    logger.debug(mode)

    # create dict w/ key huc12 and val empty list
    hucs_dict = collections.OrderedDict()
    rank_data = collections.OrderedDict()

    if int(id) == 0 or mode == 'state':
        # could use any table here
        query = "select huc_12 from forest_health order by huc_12"
        with g.db.cursor() as cur:
            cur.execute(query)
            hucs = cur.fetchall()
        for huc in hucs:
            hucs_dict[huc[0]] = []
            hucs_dict[huc[0]].append(huc[0])
    elif mode == 'aoi':
        with g.db.cursor() as cur:
            cur.execute("select huc12s from aoi_results where pk = %s", (id, ))
            huc12_str = cur.fetchone()
        hucs = huc12_str[0].split(",")
        for huc in hucs:
            hucs_dict[huc.strip()] = []
            hucs_dict[huc.strip()].append(huc.strip())
    elif mode == '12k':
        with g.db.cursor() as cur:
            cur.execute(
                "select huc12s_12k from aoi_results where pk = %s", (id, )
            )
            huc12_str = cur.fetchone()
        hucs = huc12_str[0].split(",")
        for huc in hucs:
            hucs_dict[huc.strip()] = []
            hucs_dict[huc.strip()].append(huc.strip())
    elif mode == '5k':
        with g.db.cursor() as cur:
            cur.execute(
                "select huc12s_5k from aoi_results where pk = %s", (id, )
            )
            huc12_str = cur.fetchone()
        hucs = huc12_str[0].split(",")
        for huc in hucs:
            hucs_dict[huc.strip()] = []
            hucs_dict[huc.strip()].append(huc.strip())

    hucs_dict_ranks = copy.deepcopy(hucs_dict)

    # read formdata into formvals excluding notinclude
    for formval in formdata:
        if formdata[formval] == 'notinclude':
            continue
        formvals[formval] = formdata[formval]

    try:
        year = formvals['year']
        scenario = formvals['scenario']
        # habitat = formvals['habitat']
    except KeyError:
        year = '2010'
        pass
    logger.info(formvals)



    # add habitat in in model
    if 'frst' in formvals:
        rank_data['frst'] = []
        query = "select huc_12, %s%srnk from lcscen_%s_rnk" % (
            'frst',
            year[2:],
            scenario
        )
        logger.debug(query)
        model_wts.append(float(formvals['frst']))
        model_cols.append(
            "%s %s - limit(%s)" % (
                col_names['frst'],
                col_names[scenario],
                formvals['frst'])
            )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                # logger.debug(row)
                if formvals['mode'] == 'single':
                    try:
                        hucs_dict[row[0]].append(row[1])
                    except KeyError:
                        pass
                    continue
                if int(row[1]) > int(formvals['frst']):
                    above = 1
                    rank = int(row[1])
                else:
                    above = 0
                    rank = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ranks[row[0]].append(rank)

                    # must follow this line to get hucs correct
                    rank_data['frst'].append(rank)
                except KeyError:
                    pass

    if 'ftwt' in formvals:
        rank_data['ftwt'] = []

        query = "select huc_12, %s%srnk from lcscen_%s_rnk" % (
            'ftwt',
            year[2:],
            scenario
        )
        model_wts.append(float(formvals['ftwt']))
        model_cols.append(
            "%s %s - limit(%s)" % (
                col_names['ftwt'],
                col_names[scenario],
                formvals['ftwt'])
            )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                if formvals['mode'] == 'single':
                    try:
                        hucs_dict[row[0]].append(row[1])
                    except KeyError:
                        pass
                    continue
                if int(row[1]) > int(formvals['ftwt']):
                    above = 1
                    rank = int(row[1])
                else:
                    above = 0
                    rank = 0
                # logger.debug(row)
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ranks[row[0]].append(rank)
                    rank_data['ftwt'].append(rank)
                except KeyError:
                    pass

    if 'hbwt' in formvals:
        rank_data['hbwt'] = []

        query = "select huc_12, %s%srnk from lcscen_%s_rnk" % (
            'hbwt',
            year[2:],
            scenario
        )
        model_wts.append(float(formvals['hbwt']))
        model_cols.append(
            "%s %s - limit(%s)" % (
                col_names['hbwt'],
                col_names[scenario],
                formvals['hbwt'])
            )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                if formvals['mode'] == 'single':
                    try:
                        hucs_dict[row[0]].append(row[1])
                    except KeyError:
                        pass
                    continue
                # logger.debug(row)
                if int(row[1]) > int(formvals['hbwt']):
                    above = 1
                    rank = int(row[1])
                else:
                    above = 0
                    rank = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ranks[row[0]].append(rank)
                    rank_data['hbwt'].append(rank)
                except KeyError:
                    pass

    if 'open' in formvals:
        rank_data['open'] = []

        query = "select huc_12, %s%srnk from lcscen_%s_rnk" % (
            'open',
            year[2:],
            scenario
        )
        model_wts.append(float(formvals['open']))
        model_cols.append(
            "%s %s - limit(%s)" % (
                col_names['open'],
                col_names[scenario],
                formvals['open'])
            )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                if formvals['mode'] == 'single':
                    try:
                        hucs_dict[row[0]].append(row[1])
                    except KeyError:
                        pass
                    continue
                # logger.debug(row)
                if int(row[1]) > int(formvals['open']):
                    above = 1
                    rank = int(row[1])
                else:
                    above = 0
                    rank = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ranks[row[0]].append(rank)
                    rank_data['open'].append(rank)
                except KeyError:
                    pass

    if 'shrb' in formvals:
        rank_data['shrb'] = []

        query = "select huc_12, %s%srnk from lcscen_%s_rnk" % (
            'shrb',
            year[2:],
            scenario
        )
        model_wts.append(float(formvals['shrb']))
        model_cols.append(
            "%s %s - limit(%s)" % (
                col_names['shrb'],
                col_names[scenario],
                formvals['shrb'])
            )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                if formvals['mode'] == 'single':
                    try:
                        hucs_dict[row[0]].append(row[1])
                    except KeyError:
                        pass
                    continue
                # logger.debug(row)
                if int(row[1]) > int(formvals['shrb']):
                    above = 1
                    rank = int(row[1])
                else:
                    above = 0
                    rank = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ranks[row[0]].append(rank)
                    rank_data['shrb'].append(rank)
                except KeyError:
                    pass
    # add urban growth if included
    if 'urbangrth' in formvals:
        rank_data['urbangrth'] = []

        query = "select huc_12, urb%sha_rnk from urban_ha_rnk" % year[2:]
        logger.debug(query)
        model_wts.append(float(formvals['urbangrth']))
        model_cols.append("Urban Growth - limit(%s)" % formvals['urbangrth'])
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                if formvals['mode'] == 'single':
                    try:
                        hucs_dict[row[0]].append(row[1])
                    except KeyError:
                        pass
                    continue
                if int(row[1]) > int(formvals['urbangrth']):
                    above = 1
                    rank = int(row[1])
                else:
                    above = 0
                    rank = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ranks[row[0]].append(rank)
                    rank_data['urbangrth'].append(rank)
                except KeyError:
                    pass
                # this will run for single layer



    # add fire suppression
    if 'firesup' in formvals:
        rank_data['firesup'] = []

        query = "select huc_12, urb%sden_rnk from urban_den_rnk" % year[2:]
        # logger.debug(query)
        model_wts.append(float(formvals['firesup']))
        model_cols.append("Fire Suppresion - limit(%s)" % formvals['firesup'])
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                if formvals['mode'] == 'single':
                    try:
                        hucs_dict[row[0]].append(row[1])
                    except KeyError:
                        pass
                    continue
                if int(row[1]) > int(formvals['firesup']):
                    above = 1
                    rank = int(row[1])
                else:
                    above = 0
                    rank = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ranks[row[0]].append(rank)
                    rank_data['firesup'].append(rank)
                except KeyError:
                    pass

    # add highway
    if 'hiway' in formvals:
        rank_data['hiway'] = []

        query = "select huc_12, rds%srnk from transportation_rnk" % year[2:]
        model_wts.append(float(formvals['hiway']))
        model_cols.append("Highway - limit(%s)" % formvals['hiway'])
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                if formvals['mode'] == 'single':
                    try:
                        hucs_dict[row[0]].append(row[1])
                    except KeyError:
                        pass
                    continue
                # logger.debug(row)
                # hucs_dict[row[0]].append(int(row[1]))
                if int(row[1]) > int(formvals['hiway']):
                    above = 1
                    rank = int(row[1])
                else:
                    above = 0
                    rank = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ranks[row[0]].append(rank)
                    rank_data['hiway'].append(rank)
                except KeyError:
                    pass

    # add slr up
    if 'slr_up' in formvals:
        rank_data['slr_up'] = []

        query = "select huc_12, up00%srnk from slamm_up_rnk" % year[2:]
        model_wts.append(float(formvals['slr_up']))
        model_cols.append(
            "Sea Level rise Upland change - limit(%s)" % formvals['slr_up']
        )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                if formvals['mode'] == 'single':
                    try:
                        hucs_dict[row[0]].append(row[1])
                    except KeyError:
                        pass
                    continue
                # logger.debug(row)
                # hucs_dict[row[0]].append(int(row[1]))
                if int(row[1]) > int(formvals['slr_up']):
                    above = 1
                    rank = int(row[1])
                else:
                    above = 0
                    rank = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ranks[row[0]].append(rank)
                    rank_data['slr_up'].append(rank)
                except KeyError:
                    pass

    # add sea level land cover
    if 'slr_lc' in formvals:
        rank_data['slr_lc'] = []

        query = "select huc_12, lc00%srnk from slamm_lc_rnk" % year[2:]
        model_wts.append(float(formvals['slr_lc']))
        model_cols.append(
            "Sea Level rise landcover change - limit(%s)" % formvals['slr_lc']
        )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                if formvals['mode'] == 'single':
                    try:
                        hucs_dict[row[0]].append(row[1])
                    except KeyError:
                        pass
                    continue
                # logger.debug(row)
                # hucs_dict[row[0]].append(int(row[1]))
                if int(row[1]) > int(formvals['slr_lc']):
                    above = 1
                    rank = int(row[1])
                else:
                    above = 0
                    rank = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ranks[row[0]].append(rank)
                    rank_data['slr_lc'].append(rank)

                except KeyError:
                    pass

    # add triassic
    if 'triassic' in formvals:
        rank_data['triassic'] = []

        query = "select huc_12, triassic_rnk from static_rnk"
        model_wts.append(float(formvals['triassic']))
        model_cols.append(
            "Triassic Basin - limit(%s)" % formvals['triassic']
        )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                if formvals['mode'] == 'single':
                    try:
                        hucs_dict[row[0]].append(row[1])
                    except KeyError:
                        pass
                    continue
                # logger.debug(row)
                # hucs_dict[row[0]].append(int(row[1]))
                if int(row[1]) > int(formvals['triassic']):
                    above = 1
                    rank = int(row[1])
                else:
                    above = 0
                    rank = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ranks[row[0]].append(rank)
                    rank_data['triassic'].append(rank)

                except KeyError:
                    pass

    # add wind power
    if 'wind' in formvals:
        rank_data['wind'] = []

        query = "select huc_12, WPC_rnk from wind_rnk"
        model_wts.append(float(formvals['wind']))
        model_cols.append(
            "Wind Power - limit(%s)" % formvals['wind']
        )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                if formvals['mode'] == 'single':
                    try:
                        hucs_dict[row[0]].append(row[1])
                    except KeyError:
                        pass
                    continue
                # logger.debug(row)
                # hucs_dict[row[0]].append(int(row[1]))
                if int(row[1]) > int(formvals['wind']):
                    above = 1
                    rank = int(row[1])
                else:
                    above = 0
                    rank = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ranks[row[0]].append(rank)
                    rank_data['wind'].append(rank)

                except KeyError:
                    pass

    # add manure
    if 'manure' in formvals:
        rank_data['manure'] = []

        query = "select huc_12, MANU_rnk from static_rnk"
        model_wts.append(float(formvals['manure']))
        model_cols.append(
            "Manure Application - limit(%s)" % formvals['manure']
        )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                if formvals['mode'] == 'single':
                    try:
                        hucs_dict[row[0]].append(row[1])
                    except KeyError:
                        pass
                    continue
                # logger.debug(row)
                # hucs_dict[row[0]].append(int(row[1]))
                if int(row[1]) > int(formvals['manure']):
                    above = 1
                    rank = int(row[1])
                else:
                    above = 0
                    rank = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ranks[row[0]].append(rank)
                    rank_data['manure'].append(rank)

                except KeyError:
                    pass

    # add nitrogen
    if 'nitrofrt' in formvals:
        rank_data['nitrofrt'] = []

        query = "select huc_12, FERT_rnk from static_rnk"
        model_wts.append(float(formvals['nitrofrt']))
        model_cols.append(
            "Synthetic Nitrogen - limit(%s)" % formvals['nitrofrt']
        )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                if formvals['mode'] == 'single':
                    try:
                        hucs_dict[row[0]].append(row[1])
                    except KeyError:
                        pass
                    continue
                # logger.debug(row)
                # hucs_dict[row[0]].append(int(row[1]))
                if int(row[1]) > int(formvals['nitrofrt']):
                    above = 1
                    rank = int(row[1])
                else:
                    above = 0
                    rank = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ranks[row[0]].append(rank)
                    rank_data['nitrofrt'].append(rank)

                except KeyError:
                    pass

    # add total nitrogen
    if 'totnitro' in formvals:
        rank_data['totnitro'] = []

        query = "select huc_12, TD_N_T_rnk from static_rnk"
        model_wts.append(float(formvals['totnitro']))
        model_cols.append(
            "Total Nitrogen - limit(%s)" % formvals['totnitro']
        )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                if formvals['mode'] == 'single':
                    try:
                        hucs_dict[row[0]].append(row[1])
                    except KeyError:
                        pass
                    continue
                # logger.debug(row)
                # hucs_dict[row[0]].append(int(row[1]))
                if int(row[1]) > int(formvals['totnitro']):
                    above = 1
                    rank = int(row[1])
                else:
                    above = 0
                    rank = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ranks[row[0]].append(rank)
                    rank_data['totnitro'].append(rank)

                except KeyError:
                    pass

    # add total sulphur
    if 'totsulf' in formvals:
        rank_data['totsulf'] = []

        query = "select huc_12, TD_S_T_rnk from static_rnk"
        model_wts.append(float(formvals['totsulf']))
        model_cols.append(
            "Total Sulfur - limit(%s)" % formvals['totsulf']
        )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                if formvals['mode'] == 'single':
                    try:
                        hucs_dict[row[0]].append(row[1])
                    except KeyError:
                        pass
                    continue
                # logger.debug(row)
                # hucs_dict[row[0]].append(int(row[1]))
                if int(row[1]) > int(formvals['totsulf']):
                    above = 1
                    rank = int(row[1])
                else:
                    above = 0
                    rank = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ranks[row[0]].append(rank)
                    rank_data['totsulf'].append(rank)

                except KeyError:
                    pass

    # add forest health
    if 'insectdisease' in formvals:
        rank_data['insectdisease'] = []

        query = "select huc_12, FHlth_Rnk from static_rnk"
        model_wts.append(float(formvals['insectdisease']))
        model_cols.append(
            "Forest health - limit(%s)" % formvals['insectdisease']
        )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                if formvals['mode'] == 'single':
                    try:
                        hucs_dict[row[0]].append(row[1])
                    except KeyError:
                        pass
                    continue
                # logger.debug(row)
                # hucs_dict[row[0]].append(int(row[1]))
                if int(row[1]) > int(formvals['insectdisease']):
                    above = 1
                    rank = int(row[1])
                else:
                    above = 0
                    rank = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ranks[row[0]].append(rank)
                    rank_data['insectdisease'].append(rank)

                except KeyError:
                    pass

    # add number of dams
    if 'ndams' in formvals:
        rank_data['ndams'] = []

        query = "select huc_12, NID_rnk from static_rnk"
        model_wts.append(float(formvals['ndams']))
        model_cols.append(
            "# of dams - limit(%s)" % formvals['ndams']
        )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                if formvals['mode'] == 'single':
                    try:
                        hucs_dict[row[0]].append(row[1])
                    except KeyError:
                        pass
                    continue
                # logger.debug(row)
                # hucs_dict[row[0]].append(int(row[1]))
                if int(row[1]) > int(formvals['ndams']):
                    above = 1
                    rank = int(row[1])
                else:
                    above = 0
                    rank = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ranks[row[0]].append(rank)
                    rank_data['ndams'].append(rank)

                except KeyError:
                    pass

    # add impaired biota
    if 'impairbiota' in formvals:
        rank_data['impairbiota'] = []

        query = "select huc_12, BioImpLen_rnk from static_rnk"
        logger.debug(query)
        model_wts.append(float(formvals['impairbiota']))
        model_cols.append(
            "Impaired biota - limit(%s)" % formvals['impairbiota']
        )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                if formvals['mode'] == 'single':
                    try:
                        hucs_dict[row[0]].append(row[1])
                    except KeyError:
                        pass
                    continue
                # logger.debug(row)
                if int(row[1]) > int(formvals['impairbiota']):
                    above = 1
                    rank = int(row[1])
                else:
                    above = 0
                    rank = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ranks[row[0]].append(rank)
                    rank_data['impairbiota'].append(rank)

                except KeyError:
                    pass

    # add impaired metals
    if 'impairmetal' in formvals:
        rank_data['impairmetal'] = []

        query = "select huc_12, MetImpLen_rnk from static_rnk"
        logger.debug(query)
        model_wts.append(float(formvals['impairmetal']))
        model_cols.append(
            "Impaired metal - threshold(%s)" % formvals['impairmetal']
        )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                if formvals['mode'] == 'single':
                    try:
                        hucs_dict[row[0]].append(row[1])
                    except KeyError:
                        pass
                    continue
                # logger.debug(row)
                if int(row[1]) > int(formvals['impairmetal']):
                    above = 1
                    rank = int(row[1])
                else:
                    above = 0
                    rank = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ranks[row[0]].append(rank)
                    rank_data['impairmetal'].append(rank)

                except KeyError:
                    pass
    # tot_weight = len(model_wts)

    # calculate threat count for each huc
    threat_rank = []
    threat_count = []
    for huc in hucs_dict:
        threat = 0
        threat_rnk = 0

        for idx, weight in enumerate(model_wts):
            threat += float(hucs_dict[huc][idx + 1])
            threat_rnk += float(hucs_dict_ranks[huc][idx + 1])
        threat_raw = threat
        # hucs_dict[huc].append(threat_raw)
        hucs_dict_ranks[huc].append(threat_raw)
        threat_rank.append(float(threat_rnk) / (idx + 1) )
        threat_count.append(threat)

    # calculate composite thrts
    thrt_counts_summary = []
    thrt_counts_summary.append("Composite Threat Count")
    mean = statistics.mean(threat_count)
    thrt_counts_summary.append(int(mean * 100) / 100.0)
    try:
        stdev = statistics.stdev(threat_count)
        thrt_counts_summary.append(int(stdev * 10000) / 10000.0)
    except statistics.StatisticsError:
        thrt_counts_summary.append('na')
    thrt_counts_summary.append(min(threat_count))
    thrt_counts_summary.append(max(threat_count))

    thrt_rank_summary = []
    thrt_rank_summary.append("Composite Threat Rank")
    mean = statistics.mean(threat_rank)
    thrt_rank_summary.append(int(mean * 100) / 100.0)
    try:
        stdev = statistics.stdev(threat_rank)
        thrt_rank_summary.append(int(stdev * 10000) / 10000.0)
    except statistics.StatisticsError:
        thrt_rank_summary.append('na')
    thrt_rank_summary.append(min(threat_rank))
    thrt_rank_summary.append(max(threat_rank))

    threat_summary = [thrt_counts_summary, thrt_rank_summary]

    if mode == 'aoi':
        logger.debug(threat_summary)


       # start making summary report
    logger.debug(model_cols)
    summary_params_list = collections.OrderedDict()
    summary_params_list['Threat Count'] = [
        hucs_dict[x][-1] for x in hucs_dict
    ]
    for idx, model_col in enumerate(model_cols):
        if idx != 0:
            summary_params_list[model_col] = [
                hucs_dict[x][idx] for x in hucs_dict
            ]
    if mode == 'aoi':
        logger.debug(summary_params_list)
    report = []
    report_rank = []
    for row in summary_params_list:
        report_row = [str(row)]
        mean = statistics.mean(summary_params_list[row])
        report_row.append(int(mean * 100) / 100.0)
        try:
            stdev = statistics.stdev(summary_params_list[row])
            report_row.append(int(stdev * 10000) / 10000.0)
        except statistics.StatisticsError:
            report_row.append('na')
        row_min = min(summary_params_list[row])
        report_row.append(row_min)
        row_max = max(summary_params_list[row])
        report_row.append(row_max)

        report.append(report_row)

    if formvals['mode'] != 'single':
        thrts_present = 0
        for i, threat in enumerate(rank_data):
            # logger.debug(threat)
            # logger.debug(model_cols[i + 1])
            report_row = [model_cols[i + 1]]
            cnts = summary_params_list[model_cols[i + 1]]
            mean = statistics.mean(cnts)
            report_row.append(int(mean * 100) / 100.0)
            mean = statistics.mean(rank_data[threat])
            report_row.append(int(mean * 100) / 100.0)
            try:
                stdev = statistics.stdev(rank_data[threat])
                report_row.append(int(stdev * 10000) / 10000.0)
            except statistics.StatisticsError:
                report_row.append('na')
            row_min = min(rank_data[threat])
            report_row.append(row_min)
            row_max = max(rank_data[threat])
            if row_max > 0:
                thrts_present += 1
            report_row.append(row_max)

            # add row to report
            report_rank.append(report_row)

    # logger.debug(i + 1)
    # logger.debug(thrts_present)
    thrts_included_msg = "%d of %d " %(thrts_present, i + 1)
    logger.debug(thrts_included_msg)


    return {
        "res_arr": hucs_dict_ranks,
        "col_hdrs": model_cols,
        "year": year,
        # "report": report,
        "report_rank": report_rank,
        "thrts_included_msg": thrts_included_msg,
        "threat_summary":threat_summary
        }
