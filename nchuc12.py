"""Module contains a class to perform GIS calculations."""
#import psycopg2
from flask import g
import xml.dom.minidom
import hashlib
import time
import random
import logging
import os

cwd = os.path.dirname(os.path.realpath(__file__))
logging.basicConfig(filename=cwd + '/logs/logs.log',
                    level=logging.INFO,
                    format='%(asctime)s %(levelname)s:%(message)s',
                    datefmt='%m/%d/%Y %I:%M:%S %p')


class NCHuc12():

    """Make GIS calculations to get huc12s.

    Input GML file and text description. Run method
    execute to do calculations.

    """

    def __init__(self):
        self.gml = ''
        self.aoi_desc = ''

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
        logging.debug("returning %s polygons as WKT" % len(polygons))
        return geom_list

    def calculations(self, aoiname):
        """Placeholder for actual calculations to be added later. """
        hucs = list()
        with g.db.cursor() as cur:
            cur.execute("select pk from results where identifier = %s",
                        (aoiname,))
            for pk in cur:
                hucs.append(pk[0])
            for pk in hucs:
                level = random.randint(1, 3)
                cur.execute("update results set resultcode = %s where pk = %s",
                            (level, pk))
            g.db.commit()

    def execute(self):
        """Function to run calculations, called from wps.py.

        Call mkgeom to convert GML to list of polygons as WKT.
        Create identifier using time, random and md5.
        Insert into table aoi row for each polygon of input.
        Call stored procedure with identifier to calculate overlap with
        huc12 layer and update table results with rows for each huc12.
        Calculate extents of huc12s.
        Add row to table aoi_results string representation of huc12s,
        extent, and identifier, returning the id of inserted row.

        Returns:
        ident - generated md5 string
        aoi_id - id of row in table aoi_results for this aoi
        extent - list of extents for huc12 for this aoi

        """
        logging.info("aoi description is %s" % self.aoi_desc)
        logging.debug(self.gml[:1000])
        huc12s = list()
        input_geoms = self.mkgeom()
        digest = hashlib.md5()
        digest.update(str(random.randint(10000000, 99999999)))
        digest.update(str(time.time()))
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
            self.calculations(ident)
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
            cur.execute("insert into aoi_results(identifier, huc12s,\
             description, date, x_max, x_min, y_max, y_min) values\
              (%s, %s, %s, now(), %s, %s, %s, %s) returning pk",
                        (ident, huc12_str, self.aoi_desc, xmax, xmin,
                         ymax, ymin))
            aoi_id = cur.fetchone()[0]
            g.db.commit()
            extent = [xmin, ymin, xmax, ymax]
            logging.info("md5 identifier is %s" % ident)
            logging.info("pk in table aoi_results is %s" % aoi_id)
            logging.info("extent of huc12s is %s, %s, %s, %s" %
                         (extent[0], extent[1], extent[2], extent[3]))

        return (ident, aoi_id, extent)



