"""Independent frozen ACT alternative-clause arithmetic, no state counterfactual."""
from pathlib import Path
import json,hashlib,gzip,ast
import pandas as pd
import audit_pvr_saved as I
O=I.TASK/'ar6_native_feasibility/ACT_RECOVERY_SEMANTICS'
def main():
 freeze=I.read(O/'SOURCE_FREEZE.json')
 for p,h in freeze['source_hashes'].items():assert I.sha(p)==h
 x=I.read(O/'ACT_CLOCK_AND_CLAUSES.json');rec=I.W/'mainline-absolute-Q4-20261031/recovery.csv';r=pd.read_csv(rec,index_col=0,parse_dates=True)
 # Direct current+62 and prior63 windows, deliberately not optimized by outcomes.
 dates=list(r.index);market=list(r.market);features={}
 for j,d in enumerate(dates):
  if j<63:continue
  m=market[j];inc=sum(market[j-62:j+1])/63;prior=sum(market[j-63:j])/63;up=m>market[j-1];fast=r.loc[d,'breadth']>.6
  old=m>max(market[j-63:j])and up and fast
  assert bool(old)==bool(r.loc[d,'breakout']);assert bool(fast)==bool(r.loc[d,'fast_on'])
  features[str(d.date())]=(inc,prior,bool(up),bool(fast),bool(old),bool(m>inc and up and fast),bool(m>prior and up and fast))
 count=0;periods=[]
 for arm in x['records']:
  assert I.sha(arm['source_book'])==arm['source_book_sha256'];b=I.read(arm['source_book']);actual={a['at'][:10]:a for a in b['audit']if a['kind']=='risk_checkpoint'}
  for p in arm['periods']:
   for a in p['rows']:
    f=features[a['day']];assert abs(a['inclusive_SMA63']-f[0])<1e-12 and abs(a['prior63_mean']-f[1])<1e-12
    assert tuple(a[k]for k in ['up','fast','old_breakout','A_inclusive63_input','A_prior63mean_input'])==f[2:]
    original=actual[a['day']];assert (a['actual_on'],a['actual_flat'],a['actual_event'])==(original['on'],original['flat'],original.get('event'));count+=1
   first=lambda k:next((a['day']for a in p['rows']if a[k]),None)
   assert p['first_fast_input']==first('fast')and p['first_old_breakout_input']==first('old_breakout')
   assert p['first_A_inclusive63_input']==first('A_inclusive63_input')and p['first_A_prior63mean_input']==first('A_prior63mean_input')
   periods.append({k:v for k,v in p.items()if k not in ['rows','interpretation']}|{'policy':arm['policy']})
 out={'passed':True,'source_SHA_checks':len(freeze['source_hashes']),'clause_row_checks':count,'periods':periods,'reviewer_source_SHA256':I.sha(__file__),'reviewer_account_events':0,'source_semantics':'market is exp(cumulative equal-industry mean of constituent logreturns); not HS300 or ETF. Amount-sensitive breadth uses perstock EWMA21(logreturn*min(1,sqrt(amount/prior21medianamount))), then positive fraction of ready stocks, industry min5 and market min8; FAST current1709 is breadth>.6. Old BREAK=market>prior63max AND currentpositive AND FAST. A SMA63 preserves currentpositive and FAST; ACT20_FAST instead uses saw_off plus fast false-to-true crossing, so not equivalent.','scope':'Both current-inclusive63 and prior63 means checked only as source-clause descriptions, not two economic candidates. A must freeze exactly one clock/window convention before prototype. Earlier alternative input is not an actual recovery/buy or profit: future account state changes endogenously. Recovery-only A cannot explain all-ACT-ON L04/post924 loss.'}
 (I.HERE/'PVR_ACT_CLAUSE_SEMANTICS_AUDIT.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
