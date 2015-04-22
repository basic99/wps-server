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


def get_threat_report2(id, formdata):
    # logger.debug
    formvals = {}
    model_cols = ["huc"]
    model_wts = []

    logger.debug(id)

    # create dict w/ key huc12 and val empty list
    hucs_dict = collections.OrderedDict()

    if int(id) == 0:
        query = "select huc_12 from forest_health order by huc_12"
        with g.db.cursor() as cur:
            cur.execute(query)
            hucs = cur.fetchall()
        for huc in hucs:
            hucs_dict[huc[0]] = []
            hucs_dict[huc[0]].append(huc[0])
    else:
        with g.db.cursor() as cur:
            cur.execute("select huc12s from aoi_results where pk = %s", (id, ))
            huc12_str = cur.fetchone()
        hucs = huc12_str[0].split(",")
        for huc in hucs:
            hucs_dict[huc.strip()] = []
            hucs_dict[huc.strip()].append(huc.strip())


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
            habitat,
            year[2:],
            scenario
        )
        model_wts.append(float(formvals['habitat_weight']))
        model_cols.append(
            "%s %s - weight(%s)" % (
                col_names[habitat],
                col_names[scenario],
                formvals['habitat_weight'])
            )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                # logger.debug(row)
                try:
                    hucs_dict[row[0]].append(int(row[1]))
                except KeyError:
                    pass


    # add urban growth if included
    if 'urbangrth' in formvals:
        query = "select huc_12, urb%sha_rnk from urban_ha_rnk" % year[2:]
        model_wts.append(float(formvals['urbangrth']))
        model_cols.append("Urban Growth - weight(%s)" % formvals['urbangrth'])
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                # logger.debug(row)
                # hucs_dict[row[0]].append(int(row[1]))
                try:
                    hucs_dict[row[0]].append(int(row[1]))
                except KeyError:
                    pass

    # add fire suppression
    if 'firesup' in formvals:
        query = "select huc_12, urb%sden_rnk from urban_den_rnk" % year[2:]
        model_wts.append(float(formvals['firesup']))
        model_cols.append("Fire Suppresion - weight(%s)" % formvals['firesup'])
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                # logger.debug(row)
                # hucs_dict[row[0]].append(int(row[1]))
                try:
                    hucs_dict[row[0]].append(int(row[1]))
                except KeyError:
                    pass

    # add highway
    if 'hiway' in formvals:
        query = "select huc_12, rds%srnk from transportation_rnk" % year[2:]
        model_wts.append(float(formvals['hiway']))
        model_cols.append("Highway - weight(%s)" % formvals['hiway'])
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                # logger.debug(row)
                # hucs_dict[row[0]].append(int(row[1]))
                try:
                    hucs_dict[row[0]].append(int(row[1]))
                except KeyError:
                    pass

    # add slr up
    if 'slr_up' in formvals:
        query = "select huc_12, up00%srnk from slamm_up_rnk" % year[2:]
        model_wts.append(float(formvals['slr_up']))
        model_cols.append(
            "Sea Level rise Upland change - weight(%s)" % formvals['slr_up']
        )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                # logger.debug(row)
                # hucs_dict[row[0]].append(int(row[1]))
                try:
                    hucs_dict[row[0]].append(int(row[1]))
                except KeyError:
                    pass

    # add sea level land cover
    if 'slr_lc' in formvals:
        query = "select huc_12, lc00%srnk from slamm_lc_rnk" % year[2:]
        model_wts.append(float(formvals['slr_lc']))
        model_cols.append(
            "Sea Level rise landcover change - weight(%s)" % formvals['slr_lc']
        )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                # logger.debug(row)
                # hucs_dict[row[0]].append(int(row[1]))
                try:
                    hucs_dict[row[0]].append(int(row[1]))
                except KeyError:
                    pass

    # add triassic
    if 'triassic' in formvals:
        query = "select huc_12, triassic_rnk from static_rnk"
        model_wts.append(float(formvals['triassic']))
        model_cols.append(
            "Triassic Basin - weight(%s)" % formvals['triassic']
        )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                # logger.debug(row)
                # hucs_dict[row[0]].append(int(row[1]))
                try:
                    hucs_dict[row[0]].append(int(row[1]))
                except KeyError:
                    pass

    # add wind power
    if 'wind' in formvals:
        query = "select huc_12, WPC_rnk from wind_rnk"
        model_wts.append(float(formvals['wind']))
        model_cols.append(
            "Wind Power - weight(%s)" % formvals['wind']
        )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                # logger.debug(row)
                # hucs_dict[row[0]].append(int(row[1]))
                try:
                    hucs_dict[row[0]].append(int(row[1]))
                except KeyError:
                    pass

    # add manure
    if 'manure' in formvals:
        query = "select huc_12, MANU_rnk from static_rnk"
        model_wts.append(float(formvals['manure']))
        model_cols.append(
            "Manure Application - weight(%s)" % formvals['manure']
        )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                # logger.debug(row)
                # hucs_dict[row[0]].append(int(row[1]))
                try:
                    hucs_dict[row[0]].append(int(row[1]))
                except KeyError:
                    pass

    # add nitrogen
    if 'nitrofrt' in formvals:
        query = "select huc_12, FERT_rnk from static_rnk"
        model_wts.append(float(formvals['nitrofrt']))
        model_cols.append(
            "Synthetic Nitrogen - weight(%s)" % formvals['nitrofrt']
        )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                # logger.debug(row)
                # hucs_dict[row[0]].append(int(row[1]))
                try:
                    hucs_dict[row[0]].append(int(row[1]))
                except KeyError:
                    pass

    # add total nitrogen
    if 'totnitro' in formvals:
        query = "select huc_12, TD_N_T_rnk from static_rnk"
        model_wts.append(float(formvals['totnitro']))
        model_cols.append(
            "Total Nitrogen - weight(%s)" % formvals['totnitro']
        )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                # logger.debug(row)
                # hucs_dict[row[0]].append(int(row[1]))
                try:
                    hucs_dict[row[0]].append(int(row[1]))
                except KeyError:
                    pass

    # add total sulphur
    if 'totsulf' in formvals:
        query = "select huc_12, TD_S_T_rnk from static_rnk"
        model_wts.append(float(formvals['totsulf']))
        model_cols.append(
            "Total Sulfur - weight(%s)" % formvals['totsulf']
        )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                # logger.debug(row)
                # hucs_dict[row[0]].append(int(row[1]))
                try:
                    hucs_dict[row[0]].append(int(row[1]))
                except KeyError:
                    pass

    # add forest health
    if 'insectdisease' in formvals:
        query = "select huc_12, FHlth_Rnk from static_rnk"
        model_wts.append(float(formvals['insectdisease']))
        model_cols.append(
            "Foreset health - weight(%s)" % formvals['insectdisease']
        )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                # logger.debug(row)
                # hucs_dict[row[0]].append(int(row[1]))
                try:
                    hucs_dict[row[0]].append(int(row[1]))
                except KeyError:
                    pass

    # add number of dams
    if 'ndams' in formvals:
        query = "select huc_12, NID_rnk from static_rnk"
        model_wts.append(float(formvals['ndams']))
        model_cols.append(
            "# of dams - weight(%s)" % formvals['ndams']
        )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                # logger.debug(row)
                # hucs_dict[row[0]].append(int(row[1]))
                try:
                    hucs_dict[row[0]].append(int(row[1]))
                except KeyError:
                    pass

    # add impaired waters all
    if 'impairall' in formvals:
        query = "select huc_12, TotImpLen_rnk from static_rnk"
        model_wts.append(float(formvals['impairall']))
        model_cols.append(
            "Impaired all - weight(%s)" % formvals['impairall']
        )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                # logger.debug(row)
                # hucs_dict[row[0]].append(int(row[1]))
                try:
                    hucs_dict[row[0]].append(int(row[1]))
                except KeyError:
                    pass

    # # add impaired biota
    # if 'impairbiota' in formvals and formvals['impaired'] == 'indiv':
    #     query = "select huc_12, BioImpLen_rnk from static_rnk"
    #     logger.debug(query)
    #     model_wts.append(float(formvals['impairbiota']))
    #     model_cols.append(
    #         "Impaired biota - weight(%s)" % formvals['impairbiota']
    #     )
    #     with g.db.cursor() as cur:
    #         cur.execute(query)
    #         for row in cur:
    #             # logger.debug(row)
    #             hucs_dict[row[0]].append(int(row[1]))

    # # add impaired metals
    # if 'impairmetal' in formvals and formvals['impaired'] == 'indiv':
    #     query = "select huc_12, MetImpLen_rnk from static_rnk"
    #     logger.debug(query)
    #     model_wts.append(float(formvals['impairmetal']))
    #     model_cols.append(
    #         "Impaired metal - weight(%s)" % formvals['impairmetal']
    #     )
    #     with g.db.cursor() as cur:
    #         cur.execute(query)
    #         for row in cur:
    #             # logger.debug(row)
    #             hucs_dict[row[0]].append(int(row[1]))

    # # add impaired nutrients
    # if 'impairnutr' in formvals and formvals['impaired'] == 'indiv':
    #     query = "select huc_12, NutImpLen_rnk from static_rnk"
    #     logger.debug(query)
    #     model_wts.append(float(formvals['impairnutr']))
    #     model_cols.append(
    #         "Impaired nutrients - weight(%s)" % formvals['impairnutr']
    #     )
    #     with g.db.cursor() as cur:
    #         cur.execute(query)
    #         for row in cur:
    #             # logger.debug(row)
    #             hucs_dict[row[0]].append(int(row[1]))

    # # add impaired habitat
    # if 'impairhab' in formvals and formvals['impaired'] == 'indiv':
    #     query = "select huc_12, HabImpLen_rnk from static_rnk"
    #     logger.debug(query)
    #     model_wts.append(float(formvals['impairhab']))
    #     model_cols.append(
    #         "Impaired habitat - weight(%s)" % formvals['impairhab']
    #     )
    #     with g.db.cursor() as cur:
    #         cur.execute(query)
    #         for row in cur:
    #             # logger.debug(row)
    #             hucs_dict[row[0]].append(int(row[1]))

    # # add impaired temp
    # if 'impairtemp' in formvals and formvals['impaired'] == 'indiv':
    #     query = "select huc_12, TempImpLen_rnk from static_rnk"
    #     logger.debug(query)
    #     model_wts.append(float(formvals['impairtemp']))
    #     model_cols.append(
    #         "Impaired temp - weight(%s)" % formvals['impairtemp']
    #     )
    #     with g.db.cursor() as cur:
    #         cur.execute(query)
    #         for row in cur:
    #             # logger.debug(row)
    #             hucs_dict[row[0]].append(int(row[1]))

    # # add impaired polution
    # if 'impairpolu' in formvals and formvals['impaired'] == 'indiv':
    #     query = "select huc_12, PolImpLen_rnk from static_rnk"
    #     logger.debug(query)
    #     model_wts.append(float(formvals['impairpolu']))
    #     model_cols.append(
    #         "Impaired polution - weight(%s)" % formvals['impairpolu']
    #     )
    #     with g.db.cursor() as cur:
    #         cur.execute(query)
    #         for row in cur:
    #             # logger.debug(row)
    #             hucs_dict[row[0]].append(int(row[1]))

    # # add impaired other
    # if 'impairother' in formvals and formvals['impaired'] == 'indiv':
    #     query = "select huc_12, OtherLen_rnk from static_rnk"
    #     logger.debug(query)
    #     model_wts.append(float(formvals['impairother']))
    #     model_cols.append(
    #         "Impaired other - weight(%s)" % formvals['impairother']
    #     )
    #     with g.db.cursor() as cur:
    #         cur.execute(query)
    #         for row in cur:
    #             # logger.debug(row)
    #             hucs_dict[row[0]].append(int(row[1]))



    tot_weight = sum(model_wts)
    logger.debug(model_cols)
    logger.debug(model_wts)
    logger.debug(tot_weight)
    for huc in hucs_dict:
        threat = 0
        for idx, weight in enumerate(model_wts):
            threat += float(hucs_dict[huc][idx + 1]) * float(weight)
        threat = threat / tot_weight
        threat = int(threat * 100) / 100.0
        hucs_dict[huc].append(threat)

    # res_arr = [hucs_dict[x] for x in hucs_dict]

    return {
        "res_arr": hucs_dict,
        "col_hdrs": model_cols,
        "year": year
        }





