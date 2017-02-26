import logging
import os
import hashlib
import psycopg2
import psycopg2.extras
from flask import g
import json
import random
import string
from email.message import Message
import email.utils
import smtplib
import statistics
import collections
import math
import model
import tempfile
import csv
import zipfile


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


def addnewuser(request):
    """Process form from create new user page.
    Update table users with form data and md5 hash for password.
    If sql fails due to key constraints return appropriate error msg.
     """
    logger.debug(request)

    username = request.get('UserName').strip()
    firstname = request.get('FirstName', 'john').strip()
    lastname = request.get('LastName', 'doe').strip()
    affil = request.get('Affil', 'self').strip()
    email = request.get('Email').strip()

    passwd = request.get('Password').strip()
    digest = hashlib.md5()
    digest.update(passwd)
    hash_passwd = digest.hexdigest()

    query = """insert into users(firstname, lastname, affiliate, username,
        email, password, dateadded) values (%s, %s, %s, %s, %s, %s,
         CURRENT_DATE)"""

    errormsg1 = """You have already registered with this email.
                If you don't recall your username and password you can
                request a reset on the login tab of the app."""
    errormsg2 = """This username is already in use. Please try to register
                again with a different username. """
    errormsg3 = """Registration error. """
    successmsg = """Registration completed. You can now login
                with your username and password on the login tab of the app."""

    if(len(passwd) < 6 or len(username) < 2 or len(email) < 5):
        return errormsg3

    try:
        with g.db.cursor() as cur:
            cur.execute(
                query, (
                    firstname, lastname, affil, username, email, hash_passwd
                    )
                )
        g.db.commit()
    except psycopg2.IntegrityError as e:
        if "users_email_key" in str(e.args):
            return errormsg1
        elif "users_username_key" in str(e.args):
            return errormsg2
    return successmsg


def userauth(request):
    logger.debug(request)
    username = request.get('loginUsername').strip()
    passwd = request.get('loginPassword').strip()

    digest = hashlib.md5()
    digest.update(passwd)
    hash_passwd = digest.hexdigest()

    query = """select * from users where username = %s
    and password = %s"""

    with g.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        try:
            cur.execute(query, (username, hash_passwd))
        except Exception, e:
            logger.debug(e.pgerror)
        rec = cur.fetchone()

    try:
        return json.dumps({
            'success': True,
            'username': rec['username'].strip(),
            'firstname': rec['firstname'].strip()
            })
    except TypeError:
        return json.dumps({'success': False})


def passwdreset(emailaddr):
    query = """select * from users where email = %s """
    with g.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(query, (emailaddr,))
        logger.debug(cur.rowcount)
        if cur.rowcount == 0:
            return json.dumps({
                'success': True,
                'msg': "This email has not registered."
                })
        rec = cur.fetchone()

    pk = rec['pk']
    chars = string.ascii_letters + string.digits
    pwd = ''.join(random.choice(chars) for i in range(8))
    digest = hashlib.md5()
    digest.update(pwd)
    hash_passwd = digest.hexdigest()
    logger.debug(pwd)
    query = """update users set password = %s where pk = %s"""
    with g.db.cursor() as cur:
        cur.execute(query, (hash_passwd, pk))
    g.db.commit()

    message = """
You have requested a password reset for \
login to the NC threats \
analysis web site.

Username:  %s
Password:  %s
    """ % (rec['username'], pwd)

    msg = Message()
    msg['To'] = emailaddr
    msg['From'] = 'BaSIC_WebMaster@ncsu.edu'
    msg['Subject'] = 'Requested password reset'
    msg['Date'] = email.utils.formatdate(localtime=1)
    msg['Message-ID'] = email.utils.make_msgid()
    msg.set_payload(message)

    s = smtplib.SMTP('127.0.0.1')
    s.sendmail('BaSIC_WebMaster@ncsu.edu', emailaddr, msg.as_string())

    return json.dumps({
        'success': True,
        'username': rec['username'],
        'pass': pwd,
        'msg': "Check your email."
        })


def userpage(username):
    query = """select * from usersaoi where username = %s """
    results = []
    with g.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(query, (username,))
        for rec in cur:
            results.append({'aoiid': rec['aoiid'], 'aoidesc': rec['aoidesc']})
    return {'username': username, 'results': results}


def passwdchng(username, passwd):
    if len(passwd) < 6:
            return json.dumps({'success': False})
    digest = hashlib.md5()
    digest.update(passwd)
    hash_passwd = digest.hexdigest()
    query = """update users set password = %s where username = %s"""
    with g.db.cursor() as cur:
        cur.execute(query, (hash_passwd, username))
        if cur.rowcount == 1:
            g.db.commit()
            return json.dumps({'success': True})
        else:
            g.db.rollback()
            return json.dumps({'success': False})


def qrypttojson(lon, lat, lyr):

    """select huc6 from huc6nc where ST_Contains(wkb_geometry,
        ST_Transform(ST_SetSRID(ST_Point(-9108450, 4230555),900913),4326)); """
    qry_col = lyr
    if lyr not in [
            'huc2', 'huc4', 'huc6', 'huc8', 'huc10', 'huc_12', 'co_num', 'bcr'
    ]:
        logger.info('invalid layer name')
        return
    if lyr in ['huc2', 'huc4', 'huc6', 'huc8', 'huc10']:
        qry_tbl = lyr + "nc"
    elif lyr == 'huc_12':
        qry_tbl = 'huc12nc'
    elif lyr == 'co_num':
        qry_tbl = 'counties'
    elif lyr == 'bcr':
        qry_tbl = 'nc_bcr'

    query = "select ST_AsGeoJSON(wkb_geometry, 6), "
    query += qry_col + " from " + qry_tbl
    query += " where ST_Contains(wkb_geometry, "
    query += "ST_Transform(ST_SetSRID(ST_Point(%s, %s),900913),4326)) "
    logger.debug(query % (lon, lat))
    with g.db.cursor() as cur:
        cur.execute(query, (lon, lat))
        res = cur.fetchone()
        the_geom = json.loads(res[0])
        the_huc = str(res[1])
    logger.debug(the_geom['type'])
    # logger.debug(the_geom)
    geojson_obj = {
        "type": "Feature",
        "geometry": {
            "type": the_geom['type'],
            "coordinates": the_geom['coordinates']
        },
        "properties": {
            "name": the_huc
            }
        }
    ret_dict = {
        "the_geom": geojson_obj,
        "the_huc": the_huc
    }
    # logger.debug(ret_dict)
    return json.dumps(ret_dict)


def qryptbufferjson(lon, lat, ptradius):
    """
    select ST_AsGeoJSON(ST_Transform(ST_Buffer(ST_Transform(
        ST_SetSRID(ST_Point(-78.867, 35.968),4326), 32119), 3000), 4326))
    """

    query = "select ST_AsGeoJSON(ST_Transform(ST_Buffer(ST_Transform("
    query += "ST_SetSRID(ST_Point(%s, %s),4326), 32119), %s)"
    query += ", 4326))"
    logger.debug(lon)
    logger.debug(lat)
    buffmeters = 1000 * float(ptradius)
    # logger.debug(query % (lon, lat, buffmeters))
    with g.db.cursor() as cur:
        cur.execute(query, (lon, lat, buffmeters))
        res = cur.fetchone()
        the_geom = json.loads(res[0])

    geojson_obj = {
        "type": "Feature",
        "geometry": {
            "type": the_geom['type'],
            "coordinates": the_geom['coordinates']
        }
    }
    ret_dict = {
        "the_geom": geojson_obj
    }
    logger.debug(ret_dict)
    return json.dumps(ret_dict)


def make_composite_threat_count(hucs_dict, hucs_dict_ps, model_length):
    """
    Function creates report for composite threat count. Also
    adds Threat Count column to hucs_dict_ps.

     """
    threat_count = []
    for huc in hucs_dict:
        threat = 0
        # threat_rnk = 0

        for idx in range(model_length):
            # logger.debug(idx)
            try:
                threat += float(hucs_dict[huc][idx + 1])
                # threat_rnk += float(hucs_dict_ps[huc][idx + 1])
            except IndexError:
                logger.debug(huc)
                logger.debug(idx)

        threat_raw = threat
        # hucs_dict[huc].append(threat_raw)
        hucs_dict_ps[huc].append(int(threat_raw))
        # threat_rank.append(float(threat_rnk) / (idx + 1))
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
    # logger.debug(thrt_counts_summary)
    return {
        "thrt_counts_summary": thrt_counts_summary
    }


def make_report_threats_summary(
    model_cols, hucs_dict, rank_data, dt_data
):
    """
    model_cols -list of column headers for AOI Threat Summary by HUC12
    hucs_dict -dict of huc12 - list with first item huc and rest threats 0/1
    rank_data -dict of threat name, eg firesup - list of threats ps percents
    dt_data - same as rank_data but for dt as opposed to sv

    returns:
    report_rank - occurence and severity stats per threat
    occurences - used to calculate Occurrence Rating
    num_threats - total number present
    thrts_included_msg - Distinct Threat Count text


    """
    summary_params_list = collections.OrderedDict()
    for idx, model_col in enumerate(model_cols):
        if idx != 0:
            summary_params_list[model_col] = [
                hucs_dict[x][idx] for x in hucs_dict
            ]
    # logger.debug(summary_params_list)
    report = []
    report_rank = []
    # for row in summary_params_list:
    #     report_row = [str(row)]
    #     mean = statistics.mean(summary_params_list[row])
    #     report_row.append(int(mean * 100) / 100.0)
    #     try:
    #         stdev = statistics.stdev(summary_params_list[row])
    #         report_row.append(int(stdev * 10000) / 10000.0)
    #     except statistics.StatisticsError:
    #         report_row.append('na')
    #     row_min = min(summary_params_list[row])
    #     report_row.append(row_min)
    #     row_max = max(summary_params_list[row])
    #     report_row.append(row_max)

    #     logger.debug(report_row)

    #     report.append(report_row)

    dt_labels = {
        "frst": "% lost since 2000",
        "ftwt": "% lost since 2000",
        "hbwt": "% lost since 2000",
        "open": "% lost since 2000",
        "shrb": "% lost since 2000",
        "urbangrth": "% area",
        "firesup": "urban density",
        "hiway": "meters/hectares",
        "slr_up": "% lost since 2000",
        "slr_lc": "% lost since 2000",
        "triassic": "% area",
        "wind": "wind power class",
        "manure": "kg/ha/yr",
        "nitrofrt": "kg/ha/yr",
        "totnitro": "kg/ha/yr",
        "totsulf": "kg/ha/yr",
        "insectdisease": "% area impacted",
        "ndams": "n",
        "impairbiota": "km*stream density",
        "impairmetal": "km*stream density"
    }


    # if formvals['mode'] != 'single':
    thrts_present = 0
    occurences = []
    severity = []
    for i, threat in enumerate(rank_data):
        # logger.debug(threat)
        # logger.debug(model_cols[i + 1])
        report_row = [model_cols[i + 1]]
        cnts = summary_params_list[model_cols[i + 1]]
        mean = statistics.mean(cnts)
        # logger.debug(mean)
        if mean > 0:
            thrts_present += 1
        occurences.append(mean)
        report_row.append(math.ceil(mean * 100) / 100.0)
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
        # if row_max > 0:
        #     thrts_present += 1
        report_row.append(row_max)
        try:
            dt_mean = statistics.mean(dt_data[threat])
            dt_text = str(int(dt_mean * 100) / 100.0) + " " + dt_labels[threat]
            report_row.append(dt_text)
        except KeyError:
            logger.debug(threat)
            report_row.append('-')

        # add row to report
        report_rank.append(report_row)
    num_threats = i + 1
    thrts_included_msg = "%d of %d " % (thrts_present, num_threats)
    # logger.debug(num_threats)

    return {
        "report_rank": report_rank,
        "num_threats": num_threats,
        "occurences": occurences,
        "thrts_included_msg": thrts_included_msg

    }


def aoi_spreadsheet(id, query):
    pass
    logger.debug("aoi_spreadsheet")
    if id == 0:
        report_results = model.get_threat_report2(id, query)
        report_results['samplesize'] = len(report_results['res_arr'])
        del(report_results["res_arr"])
        a = report_results["thrts_included_msg"].split("of")
        report_results["thrts_included_msg"] = a

        results_complete = {
            "state": report_results
        }
        # return json.dumps(report_results, indent=4)

    else:
        results_state = model.get_threat_report2(id, query)
        results_aoi = model.get_threat_report2(id, query, 'aoi')
        results_5k = model.get_threat_report2(id, query, '5k')
        results_12k = model.get_threat_report2(id, query, '12k')

        results_state['samplesize'] = len(results_state['res_arr'])
        del(results_state["res_arr"])
        a = results_state["thrts_included_msg"].split("of")
        results_state["thrts_included_msg"] = a

        results_aoi['samplesize'] = len(results_aoi['res_arr'])
        del(results_aoi["res_arr"])
        a = results_aoi["thrts_included_msg"].split("of")
        results_aoi["thrts_included_msg"] = a

        results_5k['samplesize'] = len(results_5k['res_arr'])
        del(results_5k["res_arr"])
        a = results_5k["thrts_included_msg"].split("of")
        results_5k["thrts_included_msg"] = a

        results_12k['samplesize'] = len(results_12k['res_arr'])
        del(results_12k["res_arr"])
        a = results_12k["thrts_included_msg"].split("of")
        results_12k["thrts_included_msg"] = a

        results_complete = collections.OrderedDict([
            ("aoi", results_aoi),
            ("5k", results_5k),
            ("12k", results_12k),
            ("state", results_state)
        ])
        # {
        #     "state": results_state,
        #     "aoi": results_aoi,
        #     "5k": results_5k,
        #     "12k": results_12k
        # }

    fieldnames = [
        "Report Year",
        "Summary",
        "# swds",
        "DTC",
        "MTC",
        "Occr",
        "CTC mean",
        "CTC sd",
        "CTC min",
        "CTC max"
    ]

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".csv",
        dir='/tmp',
        prefix='ncthreats'
    ) as temp:
        csvwriter = csv.DictWriter(temp, fieldnames=fieldnames)
        csvwriter.writeheader()
        for summary in results_complete:
            row = {}
            row["Report Year"] = results_complete[summary]['year']
            row["Summary"] = summary
            row["# swds"] = results_complete[summary]["samplesize"]
            row["DTC"] = results_complete[summary]["thrts_included_msg"][0].strip()
            row["MTC"] = results_complete[summary]["thrts_included_msg"][1].strip()
            row["Occr"] = results_complete[summary]["other_stats"]['comp_occ']
            row["CTC mean"] = results_complete[summary]["threat_summary"][0][1]
            row["CTC sd"] = results_complete[summary]["threat_summary"][0][2]
            row["CTC min"] = results_complete[summary]["threat_summary"][0][3]
            row["CTC max"] = results_complete[summary]["threat_summary"][0][4]

            csvwriter.writerow(row)
        temp_name1 = temp.name

    ##################################################################
    # start ssheet2
    ##################################################################

    fieldnames = [
        "Report Year",
        "Summary",
        "Threat Name",
        "Occurrence",
        "Severity",
        "Severity s.d.",
        "Severity min.",
        "Severity max.",
        "Data Mean"
    ]

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".csv",
        dir='/tmp',
        prefix='ncthreats'
    ) as temp:
        csvwriter = csv.DictWriter(temp, fieldnames=fieldnames)
        csvwriter.writeheader()
        for summary in results_complete:
            row = {}
            for rept_rank in results_complete[summary]['report_rank']:
                row["Report Year"] = results_complete[summary]['year']
                row["Summary"] = summary
                row["Threat Name"] = rept_rank[0]
                row["Occurrence"] = rept_rank[1]
                row["Severity"] = rept_rank[2]
                row["Severity s.d."] = rept_rank[3]
                row["Severity min."] = rept_rank[4]
                row["Severity max."] = rept_rank[5]
                row["Data Mean"] = rept_rank[6]
                csvwriter.writerow(row)

        temp_name2 = temp.name

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".zip",
        dir='/tmp',
        prefix='ncthreats'
    ) as temp:
        zf = zipfile.ZipFile(temp, mode='w')
        zf.write(temp_name1, "Summary.csv")
        zf.write(temp_name2, "ThreatData.csv")
        zf.write("/var/www/wsgi/wps-server/templates/README.txt", "README.txt")
        zf.close()

    return temp.name


def batch_spreadsheet(id, query_str):
    logger.debug("batch_spreadsheet")
    query = "select * from batch where batch_id = %s order by name"
    batch_results = collections.OrderedDict()
    with g.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(query, (id, ))
        for row in cur:
            name = row['name']
            aoi_id = row['resource'].split("/")[-1]
            logger.info(name)
            logger.debug(aoi_id)

            results_aoi = model.get_threat_report2(aoi_id, query_str, 'aoi')
            results_5k = model.get_threat_report2(aoi_id, query_str, '5k')
            results_12k = model.get_threat_report2(aoi_id, query_str, '12k')

            results_aoi['samplesize'] = len(results_aoi['res_arr'])
            del(results_aoi["res_arr"])
            a = results_aoi["thrts_included_msg"].split("of")
            results_aoi["thrts_included_msg"] = a

            results_5k['samplesize'] = len(results_5k['res_arr'])
            del(results_5k["res_arr"])
            a = results_5k["thrts_included_msg"].split("of")
            results_5k["thrts_included_msg"] = a

            results_12k['samplesize'] = len(results_12k['res_arr'])
            del(results_12k["res_arr"])
            a = results_12k["thrts_included_msg"].split("of")
            results_12k["thrts_included_msg"] = a

            batch_results[name] = collections.OrderedDict()
            batch_results[name]['aoi'] = results_aoi
            batch_results[name]['5k'] = results_5k
            batch_results[name]['12k'] = results_12k
            # batch_results[name]['samplesize'] = samplesize

    results = []
    for polygon in batch_results:
        for summary in batch_results[polygon]:
            row = {}
            row["Report Year"] = batch_results[polygon][summary]['year']
            row['Polygon'] = polygon
            row["Summary"] = summary
            row["# swds"] = batch_results[polygon][summary]["samplesize"]
            row["DTC"] = batch_results[polygon][summary]["thrts_included_msg"][0].strip()
            row["MTC"] = batch_results[polygon][summary]["thrts_included_msg"][1].strip()
            row["Occr"] = batch_results[polygon][summary]["other_stats"]['comp_occ']
            row["CTC mean"] = batch_results[polygon][summary]["threat_summary"][0][1]
            row["CTC sd"] = batch_results[polygon][summary]["threat_summary"][0][2]
            row["CTC min"] = batch_results[polygon][summary]["threat_summary"][0][3]
            row["CTC max"] = batch_results[polygon][summary]["threat_summary"][0][4]

            results.append(row)

    fieldnames = [
        "Report Year",
        "Polygon",
        "Summary",
        "# swds",
        "DTC",
        "MTC",
        "Occr",
        "CTC mean",
        "CTC sd",
        "CTC min",
        "CTC max"
    ]
    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".csv",
        dir='/tmp',
        prefix='ncthreats'
    ) as temp:
        csvwriter = csv.DictWriter(temp, fieldnames=fieldnames)
        csvwriter.writeheader()
        csvwriter.writerows(results)
        temp_name1 = temp.name

    ############################################################
    # start ss 2
    #######################################################

    fieldnames = [
        "Report Year",
        'Polygon',
        "Summary",
        "Threat Name",
        "Occurrence",
        "Severity",
        "Severity s.d.",
        "Severity min.",
        "Severity max.",
        "Data Mean"
    ]

    results = []
    for polygon in batch_results:
        for summary in batch_results[polygon]:

            rept_rank = batch_results[polygon][summary]['report_rank']
            for threat in rept_rank:
                row = {}
                # logger.debug(threat)
                row["Report Year"] = batch_results[polygon][summary]['year']
                row['Polygon'] = polygon
                row["Summary"] = summary
                row["Threat Name"] = threat[0]
                row["Occurrence"] = threat[1]
                row["Severity"] = threat[2]
                row["Severity s.d."] = threat[3]
                row["Severity min."] = threat[4]
                row["Severity max."] = threat[5]
                row["Data Mean"] = threat[6]


                results.append(row)
    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".csv",
        dir='/tmp',
        prefix='ncthreats'
    ) as temp:
        csvwriter = csv.DictWriter(temp, fieldnames=fieldnames)
        csvwriter.writeheader()
        csvwriter.writerows(results)
        temp_name2 = temp.name

    logger.debug(temp_name1)
    logger.debug(temp_name2)

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".zip",
        dir='/tmp',
        prefix='ncthreats'
    ) as temp:

        zf = zipfile.ZipFile(temp, mode='w')
        zf.write(temp_name1, "Summary.csv")
        zf.write(temp_name2, "ThreatData.csv")
        zf.write("/var/www/wsgi/wps-server/templates/README.txt", "README.txt")
        zf.close()

    return temp.name
