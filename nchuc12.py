import psycopg2
from flask import  g
import xml.dom.minidom
import hashlib
import time
import random

class NCHuc12():

    def __init__(self):
        self.gml = ''
        self.aoi_desc = ''

    def mkgeom(self):

        geom_list = list()
        dom = xml.dom.minidom.parseString(self.gml)
        polygons = dom.getElementsByTagName("gml:Polygon")
        with g.db.cursor() as cur:
            for polygon in polygons:
                gml_fragment =  polygon.toxml()
                cur.execute("select st_astext(st_geomfromgml(%s))", (gml_fragment,))
                geom_list.append( cur.fetchone()[0] )
        return geom_list
    
    def calculations(self, aoiname):
        hucs = list()
        with g.db.cursor() as cur:
            cur.execute("select pk from results where identifier = %s", (aoiname,))
            for pk in cur:
                hucs.append(pk[0])
            for pk in hucs:
                level = random.randint(1,3)
                cur.execute("update results set resultcode = %s where pk = %s", 
                            (level, pk))
            g.db.commit()
       
    def execute(self):
        huc12s = list()
        input_geoms = self.mkgeom()
        digest = hashlib.md5()
        digest.update(str(random.randint(10000000, 99999999)))
        digest.update(str(time.time()))
        ident = digest.hexdigest()
        with g.db.cursor() as cur:
            cur.execute("insert into aoi_lookup(identifier) values (%s)", (ident, ))
            for b in input_geoms:
                cur.execute("insert into aoi(identifier, the_geom) values (%s, ST_GeomFromText(%s, 4326))", (ident , b))
            cur.execute("select aoitohuc(%s)", (ident,))
            self.calculations(ident)
            g.db.commit()
            
        return ident
        



