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
from flask import g, render_template, session, flash, redirect
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
import csv

#modules for this app
import nchuc12
import model
import siteutils
import siteprivate

# from gevent import monkey
# monkey.patch_all()
# from flask import copy_current_request_context
# import gevent

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
# app.config.from_object(__name__)
app.config.update(dict(
    DATABASE='ncthreats'
))

# set the secret key.  keep this really secret:
app.secret_key = siteprivate.secret_key


def connect_db():
    return psycopg2.connect(database=app.config['DATABASE'], user="postgres")


@app.before_request
def before_request():
    try:
        g.db = connect_db()
    except Exception as e:
        logger.debug(e.args)


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
    # huc.aoi_list = request.form.getlist('aoi_list[]')
    huc.aoi_list = request.form.get('aoi_list').split(":")
    logger.debug(huc.aoi_list)
    huc.predef_type = request.form['predef_type']
    huc.sel_type = request.form['sel_type']
    try:
        huc.referer = request.environ['HTTP_REFERER']
    except:
        pass
    logger.debug(huc.aoi_list)

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
    try:
        logger.debug(session['username'])
        username = session['username']
        loggedin = True
    except KeyError:
        logger.debug('user not logged in')
        loggedin = False
        username = ''

    with g.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("select * from aoi_results where pk = %s", (id, ))
        rec = cur.fetchone()
    return render_template(
        'aoi_resource.html',
        aoi=dict(rec),
        loggedin=loggedin,
        username=username
        # permalink=permalink
        )


@app.route('/<int:id>/saved', methods=['GET', ])
def saved_aoi(id):
    """Return geojson and extent given aoi id. """
    with g.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("select * from aoi_results where pk = %s", (id, ))
        rec = cur.fetchone()
    results = nchuc12.getgeojson(rec['huc12s'])
    extent = [
        float(rec['x_min']),
        float(rec['y_min']),
        float(rec['x_max']),
        float(rec['y_max']),

    ]
    return (
        json.dumps({
            'extent': extent,
            'geojson': results
        })
    )


@app.route('/<int:id>/map', methods=['GET', ])
def map_aoi(id):
    """Run model on AOI to create map.

    Get geojson for AOI with threat as 1. Get report and create dict from
    it with huc12 as key and threat as value and use to assign levels
    to map by looping geojson.
    """
    logger.debug(request.args)
    with g.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("select * from aoi_results where pk = %s", (id, ))
        rec = cur.fetchone()
    huc12_str = rec['huc12s']
    report_results = model.get_threat_report(huc12_str, request.args)
    results = nchuc12.getgeojson(huc12_str)
    results_dic = {huc12[0]: huc12[-1] for huc12 in report_results['res_arr']}
    for huc12 in results["features"]:
        huc12["properties"]["threat"] = results_dic[
            huc12["properties"]["huc12"]
            ]
    return json.dumps({"results": results})


@app.route('/<int:id>/report', methods=['GET', ])
def report_aoi(id):
    """Create model report as html from aoi id. """
    with g.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("select * from aoi_results where pk = %s", (id, ))
        rec = cur.fetchone()
    huc12_str = rec['huc12s']
    report_results = model.get_threat_report(huc12_str, request.args)
    logger.debug(report_results)
    return render_template(
        'report.html',
        col_hdrs=report_results['col_hdrs'],
        res_arr=report_results['res_arr'],
        year=report_results['year']
        )


@app.route('/<int:id>/ssheet', methods=['GET', ])
def ssheet_aoi(id):
    """Create model report as csv from aoi id. """
    with g.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("select * from aoi_results where pk = %s", (id, ))
        rec = cur.fetchone()
    huc12_str = rec['huc12s']
    report_results = model.get_threat_report(huc12_str, request.args)
    with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".txt",
            dir='/tmp',
            prefix='ncthreats'
            ) as temp:
        csvwriter = csv.writer(temp, quoting=csv.QUOTE_ALL, delimiter='\t')
        csvwriter.writerow(["Year - " + str(report_results['year'])])
        csvwriter.writerow(report_results['col_hdrs'])
        for row in report_results['res_arr']:
            # row_esc = ['="' + str(x) + '"' for x in row]
            # huc12_col = '="' + str(row[0]) + '"'
            # huc12_col = "'%s'" % str(row[0])
            # row_esc = [huc12_col]
            # for x in row[1:]:
            #     row_esc.append(x)
            csvwriter.writerow(row)

    headers = dict()
    headers['Location'] = url_for('get_ssheet', fname=temp.name[5:])
    return ('', 201, headers)


@app.route('/ssheet/<path:fname>')
def get_ssheet(fname):
    """Get PDF resource. """
    return send_from_directory('/tmp', fname, as_attachment=True)


@app.route('/pdf', methods=['POST', ])
def make_pdf():
    """Create PDF resource and return in location header. """
    # try http://flask.pocoo.org/snippets/68/
    htmlseg = request.form["htmlseg"].encode('ascii', 'ignore')
    with open("/tmp/test.html", "wb") as fp:
        fp.write(htmlseg)
    cmd1 = "/usr/local/wkhtmltox/bin/wkhtmltopdf"
    fname = tempfile.NamedTemporaryFile(
        delete=False, suffix=".pdf", dir='/tmp', prefix='ncthreats'
        )
    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as temp:
        temp.write(htmlseg)
        temp.flush()
    subprocess.call([
        cmd1, '-O', "Portrait",
        temp.name, fname.name,
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


@app.route('/login', methods=['POST', ])
def login():
    result = siteutils.userauth(request.form)
    if json.loads(result)['success']:
        session['username'] = json.loads(result)['username']
        session['firstname'] = json.loads(result)['firstname']
    return result


@app.route('/register')
def register():
    """ """
    return render_template('register.html')


@app.route('/createuser', methods=['POST', ])
def createuser():
    """ """
    flash(siteutils.addnewuser(request.form))
    return redirect(url_for('register'))


@app.route('/reset', methods=['POST', ])
def passwdreset():
    email = request.form['email'].strip()
    return(siteutils.passwdreset(email))


@app.route('/useraddaoi', methods=['POST', ])
def useraddaoi():
    logger.debug(request.form)
    query = """insert into usersaoi (username, aoiid, aoidesc) values
    (%s, %s, %s) """
    msg = 'AOI saved for user ' + request.form['username'] + "."

    with g.db.cursor() as cur:
        try:
            cur.execute(query, (
                request.form['username'], request.form['aoiid'],
                request.form['aoidesc'])
            )
        except psycopg2.IntegrityError:
            msg = 'You have already saved this AOI.'
    g.db.commit()
    flash(msg)
    return redirect(url_for('resource_aoi', id=request.form['aoiid']))


@app.route('/loginchk')
def loginchk():
    try:
        logger.debug(session['username'])
        username = session['username']
        firstname = session['firstname']
        loggedin = True

    except KeyError:
        logger.debug('user not logged in')
        loggedin = False
        username = '',
        firstname = ''

    return json.dumps({
        'loggedin': loggedin,
        'username': username,
        'firstname': firstname
        })


@app.route('/user/<username>')
def userpage(username):
    try:
        loggedinname = session['username']
        if username == loggedinname:
            results = siteutils.userpage(username)
            return render_template(
                "userpage.html",
                results=results,
                referer=request.environ['HTTP_REFERER']
            )
        else:
            return "not logged in to this account"
    except KeyError:
        return "not logged in to this account"


@app.route('/passwdchng',  methods=['POST', ])
def passwdchng():
    passwd = request.form['newpasswd'].strip()
    try:
        username = session['username']
        return siteutils.passwdchng(username, passwd)

    except KeyError:
        return json.dumps({'success': False})


@app.route('/pttojson',  methods=['GET', ])
def pttojson():
    """input layer and point, return geo and id """
    # pt_obj = request.form['pt_obj']
    # qry_lyr = request.form['qry_lyr']
    lon = request.args.get("pt_lon", "")
    lat = request.args.get("pt_lat", "")
    layer = request.args.get("qry_lyr", "")

    return siteutils.qrypttojson(lon, lat, layer)


@app.route('/huc12_state',  methods=['GET', ])
def huc12_state():
    huc12s = []
    with g.db.cursor() as cur:
        query = "select  huc_12 from huc12nc"
        cur.execute(query)
        # recs = cur.fetchall()
        for row in cur:
            huc12s.append(row[0])
    huc12_str = ", ".join(huc12s)
    logger.info(len(huc12s))
    # logger.debug(huc12_str)
    return json.dumps(nchuc12.getgeojson(huc12_str))


@app.route('/huc12_map',  methods=['GET', ])
def huc12_map():
    mymap_str = request.args.get("map", "")
    # year = request.args.get("year", "")
    # scenario = request.args.get("scenario", "")
    try:
        mymap = mymap_str.split(":")[0]
        # note year may be some other param
        year = mymap_str.split(":")[1]
        scenario = mymap_str.split(":")[2]
    except IndexError:
        pass
    results_dict = {}
    results_list = []
    rang = {}

    logger.debug(request.args)

    query2 = "select * from legend_data where layer_str = %s"
    if mymap in [
                "frst", 'ftwt', 'hbwt', 'open', 'shrb'
            ]:
        query1 = "select huc_12, %s%sha from lcscen_%s_ha" % (
            mymap, year, scenario
            )
        legend_param = mymap

    elif mymap in ['urban']:
        query1 = "select huc_12, urb%sha from urban_ha" % year
        legend_param = mymap
    elif mymap in ['fire']:
        query1 = "select huc_12, urb%sden from urban_den" % year
        legend_param = mymap
    elif mymap in ['trans']:
        query1 = "select huc_12, rds%smha from transportation" % year
        legend_param = mymap
    elif mymap in ['nutrient']:
        query1 = "select huc_12, %s from ea_pol" % year
        legend_param = mymap_str
    elif mymap in ['water']:
        query1 = "select huc_12, %s from ea_h20" % year
        legend_param = mymap_str
    elif mymap in ['frsthlth']:
        query1 = "select huc_12, fhlth_ha from forest_health"
        legend_param = mymap
    elif mymap in ['energydev']:
        query1 = " select huc_12, triassic_ha from energy_dev"
        legend_param = mymap
    elif mymap in ['wind']:
        query1 = "select * from wind_avg"
        legend_param = mymap
    elif mymap in ['slr_up']:
        query1 = "select huc_12, up00%sha from slamm_up_ha" % year
        legend_param = mymap
    elif mymap in ['slr_lc']:
        query1 = "select huc_12, lc00%sha from slamm_lc_ha" % year
        legend_param = mymap

    with g.db.cursor() as cur:
        cur.execute(query1)
        for row in cur:
            results_dict[row[0]] = float(row[1])
            results_list.append(row[1])
    logger.debug(len(results_list))
    results_list.sort()
    logger.debug(mymap)
    logger.debug(query2)
    # with g.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
    #     cur.execute(query2, (legend_param, ))
    #     for row in cur:
    #         logger.debug(row)
    #         pass
    with g.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(query2, (legend_param, ))
        for row in cur:
            logger.debug(row)
            # ranges = siteutils.legend_ranges(
            #     row['range1_vals'],
            #     row['range2_vals'],
            #     row['range3_vals'],
            #     row['range4_vals'],
            #     row['range5_vals'],
            #     row['range6_vals']
            # )
            colors = [
                row['color1'],
                row['color2'],
                row['color3'],
                row['color4'],
                row['color5'],
                row['color6']
            ]

            lgd_text = [
                row['range1'],
                row['range2'],
                row['range3'],
                row['range4'],
                row['range5'],
                row['range6']
            ]

    # colors_json = json.dumps(colors)
    # range_vals = json.loads(ranges)

    for huc in results_dict:
        if results_dict[huc] <= float(row['range1_high']):
            results_dict[huc] = 0
        elif results_dict[huc] <= float(row['range2_high']):
            results_dict[huc] = 1
        elif results_dict[huc] <= float(row['range3_high']):
            results_dict[huc] = 2
        elif results_dict[huc] <= float(row['range4_high']):
            results_dict[huc] = 3
        elif results_dict[huc] <= float(row['range5_high']):
            results_dict[huc] = 4
        else:
            results_dict[huc] = 5

    return json.dumps({
        "map": legend_param,
        "lgd_text": lgd_text,
        "res": results_dict,
        'colors': colors
    })


@app.route('/map',  methods=['GET', ])
def map():
    # logger.debug(request.args)
    # logger.debug(len(request.args))
    res = model.get_threat_report2(request.args)
    return json.dumps(res)


@app.route('/report',  methods=['GET', ])
def report():
    logger.debug(request.args)
    logger.debug(len(request.args))
    return "test"


@app.route('/ssheet',  methods=['GET', ])
def ssheet():
    logger.debug(request.args)
    logger.debug(len(request.args))
    return "test"


if __name__ == '__main__':
    app.run(debug=True)
