import logging
import os
import hashlib
import psycopg2
import psycopg2.extras
from flask import g


cwd = os.path.dirname(os.path.realpath(__file__))
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler(cwd + '/logs/logs.log')
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
fh.setFormatter(formatter)
logger.addHandler(fh)

def addnewuser(request):

    username = request.get('UserName').strip()
    firstname = request.get('FirstName').strip()
    lastname = request.get('LastName').strip()
    affil = request.get('Affil').strip()
    email = request.get('Email').strip()

    passwd = request.get('Password').strip()
    digest = hashlib.md5()
    digest.update(passwd)
    hash_passwd = digest.hexdigest()

    query = """insert into users(firstname, lastname, affiliate, username,
        email, password, dateadded) values (%s, %s, %s, %s, %s, %s,
         CURRENT_DATE)"""
    try:
        with g.db.cursor() as cur:
            cur.execute(
                query, (firstname, lastname, affil, username, email, hash_passwd)
                )
        g.db.commit()
    except psycopg2.IntegrityError as e:
        if "users_email_key" in str(e.args):
            return "duplicate  email"
        elif "users_username_key" in str(e.args):
            return "duplicate username"
    return "user added"
