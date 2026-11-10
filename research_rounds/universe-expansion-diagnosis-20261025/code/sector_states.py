from common import *
from concurrent.futures import ProcessPoolExecutor

def worker(rec):
 sys.path.insert(0,str(ROOT/'research_rounds/pv-strength-b5-20261025/code'));import api
 sys.path.insert(0,str(G1/'code'));from grade import classify
 from policies_g1 import project
 sys.path.insert(0,str(ROOT/'research_rounds/pv-participation-response-20261020/code'));from data_utils import eligible_prices
 p=OLD/'prepared-v2'/rec['files']['signal']['path'];assert sha(p)==rec['files']['signal']['sha256'];f=eligible_prices(pd.read_parquet(p))[['open','high','low','close','volume','segment_id']].copy();f['valid_price_observation']=True;f['valid_strength_observation']=np.isfinite(f.volume)&f.volume.gt(0)
 r=api.run_b5(f,enhancements=False);b=r['state'];g,_=classify(r['evidence']);ix=project(r['evidence'],b,g,'G1_IX');old=pd.read_parquet(OLD/'prepared-v2'/rec['files']['states']['path']);assert old.index.equals(b.index)
 for col in ['ready','target','floor']:np.testing.assert_allclose(old[col].to_numpy(float,na_value=np.nan),b[col].to_numpy(float,na_value=np.nan),rtol=0,atol=0,equal_nan=True)
 result=pd.DataFrame(dict(e0_target=b.target,ix_target=ix.target,buy_event=ix.buy_event,ix_floor=ix.floor,grade=g.grade,ready=g.ready),index=f.index);out=HERE/'sector-states'/f'{rec["series_id"]}.parquet';result.to_parquet(out)
 return dict(symbol=rec['series_id'],rows=len(f),E0_exact=True,source_sha256=sha(p),output_sha256=sha(out))
def main():
 out=HERE/'sector-states';out.mkdir(exist_ok=False);recs=[r for r in read(OLD/'prepared-v2/manifest.json')['series'] if r['series_id'].startswith('URFI')];rows=[]
 with ProcessPoolExecutor(max_workers=4) as pool:
  for row in pool.map(worker,recs):
   rows.append(row)
   if len(rows)%15==0:print(dict(sectors_done=len(rows)),flush=True)
 write(out/'manifest.json',dict(recorded_at=now(),sectors=len(rows),new_trend_formula=False,rows=rows,old_IX_reused=True,account_runs=0));print(dict(sector_states_complete=len(rows)),flush=True)
if __name__=='__main__':main()
