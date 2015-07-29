"""model threat """


import logging
# import psycopg2
# import psycopg2.extras
from flask import g
import os
# import numpy as np
import collections
import statistics
import copy
import siteutils

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



# def get_threat_report(huc12_str, query):
#     col_hdrs = []
#     outputType = []
#     huc12s = huc12_str.split(", ")
#     huc12s.sort()
#     for col_hdr in query.keys():
#         if col_hdr != 'year':
#             col_hdrs.append(col_hdr)
#     col_hdrs.sort()
#     col_hdrs.append("result")
#     # logger.debug(col_hdr)

#     col_len = len(huc12s)
#     outputType.append(("huc12", "U20"))
#     for col_hdr in col_hdrs:
#         outputType.append((col_hdr, 'i4'))

#     dtype = np.dtype(outputType)
#     nparray = np.ones((col_len,), dtype=dtype)

#     for idx, row in enumerate(nparray):
#         huc12 = huc12s[idx]
#         # set huc12 value
#         row['huc12'] = huc12
#         # now rest of columns
#         num_factors = len(query.keys()) - 1
#         year = query.get('year')
#         threat = 0
#         if(query.get('urb', default='off') == 'on'):
#             with g.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
#                 cur.execute(
#                     "select * from nc_urb_mean where huc_12 = %s", (huc12, )
#                     )
#                 rec = cur.fetchone()
#                 try:
#                     threat += rec["yr" + year]
#                     row['urb'] = rec["yr" + year]
#                 except KeyError:
#                     continue

#         if(query.get('frag', default='off') == 'on'):
#             with g.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
#                 cur.execute(
#                     "select * from data_frag where huc_12 = %s", (huc12, )
#                     )
#                 rec = cur.fetchone()
#                 try:
#                     threat += rec["yr" + year]
#                     row['frag'] = rec["yr" + year]
#                 except KeyError:
#                     continue

#         with g.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
#                 cur.execute(
#                     "select * from data_static where huc_12 = %s", (huc12, )
#                     )
#                 rec = cur.fetchone()
#                 if(query.get('polu1', default='off') == 'on'):
#                     threat += rec['polu1']
#                     row['polu1'] = rec['polu1']
#                 if(query.get('polu2', default='off') == 'on'):
#                     threat += rec['polu2']
#                     row['polu2'] = rec['polu2']
#                 if(query.get('dise1', default='off') == 'on'):
#                     threat += rec['dise1']
#                     row['dise1'] = rec['dise1']
#                 if(query.get('dise2', default='off') == 'on'):
#                     threat += rec['dise2']
#                     row['dise2'] = rec['dise2']
#                 if(query.get('slr', default='off') == 'on'):
#                     threat += rec['slr']
#                     row['slr'] = rec['slr']
#                 if(query.get('firp', default='off') == 'on'):
#                     threat += rec['firp']
#                     row['firp'] = rec['firp']
#                 if(query.get('firs', default='off') == 'on'):
#                     threat += rec['firs']
#                     row['firs'] = rec['firs']
#                 if(query.get('tran', default='off') == 'on'):
#                     threat += rec['tran']
#                     row['tran'] = rec['tran']

#         try:
#             threat = threat / (num_factors * 200) + 1
#         except ZeroDivisionError:
#             threat = 1
#             pass
#         if threat == 6:
#             threat = 5
#         row['result'] = threat

#     col_disp = []
#     for col in nparray.dtype.names:
#         col_disp.append(col_names[col])

#     return {
#         "res_arr": nparray.tolist(),
#         "col_hdrs": col_disp,
#         "year": year
#         }

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
    mean_pct_areas = {}

    logger.debug(id)
    logger.debug(mode)

    # create dict w/ key huc12 and val empty list
    hucs_dict = collections.OrderedDict()
    rank_data = collections.OrderedDict()

    if int(id) == 0 or mode == 'state':
        # could use any table here
        query = "select huc12rng from huc_names order by huc12rng"
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

    hucs_dict_ps = copy.deepcopy(hucs_dict)

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

    model_length = 0



    # add habitat in in model
    if 'frst' in formvals:
        rank_data['frst'] = []
        query = "select huc_12, frst%sps, frst%sdt from lcscen_%s" % (
            year[2:],
            year[2:],
            scenario
        )
        # query2 = "select huc_12, %s%spct from lcscen_%s_pct" % (
        #     'frst',
        #     year[2:],
        #     scenario
        # )
        logger.debug(query)
        # model_wts.append(float(formvals['frst']))
        model_length += 1
        model_col = "%s %s - limit(%s)" % (
                col_names['frst'],
                col_names[scenario],
                formvals['frst']
            )
        model_cols.append(model_col)
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                # logger.debug(row)
                # if formvals['mode'] == 'single':
                #     try:
                #         hucs_dict[row[0]].append(row[1])
                #     except KeyError:
                #         pass
                #     continue
                if float(row[1]) > float(formvals['frst']):
                    above = 1
                    # rank = int(row[2])
                else:
                    above = 0
                    # rank = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ps[row[0]].append(float(row[1]))

                    # must follow this line to get hucs correct
                    rank_data['frst'].append(float(row[1]))
                except KeyError:
                    pass
        # pct_arr = []
        # with g.db.cursor() as cur:
        #     cur.execute(query2)
        #     for row in cur:
        #         if row[0] in hucs_dict:
        #             pct_arr.append(row[1])

        # pct_mean = statistics.mean(pct_arr)
        # logger.debug(int(pct_mean * 10) / 10.0)
        # mean_pct_areas['frst'] = int(pct_mean * 10) / 10.0

    if 'ftwt' in formvals:
        rank_data['ftwt'] = []

        query = "select huc_12, ftwt%sps, ftwt%sdt from lcscen_%s" % (
                year[2:],
                year[2:],
                scenario
        )

        # model_wts.append(float(formvals['ftwt']))
        logger.debug(query)
        model_length += 1
        model_cols.append(
            "%s %s - limit(%s)" % (
                col_names['ftwt'],
                col_names[scenario],
                formvals['ftwt'])
            )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                # if formvals['mode'] == 'single':
                #     try:
                #         hucs_dict[row[0]].append(row[1])
                #     except KeyError:
                #         pass
                #     continue
                if float(row[1]) > float(formvals['ftwt']):
                    above = 1
                    # rank = int(row[1])
                else:
                    above = 0
                    # rank = 0
                # logger.debug(row)
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ps[row[0]].append(float(row[1]))
                    rank_data['ftwt'].append(float(row[1]))
                except KeyError:
                    pass



    if 'hbwt' in formvals:
        rank_data['hbwt'] = []

        query = "select huc_12, hbwt%sps, hbwt%sdt from lcscen_%s" % (
                year[2:],
                year[2:],
                scenario
        )
        # model_wts.append(float(formvals['hbwt']))
        model_length += 1
        model_cols.append(
            "%s %s - limit(%s)" % (
                col_names['hbwt'],
                col_names[scenario],
                formvals['hbwt'])
            )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                # if formvals['mode'] == 'single':
                #     try:
                #         hucs_dict[row[0]].append(row[1])
                #     except KeyError:
                #         pass
                #     continue
                # logger.debug(row)
                if float(row[1]) > float(formvals['hbwt']):
                    above = 1
                    # rank = int(row[1])
                else:
                    above = 0
                    # rank = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ps[row[0]].append(float(row[1]))
                    rank_data['hbwt'].append(float(row[1]))
                except KeyError:
                    pass



    if 'open' in formvals:
        rank_data['open'] = []

        query = "select huc_12, open%sps, open%sdt from lcscen_%s" % (
                year[2:],
                year[2:],
                scenario
        )
        # model_wts.append(float(formvals['open']))
        model_length += 1
        model_cols.append(
            "%s %s - limit(%s)" % (
                col_names['open'],
                col_names[scenario],
                formvals['open'])
            )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                # if formvals['mode'] == 'single':
                #     try:
                #         hucs_dict[row[0]].append(row[1])
                #     except KeyError:
                #         pass
                #     continue
                # logger.debug(row)
                if float(row[1]) > float(formvals['open']):
                    above = 1
                    # rank = int(row[1])
                else:
                    above = 0
                    # rank = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ps[row[0]].append(float(row[1]))
                    rank_data['open'].append(float(row[1]))
                except KeyError:
                    pass



    if 'shrb' in formvals:
        rank_data['shrb'] = []

        query = "select huc_12, shrb%sps, shrb%sdt from lcscen_%s" % (
                year[2:],
                year[2:],
                scenario
        )
        # model_wts.append(float(formvals['shrb']))
        model_length += 1
        model_cols.append(
            "%s %s - limit(%s)" % (
                col_names['shrb'],
                col_names[scenario],
                formvals['shrb'])
            )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                # if formvals['mode'] == 'single':
                #     try:
                #         hucs_dict[row[0]].append(row[1])
                #     except KeyError:
                #         pass
                #     continue
                # logger.debug(row)
                if float(row[1]) > float(formvals['shrb']):
                    above = 1
                    # rank = int(row[1])
                else:
                    above = 0
                    # rank = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ps[row[0]].append(float(row[1]))
                    rank_data['shrb'].append(float(row[1]))
                except KeyError:
                    pass



    # add urban growth if included
    if 'urbangrth' in formvals:
        rank_data['urbangrth'] = []

        query = "select huc_12, urb%sps from urban" % year[2:]
        logger.debug(query)
        # model_wts.append(float(formvals['urbangrth']))
        model_cols.append("Urban Growth - limit(%s)" % formvals['urbangrth'])
        model_length += 1
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                # if formvals['mode'] == 'single':
                #     try:
                #         hucs_dict[row[0]].append(row[1])
                #     except KeyError:
                #         pass
                #     continue
                if float(row[1]) > float(formvals['urbangrth']):
                    above = 1
                    # rank = int(row[1])
                else:
                    above = 0
                    # rank = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ps[row[0]].append(float(row[1]))
                    rank_data['urbangrth'].append(float(row[1]))
                except KeyError:
                    pass

    # add fire suppression
    if 'firesup' in formvals:
        rank_data['firesup'] = []

        query = "select huc_12, fsupp%sps from fsupp" % year[2:]
        # logger.debug(query)
        # model_wts.append(float(formvals['firesup']))
        model_length += 1
        model_cols.append("Fire Suppresion - limit(%s)" % formvals['firesup'])
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                # if formvals['mode'] == 'single':
                #     try:
                #         hucs_dict[row[0]].append(row[1])
                #     except KeyError:
                #         pass
                #     continue
                if float(row[1]) > float(formvals['firesup']):
                    above = 1
                    # rank = int(row[1])
                else:
                    above = 0
                    # rank = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ps[row[0]].append(float(row[1]))
                    rank_data['firesup'].append(float(row[1]))
                except KeyError:
                    pass

    # add highway
    if 'hiway' in formvals:
        rank_data['hiway'] = []

        query = "select huc_12, rds%sps from DCLRds" % year[2:]
        # model_wts.append(float(formvals['hiway']))
        model_length += 1
        model_cols.append("Highway - limit(%s)" % formvals['hiway'])
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:
                # if formvals['mode'] == 'single':
                #     try:
                #         hucs_dict[row[0]].append(row[1])
                #     except KeyError:
                #         pass
                #     continue
                # logger.debug(row)
                # hucs_dict[row[0]].append(int(row[1]))
                if float(row[1]) > float(formvals['hiway']):
                    above = 1
                else:
                    above = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ps[row[0]].append(float(row[1]))
                    rank_data['hiway'].append(float(row[1]))
                except KeyError:
                    pass

    # add slr up
    if 'slr_up' in formvals:
        rank_data['slr_up'] = []

        query = "select huc_12, up%sps from SLRup" % year[2:]
        # model_wts.append(float(formvals['slr_up']))
        model_length += 1
        model_cols.append(
            "Sea Level rise Upland change - limit(%s)" % formvals['slr_up']
        )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:

                if float(row[1]) > float(formvals['slr_up']):
                    above = 1
                else:
                    above = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ps[row[0]].append(float(row[1]))
                    rank_data['slr_up'].append(float(row[1]))
                except KeyError:
                    pass

    # add sea level land cover
    if 'slr_lc' in formvals:
        rank_data['slr_lc'] = []

        query = "select huc_12, lc%sps from SLRlc" % year[2:]
        # model_wts.append(float(formvals['slr_lc']))
        model_length += 1
        model_cols.append(
            "Sea Level rise landcover change - limit(%s)" % formvals['slr_lc']
        )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:

                if float(row[1]) > float(formvals['slr_lc']):
                    above = 1
                else:
                    above = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ps[row[0]].append(float(row[1]))
                    rank_data['slr_lc'].append(float(row[1]))

                except KeyError:
                    pass

    # add triassic
    if 'triassic' in formvals:
        rank_data['triassic'] = []

        query = "select huc_12, triassic_ps from Triassic"
        # model_wts.append(float(formvals['triassic']))
        model_length += 1
        model_cols.append(
            "Triassic Basin - limit(%s)" % formvals['triassic']
        )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:

                if float(row[1]) > float(formvals['triassic']):
                    above = 1
                else:
                    above = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ps[row[0]].append(float(row[1]))
                    rank_data['triassic'].append(float(row[1]))

                except KeyError:
                    pass

    # add wind power
    if 'wind' in formvals:
        rank_data['wind'] = []

        query = "select huc_12, WPC_ps from WPC"
        # model_wts.append(float(formvals['wind']))
        model_length += 1
        model_cols.append(
            "Wind Power - limit(%s)" % formvals['wind']
        )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:

                if float(row[1]) > float(formvals['wind']):
                    above = 1
                else:
                    above = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ps[row[0]].append(float(row[1]))
                    rank_data['wind'].append(float(row[1]))

                except KeyError:
                    pass

    # add manure
    if 'manure' in formvals:
        rank_data['manure'] = []

        query = "select huc_12, manu_ps from Manu"
        # model_wts.append(float(formvals['manure']))
        model_length += 1
        model_cols.append(
            "Manure Application - limit(%s)" % formvals['manure']
        )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:

                if float(row[1]) > float(formvals['manure']):
                    above = 1
                else:
                    above = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ps[row[0]].append(float(row[1]))
                    rank_data['manure'].append(float(row[1]))

                except KeyError:
                    pass

    # add nitrogen
    if 'nitrofrt' in formvals:
        rank_data['nitrofrt'] = []

        query = "select huc_12, fert_ps from Fert"
        # model_wts.append(float(formvals['nitrofrt']))
        model_length += 1
        model_cols.append(
            "Synthetic Nitrogen - limit(%s)" % formvals['nitrofrt']
        )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:

                if float(row[1]) > float(formvals['nitrofrt']):
                    above = 1
                else:
                    above = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ps[row[0]].append(float(row[1]))
                    rank_data['nitrofrt'].append(float(row[1]))

                except KeyError:
                    pass

    # add total nitrogen
    if 'totnitro' in formvals:
        rank_data['totnitro'] = []

        query = "select huc_12, tdnt_ps from TDNT"
        # model_wts.append(float(formvals['totnitro']))
        model_length += 1
        model_cols.append(
            "Total Nitrogen - limit(%s)" % formvals['totnitro']
        )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:

                if float(row[1]) > float(formvals['totnitro']):
                    above = 1
                else:
                    above = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ps[row[0]].append(float(row[1]))
                    rank_data['totnitro'].append(float(row[1]))

                except KeyError:
                    pass

    # add total sulphur
    if 'totsulf' in formvals:
        rank_data['totsulf'] = []

        query = "select huc_12, tdst_ps from TDST"
        logger.debug(query)
        # model_wts.append(float(formvals['totsulf']))
        model_length += 1
        model_cols.append(
            "Total Sulfur - limit(%s)" % formvals['totsulf']
        )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:

                if float(row[1]) > float(formvals['totsulf']):
                    above = 1
                else:
                    above = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ps[row[0]].append(float(row[1]))
                    rank_data['totsulf'].append(float(row[1]))

                except KeyError:
                    pass

    # add forest health
    if 'insectdisease' in formvals:
        rank_data['insectdisease'] = []

        query = "select huc_12, FHlth_ps from FHlth"
        # model_wts.append(float(formvals['insectdisease']))
        model_length += 1
        model_cols.append(
            "Forest health - limit(%s)" % formvals['insectdisease']
        )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:

                if float(row[1]) > float(formvals['insectdisease']):
                    above = 1
                else:
                    above = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ps[row[0]].append(float(row[1]))
                    rank_data['insectdisease'].append(float(row[1]))

                except KeyError:
                    pass

    # add number of dams
    if 'ndams' in formvals:
        rank_data['ndams'] = []

        query = "select huc_12, nid_ps from NID"
        logger.debug(query)
        # model_wts.append(float(formvals['ndams']))
        model_length += 1
        model_cols.append(
            "# of dams - limit(%s)" % formvals['ndams']
        )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:

                if float(row[1]) > float(formvals['ndams']):
                    above = 1
                else:
                    above = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ps[row[0]].append(float(row[1]))
                    rank_data['ndams'].append(float(row[1]))

                except KeyError:
                    logger.debug(row[0])
                    # hucs_dict[row[0]].append(0)
                    # hucs_dict_ps[row[0]].append(0)
                    pass

    # add impaired biota
    if 'impairbiota' in formvals:
        rank_data['impairbiota'] = []

        query = "select huc_12, BioImpLen_ps from BioImpLen"
        logger.debug(query)
        # model_wts.append(float(formvals['impairbiota']))
        model_length += 1
        model_cols.append(
            "Impaired biota - limit(%s)" % formvals['impairbiota']
        )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:

                if float(row[1]) > float(formvals['impairbiota']):
                    above = 1
                else:
                    above = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ps[row[0]].append(float(row[1]))
                    rank_data['impairbiota'].append(float(row[1]))

                except KeyError:
                    pass

    # add impaired metals
    if 'impairmetal' in formvals:
        rank_data['impairmetal'] = []

        query = "select huc_12, MetImpLen_ps from MetImpLen"
        logger.debug(query)
        # model_wts.append(float(formvals['impairmetal']))
        model_length += 1
        model_cols.append(
            "Impaired metal - threshold(%s)" % formvals['impairmetal']
        )
        with g.db.cursor() as cur:
            cur.execute(query)
            for row in cur:

                if float(row[1]) > float(formvals['impairmetal']):
                    above = 1
                else:
                    above = 0
                try:
                    hucs_dict[row[0]].append(above)
                    hucs_dict_ps[row[0]].append(float(row[1]))
                    rank_data['impairmetal'].append(float(row[1]))

                except KeyError:
                    pass

    ##################################################################
    # start statistics
    # call function to get Composite Threat Count
    # also modifies hucs_dict_ps by reference
    ################################################################

    comp_thrt_dict = siteutils.make_composite_threat_count(
        hucs_dict, hucs_dict_ps, model_length
    )
    logger.debug(comp_thrt_dict)
    thrt_counts_summary = comp_thrt_dict['thrt_counts_summary']
    threat_summary = [thrt_counts_summary]


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

        logger.debug(report_row)

        report.append(report_row)

    # if formvals['mode'] != 'single':
    thrts_present = 0
    occurences = []
    severity = []
    for i, threat in enumerate(rank_data):
        logger.debug(threat)
        # logger.debug(model_cols[i + 1])
        report_row = [model_cols[i + 1]]
        cnts = summary_params_list[model_cols[i + 1]]
        mean = statistics.mean(cnts)
        occurences.append(mean)
        report_row.append(int(mean * 100) / 100.0)
        mean = statistics.mean(rank_data[threat])
        severity.append(mean)
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
        try:
            report_row.append(mean_pct_areas[threat])
        except KeyError:
            report_row.append('-')

        # add row to report
        report_rank.append(report_row)
        num_threats = i + 1

    other_stats = {}
    other_stats['comp_occ'] = int(
        sum(occurences) * 100 / num_threats
    )
    # other_stats['comp_sev'] = int(
    #     50
    #     # sum(severity) * 10 / num_threats**2
    # )
    # other_stats['risk_rank'] = (
    #     50
    #     # other_stats['comp_occ'] * other_stats['comp_sev']
    # )
    # if mode == 'aoi':
    logger.debug(occurences)
    logger.debug(severity)
    logger.debug(num_threats)
    logger.debug(other_stats)

    # logger.debug(i + 1)
    # logger.debug(thrts_present)
    thrts_included_msg = "%d of %d " % (thrts_present, i + 1)
    logger.debug(thrts_included_msg)

    # hucs_dict_ps - dict of hucs wiht ps vals and threat

    return {
        "res_arr": hucs_dict_ps,
        "col_hdrs": model_cols,
        "year": year,
        # "report": report,
        "report_rank": report_rank,
        "thrts_included_msg": thrts_included_msg,
        "threat_summary": threat_summary,
        "other_stats": other_stats
        }


def get_indiv_report(id, mymap_str, mode='state'):
    logger.debug(mymap_str)
    logger.debug(mode)
    col_name = ""
    legend_titles = {
        'frst': 'Forest Habitat (ha)',
        'ftwt': 'Wet Forest Habitat (ha)',
        'hbwt': 'Wet Herbaceous Habitat (ha)',
        'open': 'Open Habitat (ha)',
        'shrb': 'Scrub/Shrub Habitat (ha)',
        'urban': 'Urban Land Cover (ha)',
        'fire': 'Mean Urban Density w/in 5 mile radius',
        'trans': 'Mean Length/Area of Major Highways (m/ha)',
        "nutrient:manu": "Manure Application (kg/ha/yr)",
        "nutrient:fert": "Syn. Nitrogen Fertilizer Application (kg/ha/yr)",
        "nutrient:td_n_t": "Total Nitrogen Deposition (kg/ha/yr)",
        "nutrient:td_s_t": "Total Sulfur Deposition (kg/ha/yr)",
        'frsthlth': "Forest Insect/Disease Risk (ha)",
        'energydev': "Triassic basin (ha)",
        "water:bioimplen": "Biota Impairments (km*stream density)",
        "water:metimplen": "Metal Impariments (km*stream density)",
        "water:NID": "Number of Dams (n)",
        'wind': "Wind Power Class (mean)",
        'slr_lc': "Terrestrial Landcover Change (ha)",
        'slr_up': "Undeveloped Upland Change (ha)"
    }
    year = 10
    try:
        mymap = mymap_str.split(":")[0]

        # set year and param2 for queries where it is not year
        year = mymap_str.split(":")[1]
        param2 = mymap_str.split(":")[1]
        scenario = mymap_str.split(":")[2]
    except IndexError:
        pass
    try:
        year = int(year)
    except ValueError:
        year = 10

    # try to assign column name from dict copied from javascript
    try:
        col_name = legend_titles[mymap]
    except KeyError:
        try:
            col_name = legend_titles[mymap_str]
        except KeyError:
            pass

    results_dict = collections.OrderedDict()
    # hucs_dict = collections.OrderedDict()
    if int(id) == 0 or mode == 'state':
        # could use any table here
        query = "select huc_12 from huc12nc order by huc_12"
        with g.db.cursor() as cur:
            cur.execute(query)
            hucs_row = cur.fetchall()
            hucs = [x[0] for x in hucs_row]

    elif mode == 'aoi':
        with g.db.cursor() as cur:
            cur.execute("select huc12s from aoi_results where pk = %s", (id, ))
            huc12_str = cur.fetchone()
        hucs = huc12_str[0].split(", ")

    elif mode == '12k':
        with g.db.cursor() as cur:
            cur.execute(
                "select huc12s_12k from aoi_results where pk = %s", (id, )
            )
            huc12_str = cur.fetchone()
        hucs = huc12_str[0].split(", ")

    elif mode == '5k':
        with g.db.cursor() as cur:
            cur.execute(
                "select huc12s_5k from aoi_results where pk = %s", (id, )
            )
            huc12_str = cur.fetchone()
        hucs = huc12_str[0].split(", ")

    # hucs_dict_ps = copy.deepcopy(hucs_dict)
    # results_list = []
    # rang = {}

    # logger.debug(request.args)

    if mymap in [
                "frst", 'ftwt', 'hbwt', 'open', 'shrb'
            ]:
        query1 = "select huc_12, %s%sdt from lcscen_%s" % (
            mymap, year, scenario
            )
        legend_param = mymap

    elif mymap in ['urban']:
        query1 = "select huc_12, urb%sdt from urban" % year
        legend_param = mymap
    elif mymap in ['fire']:
        query1 = "select huc_12, fsupp%sdt from fsupp" % year
        legend_param = mymap
    elif mymap in ['trans']:
        query1 = "select huc_12, rds%sdt from DCLRds" % year
        legend_param = mymap
    elif mymap_str in ['nutrient:manu']:
        query1 = "select huc_12, manu_dt from Manu"
        legend_param = mymap_str
    elif mymap_str in ['nutrient:fert']:
        query1 = "select huc_12, fert_dt from Fert"
        legend_param = mymap_str
    elif mymap_str in ['nutrient:td_n_t']:
        query1 = "select huc_12, tdnt_dt from TDNT"
        legend_param = mymap_str
    elif mymap_str in ['nutrient:td_s_t']:
        query1 = "select huc_12, tdst_dt from TDST"
        legend_param = mymap_str
    elif mymap_str in ['water:NID']:
        query1 = "select huc_12, nid_dt from NID"
        legend_param = mymap_str
    elif mymap in ['frsthlth']:
        query1 = "select huc_12, FHlth_dt from FHlth"
        legend_param = mymap
    elif mymap in ['energydev']:
        query1 = " select huc_12, triassic_dt from Triassic"
        legend_param = mymap
    elif mymap in ['wind']:
        query1 = "select huc_12, WPC_dt from WPC"
        legend_param = mymap
    elif mymap in ['slr_up']:
        query1 = "select huc_12, up%sdt from  SLRup" % year
        legend_param = mymap
    elif mymap in ['slr_lc']:
        query1 = "select huc_12, lc%sdt from SLRlc" % year
        legend_param = mymap
    elif mymap_str in ['water:bioimplen']:
        query1 = "select huc_12, BioImpLen_dt from BioImpLen"
        legend_param = mymap_str
    elif mymap_str in ['water:metimplen']:
        query1 = "select huc_12, MetImpLen_dt from MetImpLen"
        legend_param = mymap_str

    res_arr = []
    logger.debug(query1)

    with g.db.cursor() as cur:
        cur.execute(query1)
        for row in cur:
            if row[0] in hucs:
                # logger.debug(row[0])
                results_dict[row[0]] = float(row[1])
                res_arr.append(float(row[1]))

    mean = int(statistics.mean(res_arr) * 1000) / 1000.0
    try:
        stdev = int(statistics.stdev(res_arr) * 1000) / 1000.0
    except statistics.StatisticsError:
        stdev = 'na'
    res_max = min(res_arr)
    res_min = max(res_arr)
    num_hucs = len(res_arr)

    stats = [mean, stdev, res_max, res_min]
    res_arr = [
            [x, results_dict[x]]
            for x in results_dict
        ]

    # logger.debug(results_dict)
    logger.debug(mymap)
    logger.debug(legend_param)

    # first 2 params for indiv map
    return {
        "legend_param": legend_param,
        "res_arr": res_arr,
        'year': year,
        "stats": stats,
        "results_dict": results_dict,
        "col_name": col_name,
        "num_hucs": num_hucs

    }


def preview_map(data):
    year = data.get('year')[2:]
    mymap = data.get('map')
    scenario = data.get('scenario')
    limit = float(data.get('limit'))
    logger.debug(limit)
    results_dict = collections.OrderedDict()
    res_arr = []
    query = "select huc12rng from huc_names order by huc12rng"
    with g.db.cursor() as cur:
        cur.execute(query)
        hucs_row = cur.fetchall()
        hucs = [x[0] for x in hucs_row]

    # if mymap in [
    #             "frst", 'ftwt', 'hbwt', 'open', 'shrb'
    #         ]:
    #     query1 = "select huc_12, %s%sha from lcscen_%s_ha" % (
    #         mymap, year, scenario
    #         )
    if mymap == 'urbangrth_limit':
        query1 = "select huc_12, urb%sdt, urb%sps from urban" % (year, year)
        # legend_param = 'urban'
    elif mymap == 'firesup_limit':
        query1 = "select huc_12,fsupp%sdt, fsupp%sps from fsupp" % (year, year)
    elif mymap == 'frst_limit':
        query1 = "select huc_12, frst%sdt, frst%sps from lcscen_%s" % (
            year, year, scenario
        )
    elif mymap == 'ftwt_limit':
        query1 = "select huc_12, ftwt%sdt, ftwt%sps from lcscen_%s" % (
            year, year, scenario
        )
    elif mymap == 'hbwt_limit':
        query1 = "select huc_12, hbwt%sdt, hbwt%sps from lcscen_%s" % (
            year, year, scenario
        )
    elif mymap == 'open_limit':
        query1 = "select huc_12, open%sdt, open%sps from lcscen_%s" % (
            year, year, scenario
        )
    elif mymap == 'shrb_limit':
        query1 = "select huc_12, shrb%sdt, shrb%sps from lcscen_%s" % (
            year, year, scenario
        )
    elif mymap == 'hiway_limit':
        query1 = "select huc_12, rds%sdt, rds%sps from DCLRds" % (
            year, year
        )
    elif mymap == 'slr_up_limit':
        query1 = "select huc_12, up%sdt, up%sps from SLRup" % (
            year, year
        )
    elif mymap == 'slr_lc_limit':
        query1 = "select huc_12, lc%sdt, lc%sps from SLRlc" % (
            year, year
        )
    elif mymap == 'triassic_limit':
        query1 = "select huc_12, triassic_dt, triassic_ps from Triassic"
    elif mymap == 'wind_limit':
        query1 = "select huc_12, wpc_dt, wpc_ps from WPC"
    elif mymap == 'manure_limit':
        query1 = "select huc_12, manu_dt, manu_ps from manu"
    elif mymap == 'nitrofrt_limit':
        query1 = "select huc_12, fert_dt, fert_ps from fert"
    elif mymap == 'totnitro_limit':
        query1 = "select huc_12, tdnt_dt, tdnt_ps from tdnt"
    elif mymap == 'totsulf_limit':
        query1 = "select huc_12, tdst_dt, tdst_ps from tdst"
    elif mymap == 'insectdisease_limit':
        query1 = "select huc_12, fhlth_dt, fhlth_ps from fhlth"
    elif mymap == 'ndams_limit':
        query1 = "select huc_12, nid_dt, nid_ps from nid"
    elif mymap == 'impairbiota_limit':
        query1 = "select huc_12, bioimplen_dt, bioimplen_ps from bioimplen"
    elif mymap == 'impairmetal_limit':
        query1 = "select huc_12, metimplen_dt, metimplen_ps from metimplen"

    logger.debug(query1)
    with g.db.cursor() as cur:
        cur.execute(query1)
        for row in cur:
            # logger.debug(row)
            if row[0] in hucs:
                # logger.debug(row[0])
                # results_dict[row[0]] = float(row[1])
                if float(row[2]) > float(limit):
                    res_arr.append(float(row[1]))
                    results_dict[row[0]] = float(row[1])
                else:
                    res_arr.append(0)
                    results_dict[row[0]] = 0
    return {
        # "legend_param": legend_param,
        "res_arr": res_arr,
        'year': year,
        # "stats": stats,
        "results_dict": results_dict
        # "col_name": col_name,
        # "num_hucs": num_hucs

    }
