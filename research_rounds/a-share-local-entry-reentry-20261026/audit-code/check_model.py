from pathlib import Path
import json,hashlib,math,sys
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1];IX=ROOT/'research_rounds/ix-a-share-entry-20261025'
sys.path.insert(0,str(HERE/'code'));from local_model import receipts,shadow

def main():
 out=HERE/'technical/model-v1';out.mkdir(parents=True,exist_ok=False)
 frozen=json.loads((HERE/'model-freeze-v1.json').read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
 for p,v in frozen['source_sha256'].items():assert sha(ROOT/p)==v,p
 for p,v in frozen['signal_files'].items():assert sha(HERE/p)==v,p
 n=78;c=np.array([100 if i%2==0 else 101 for i in range(n)],float);c[-5:]=[100.5,100,100.1,100.2,100.85]
 f=pd.DataFrame({'open':c,'high':c+.1,'low':c-.2,'close':c,'volume':100.,'segment_id':0,'e0_target':True,'e0_ready':True,'e0_floor':95.},index=pd.date_range('2020-01-01',periods=n))
 low=f.copy();low.iloc[-1,low.columns.get_loc('volume')]=1;high=f.copy();high.iloc[-1,high.columns.get_loc('volume')]=1600;rl=receipts(low);rh=receipts(high);assert not rl.receipt.iloc[-1] and rh.receipt.iloc[-1]
 flat=high.copy();flat.iloc[-1,flat.columns.get_loc('close')]=100.2;flat.iloc[-1,flat.columns.get_loc('high')]=100.3;assert not receipts(flat).receipt.iloc[-1]
 g=f.tail(7).copy();g['close']=[100,98,100,103,104,103,102];g['e0_floor']=[95,95,95,100,101,101,101];g['e0_target']=[True]*6+[False]
 rr=pd.DataFrame({'receipt':[True,False,True,False,False,False,True],'local_floor':[99,np.nan,97,np.nan,np.nan,np.nan,100]},index=g.index);a=shadow(g,rr,True);b=shadow(g,rr,False)
 assert a.entered.sum()==2 and a.exited.sum()==2 and a.exit_reason.iloc[1]=='local' and a.handoff.iloc[3];assert not a.entered.iloc[-1] and b.entered.sum()==1
 for cut in [68,72,76]:pd.testing.assert_frame_equal(receipts(high.iloc[:cut]),rh.iloc[:cut],check_exact=True)
 cases=pd.read_csv(HERE/'raw/cases.csv');prefix=[];formula=[];volume_changed=0;rows=0;events=0
 for p in sorted((HERE/'signals-v1').glob('*.parquet')):
  sid=p.stem;f=pd.read_parquet(IX/'signals'/p.name);r=pd.read_parquet(p);rows+=len(f);events+=int(r.receipt.sum());positions=np.flatnonzero(r.receipt.to_numpy())
  for t in positions[::max(1,len(positions)//3)][:3]:
   j=int(r.anchor_pos.iloc[t]);assert t-3<=j<t
   seg=f.segment_id.iloc[j];h=f.iloc[:j];h=h[h.segment_id.eq(seg)];px=np.r_[h.close.to_numpy(),f.close.iloc[j]]
   # sigma_j excludes return at j itself.
   rr0=np.diff(np.log(h.close.to_numpy()))[-63:];sigma=max(math.sqrt(math.fsum(float(x*x) for x in rr0)/63),1e-8);v0=float(np.median(h.volume.to_numpy()[-21:]));mean=math.fsum(float(x) for x in f.volume.iloc[j+1:t+1])/(t-j);amp=max(.5,min(2.,math.sqrt(mean/v0)));k=math.log(float(f.close.iloc[t])/float(f.close.iloc[j]))*amp/sigma
   assert abs(k-r.credit.iloc[t])<1e-9 and abs(v0-r.volume_baseline.iloc[t])<1e-8*max(v0,1)
   assert float(f.close.iloc[t])>float(f.high.iloc[t-1]);assert abs(float(f.low.iloc[j:t+1].min())-r.local_floor.iloc[t])<1e-12
   formula.append(dict(symbol=sid,date=str(f.index[t].date()),passed=True))
  highprev=f.groupby('segment_id',sort=False).high.shift();candidate=(f.close>highprev)&r.credit.notna();price_credit=r.credit/r.amplifier
  volume_changed+=int(((r.credit>=1)!=(price_credit>=1))[candidate].sum())
  for case in cases[cases.symbol.eq(sid)].to_dict('records'):
   path=out/(case['case']+'-truncated-evidence.parquet');f.loc[:case['anchor']].to_parquet(path);ff=pd.read_parquet(path);q=receipts(ff)
   pd.testing.assert_frame_equal(q,r.loc[ff.index,q.columns],check_exact=True);prefix.append(dict(case=case['case'],rows=len(ff),passed=True))
 result=dict(passed=True,source_hash_checks=len(frozen['source_sha256']),signal_hash_checks=len(frozen['signal_files']),rows=rows,receipts=events,independent_formula_checks=len(formula),physical_local_fact_prefixes=prefix,synthetic_prefixes=3,same_price_different_volume_changes_receipt=True,giant_volume_no_price_no_receipt=True,local_stop_reentry_and_E0_handoff=True,marginal_volume_amplifier_changes_receipt_dates=volume_changed,marginal_ablation_not_full_price_only_E0_policy=True,code_sha256=sha(__file__))
 (HERE/'technical/model-receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');pd.DataFrame(formula).to_csv(out/'formula.csv',index=False);print({k:v for k,v in result.items() if k!='physical_local_fact_prefixes'},flush=True)
if __name__=='__main__':main()
