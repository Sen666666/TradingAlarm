import pandas as pd,numpy as np,json,math,hashlib
from pathlib import Path
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
ma={r['symbol']:r for r in json.loads(M.read_text())}
base=json.loads((R/'selection_entry_diagnosis_v1/cp1_signal_mechanism_v1/cp_band_structure_case_audit_v1/FORMULA_FREEZE.json').read_text())['case_set']
cases=base+[('002317.SZ','2022-10-14'),('300085.SZ','2024-09-19'),('300085.SZ','2024-09-24'),('002583.SZ','2024-09-19'),('002583.SZ','2024-09-24'),('300666.SZ','2026-01-15'),('603061.SH','2026-01-15'),('000681.SZ','2026-01-15'),('603000.SH','2026-01-15'),('002153.SZ','2026-01-15'),('002716.SZ','2026-01-15'),('002865.SZ','2026-01-15'),('688603.SH','2026-01-15'),('301611.SZ','2026-01-15')]
print('FREEZE_BEFORE_CASE_COMPUTE',json.dumps(dict(cases=cases,diagnostic='price EMA12/26 seeds first log price; DEA9 seeds0; hist=DIF-DEA not2hist. G EMA5/21 seeds first return; source reset only; 65th close readiness; s previous63 abs median*1.4826 floor1e-8; no signal filter, no account, no outcomes in formulas; PVR21/.9 positive and negative decomposition; inspect full prefixes, not signal-only reset')))
def calc(f,cp):
 out=[]
 for seg,g in f.groupby('segment_id',sort=False):
  p=np.log(g.close/g.close.iloc[0]);r=p.diff();e=lambda x,n:x.ewm(span=n,adjust=False).mean()
  d=e(p,12)-e(p,26);dea=e(d,9);h=d-dea
  r0=r.fillna(0);v=e(e(r0,12),26);acc=e(e(e(r0.diff().fillna(0),12),26),9)
  assert np.max(np.abs(d/7-v))<1e-12
  assert np.max(np.abs(h/28-acc))<1e-12
  m5=e(r,5);m21=e(r,21);aG=(m5-m21)/8
  sg=cp.reindex(g.index).s;z=cp.reindex(g.index).z;u=cp.reindex(g.index).u;m=cp.reindex(g.index).m
  w=.9**np.arange(20,-1,-1);w/=w.sum()
  roll=lambda x:x.rolling(21,min_periods=21).apply(lambda x:np.dot(w,x),raw=True)
  eneg=roll(m*np.maximum(-u,0));epos=roll(m*np.maximum(u,0));E=epos-eneg
  zz=pd.DataFrame(dict(r=r,s=sg,z=z,DIF=d,DEA=dea,hist=h,v=d/7,acc=h/28,m5=m5,m21=m21,aG=aG,v_s=d/7/sg,h_s=h/7/sg,aG_s=aG/sg,En= eneg,Ep=epos,E=E,PVR=50+50*np.tanh(2*E)),index=g.index)
  zz.iloc[:64]=np.nan
  out.append(zz)
 return pd.concat(out)
res=[];pref=0;hashes={};traj=[]
for sid in sorted(set(s for s,d in cases)):
 refs=ma[sid]['refs'];f=pd.read_parquet(refs['facts']);cp=pd.read_parquet(refs['CP1'])
 cut=max(d for s,d in cases if s==sid);f=f.loc[:cut];cp=cp.reindex(f.index)
 z=calc(f,cp)
 for path in [refs['facts'],refs['CP1']]:hashes[path]=hashlib.sha256(Path(path).read_bytes()).hexdigest()
 ixp=next((p for p in ma[sid]['source_sha256'] if '/ix-a-share-entry-' in p),None)
 if ixp:
  ix=pd.read_parquet(ixp).reindex(f.index)
  both=ix.z5.notna()&z.s.notna()
  assert np.max(np.abs(ix.z5[both]-np.sqrt(5)*z.m5[both]/z.s[both]))<1e-9,(sid,'G5')
  assert np.max(np.abs(ix.z21[both]-np.sqrt(21)*z.m21[both]/z.s[both]))<1e-9,(sid,'G21')
 for s,d in cases:
  if s!=sid:continue
  t=f.index.get_loc(pd.Timestamp(d))
  for n in [t,t+1]:
   pd.testing.assert_frame_equal(calc(f.iloc[:n],cp.iloc[:n]),z.iloc[:n],check_exact=True);pref+=1
  a=z.iloc[t];fr=f.iloc[t];cr=cp.iloc[t]
  res.append(dict(sid=sid,day=d,grade=fr.g_grade,I=bool(fr.i_target),ibuy=bool(fr.i_buy),CP=bool(cr.receipt),raw=fr.raw_close,r_bp=a.r*1e4,m5_bp=a.m5*1e4,m21_bp=a.m21*1e4,v_bp=a.v*1e4,acc_bp=a.acc*1e4,aG_bp=a.aG*1e4,v_s=a.v_s,h_s=a.h_s,PVR=a.PVR,Ep=a.Ep,En=a.En))
  q=z.iloc[max(0,t-5):t+1].copy()
  q['sid']=sid;q['query']=d;q['day']=q.index.strftime('%Y-%m-%d');q['CP']=cp.reindex(q.index).receipt;q['I']=f.reindex(q.index).i_target
  traj.append(q.reset_index(drop=True))
print('FIXED22',pd.DataFrame(res).round(8).to_json(orient='records'))
print('TRAJ22_LAST6',pd.concat(traj)[['sid','query','day','I','CP','v','acc','aG','PVR','Ep','En']].round(8).to_json(orient='records'))
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
print('CHECKS',json.dumps(dict(prefix_exact=pref,source_hashes_unchanged=True,stocks=len(hashes)//2,identities_exact_tol=1e-12,G_native_ratios_exact_tol=1e-9,no_accounts=True)))
