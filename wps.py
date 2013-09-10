from flask import Flask
from flask import request
from flask import url_for
import time
import gevent
from flask import copy_current_request_context, g
import psycopg2

from gevent import monkey
monkey.patch_all()

def connect_db():
    return psycopg2.connect("dbname=ncthreats user=postgres")

app = Flask(__name__)

@app.before_request
def before_request():
    g.db = connect_db()

@app.teardown_request
def teardown_request(exception):
    db = getattr(g, 'db', None)
    if db is not None:
        db.close()
        
@app.route('/wps', methods=['POST', ])
def hello_world():
    cur = g.db.cursor()
    
    return request.form['gml']
    #return "rest wps process"

if __name__ == '__main__':
    app.run(debug = True)