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
  vp=e(e(r0.clip(lower=0),12),26);vn=e(e((-r0).clip(lower=0),12),26);bp=e(vp,9);bn=e(vn,9)
  L=np.maximum(0,np.minimum(np.minimum(vn-bn,dea/7-d/7),m21-m5))
  sg=cp.reindex(g.index).s;z=cp.reindex(g.index).z;u=cp.reindex(g.index).u;m=cp.reindex(g.index).m
  w=.9**np.arange(20,-1,-1);w/=w.sum()
  roll=lambda x:x.rolling(21,min_periods=21).apply(lambda x:np.dot(w,x),raw=True)
  eneg=roll(m*np.maximum(-u,0));epos=roll(m*np.maximum(u,0));E=epos-eneg
  zz=pd.DataFrame(dict(r=r,s=sg,z=z,DIF=d,DEA=dea,hist=h,v=d/7,acc=h/28,m5=m5,m21=m21,aG=aG,v_s=d/7/sg,h_s=h/7/sg,aG_s=aG/sg,Vp=vp,Vn=vn,Bp=bp,Bn=bn,L=L,Lnorm=L/sg,En= eneg,Ep=epos,E=E,PVR=50+50*np.tanh(2*E)),index=g.index)
  zz.iloc[:64]=np.nan
  out.append(zz)
 return pd.concat(out)

mother=pd.read_parquet(R/'selection_entry_diagnosis_v1/mobile_candidate_response_v1/LEGAL_EMPTY_MOBILE_CANDIDATES.parquet')
mother=mother[mother.account.eq('PVR')]
pieces=[];summary=[];hashes={};prefix=0
for sid in sorted(set(s for s,d in cases)):
 refs=ma[sid]['refs'];f=pd.read_parquet(refs['facts']);cp=pd.read_parquet(refs['CP1'])
 cutoff=max(d for s,d in cases if s==sid);f=f.loc[:cutoff];cp=cp.reindex(f.index);z=calc(f,cp)
 for path in [refs['facts'],refs['CP1']]:hashes[path]=hashlib.sha256(Path(path).read_bytes()).hexdigest()
 z['Enew']=z.E-np.minimum(np.maximum(z.E,0),z.Lnorm);z['Pnew']=50+50*np.tanh(2*z.Enew);z['delta']=z.Pnew-z.PVR
 assert (z.delta.dropna()<=1e-10).all()
 assert (z.loc[z.E<=0,'delta'].abs()<1e-10).all()
 assert (z.loc[(z.m5>=z.m21)|(z.hist>=0),'delta'].abs().dropna()<1e-10).all()
 z['sid']=sid;z['day']=z.index.strftime('%Y-%m-%d');z['I']=f.i_target;z['ibuy']=f.i_buy;z['CP']=cp.receipt;z['grade']=f.g_grade;z['raw']=f.raw_close
 piece=z[(z.day>='2022-01-01')&z.CP].copy();pieces.append(piece)
 zz=piece.merge(mother[mother.sid.eq(sid)][['day','original_PVR']] if 'original_PVR' in mother else mother[mother.sid.eq(sid)][['day']],on='day',how='inner')
 for d in [x[1] for x in cases if x[0]==sid]:
  t=f.index.get_loc(pd.Timestamp(d))
  for n in [t,t+1]:
   sub=calc(f.iloc[:n],cp.iloc[:n]);pd.testing.assert_frame_equal(sub,z.iloc[:n][sub.columns],check_exact=True);prefix+=1
 summary.append(dict(sid=sid,cutoff=cutoff,CP=len(piece),hist_negative=int(piece.hist.lt(0).sum()),downside_driver=int(piece.L.gt(1e-14).sum()),score_changed=int(piece.delta.lt(-1e-10).sum()),legal=len(zz),legal_changed=int(zz.delta.lt(-1e-10).sum()),max_drop=-float(piece.delta.min()) if len(piece) else None))
allcp=pd.concat(pieces)
legal=allcp.merge(mother[['sid','day']],on=['sid','day'],how='inner',validate='one_to_one')
print('FUSION_FULL_PREFIX_COUNTS',json.dumps(summary))
print('TOTAL',json.dumps(dict(CP=len(allcp),hist_negative=int(allcp.hist.lt(0).sum()),downside_driver=int(allcp.L.gt(1e-14).sum()),score_changed=int(allcp.delta.lt(-1e-10).sum()),legal_CP=len(legal),legal_changed=int(legal.delta.lt(-1e-10).sum()),prefix=prefix,max_drop=float(-allcp.delta.min()))))
print('LARGEST_CHANGED',allcp[allcp.delta.lt(-1e-10)].sort_values('delta').head(12)[['sid','day','I','ibuy','CP','grade','raw','m5','m21','v','acc','Vn','Bn','Lnorm','PVR','Pnew','delta']].round(10).to_json(orient='records'))
print('FIXED_DAY_FUSION',allcp[[((s,d)in cases)or((s,d)in [tuple(c) for c in cases]) for s,d in zip(allcp.sid,allcp.day)]][['sid','day','PVR','Pnew','delta']].round(10).to_json(orient='records'))
for name,rr in [('steady',np.r_[0,np.full(599,.01)]),('positive_slowdown',np.r_[0,np.full(299,.02),np.full(300,.005)]),('upturn',np.r_[0,np.full(299,-.01),np.full(30,.02)]),('deterioration',np.r_[0,np.full(299,.01),np.full(30,-.02)])]:
 f=pd.DataFrame({'close':np.exp(np.cumsum(rr)), 'segment_id':0});r=pd.Series(rr);s=pd.Series(.01,index=f.index)
 cp=pd.DataFrame(dict(s=s,z=s,u=np.tanh(r/s),m=1.))
 zz=calc(f,cp)
 ix=[299,300,301,304,310,329] if len(f)>329 else [299,300,301,304,310,len(f)-1]
 print('SYNTHETIC',name,zz.loc[sorted(set(j for j in ix if j<len(f))),['r','v','acc','aG','Vn','Bn','Lnorm']].round(10).to_json(orient='index'))
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
print('SOURCE_UNCHANGED',True)
