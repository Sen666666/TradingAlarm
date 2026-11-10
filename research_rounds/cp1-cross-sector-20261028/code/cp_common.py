from pathlib import Path
import sys,json,hashlib,gzip,importlib.util
import pandas as pd
import numpy as np
ROOT=Path(__file__).resolve().parents[3];O=Path(__file__).resolve().parents[1]
SA=ROOT/'research_rounds/s-amount-cross-sector-20261028';CP=ROOT/'research_rounds/continuous-protection-lines-20261028';PH=ROOT/'research_rounds/ph1-cross-sector-20261028'
COMBO=ROOT/'research_rounds/swf-pvr-combination-20261028';LOCAL=ROOT/'research_rounds/innovative-drug-local-recovery-20261028'
sys.path.insert(0,str(SA/'code'))
from sa_common import PRIOR,PREPS,POOLS,OLD_TABLES,SFOLD,pool,read,rows,save,sha
MODES=['ACT','S','SF','SW3F','SAMT','ACP','SCP','WCP','MCP'];CPS={'ACP','SCP','WCP','MCP'};END='2026-10-27'
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def frame(sector,sid,cut=None):
 f=pd.read_parquet(PREPS[sector]/'facts'/f'{sid}.parquet').loc[:cut]
 raw=pd.read_parquet(PREPS[sector]/'signals'/f'{sid}.parquet').reindex(f.index)
 ev=pd.read_parquet(PH/'events'/sector/f'{sid}.parquet').reindex(f.index)
 assert f.close.equals(raw.close) and set(raw.amount_unit)=={'CNY'}
 out=f[['close','segment_id','i_target','i_floor']].copy();out['amount']=raw.amount;out['e0_valid']=f.i_target.astype(bool);out['e0_down']=ev.event.eq(-1)
 return out
def cpdir(sector):return CP/'signals' if sector=='TECH' else O/'signals/DRUG'
def reference(sector,mode):
 if mode=='SAMT':return SA/sector/'AMT/accounts-v2','S'
 if sector=='DRUG':return LOCAL/'S0/accounts-v2',mode
 if mode=='SW3F':return COMBO/'RS/S0/accounts-v2',mode
 return SFOLD/'S0/accounts-v2',mode
