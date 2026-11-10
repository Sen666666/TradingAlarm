"""Prepare exactly the previous ten sources, no download or account engine."""
from common_rc1 import *
from checks_rc1 import modules
import pandas as pd

def main():
 out=HERE/'inputs';out.mkdir(exist_ok=False);api,grade,policy,m1=modules();rows=[]
 recs={x['series_id']:x for x in read(OLD/'prepared-v2/manifest.json')['series']}
 for sid in NAMES:
  if sid in list(NAMES)[:7]:
   f=pd.read_parquet(B5/'inputs'/f'{sid}.parquet');e=pd.read_parquet(B5/'results-v2'/sid/'evidence.parquet');b=pd.read_parquet(B5/'results-v2'/sid/'state.parquet');source=[B5/'inputs'/f'{sid}.parquet',B5/'results-v2'/sid/'evidence.parquet',B5/'results-v2'/sid/'state.parquet']
  else:
   sys.path.insert(0,str(ROOT/'research_rounds/pv-participation-response-20261020/code'));from data_utils import eligible_prices
   ref=recs[sid]['files']['signal'];p=OLD/'prepared-v2'/ref['path'];assert sha(p)==ref['sha256'];raw=pd.read_parquet(p);f=eligible_prices(raw)[['open','high','low','close','volume','segment_id']].copy();f['valid_price_observation']=True;f['valid_strength_observation']=np.isfinite(f.volume)&f.volume.gt(0)
   a=api.run_b5(f);e=a['evidence'];b=a['state'];source=[p,SRC/'signals'/f'{sid}.parquet']
  g,_=grade.classify(e);oldix=policy.project(e,b,g,'G1_IX');mm=m1.describe(f.assign(acute_down=g.acute_down))
  if sid not in list(NAMES)[:7]:
   old=pd.read_parquet(SRC/'signals'/f'{sid}.parquet');assert f.index.equals(old.index)
   for col in ['grade','score','proposal','z5','z21','fresh_up','promotion_blocked','acute_down']:np.testing.assert_array_equal(g[col].to_numpy(),old[col].to_numpy(),err_msg=sid+col)
   for col in ['target','entered','exited','floor']:np.testing.assert_array_equal(oldix[col].to_numpy(),old['ix_'+col].to_numpy(),err_msg=sid+col)
   for col in ['target','entered','exited','floor']:np.testing.assert_array_equal(b[col].to_numpy(dtype=float,na_value=np.nan),old['e0_'+col].to_numpy(dtype=float,na_value=np.nan))
  folder=out/sid;folder.mkdir()
  for name,frame in [('bars',f),('evidence',e),('E0',b),('G1',g),('IX',oldix),('M1',mm)]:frame.to_parquet(folder/f'{name}.parquet')
  rows.append(dict(symbol=sid,name=NAMES[sid],rows=len(f),sources={str(p.relative_to(ROOT)):sha(p) for p in source},prepared={str(p.relative_to(ROOT)):sha(p) for p in folder.glob('*.parquet')},old_IX_identity=True))
  print(dict(prepared=sid,rows=len(f)),flush=True)
 write(out/'manifest.json',dict(recorded_at=now(),series=rows,accounts=0,downloads=0))
if __name__=='__main__':main()
