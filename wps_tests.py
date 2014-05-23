import wps
import unittest
import os
import logging
import json

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
        logger.debug(rv.headers['Location'])
        self.resource = rv.headers['Location'].split("/")[-1]
        self.gml = gml

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
        rv = self.app.get(
            "/" + self.resource + "/map?year=2010&urb=on"
        )
        res = json.loads(rv.data)
        assert 'geometry' in res['results']['features'][0]
        assert rv.status_code == 200

if __name__ == '__main__':
    unittest.main()
