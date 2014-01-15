"""Main file to run Flask app.

The web app is a GIS app that uses REST architecture.
It is based loosely on the concept of a WPS(Web Processing Service),
but does not comply with that standard.
Create a resource that is a list of huc12s(12 digit hydrologic units)
that overlap the input geometry which is input as GML file.
Allow access to this resource.

"""

from flask import Flask
from flask import request
from flask import url_for
from flask import copy_current_request_context, g, render_template

#import time
import gevent
import psycopg2
import psycopg2.extras
import nchuc12
import json

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
def post_aoi():
    """Create a new resource with post request.

    Create nchuc12 object to make the calculations and
    pass the post data of gml and text description.
    Return identifier and extent as json, an http response of 201
    and location header with resource location.

    """
    huc = nchuc12.NCHuc12()
    huc.aoi_desc = request.form['text']
    huc.gml = request.form['gml']
    aoi_id = huc.execute()

    resource = url_for('resource_aoi', id=aoi_id[1])
    headers = dict()
    headers['Location'] = resource
    headers['Content-Type'] = 'application/json'

    return (json.dumps({'aoi_id': aoi_id[0], 'extent': aoi_id[2]}),
            201, headers)


@app.route('/wps/<int:id>', methods=['GET', ])
def resource_aoi(id):
    """Method to get resource of huc12s returned as a web page. """
    with g.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("select * from aoi_results where pk = %s", (id, ))
        rec = cur.fetchone()
    return render_template('aoi_resource.html', aoi=dict(rec))

if __name__ == '__main__':
    app.run(debug=True)
