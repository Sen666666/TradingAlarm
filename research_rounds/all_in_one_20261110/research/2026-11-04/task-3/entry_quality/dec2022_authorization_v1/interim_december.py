"""Read completed checkpoint observations only; never restore or advance accounts."""
from pathlib import Path
from decimal import Decimal as D,getcontext
import json,pickle,hashlib,gzip,sys
getcontext().prec=60
O=Path(__file__).resolve().parent;R=O.parent/'trend_exit_controls_v1'
sys.path.insert(0,str(R));import load_inputs as V
def main():
 out=[]
 for arm in ['BASE','R_ONLY','P_ONLY','JOINT']:
  root=R/'runs/BASELINE/2022_2024' if arm=='BASE' else O/'runs'/arm/'2022_2024';cp=root/'checkpoint.pkl';mp=root/'checkpoint.json'
  if not mp.exists():continue
  meta=json.loads(mp.read_text());raw=cp.read_bytes()
  if hashlib.sha256(raw).hexdigest()!=meta['sha256']:print('checkpoint moving',arm);continue
  p=pickle.loads(raw);rr=V.J.W.canon(p['runner']['daily']);tt=V.J.W.canon(p['accounts']['B']['trades']);dm={x['at'][:10]:j for j,x in enumerate(rr)}
  if '2022-12-30' not in dm:continue
  ix=[j for j,x in enumerate(rr) if x['at'][:7]=='2022-12'];a=D(rr[dm['2022-11-30']]['nav']);b=D(rr[dm['2022-12-30']]['nav']);ts=[x for x in tt if x['at'][:7]=='2022-12']
  z=dict(arm=arm,checkpoint_through=meta['at'],checkpoint_sha256=meta['sha256'],full_path_done=(root/'DONE.json').exists(),Dec_start_NAV=a,Dec_end_NAV=b,Dec_wealth=b-a,Dec_return_pct=(b/a-1)*100,lagged_CLOSE_mean_exposure_pct=sum((D(rr[j-1]['inventory'])/D(rr[j-1]['nav']) for j in ix),D(0))/len(ix)*100,Dec_ACT_on=sum(rr[j]['on'] for j in ix),Dec_buy_fills=sum(x['side']=='buy' for x in ts),Dec_sell_fills=sum(x['side']=='sell' for x in ts),Dec_fees=sum((D(x['fees_cny']) for x in ts),D(0)),scope='Completed Dec interval inside still-running complete path; no parameter or action selection from these values')
  out.append(z)
 (O/'INTERIM_DECEMBER_COMPLETED_INTERVALS.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str)+'\n')
 for x in out:print({k:round(float(v),4) if isinstance(v,D) else v for k,v in x.items() if k not in ['checkpoint_sha256','scope']})
if __name__=='__main__':main()
