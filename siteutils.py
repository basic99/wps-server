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


def qryptbufferjson(lon, lat):
    """
    select ST_AsGeoJSON(ST_Transform(ST_Buffer(ST_Transform(
        ST_SetSRID(ST_Point(-78.867, 35.968),4326), 32119), 3000), 4326))
    """

    query = "select ST_AsGeoJSON(ST_Transform(ST_Buffer(ST_Transform("
    query += "ST_SetSRID(ST_Point(%s, %s),4326), 32119), 3000)"
    query += ", 4326))"
    logger.debug(lon)
    logger.debug(lat)
    logger.debug(query % (lon, lat))
    with g.db.cursor() as cur:
        cur.execute(query, (lon, lat))
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
    logger.debug(thrt_counts_summary)
    return {
        "thrt_counts_summary": thrt_counts_summary
    }


def make_report_threats_summary(
            model_cols, hucs_dict, rank_data, mean_pct_areas
        ):
    summary_params_list = collections.OrderedDict()
    # summary_params_list['Threat Count'] = [
    #     hucs_dict[x][-1] for x in hucs_dict
    # ]
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
        logger.debug(model_cols[i + 1])
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
    thrts_included_msg = "%d of %d " % (thrts_present, i + 1)

    return {
        "report_rank": report_rank,
        "num_threats": num_threats,
        "occurences": occurences,
        "thrts_included_msg": thrts_included_msg

    }
