from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent
x=pd.read_csv(O/'FIRST_ENTRIES_WITH_FIP.csv');p=pd.read_csv(O/'MATCHED_PAIRS.csv')
m={r['symbol']:r for r in json.loads(Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json').read_text())}
checks=[]
# Independent direct count, not rolling-helper reuse. Deterministic sample across the entire entry list.
for i in np.linspace(0,len(x)-1,30,dtype=int):
 a=x.iloc[i]; f=pd.read_parquet(m[a.sid]['refs']['facts'],columns=['close','segment_id'])
 pos=f.index.get_loc(pd.Timestamp(a.signal_day))
 for n in [20,60]:
  q=f.iloc[pos-n:pos+1]
  assert len(q)==n+1 and q.segment_id.nunique()==1
  c=q.close.to_numpy();r=np.log(c[1:]/c[:-1]);pret=c[-1]/c[0]-1
  z=np.sign(pret)*((r>0).sum()-(r<0).sum())/n
  assert abs(z-a['F'+str(n)])<1e-12
  assert abs(pret-a['pret'+str(n)])<1e-12
  checks.append(dict(sid=a.sid,day=a.signal_day,n=n,direct_F=float(z),passed=True))
pd.DataFrame(checks).to_csv(O/'DIRECT_COUNT_CHECKS.csv',index=False)
rows=[]
for n,g in p[p['mode'].eq('feature_blind')].groupby('n'):
 used=set();ix=[]
 for i,r in g.sort_values(['signal_day','a_sid','b_sid']).iterrows():
  ks=[(r.a_sid,r.a_root),(r.b_sid,r.b_root)]
  if not any(k in used for k in ks):ix.append(i);used.update(ks)
 for name,q in [('root_dedup',g.loc[ix]),('PVR_gap_le2_posthoc_sensitivity',g[g.pvr_gap.abs()<=2]),('drop_best_ret20_pair_posthoc_sensitivity',g.drop(g.diff_ret20.idxmax()))]:
  d=dict(n=int(n),sensitivity=name,pairs=len(q),description='Diagnostic after main result; not revised selection rule')
  for h in [20,60]:
   z=q[q['both_complete'+str(h)]]
   d['complete'+str(h)]=len(z);d['diff_ret'+str(h)]=z['diff_ret'+str(h)].mean()
  rows.append(d)
pd.DataFrame(rows).to_csv(O/'SENSITIVITIES.csv',index=False)
pd.DataFrame([dict(n=n,long_eligible=int(x['pret'+str(n)].gt(0).sum()),known=int(x['F'+str(n)].notna().sum()),total=len(x))for n in [20,60]]).to_csv(O/'SCOPE.csv',index=False)
c=x[x.closed];print('TOTAL',len(c),int((c.round_pnl>0).sum()),float((c.round_pnl>0).mean()))
for n in [20,60]:
 b=x[x.native_big60];bad=b[(b['pret'+str(n)]<=0)|(b['F'+str(n)]<=0)]
 print('hypothetical_gate_righttail',n,len(b),len(bad),'only diagnostic not new strategy')
print(pd.DataFrame(rows).to_string(index=False))
(O/'SUPPLEMENT_CHECKS.json').write_text(json.dumps(dict(direct_count_checks=len(checks),passed=True,posthoc_sensitivities_declared=True,new_accounts=0),indent=2))

