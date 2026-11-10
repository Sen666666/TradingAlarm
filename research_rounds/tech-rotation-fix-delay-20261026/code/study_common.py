from pathlib import Path
import sys
HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1];BASE=ROOT/'research_rounds/tech-finite-compound-20261026'
sys.path.insert(0,str(BASE/'code'))
from common import *
HERE=Path(__file__).resolve().parents[1]
base_engine=import_path('rotation_original_engine',BASE/'code/engine.py')
base_run=import_path('rotation_original_run',BASE/'code/run_v2.py')
