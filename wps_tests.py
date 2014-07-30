import wps
import unittest
import os
import logging
import json
import urllib
import test_resource1
import test_resource2
import siteutils
from flask import Flask, current_app, g
import psycopg2
import psycopg2.extras

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

gml = """<gml:featureMembers xmlns:gml="http://www.opengis.net/gml"
 xsi:schemaLocation="http://www.opengis.net/gml
 http://schemas.opengis.net/gml/3.1.1/profiles/gmlsfProfile/1.0.0/gmlsf.xsd"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
 <feature:MultiPolygon xmlns:feature="http://jimserver.net/">
 <feature:aoi><gml:Polygon><gml:exterior>
 <gml:LinearRing><gml:posList>-81.13320802743071 35.2360513054988
 -80.41909669930497 35.01590447020165 -80.55642580086831 35.37502023731942
 -81.13320802743071 35.2360513054988</gml:posList>
 </gml:LinearRing></gml:exterior></gml:Polygon></feature:aoi>
 </feature:MultiPolygon></gml:featureMembers> """


class WPSTestCase(unittest.TestCase):

    def setUp(self):
        wps.app.config['DATABASE'] = 'testncthreats'
        self.app = wps.app.test_client()
        rv = self.app.post('/', data=dict(
            gml='',
            aoi_list='183:63',
            predef_type='NC Counties',
            sel_type='predefined'))
        # logger.debug(rv.headers['Location'])
        self.resource = rv.headers['Location'].split("/")[-1]
        self.gml = gml
        self.htmlseg = test_resource1.htmlseg

    def tearDown(self):
        pass

    def test_post_aoi1(self):
        rv = self.app.post(
            '/', data=dict(
                gml='',
                aoi_list='183:63',
                predef_type='NC Counties',
                sel_type='predefined'
                )
        )
        res = json.loads(rv.data)
        assert 'geometry' in res['geojson']['features'][0]
        assert rv.status_code == 201

    def test_post_aoi2(self):
        rv = self.app.post('/', data=dict(
            gml=self.gml,
            aoi_list='',
            predef_type='',
            sel_type='custom'))
        res = json.loads(rv.data)
        assert 'geometry' in res['geojson']['features'][0]
        assert rv.status_code == 201

    def test_resource_aoi(self):
        rv = self.app.get("/" + self.resource)
        assert 'HUC 12 List' in rv.data
        assert rv.status_code == 200

    def test_saved_aoi(self):
        rv = self.app.get("/" + self.resource + "/saved")
        res = json.loads(rv.data)
        assert 'geometry' in res['geojson']['features'][0]
        assert rv.status_code == 200

    def test_map_aoi(self):
        data = dict(
            year=2010,
            urb='on'
            )
        qrystr = urllib.urlencode(data)
        rv = self.app.get(
            "/" + self.resource + "/map?" + qrystr
        )
        res = json.loads(rv.data)
        assert 'geometry' in res['results']['features'][0]
        assert rv.status_code == 200

    def test_report_aoi(self):
        data = dict(
            year=2050,
            tran='on',
            frag='on'
            )
        qrystr = urllib.urlencode(data)
        rv = self.app.get(
            "/" + self.resource + "/report?" + qrystr
        )
        assert 'Fragmentation Index' in rv.data
        assert 'Transportation Corridors' in rv.data
        assert 'Result' in rv.data

    def test_ssheet_aoi(self):
        data = dict(
            year=2050,
            polu1='on',
            polu2='on',
            dise1='on',
            dise2='on'
            )
        qrystr = urllib.urlencode(data)
        rv = self.app.get(
            "/" + self.resource + "/ssheet?" + qrystr
        )
        assert 'wps/ssheet' in rv.headers['Location']
        fname = rv.headers['Location'].split('/')[-1]
        rv2 = self.app.get(
            "/ssheet/" + fname
        )
        assert 'HUC12,Disease 1,Disease 2,Pollution 1' in rv2.data

    def test_make_pdf(self):
        rv = self.app.post(
            '/pdf', data=dict(
                htmlseg=self.htmlseg
                )
        )
        logger.debug(rv.headers['Location'])
        assert "/wps/pdf/ncthreats" in rv.headers['Location']

    def test_shptojson(self):
        rv = self.app.post(
            '/shptojson', data=dict(
                shp=test_resource2.shp,
                shx=test_resource2.shx,
                prj=test_resource2.prj
                )
        )
        assert 'geometry": { "type":' in rv.data

    def test_login(self):
        user = 'testuser'
        passwd = 'supersecret'
        badpass = 'short'
        email = 'jim@test.com'
        request = dict(
            UserName=user,
            Email=email,
            Password=passwd
        )
        request_bad = dict(
            UserName=user,
            Email=email,
            Password=badpass
        )
        login = dict(
            loginUsername=user,
            loginPassword=passwd
        )
        bad_login = dict(
            loginUsername=user,
            loginPassword='badguess'
        )

        db = psycopg2.connect(
            database=wps.app.config['DATABASE'],
            user="postgres"
        )
        query = "delete from users"
        with db.cursor() as cur:
            cur.execute(query)
        db.commit()

        app = Flask(__name__)
        with app.app_context():
            g.db = psycopg2.connect(
                database=wps.app.config['DATABASE'],
                user="postgres"
            )
            rv = siteutils.addnewuser(request_bad)
            assert 'Registration error' in rv
            rv = siteutils.addnewuser(request)
            assert 'Registration completed' in rv
            rv = siteutils.addnewuser(request)
            assert 'You have already registered with this email' in rv

        #not sure why needs to do this twice but database fail otherwise
        with app.app_context():
            g.db = psycopg2.connect(
                database=wps.app.config['DATABASE'],
                user="postgres"
            )
            rv = siteutils.userauth(login)
            assert '"success": true' in rv
            rv = siteutils.userauth(bad_login)
            assert '{"success": false}' in rv

if __name__ == '__main__':
    unittest.main()
