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
# from jinja2 import Environment, PackageLoader

import psycopg2
import psycopg2.extras
import json
import os
import logging
import subprocess
import tempfile
import urllib
import base64

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


class ReverseProxied(object):
    """Modified snippet.
    http://flask.pocoo.org/snippets/35/
    See also:
    http://flask.pocoo.org/docs/deploying/wsgi-standalone/#proxy-setups

    """
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        # logger.debug(environ)
        script_name = '/wps'
        environ['SCRIPT_NAME'] = script_name

        return self.app(environ, start_response)

app = Flask(__name__)
app.wsgi_app = ReverseProxied(app.wsgi_app)


def connect_db():
    return psycopg2.connect("dbname=ncthreats user=postgres")


@app.before_request
def before_request():
    g.db = connect_db()


@app.teardown_request
def teardown_request(exception):
    db = getattr(g, 'db', None)
    if db is not None:
        db.close()


@app.route('/', methods=['POST', ])
def post_aoi():
    """Create a new AOI resource with post request of GML.

    Create nchuc12 object to make the calculations and
    pass the post data of gml.
    Return geojson and extent as json, an http response of 201
    and location header with resource location.

    """
    huc = nchuc12.NCHuc12()
    huc.gml = request.form['gml']
    huc.aoi_list = request.form.getlist('aoi_list[]')
    huc.predef_type = request.form['predef_type']
    huc.sel_type = request.form['sel_type']
    new_aoi = huc.execute()

    resource = url_for(
        'resource_aoi',
        id=new_aoi[0]
        )
    headers = dict()
    headers['Location'] = resource
    # headers['Content-Type'] = 'application/json'

    return (
        json.dumps({
            'extent': new_aoi[1],
            'geojson': new_aoi[2]
            }),
        201, headers
        )


@app.route('/<int:id>', methods=['GET', ])
def resource_aoi(id):
    """Method to get resource of huc12s returned as a web page. """
    with g.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("select * from aoi_results where pk = %s", (id, ))
        rec = cur.fetchone()
    return render_template(
        'aoi_resource.html',
        aoi=dict(rec)
        )


@app.route('/<int:id>/saved', methods=['GET', ])
def saved_aoi(id):

    return (
        json.dumps({
            'extent': new_aoi[1],
            'geojson': new_aoi[2]
        })
        )


@app.route('/<int:id>/map', methods=['GET', ])
def map_aoi(id):
    """Run model on AOI to create map.

    Get geojson for AOI with threat as 1. Loop through huc12s,
    running model on each, set threat result, return geojson.
    """
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


@app.route('/<int:id>/report', methods=['GET', ])
def report_aoi(id):
    with g.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("select * from aoi_results where pk = %s", (id, ))
        rec = cur.fetchone()
    huc12_str = rec['huc12s']
    report_results = model.get_threat_report(huc12_str, request.args)
    # logger.debug(report_results)
    return render_template(
        'report.html',
        col_hdrs=report_results['col_hdrs'],
        res_arr=report_results['res_arr'],
        year=report_results['year']
        )
    # return json.dumps(report_results)


@app.route('/pdf', methods=['POST', ])
def make_pdf():
    """Create PDF resource and return in location header. """
    htmlseg = request.form["htmlseg"].encode('ascii', 'ignore')
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


@app.route('/pdf/<path:fname>')
def get_pdf(fname):
    """Get PDF resource. """
    return send_from_directory('/tmp', fname, as_attachment=True)


@app.route('/shptojson', methods=['POST', ])
def shptojson():
    """Convert shapefile upload to geojson. """
    shp = {}
    shp_dir = tempfile.mkdtemp()
    cmd1 = "/usr/local/bin/ogr2ogr"
    fluff = "data:application/octet-stream;base64,"  # for firefox
    fluff2 = "data:;base64,"  # for chrome
    fluff3 = urllib.urlencode({'fluff': fluff2}).replace('fluff=', '')  # ie
    for key, data in request.form.iterlists():
        shp[key] = str(data[0])
        shp[key] = shp[key].replace(fluff, '')
        shp[key] = shp[key].replace(fluff2, '')
        shp[key] = shp[key].replace(fluff3, '')
        shp[key] = base64.b64decode(shp[key])
        with open(shp_dir + "/shape." + key, "wb") as temp:
            temp.write(shp[key])
            temp.flush()

    subprocess.call([
        cmd1, "-f", "GeoJSON", "-t_srs", "EPSG:900913",
        shp_dir + "/shape.json", shp_dir
        ])

    return send_from_directory(shp_dir, "shape.json")


if __name__ == '__main__':
    app.run(debug=True)
