from pathlib import Path
import sys
import numpy as np,pandas as pd
from data import HERE,ROOT,read,write,sha,now
from model import strength_frame
CORE=ROOT/'research_rounds/pv-participation-response-20261020/code';sys.path.insert(0,str(CORE))
from numeric import event_frame_numeric
from participation import participation_frame

def e0(f,sid):
 p=HERE/'inputs'/(sid+'-e0-frozen.parquet')
 if p.exists():
  x=pd.read_parquet(p);return x[['ready','target','entered','exited','floor']].reindex(f.index)
 all=[]
 for _,g in f.groupby('segment_id',sort=False):
  z=g.loc[g.valid_strength_observation];ev=event_frame_numeric(z.close,z.volume);st,_=participation_frame(z,ev,mode='volume');all.append(st[['ready','target','entered','exited','floor']])
 return pd.concat(all).reindex(f.index)
def main():
 assert not (HERE/'results').exists();(HERE/'results').mkdir();m=read(HERE/'inputs/manifest.json')
 write(HERE/'freeze.json',dict(recorded_at=now(),status='frozen_before_real_model_outputs',protocol_sha256=sha(HERE/'PROTOCOL.md'),code={p.name:sha(p) for p in sorted((HERE/'code').glob('*.py'))},inputs={x['path']:x['sha256'] for x in m['series']},source_manifest_sha256=sha(HERE/'inputs/manifest.json'),research_basis='seen_historical_development',formal_candidates=1,real_output_rule_revisions=0,account_runs=0))
 rows=[]
 for x in m['series']:
  sid=x['asset'];f=pd.read_parquet(x['path']);a=strength_frame(f);p=strength_frame(f,False);b=e0(f,sid)
  result=f[['open','high','low','close','volume','valid_strength_observation','segment_id']].join(a).join(b.add_prefix('e0_'));result['price_only_strength']=p.strength;result['volume_delta_strength']=a.strength-p.strength
  result.to_parquet(HERE/'results'/(sid+'.parquet'));result.loc['2021-01-01':].to_csv(HERE/'results'/(sid+'.csv'),encoding='utf-8-sig')
  v=result.loc['2021-01-01':];good=v.strength.dropna();rows.append(dict(asset=sid,name=x['name'],first=str(v.index[0].date()),last=str(v.index[-1].date()),observations=len(v),scored=len(good),positive=int((good>0).sum()),negative=int((good<0).sum()),e0_valid_days=int(v.e0_target.eq(1).sum()),e0_valid_negative_strength_days=int((v.e0_target.eq(1)&v.strength.lt(0)).sum()),mean_abs_volume_score_delta=float(v.volume_delta_strength.abs().mean()),max_abs_volume_score_delta=float(v.volume_delta_strength.abs().max())))
  print({'asset':sid,'scored':len(good)},flush=True)
 write(HERE/'results/summary.json',dict(recorded_at=now(),rows=rows,accounts=0,no_trade_thresholds=True,formal_candidates=1,real_output_formula_revisions=0))
if __name__=='__main__':main()
