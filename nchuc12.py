"""Module contains a class to perform GIS calculations."""
import psycopg2
from flask import g
import xml.dom.minidom
import hashlib
# import time
import random
import logging
import os
import json
import psycopg2.extras

cwd = os.path.dirname(os.path.realpath(__file__))
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
fh = logging.FileHandler(cwd + '/logs/logs.log')
formatter = logging.Formatter(
    '%(asctime)s - %(name)s, %(lineno)s - %(levelname)s - %(message)s',
    datefmt='%m/%d %H:%M:%S'
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
                """select ST_AsGeoJSON(geomsimp, 6) from huc12nc
                where huc_12 = %s""", (huc12, )
            )
            the_geom = cur.fetchone()
            the_geom = (json.loads(the_geom[0]))

            new_feature = {
                "type": "Feature",
                "geometry": the_geom,
                "properties": {
                    "huc12": huc12,
                    "threat": 0}
                }
            list_features.append(new_feature)
        dict_for_json = {
            "type": "FeatureCollection", "features": list_features
            }
    return dict_for_json


class NCHuc12():

    """Make GIS calculations to get huc12s.

   Input:
   gml - gml string for custom AOI, unused otherwise
   aoi_list - list of ids for predefined types, can be hucs or other
   predef_type - value of type from select list on form
   sel_type - predefined, custom or statewide

   For predefined hucs calculate from database or using start of huc string.
   For predefined county or bcr use cache tables.
   For custom and shapefiles calculate with postgis.

   Put huc12s into table results and calculate extent, create csv string of
   huc12 and insert with extents into table aoi_results returning pk as
   resource identifier.


    Common projections for North Carolina:
     EPSG:2264 NC State Plane Feet NAD83
     EPSG:32119 NC State Plane Meters NAD83
     see http://epsg.io/?q=North+Carolina

    """

    def __init__(self):
        self.gml = ''
        self.aoi_list = []
        self.referer = ''
        self.predef_type = ''
        self.sel_type = ''
        self.buff_list5 = []
        self.buff_list12 = []
        self.pt_lon = ""
        self.pt_lat = ""
        self.ptbuffer_km = ''

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
        logger.debug(len(geom_list))
        return geom_list

    def gethucsfromhucs(self, ident):
        """Get list of huc12 for huc predefined type.
        Also accepts list of hus12 from custom type.
        """

        query_str = """select wkb_geometry, huc_12 from huc12nc
        where huc_12 like %s  """
        logger.debug(query_str)
        with g.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            for huc in self.aoi_list:
                cur.execute(
                    query_str, (huc + "%",)
                )
                recs = cur.fetchall()
                for rec in recs:
                    the_geom = rec['wkb_geometry']
                    huc12 = rec['huc_12']
                    cur.execute(
                        """insert into results (huc12, identifier,
                         the_geom, date_added)
                         values (%s, %s, %s, now()) """,
                        (huc12, ident, the_geom)
                    )

    def gethucsfromcache(self, ident, layer):
        """Get list of huc12s for predefined county and bcr. """
        query = "select huc12 from cache_huc12 where " + layer + " = %s"
        huc12_list = []
        with g.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                for lyr_id in self.aoi_list:
                    cur.execute(
                        query, (lyr_id,)
                        )
                    recs = cur.fetchall()
                    for rec in recs:
                        huc12_list.append(rec['huc12'])
        huc12s = set(huc12_list)
        query_str = (
            "select wkb_geometry, huc_12 from huc12nc where huc_12 = %s"
            )
        with g.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            for huc in huc12s:
                cur.execute(
                    query_str, (huc,)
                    )
                recs = cur.fetchall()
                for rec in recs:
                    the_geom = rec['wkb_geometry']
                    huc12 = rec['huc_12']
                    try:
                        cur.execute(
                            """insert into results (huc12, identifier,
                             the_geom, date_added)
                             values (%s, %s, %s, now()) """,
                            (huc12, ident, the_geom)
                            )
                    except Exception as e:
                        logger.debug(e)


    def execute(self):
        """Function to run calculations.

        Returns:
        geojson - dict representing geojson
        aoi_id - id of row in table aoi_results for this aoi
        extent - list of extents for huc12 for this aoi

        """

        huc12s = list()

        digest = hashlib.md5()
        digest.update(str(random.randint(10000000, 99999999)))
        ident = digest.hexdigest()
        with g.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            if self.sel_type == 'predefined':
                if 'Counties' in self.predef_type:
                    # get data for aoi
                    self.gethucsfromcache(ident, 'county')

                    # add buffer data
                    with open('data/countiescache_5k.json') as fp:
                        json_str = fp.read()
                    cache = json.loads(json_str)
                    buff_list = []
                    for co_num in self.aoi_list:
                        buff_list += cache[co_num]
                    self.buff_list5 = list(set(buff_list))
                    # logger.debug(buff_list5)
                    with open('data/countiescache_12k.json') as fp:
                        json_str = fp.read()
                    cache = json.loads(json_str)
                    buff_list = []
                    for co_num in self.aoi_list:
                        buff_list += cache[co_num]
                    self.buff_list12 = list(set(buff_list))

                elif 'BCR' in self.predef_type:
                    self.gethucsfromcache(ident, 'bcr')

                    with open('data/bcrcache_5k.json') as fp:
                        json_str = fp.read()
                    cache = json.loads(json_str)
                    buff_list = []
                    for bcr in self.aoi_list:
                        buff_list += cache[bcr]
                    self.buff_list5 = list(set(buff_list))
                    # logger.debug(len(buff_list5))
                    with open('data/bcrcache_12k.json') as fp:
                        json_str = fp.read()
                    cache = json.loads(json_str)
                    buff_list = []
                    for bcr in self.aoi_list:
                        buff_list += cache[bcr]
                    self.buff_list12 = list(set(buff_list))

                elif 'HUC' in self.predef_type:
                    logger.debug(self.predef_type)
                    logger.debug(len(self.aoi_list[0]))
                    self.gethucsfromhucs(ident)

                    if len(self.aoi_list[0]) == 6:
                        logger.debug("huc6")
                        file_name_5kbuf = 'data/huc6cache_5k.json'
                        file_name_12kbuf = 'data/huc6cache_12k.json'
                    elif len(self.aoi_list[0]) == 8:
                        logger.debug("huc8")
                        file_name_5kbuf = 'data/huc8cache_5k.json'
                        file_name_12kbuf = 'data/huc8cache_12k.json'
                    elif len(self.aoi_list[0]) == 12:
                        logger.debug("huc8")
                        file_name_5kbuf = 'data/huc12cache_5k.json'
                        file_name_12kbuf = 'data/huc12cache_12k.json'
                    else:
                        logger.debug("huc10")
                        file_name_5kbuf = 'data/huc10cache_5k.json'
                        file_name_12kbuf = 'data/huc10cache_12k.json'
                    with open(file_name_5kbuf) as fp:
                        json_str = fp.read()
                    cache = json.loads(json_str)
                    buff_list = []
                    for huc in self.aoi_list:
                        buff_list += cache[huc]
                    self.buff_list5 = list(set(buff_list))
                    # logger.debug(len(buff_list5))
                    with open(file_name_12kbuf) as fp:
                        json_str = fp.read()
                    cache = json.loads(json_str)
                    buff_list = []
                    for huc in self.aoi_list:
                        buff_list += cache[huc]
                    self.buff_list12 = list(set(buff_list))

                else:
                    logger.debug('none type selected')

            elif self.sel_type == 'custom':
                # custom includes shapefile and drawn
                cust_huc12s = []
                # query = """select huc_12 from huc12nc where ST_Intersects(
                #     wkb_geometry, ST_GeomFromText(%s, 4326))"""
                query2 = """
                SELECT ST_Distance(
                    ST_Transform((ST_GeomFromText(%s, 4326)),32119),
                    ST_Transform((select wkb_geometry from huc12nc where
                     huc_12 = %s),32119)
                );
                """
                query3 = "select huc12 from huc12nc order by huc12"
                cur.execute(query3)
                hucs = cur.fetchall()
                input_geom = self.mkgeom()[0]

                for huc in hucs:
                    try:
                        cur.execute(query2, (input_geom, huc[0]))
                    except psycopg2.ProgrammingError:
                        continue
                    res = cur.fetchall()
                    for cust_huc in res:
                        if cust_huc[0] == 0:
                            cust_huc12s.append(huc[0])
                        if cust_huc[0] < 5000:
                            self.buff_list5.append(huc[0])
                        if cust_huc[0] < 12000:
                            self.buff_list12.append(huc[0])

                # from list of hucs12 set aoi_list
                self.aoi_list = list(set(cust_huc12s))
                self.predef_type = 'NC HUC 12'
                self.gethucsfromhucs(ident)
            elif self.sel_type == 'point_buffer':
                logger.debug(self.pt_lon)
                logger.debug(self.pt_lat)
                logger.debug(self.ptbuffer_km)
                lim1 = int(1000 * float(self.ptbuffer_km))
                lim2 = int(1000 * float(self.ptbuffer_km) + 5000)
                lim3 = int(1000 * float(self.ptbuffer_km) + 12000)
                logger.debug("%d %d %d" % (lim1, lim2, lim3))
                query3 = "select huc12 from huc12nc order by huc12"
                cur.execute(query3)
                hucs = cur.fetchall()
                cust_huc12s = []
                # query = """
                #     SELECT (ST_Transform(ST_Buffer(ST_Transform(
                #     ST_GeomFromText('POINT(%s %s)', 4326),32119),
                #     3000), 4326);
                #  """
                query2 = """
                SELECT ST_Distance(
                ST_Transform((ST_GeomFromText('POINT(%s %s)', 4326)),32119),
                ST_Transform((select wkb_geometry from huc12nc where
                huc_12 = %s),32119)
                );
                """
                cur.execute(query3)
                hucs = cur.fetchall()
                for huc in hucs:
                    try:
                        cur.execute(query2, (
                            float(self.pt_lon),
                            float(self.pt_lat),
                            huc[0])
                        )
                    except psycopg2.ProgrammingError:
                        continue
                    res = cur.fetchall()
                    # limit = float(self.ptbuffer_km)

                    for cust_huc in res:
                        if cust_huc[0] < lim1:
                            cust_huc12s.append(huc[0])
                        if cust_huc[0] < lim2:
                            self.buff_list5.append(huc[0])
                        if cust_huc[0] < lim3:
                            self.buff_list12.append(huc[0])

                # from list of hucs12 set aoi_list
                self.aoi_list = list(set(cust_huc12s))
                self.predef_type = 'NC HUC 12'
                self.gethucsfromhucs(ident)

            cur.execute(
                "select huc12 from results where identifier = %s", (ident,)
                )
            for row in cur:
                huc12s.append(row[0])

            huc12_str = ", ".join(huc12s)
            logger.debug("total hucs in aoi is %s" % len(set(huc12s)))
            logger.debug("total hucs in aoi and 5k is %s" % len(set(self.buff_list5)))
            logger.debug("total hucs in aoi and 12k is %s" % len(set(self.buff_list12)))
            buffer5k_str = ", ".join(
                list(set(self.buff_list5) - set(huc12s))
            )
            buffer12k_str = ", ".join(
                list(set(self.buff_list12) - set(huc12s))
            )
            cur.execute(
                """select max(st_xmax(the_geom)) from results where
                identifier = %s""", (ident,)
                )
            xmax = cur.fetchone()[0]
            cur.execute(
                """select min(st_xmin(the_geom)) from results where
                identifier = %s""", (ident,)
                )
            xmin = cur.fetchone()[0]
            cur.execute(
                """select max(st_ymax(the_geom)) from results where
                identifier = %s""", (ident,)
                )
            ymax = cur.fetchone()[0]
            cur.execute(
                """select min(st_ymin(the_geom)) from results where
                identifier = %s""", (ident,)
                )
            ymin = cur.fetchone()[0]
            g.db.rollback()

            cur.execute(
                """insert into aoi_results(identifier, huc12s,
                date, x_max, x_min, y_max, y_min, huc12s_5k, huc12s_12k) values
                (%s, %s,  now(), %s, %s, %s, %s, %s, %s) returning pk""",
                (
                    ident,
                    huc12_str,
                    xmax,
                    xmin,
                    ymax,
                    ymin,
                    buffer5k_str,
                    buffer12k_str
                )
                )
            aoi_id = cur.fetchone()[0]
            logger.debug("aoi id is %d" % aoi_id)
            permalink = self.referer + "#" + str(aoi_id)
            cur.execute(
                """update aoi_results set permalink = %s
                where pk = %s""", (permalink, aoi_id)
                )

            g.db.commit()
            geojson = getgeojson(huc12_str)
            extent = [xmin, ymin, xmax, ymax]
            # logger.debug("md5 identifier is %s" % ident)
            # logger.debug("pk in table aoi_results is %s" % aoi_id)
            # logger.debug(
            #     "extent of huc12s is %s, %s, %s, %s" %
            #     (extent[0], extent[1], extent[2], extent[3])
            #     )

        return (aoi_id, extent, geojson)
