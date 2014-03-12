"""Main file to run Flask app.

The web app is a GIS app that uses REST architecture.
It is based loosely on the concept of a WPS(Web Processing Service),
but does not comply with that standard.
Create a resource that is a list of huc12s(12 digit hydrologic units)
that overlap the input geometry which is input as GML file.
Allow access to this resource.

"""

from flask import Flask
from flask import send_from_directory
from flask import request
from flask import url_for
from flask import g, render_template

import psycopg2
import psycopg2.extras
import json
import os
import logging
import subprocess
import tempfile

#modules for this app
import nchuc12
import model

# from gevent import monkey
# monkey.patch_all()
# from flask import copy_current_request_context
# import gevent

cwd = os.path.dirname(os.path.realpath(__file__))
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler(cwd + '/logs/logs.log')
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
fh.setFormatter(formatter)
logger.addHandler(fh)


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
    # logger.debug(aoi_id[2])

    resource = url_for('resource_aoi', id=aoi_id[0])
    headers = dict()
    headers['Location'] = resource
    headers['Content-Type'] = 'application/json'

    return (
        json.dumps({
            # 'aoi_id': aoi_id[0],
            'extent': aoi_id[1],
            'geojson': aoi_id[2]
            }),
        201, headers
        )


@app.route('/wps/<int:id>', methods=['GET', ])
def resource_aoi(id):
    """Method to get resource of huc12s returned as a web page. """
    with g.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("select * from aoi_results where pk = %s", (id, ))
        rec = cur.fetchone()
    return render_template('aoi_resource.html', aoi=dict(rec))


@app.route('/wps/<int:id>/map', methods=['GET', ])
def map_aoi(id):
    """fl """
    with g.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("select * from aoi_results where pk = %s", (id, ))
        rec = cur.fetchone()
    huc12_str = rec['huc12s']
    results = nchuc12.getgeojson(huc12_str)
    for huc12 in results["features"]:
        huc12["properties"]["threat"] = model.get_threat(
            huc12["properties"]["huc12"], request.args
            )

    return json.dumps({"results": results})


@app.route('/wps/pdf', methods=['POST', ])
def make_pdf():
    htmlseg = request.form["htmlseg"].encode('ascii', 'ignore')
    logger.debug(request.form["text"])
    # logger.debug(request.form["orient"])
    cmd1 = "/usr/local/wkhtmltox/bin/wkhtmltopdf"
    fname = tempfile.NamedTemporaryFile(
        delete=False, suffix=".pdf", dir='/tmp', prefix='ncthreats'
        )
    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as temp:
        temp.write(htmlseg)
        temp.flush()
    subprocess.call([
        cmd1, '-O', "Portrait",
        temp.name, fname.name
        ])
    headers = dict()
    headers['Location'] = url_for('get_pdf', fname=fname.name[5:])
    return ('', 201, headers)


@app.route('/wps/pdf/<path:fname>')
def get_pdf(fname):
    return send_from_directory('/tmp', fname, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
