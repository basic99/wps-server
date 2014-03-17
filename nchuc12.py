"""Module contains a class to perform GIS calculations."""
#import psycopg2
from flask import g
import xml.dom.minidom
import hashlib
# import time
import random
import logging
import os
import json

cwd = os.path.dirname(os.path.realpath(__file__))
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler(cwd + '/logs/logs.log')
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
fh.setFormatter(formatter)
logger.addHandler(fh)


def getgeojson(huc12_str):
    """Convert sting of comma separated huc12s to a dict representing
    geojson, properties huc12 set and threat set to 1.

    """
    list_features = []
    huc12s = huc12_str.rsplit(", ")
    # print huc12s
    for huc12 in huc12s:
        with g.db.cursor() as cur:
            cur.execute(
                "select ST_AsGeoJSON(wkb_geometry, 6) from nchuc12_100m\
                where huc_12 = %s",
                (huc12, )
            )
            the_geom = cur.fetchone()
            the_geom = (json.loads(the_geom[0]))

            new_feature = {
                "type": "Feature",
                "geometry": the_geom,
                "properties": {
                    "huc12": huc12,
                    "threat": 1}
                }
            list_features.append(new_feature)
        dict_for_json = {
            "type": "FeatureCollection", "features": list_features
            }
    return dict_for_json


class NCHuc12():

    """Make GIS calculations to get huc12s.

    Input GML file and text description. Run method
    execute to do calculations.

    """

    def __init__(self):
        self.gml = ''
        self.aoi_list = []
        self.predef_type = ''

    def mkgeom(self):
        """ Convert GML into list of Well-Known Text representations."""
        geom_list = list()
        dom = xml.dom.minidom.parseString(self.gml)
        polygons = dom.getElementsByTagName("gml:Polygon")
        with g.db.cursor() as cur:
            for polygon in polygons:
                gml_fragment = polygon.toxml()
                cur.execute("select st_astext(st_geomfromgml(%s))",
                            (gml_fragment,))
                geom_list.append(cur.fetchone()[0])
        logger.debug("returning %s polygons as WKT" % len(polygons))
        return geom_list

    def execute(self):
        """Function to run calculations, called from wps.py.

        Call mkgeom to convert GML to list of polygons as WKT.
        Create identifier using  random and md5.
        Insert into table aoi row for each polygon of input.
        Call stored procedure with identifier to calculate overlap with
        huc12 layer and update table results with rows for each huc12.
        Calculate extents of huc12s.
        Add row to table aoi_results string representation of huc12s,
        extent, and identifier, returning the id of inserted row.

        Returns:
        geojson - dict representing geojson
        aoi_id - id of row in table aoi_results for this aoi
        extent - list of extents for huc12 for this aoi

        """
        # logger.debug(self.gml[:1000])
        logger.debug(self.aoi_list)
        logger.debug(self.predef_type)
        huc12s = list()
        input_geoms = self.mkgeom()
        digest = hashlib.md5()
        digest.update(str(random.randint(10000000, 99999999)))
        # digest.update(str(time.time()))
        ident = digest.hexdigest()
        with g.db.cursor() as cur:
            for b in input_geoms:
                cur.execute("insert into aoi(identifier, the_geom) values\
                 (%s, ST_GeomFromText(%s, 4326))", (ident, b))
            #Stored PL/PGSQL procedure. Use PostGIS to calculate overlaps.
            #Add row to table results for each huc12 with identifier.
            #Identifier column is used by geoserver cql filter.
            cur.execute("select aoitohuc(%s)", (ident,))
            #insert random results
            # self.calculations(ident)
            cur.execute("select huc12 from results where identifier = %s",
                        (ident,))
            for row in cur:
                huc12s.append(row[0])
            huc12_str = ", ".join(huc12s)
            cur.execute("select max(st_xmax(the_geom)) from results where\
             identifier = %s", (ident,))
            xmax = cur.fetchone()[0]
            cur.execute("select min(st_xmin(the_geom)) from results where\
             identifier = %s", (ident,))
            xmin = cur.fetchone()[0]
            cur.execute("select max(st_ymax(the_geom)) from results where\
             identifier = %s", (ident,))
            ymax = cur.fetchone()[0]
            cur.execute("select min(st_ymin(the_geom)) from results where\
             identifier = %s", (ident,))
            ymin = cur.fetchone()[0]
            g.db.rollback()
            cur.execute("insert into aoi_results(identifier, huc12s,\
              date, x_max, x_min, y_max, y_min) values\
              (%s, %s,  now(), %s, %s, %s, %s) returning pk",
                        (ident, huc12_str, xmax, xmin,
                         ymax, ymin))
            aoi_id = cur.fetchone()[0]
            g.db.commit()
            geojson = getgeojson(huc12_str)
            extent = [xmin, ymin, xmax, ymax]
            logger.debug("md5 identifier is %s" % ident)
            logger.debug("pk in table aoi_results is %s" % aoi_id)
            logger.debug(
                "extent of huc12s is %s, %s, %s, %s" %
                (extent[0], extent[1], extent[2], extent[3])
                )

        return (aoi_id, extent, geojson)



