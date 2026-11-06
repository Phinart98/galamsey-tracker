"""Settings shared by several pipeline steps, kept in one place so they cannot drift apart."""
import os

WORK_CRS = "EPSG:32630"  # UTM 30N: metres, for areas and distances across the belt
BELT_BBOX = "-3.3,4.7,-0.3,7.5"  # the southern gold belt we cover (lon/lat), for NASA searches
GHANA_BBOX = "-3.3,4.5,1.3,11.2"  # all of Ghana, for checking a tile before it is switched on
CHIP_HALF_KM = 0.8  # each picture is 1.6 km across
HEADERS = {"User-Agent": "galamsey-tracker/0.1 (+https://github.com/Phinart98/galamsey-tracker)"}

PIPELINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(PIPELINE_DIR)
DATA = os.path.join(REPO, "data")  # small JSON the site reads, committed by the weekly run
OUT = os.path.join(PIPELINE_DIR, "out")  # working files, saved on the pipeline-state release
CACHE = os.path.join(OUT, "cache")
