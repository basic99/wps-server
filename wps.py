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
import re
import zipfile
import collections

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

# needs to be used for production server
# app.config.update(dict(
#     CONNECT_STR='dbname=ncthreats user=postgres'
# ))

# set up of a user in db
# grant all on all tables in schema public to vashek;
# grant all on all sequences in schema public to vashek;

# change to the public ip to get conn to local db server
app.config.update(dict(
    CONNECT_STR='dbname=ncthreats user=postgres'
))

# set the secret key.  keep this really secret:
app.secret_key = siteprivate.secret_key


def connect_db():
    logger.debug(app.config['CONNECT_STR'])
    return psycopg2.connect(
        app.config['CONNECT_STR']
    )



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
    # pt_lon = request.form.get('point_buffer[lon]')
    # pt_lat = request.form.get('point_buffer[lat]')
    # logger.debug(request.form)
    huc = nchuc12.NCHuc12()
    huc.gml = request.form['gml']
    huc.pt_lon = request.form.get('point_buffer[lon]')
    huc.pt_lat = request.form.get('point_buffer[lat]')
    huc.ptbuffer_km = request.form.get('ptradius')
    # logger.debug(huc.ptbuffer_km)
    # huc.aoi_list = request.form.getlist('aoi_list[]')
    huc.aoi_list = request.form.get('aoi_list').split(":")
    # logger.debug(huc.aoi_list)
    huc.predef_type = request.form['predef_type']
    huc.sel_type = request.form['sel_type']
    try:
        huc.referer = request.environ['HTTP_REFERER']
    except:
        pass
    # logger.debug(huc.aoi_list)

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


@app.route('/batch', methods=['POST', ])
def post_batch():
    logger.debug(request.form)
    try:
        referer = request.environ['HTTP_REFERER']
    except:
        referer = ''
    for name in request.form:
        logger.debug(request.form.get(name))
    with g.db.cursor() as cur:
        cur.execute("select max(batch_id) from batch")
        rec = cur.fetchone()
        logger.debug(rec[0])
        rec_id = rec[0] + 1
        permalink = referer + "#batch_%s" % rec_id
        for name in request.form:
            cur.execute(
                "insert into batch(batch_id, name, resource, permalink, date) values(%s, %s, %s, %s, now())",
                (rec_id, name, request.form.get(name), permalink)
            )
    g.db.commit()
    resource = url_for(
        'resource_batch',
        id=rec_id
        )
    headers = dict()
    headers['Location'] = resource
    # headers['Content-Type'] = 'application/json'

    return (
        json.dumps({
            'status': "created"
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


@app.route('/batch/<int:id>', methods=['GET', ])
def resource_batch(id):
    aoi_list = []
    with g.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("select * from batch where batch_id = %s", (id, ))
        for rec in cur:
            aoi_list.append({
                "name": rec[2],
                "url": rec[3]
            })
        mydate = rec['date']
        permalink = rec['permalink']

    return render_template(
        'batch_resource.html',
        batch_id=id,
        date=mydate,
        aoi_list=aoi_list,
        permalink=permalink

    )

    # return json.dumps(aoi_list)



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


@app.route('/batch/<int:id>/saved', methods=['GET', ])
def saved_batch(id):
    """Return geojson and extent given aoi id. """

    query = "select * from batch where batch_id = %s"
    rec_pk_list = []
    results_list = []
    resource = {}
    with g.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(query, (id,))
        for rec in cur:
            resource[rec['name']] = rec['resource']
            logger.debug(rec)
            rec_pk = rec['resource'].split("/")[-1]
            rec_pk_list.append(rec_pk)
    for rec_pk in rec_pk_list:
        with g.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("select * from aoi_results where pk = %s", (rec_pk, ))
            rec = cur.fetchone()
            logger.debug(type(rec['huc12s']))
            results = nchuc12.getgeojson(rec['huc12s'])
            results_list.append(results)
    return (
        json.dumps({
            'geojson': results_list,
            'resource': resource
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


# @app.route('/<int:id>/report', methods=['GET', ])
# def report_aoi(id):
#     """Create model report as html from aoi id. """
#     with g.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
#         cur.execute("select * from aoi_results where pk = %s", (id, ))
#         rec = cur.fetchone()
#     huc12_str = rec['huc12s']
#     report_results = model.get_threat_report(huc12_str, request.args)
#     logger.debug(report_results)
#     return render_template(
#         'report.html',
#         col_hdrs=report_results['col_hdrs'],
#         res_arr=report_results['res_arr'],
#         year=report_results['year']
#         )


@app.route('/<int:id>/ssheet1', methods=['GET', ])
def ssheet_aoi(id):
    """Create model report as csv from aoi id. """

    logger.debug(id)
    tmp_name = siteutils.aoi_spreadsheet(id, request.args)

    headers = dict()
    headers['Location'] = url_for('get_ssheet', fname=tmp_name[5:])
    return ('', 201, headers)


@app.route('/batch/<int:id>/ssheet1', methods=['GET', ])
def ssheet_batch(id):
    """Create model report as csv from aoi id. """

    tmp_name = siteutils.batch_spreadsheet(id, request.args)

    headers = dict()
    headers['Location'] = url_for('get_ssheet', fname=tmp_name[5:])
    return ('', 201, headers)


@app.route('/ssheet/<path:fname>')
def get_ssheet(fname):
    """Get PDF resource. """
    return send_from_directory('/tmp', fname, as_attachment=True)


@app.route('/pdf', methods=['POST', ])
def make_pdf():
    """Create PDF resource and return in location header. """
    # try http://flask.pocoo.org/snippets/68/
    legend_files = {
        "water:bioimplen": "imp_bio.png",
        "water:metimplen": "imp_metal.png",
        "frst": "frst.png",
        "ftwt": "ftwt.png",
        "hbwt": "ftwt.png",
        "open": "open.png",
        "shrb": "shrb.png",
        "urban": "urban.png",
        "fire": "fire.png",
        "trans": "trans.png",
        "manu": "manu.png",
        "fert": "syn_nitro.png",
        "td_n_t": "tot_nitro.png",
        "td_s_t": "tot_sulf.png",
        "water": "nd.png",
        "frsthlth": "frsthlth.png",
        "energydev": "energy.png",
        "wind": "wind.png",
        "slr_up": "slr_up.png",
        "slr_lc": "slr_lc.png"
    }
    htmlseg = request.form["htmlseg"].encode('ascii', 'ignore')

    logger.debug(request.form["legend_print"])
    legend_print = request.form["legend_print"]

    # pattern = re.compile("<img class=\"olTileImage olImageLoadError^>*>")
    htmlseg = re.sub(
        "<img class=\"olTileImage olImageLoadError[^>]*>",
        "",
        htmlseg
    )

    # this is to create new svg
    # htmlseg_lgd = request.form["htmlseg_lgd"].encode('ascii', 'ignore')
    # with tempfile.NamedTemporaryFile(delete=False, suffix=".svg") as temp:
    #     temp.write(htmlseg_lgd)
    #     temp.flush()
    #     lgd_file = temp.name
    # logger.debug(lgd_file)
    with open("/tmp/test.html", "wb") as fp:
        fp.write(htmlseg)
    if legend_print == "individual":
        logger.debug("individula print")
        logger.debug(request.form["indiv_layer"])
        indiv_layer = request.form["indiv_layer"].split(":")[0]
        if indiv_layer == "nutrient":
            indiv_layer = request.form["indiv_layer"].split(":")[1]
        lgd_file = "http://localhost/images/legends/%s" % legend_files[indiv_layer]
        svg_fragment = '<image xlink:href="%s" x="30" y="400" width="220" height="220"/></svg>' % lgd_file
        logger.debug(svg_fragment)
        htmlseg = htmlseg.replace("</svg>", svg_fragment)

    elif legend_print == "model":
        logger.debug("model print")
        lgd_file = "http://localhost/threats/images/threat_legend.png"
        svg_fragment = '<image xlink:href="%s" x="30" y="450" width="220" height="220"/></svg>' % lgd_file
        logger.debug(svg_fragment)
        htmlseg = htmlseg.replace("</svg>", svg_fragment)

    # https://github.com/wkhtmltopdf/wkhtmltopdf/issues/2037#issuecomment-62019521
    cmd1 = "/usr/local/wkhtmltox/bin/wkhtmltopdf"
    fname = tempfile.NamedTemporaryFile(
        delete=False, suffix=".pdf", dir='/tmp', prefix='ncthreats'
        )
    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as temp:
        temp.write(htmlseg)
        temp.flush()
    logger.debug(temp.name)
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
    pattern1 = re.compile('data.+base64,')
    # fluff = "data:application/octet-stream;base64,"  # for firefox
    # fluff2 = "data:;base64,"  # for chrome
    # fluff3 = urllib.urlencode({'fluff': fluff2}).replace('fluff=', '')  # ie
    for key, data in request.form.iterlists():
        shp[key] = str(data[0])
        mymatch = re.search(pattern1, shp[key])
        fluff = mymatch.group()
        logger.debug(key)
        logger.debug(fluff)
        shp[key] = shp[key].replace(fluff, '')
        # shp[key] = shp[key].replace(fluff2, '') # add something for ie
        try:
            shp[key] = base64.b64decode(shp[key])
        except TypeError:
            logger.debug(shp[key])
        with open(shp_dir + "/shape." + key, "wb") as temp:
            temp.write(shp[key])
            temp.flush()

    subprocess.call([
        cmd1, "-f", "GeoJSON", "-t_srs", "EPSG:3857",
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


@app.route('/passwdchng', methods=['POST', ])
def passwdchng():
    passwd = request.form['newpasswd'].strip()
    try:
        username = session['username']
        return siteutils.passwdchng(username, passwd)

    except KeyError:
        return json.dumps({'success': False})


@app.route('/pttojson', methods=['GET', ])
def pttojson():
    """input layer and point, return geo and id """
    # pt_obj = request.form['pt_obj']
    # qry_lyr = request.form['qry_lyr']
    lon = request.args.get("pt_lon", "")
    lat = request.args.get("pt_lat", "")
    layer = request.args.get("qry_lyr", "")

    return siteutils.qrypttojson(lon, lat, layer)


@app.route('/ptbufferjson', methods=['GET', ])
def ptbufferjson():
    """input layer and point, return geo and id """
    # pt_obj = request.form['pt_obj']
    # qry_lyr = request.form['qry_lyr']
    lon = request.args.get("lon", "")
    lat = request.args.get("lat", "")
    ptradius = request.args.get("ptradius", "")

    return siteutils.qryptbufferjson(lon, lat, ptradius)


@app.route('/huc12_state', methods=['GET', ])
def huc12_state():
    logger.debug("test")
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


@app.route('/huc12_map', methods=['GET', ])
def huc12_map():
    mymap_str = request.args.get("map", "")

    report_res = model.get_indiv_report(0, mymap_str)
    legend_param = report_res['legend_param']
    results_dict = report_res['results_dict']

    query2 = "select * from legend_data where layer_str = %s"
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


@app.route('/map', methods=['GET', ])
def map():
    # logger.debug(request.args)
    # logger.debug(len(request.args))
    res = model.get_threat_report2(0, request.args)
    # logger.debug(res)
    # return "tst"
    return json.dumps(res)


@app.route('/<int:id>/report', methods=['GET', ])
def report(id):
    logger.debug(id)
    logger.debug(request.args)
    logger.debug(len(request.args))
    if id == 0:
        report_results = model.get_threat_report2(id, request.args)
        # logger.debug(report_results)
        res_arr = [report_results['res_arr'][x] for x in report_results['res_arr']]
        col_hdrs = report_results['col_hdrs']
        # col_hdrs.append("results (normalized) ")
        col_hdrs.append("Threat Count")
        logger.debug(col_hdrs)
        samplesize = len(res_arr)

        tmp_name = siteutils.aoi_spreadsheet(id, request.args)
        link_ssht = url_for('get_ssheet', fname=tmp_name[5:])

        return render_template(
            'reporta.html',
            col_hdrs=col_hdrs,
            res_arr=res_arr,
            year=report_results['year'],
            samplesize=samplesize,
            link_ssht=link_ssht,
            threats_summary_state=report_results['threat_summary'],
            thrts_msg_state=report_results["thrts_included_msg"],
            report_rank_state=report_results['report_rank'],
            other_stats_state=report_results['other_stats']
        )
    else:
        results_state = model.get_threat_report2(id, request.args)
        results_aoi = model.get_threat_report2(id, request.args, 'aoi')
        results_5k = model.get_threat_report2(id, request.args, '5k')
        results_12k = model.get_threat_report2(id, request.args, '12k')

        # logger.debug(results_aoi['report_rank'])
        # logger.debug(results_5k['report_rank'])
        # logger.debug(results_12k['report_rank'])
        # logger.debug(results_5k['report_rank'])

        res_arr = [results_aoi['res_arr'][x] for x in results_aoi['res_arr']]
        col_hdrs = results_aoi['col_hdrs']
        # col_hdrs.append("results (normalized) ")
        col_hdrs.append("Threat Count")
        logger.debug(col_hdrs)
        samplesize = len(res_arr)
        samplesize_5k = len(
            [results_5k['res_arr'][x] for x in results_5k['res_arr']]
        )
        samplesize_12k = len(
            [results_12k['res_arr'][x] for x in results_12k['res_arr']]
        )

        tmp_name = siteutils.aoi_spreadsheet(id, request.args)
        link_ssht = url_for('get_ssheet', fname=tmp_name[5:])

        return render_template(
            'reporta2.html',
            year=results_aoi['year'],
            col_hdrs=col_hdrs,
            res_arr=res_arr,
            link_ssht=link_ssht,
            samplesize_aoi=samplesize,
            samplesize_5k=samplesize_5k,
            samplesize_12k=samplesize_12k,
            report_rank_aoi=results_aoi['report_rank'],
            report_rank_5k=results_5k['report_rank'],
            report_rank_12k=results_12k['report_rank'],
            report_rank_state=results_state['report_rank'],
            thrts_msg_aoi=results_aoi["thrts_included_msg"],
            thrts_msg_state=results_state["thrts_included_msg"],
            thrts_msg_5k=results_5k["thrts_included_msg"],
            thrts_msg_12k=results_12k["thrts_included_msg"],
            threats_summary_aoi=results_aoi['threat_summary'],
            threats_summary_5k=results_5k['threat_summary'],
            threats_summary_12k=results_12k['threat_summary'],
            threats_summary_state=results_state['threat_summary'],
            other_stats_aoi=results_aoi['other_stats'],
            other_stats_5k=results_5k['other_stats'],
            other_stats_12k=results_12k['other_stats'],
            other_stats_state=results_state['other_stats']
        )


@app.route('/batch/<int:id>/report', methods=['GET', ])
def report_batch(id):
    query = "select * from batch where batch_id = %s order by name"
    batch_results = collections.OrderedDict()
    with g.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(query, (id, ))
        for row in cur:
            name = row['name']
            aoi_id = row['resource'].split("/")[-1]
            logger.debug(name)
            logger.debug(aoi_id)

            results_aoi = model.get_threat_report2(aoi_id, request.args, 'aoi')
            results_5k = model.get_threat_report2(aoi_id, request.args, '5k')
            results_12k = model.get_threat_report2(aoi_id, request.args, '12k')

            res_arr = [results_aoi['res_arr'][x] for x in results_aoi['res_arr']]
            col_hdrs = results_aoi['col_hdrs']
            # col_hdrs.append("results (normalized) ")
            col_hdrs.append("Threat Count")
            logger.debug(col_hdrs)
            samplesize = {}
            samplesize['aoi'] = len(res_arr)
            samplesize['5k'] = len(
                [results_5k['res_arr'][x] for x in results_5k['res_arr']]
            )
            samplesize['12k'] = len(
                [results_12k['res_arr'][x] for x in results_12k['res_arr']]
            )

            batch_results[name] = {}
            batch_results[name]['aoi'] = results_aoi
            batch_results[name]['5k'] = results_5k
            batch_results[name]['12k'] = results_12k
            batch_results[name]['samplesize'] = samplesize

    year = results_aoi['year']
    tmp_name = siteutils.batch_spreadsheet(id, request.args)
    link_ssht = url_for('get_ssheet', fname=tmp_name[5:])
    logger.debug(request.args)
    # logger.debug(batch_results)
    logger.debug(year)
    logger.debug(request.args.get('aoi_mode'))
    meta1 = request.args.get("basins_meta1", "")
    meta2 = request.args.get("basins_meta2", "")
    meta = (meta1, meta2)
    if request.args.get('aoi_mode') != 'coa':
        return render_template(
            'report_batch.html',
            year=year,
            link_ssht=link_ssht,
            results=batch_results,
            meta=meta
        )
    else:
        # reg_com = request.args['reg_com']
        # region = request.args['region'].replace("_", " ")
        reg_com = request.args.get('reg_com', "")
        region = request.args.get('region', "").replace("_", "")
        logger.debug(reg_com)
        query = "select communityname from coa_keylist where keycode =%s"
        with g.db.cursor() as cur:
            cur.execute(query, (reg_com, ))
            com = cur.fetchone()
        com_str = "%s / %s" % (region, com[0])
        logger.debug(com)

        query = """
select comname_gap, sciname_gap, strProtAc,
strUnprotAc, strPredHabAc, strPercUnprot
from coa_spphabmatrixsgcn, coa_SppHucProtData
where coa_SppHabMatrixSGCN.SppCode_GAP = coa_SppHucProtData.strUC
and coa_SppHucProtData.huc12 = %s
and coa_spphabmatrixsgcn."""

        query += reg_com.replace(".", "_") + " is not null;"
        logger.debug(query)

        for huc12 in batch_results:
            report_rows = []
            logger.debug(huc12)
            with g.db.cursor() as cur:
                cur.execute(query, (huc12,))
                for cnt, row in enumerate(cur):
                    # logger.debug(row)
                    report_rows.append(row)
            batch_results[huc12]['scgn'] = report_rows

        return render_template(
            'report_coa.html',
            year=year,
            link_ssht=link_ssht,
            results=batch_results,
            com=com_str
        )


@app.route('/ssheet', methods=['GET', ])
def ssheet():
    logger.debug(request.args)
    logger.debug(len(request.args))
    report_results = model.get_threat_report2(request.args)
    res_arr = [report_results['res_arr'][x] for x in report_results['res_arr']]
    col_hdrs = report_results['col_hdrs']
    col_hdrs.append("results")
    with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".txt",
            dir='/tmp',
            prefix='ncthreats'
            ) as temp:
        csvwriter = csv.writer(temp, quoting=csv.QUOTE_ALL, delimiter='\t')
        csvwriter.writerow(["Year - " + str(report_results['year'])])
        csvwriter.writerow(col_hdrs)
        for row in res_arr:
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


@app.route('/<int:id>/report_indiv', methods=['GET', ])
def report_indiv(id):
    mymap_str = request.args.get("map", "")
    if id == 0:
        report_results = model.get_indiv_report(id, mymap_str)
        # res_arr = [
        #     [x, report_results['results_dict'][x]]
        #     for x in report_results['results_dict']
        # ]
        # logger.debug(res_arr)
        logger.debug(report_results['stats'])
        return render_template(
                'report_indiv.html',
                year=report_results['year'],
                stats=report_results['stats'],
                results_dict=report_results['res_arr'],
                col_name=report_results['col_name']
                )

    else:
        results_state = model.get_indiv_report(id, mymap_str)
        results_aoi = model.get_indiv_report(id, mymap_str, 'aoi')
        results_5k = model.get_indiv_report(id, mymap_str, '5k')
        results_12k = model.get_indiv_report(id, mymap_str, '12k')
        num_hucs = {}
        num_hucs['aoi'] = results_aoi['num_hucs']
        num_hucs['5k'] = results_5k['num_hucs']
        num_hucs['12k'] = results_12k['num_hucs']

        return render_template(
                'report_indiv2.html',
                col_name=results_state['col_name'],
                num_hucs=num_hucs,
                year=results_state['year'],
                results_dict_state=results_state['res_arr'],
                stats_state=results_state['stats'],
                results_dict_aoi=results_aoi['res_arr'],
                stats_aoi=results_aoi['stats'],
                results_dict_5k=results_5k['res_arr'],
                stats_5k=results_5k['stats'],
                results_dict_12k=results_12k['res_arr'],
                stats_12k=results_12k['stats']
                )


@app.route('/batch/<int:id>/report_indiv', methods=['GET', ])
def report_indiv_batch(id):
    mymap_str = request.args.get("map", "")
    query = "select * from batch where batch_id = %s"
    batch_results = {}
    with g.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(query, (id, ))
        for row in cur:
            name = row['name']
            aoi_id = row['resource'].split("/")[-1]
            results_aoi = model.get_indiv_report(aoi_id, mymap_str, 'aoi')
            results_5k = model.get_indiv_report(aoi_id, mymap_str, '5k')
            results_12k = model.get_indiv_report(aoi_id, mymap_str, '12k')
            num_hucs = {}
            num_hucs['aoi'] = results_aoi['num_hucs']
            num_hucs['5k'] = results_5k['num_hucs']
            num_hucs['12k'] = results_12k['num_hucs']
            batch_results[name] = {}
            batch_results[name]['aoi'] = results_aoi
            batch_results[name]['5k'] = results_5k
            batch_results[name]['12k'] = results_12k
            batch_results[name]['num_hucs'] = num_hucs
    year = results_aoi['year']
    logger.debug(request.args)
    logger.debug(batch_results)
    logger.debug(year)
    return render_template(
                'report_batch_indiv.html',
                year=year,
                results=batch_results
                )
    # return "hello world"


@app.route('/preview_map', methods=['POST', ])
def limit_preview_map():
    logger.debug(request.form)
    report_res = model.preview_map(request.form)
    results_dict = report_res['results_dict']
    # legend_param = report_res['legend_param']
    layer = request.form.get("map")
    logger.debug(layer)
    legend_crswlk = {
        'urbangrth_limit': 'urban',
        'firesup_limit': 'fire',
        'frst_limit': 'frst',
        'ftwt_limit': 'ftwt',
        'hbwt_limit': 'hbwt',
        'open_limit': 'open',
        'shrb_limit': 'shrb',
        'hiway_limit': 'trans',
        'slr_up_limit': 'slr_up',
        'slr_lc_limit': 'slr_lc',
        'triassic_limit': 'energydev',
        'wind_limit': 'wind',
        'manure_limit': 'nutrient:manu',
        'nitrofrt_limit': 'nutrient:fert',
        'totnitro_limit': 'nutrient:td_n_t',
        'totsulf_limit': 'nutrient:td_s_t',
        'insectdisease_limit': 'frsthlth',
        'ndams_limit': 'water:NID',
        'impairbiota_limit': 'water:bioimplen',
        'impairmetal_limit': 'water:metimplen'
    }
    legend_param = legend_crswlk[layer]

    query2 = "select * from legend_data where layer_str = %s"
    logger.debug(query2 % "'" + legend_crswlk[layer] + "'")
    # with g.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
    #     cur.execute(query2, (legend_param, ))
    #     for row in cur:
    #         logger.debug(row)
    #         pass
    with g.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(query2, (legend_crswlk[layer], ))
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

    # return json.dumps(results)
    return json.dumps({
        "map": legend_param,
        "lgd_text": lgd_text,
        "res": results_dict,
        'colors': colors
    })


@app.route('/coa_map', methods=['POST', ])
def coa_map():
    keycode = request.form.get("keycode")
    col_name = "UR_" + keycode.replace(".", "_")
    ecoregion_code = keycode[0]
    logger.debug(ecoregion_code)
    query = "select HUC12RNG, %s from coa_UnprRatioSGCNSpp" % col_name
    logger.debug(query)
    ratio_list = []
    ratio_dict = {}
    num_zeros = 0

    # get list of hucs in ecoregion
    huc12s = []
    with g.db.cursor() as cur:
        cur.execute(
            "select huc12 from coa_ecohuc where ecoregion = %s",
            (ecoregion_code,)
        )
        for rec in cur:
            huc12s.append(rec[0])

    #  get min and max ratio values
    # create dict of huc/ratio
    with g.db.cursor() as cur:
        cur.execute(query)
        for rec in cur:
            if rec[1] > 0:
                ratio_list.append(rec[1])
            else:
                num_zeros += 1
            ratio_dict[rec[0]] = rec[1]

    dict_sorted = collections.OrderedDict(
        sorted(ratio_dict.items(), key=lambda t: t[1], reverse=True)
    )

    min_val = min(ratio_list)
    max_val = max(ratio_list)
    val_range = max_val - min_val

    cnt = 0
    top_five = []
    for huc in dict_sorted:
        if huc in huc12s:
            cnt += 1
            thrt_val = dict_sorted[huc]
            cat = int(round(((thrt_val - min_val) / val_range) * 10)) + 1
            top_five.append((huc, cat))
            if cnt > 4:
                break

    logger.debug(top_five)
    logger.debug(num_zeros)
    logger.debug(min_val)
    logger.debug(max_val)

    # assigne categories to huc12
    huc12_cats = {}
    with g.db.cursor() as cur:
        cur.execute(query)
        for rec in cur:
            if rec[1] > 0:
                cat = int(round(((rec[1] - min_val) / val_range) * 10)) + 1
            else:
                cat = 0
            # logger.debug(cat)
            huc12_cats[rec[0]] = cat

    return json.dumps({
        "test": "success",
        "huc12_cats": huc12_cats,
        "top_five": top_five
    })


@app.route('/coa_model', methods=['POST', ])
def coa_model():
    keycode = request.form.get("keycode")
    tbl = request.form.get("tbl")
    logger.debug(keycode)
    logger.debug(tbl)
    if tbl == 'coa':
        query = "select * from coa_keythreats where KeyCode = %s"
    elif tbl == 'basins':
        query = "select * from coa_keythreats_basins where KeyCode = %s"
    with g.db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, (keycode,))
        rec = cur.fetchone()
    logger.debug(rec)

    return json.dumps({
        "test": "success",
        "row": rec
    })


@app.route('/qry_tool', methods=['GET', ])
def qry_tool():
    keycode = request.args.get("community")

    lon = request.args.get('pt_lon')
    lat = request.args.get('pt_lat')
    toolid = request.args.get('qry')
    logger.debug(toolid)
    logger.debug(keycode)
    logger.debug(request.args)

    if len(keycode) == 0 and int(toolid) == 1:
        return "no community selected"
    try:
        retval = siteutils.qrypttojson(lon, lat, 'huc_12')
        huc12 = json.loads(retval)['the_huc']
    except TypeError:
        pass

    if toolid == '1':
        basins = [
            'Broad',
            'Cape Fear',
            'Catawba',
            'Chowan',
            'French Broad',
            'Hiwassee',
            'Little Tennessee',
            'Lumber',
            'Neuse',
            'New',
            'Pasquotank',
            'Roanoke',
            'Savannah',
            'Tar - Pamlico',
            'Watauga',
            'White Oak',
            'Yadkin - PeeDee'
        ]
        if keycode in basins:
            return "no community selected"
        # for coa query

        query = """
select comname_gap, sciname_gap, strProtAc,
strUnprotAc, strPredHabAc, strPercUnprot
from coa_spphabmatrixsgcn, coa_SppHucProtData
where coa_SppHabMatrixSGCN.SppCode_GAP = coa_SppHucProtData.strUC
and coa_SppHucProtData.huc12 = %s
and coa_spphabmatrixsgcn."""

        query += keycode.replace(".", "_") + " is not null;"
        logger.debug(query)
        report_rows = []
        with g.db.cursor() as cur:
            cur.execute(query, (huc12,))
            for cnt, row in enumerate(cur):
                # logger.debug(row)
                report_rows.append(row)
            logger.debug("rows returned %s" % cnt)
        query = "select region, communityname from coa_keylist where keycode = %s"
        with g.db.cursor() as cur:
            cur.execute(query, (keycode,))
            commrow = cur.fetchone()
        logger.debug(commrow)
        query = "select subwatersh from huc12nc where huc_12 = %s"
        with g.db.cursor() as cur:
            cur.execute(query, (huc12,))
            subwatersh = cur.fetchone()
        logger.debug(subwatersh)

        return render_template(
            'query_coa.html',
            huc12=huc12,
            report_rows=report_rows,
            commrow=commrow,
            subwatersh=subwatersh
        )
    elif toolid == '2':
        logger.debug("query threat info")
        x = model.get_threat_report2(
            -1, request.args, mode='huc12', huc12=huc12
        )

        # for y in x:
        #     logger.debug(y)
        # x['col_hdrs'].append('Threat Count')
        datavals = ["blah"]
        occurvals = ["blah"]
        thrt_cnt = x['res_arr'][huc12].pop()
        for thrt in x['report_rank']:
            logger.debug(thrt[-1])
            datavals.append(thrt[-1])
            occurvals.append(int(thrt[1]))
        report = zip(x['col_hdrs'], datavals, occurvals, x['res_arr'][huc12])[1:]

        query = "select subwatersh from huc12nc where huc_12 = %s"
        with g.db.cursor() as cur:
            cur.execute(query, (huc12,))
            subwatersh = cur.fetchone()
        logger.debug(subwatersh)
        # for threat info query
        return render_template(
            'query_threats.html',
            # report_cols=x['col_hdrs'],
            # report_vals=x['res_arr'][huc12],
            report=report,
            huc12=huc12,
            thrt_cnt=thrt_cnt,
            subwatersh=subwatersh

        )
    elif toolid == '3':
        logger.debug("query managed area")
        """
        select man_desc from se_manage where ST_Contains
        (wkb_geometry, ST_SetSRID(ST_Point(-8488393.0058056, 4267245.3329947)
        ,4326));
        """
        qry = """select man_desc from se_manage where ST_Contains \
        (wkb_geometry, ST_SetSRID(ST_Point(%s, %s) \
        ,4326));
        """
        with g.db.cursor() as cur:
            cur.execute(qry, (lon, lat))
            rec = cur.fetchone()
        try:
            logger.debug(rec[0])
            return "<h3>Management Designation: %s</h3>" % rec[0]
            # res = {
            #     "man_area": rec[0]
            # }
            # return json.dumps(res)
        except TypeError:
            logger.debug("not managed area")
            return "<h3>not managed area</h3>"

            # res = {
            #     "man_area": "not managed area"
            # }
            # return json.dumps(res)


@app.route('/ncwrc_basins_map', methods=['POST', ])
def ncwrc_basins_map():
    basin = request.form.get("basin")
    tier1 = request.form.get('tier1')
    tier2 = request.form.get('tier2')
    rivbuff = request.form.get('rivbuff')
    if tier1 == 'true':
        tier1 = "Tier 1"
    else:
        tier1 = "xxx"
    if tier2 == 'true':
        tier2 = "Tier 2"
    else:
        tier2 = "xxx"
    if rivbuff == 'true':
        rivbuff = "1km River Buffer"
    else:
        rivbuff = "xxx"
    logger.debug(tier1)
    huc12s = []
    query = """
select huc12rng from ncwrc_priorities where (priorityty = %s \
or priorityty = %s or priorityty = %s) and  riverbasin = %s
"""
    with g.db.cursor() as cur:
        cur.execute(query, (tier1, tier2, rivbuff, basin))
        for rec in cur:
            logger.debug(rec[0])
            huc12s.append(rec[0].strip())

    return json.dumps({
        "huc12s": huc12s
    })


if __name__ == '__main__':
    """
    debug server
    cd /usr/local/pythonenvs/ncthreatsenv/bin
    source activate
    cd /var/www/wsgi/wps-server
    python wps.py

    production server
    su
    supervisorctl
    restart wps-server


    """
    app.run(debug=True)
