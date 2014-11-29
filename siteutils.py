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

    query = "select " + lyr + " from " + lyr +"nc where ST_Contains(wkb_geometry, ST_Transform(ST_SetSRID(ST_Point(%s, %s),900913),4326)) "
    with g.db.cursor() as cur:
        cur.execute(query, ( lon, lat))
        res = cur.fetchone()[0]

    return json.dumps({'lon': lon, "lat": lat, "lyr": lyr, "res": res})

