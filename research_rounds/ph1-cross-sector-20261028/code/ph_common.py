from pathlib import Path
import sys,json,hashlib,gzip,importlib.util
import pandas as pd
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
O=Path(__file__).resolve().parents[1]
SA=ROOT/'research_rounds/s-amount-cross-sector-20261028'
sys.path.insert(0,str(SA/'code'))
from sa_common import PRIOR,PREPS,POOLS,LOCAL,TECH,DRUG,SFOLD,pool,sha,read,rows,save
DESIGN=ROOT/'research_rounds/stage-protection-design-20261028'
VARIANTS=['A_E0','A_F','A_PH','R_E0','R_F','R_PH']
FAST={'TECH':ROOT/'research_rounds/intent-support-20261027/signals','DRUG':DRUG/'fast'}
STRICT={s:SA/'signals'/s for s in PREPS}
END='2026-10-27'
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
