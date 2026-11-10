import json,pathlib,hashlib
import pandas as pd,numpy as np
R=pathlib.Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');N=R/'act_peer_volume_mechanism_v1';O=R/'act_entry_research_independent_audit_v1'
paths=json.loads((N/'SOURCE_PATHS.json').read_text());mapping=json.loads((N/'MAPPING_AND_PEERS.json').read_text());cases=json.loads((N/'FIXED_CASES.json').read_text());points=pd.read_csv(N/'POINT_FEATURES.csv');dd=pd.read_csv(N/'DAILY_CONTRIBUTIONS.csv');peers=pd.read_csv(N/'PEER_UNIQUE_SOURCE_AUDIT.csv');cover=pd.read_csv(N/'PEER_COVERAGE_EVERY_CONTRIBUTION.csv');assert len(cases)==22 and set((x[0],x[1]) for x in cases)==set(zip(points.sid,points.day));assert len(dd)==462
frames={};starts={};valids={};oks={};positions={};cols=['open','high','low','close'];raw=['raw_'+s for s in cols];identity=['source_kind','source_path','segment_id','adjustment_factor','volume_factor']
for sid,path in paths.items():
 f=pd.read_parquet(path);frames[sid]=f;positions[sid]={str(d.date()):i for i,d in enumerate(f.index)}
 v=np.isfinite(f.close)&f.close.gt(0)&np.isfinite(f.amount)&f.amount.gt(0)
 for c in ['price_eligible','observed_bar','is_observed_bar']:v&=f[c].eq(True)
 for c in ['source_invalid','synthetic_event_bar']:v&=f[c].eq(False)
 valid=v.to_numpy();seg=f.segment_id.to_numpy();start=np.zeros(len(f),int)
 for i in range(len(f)):
  start[i]=i if i==0 or not valid[i] or not valid[i-1] or seg[i]!=seg[i-1] else start[i-1]
 starts[sid]=start;valids[sid]=valid
 ok=np.isfinite(f[cols+raw]).all(axis=1)&f[cols+raw].gt(0).all(axis=1)
 ok&=f.high.ge(f[['open','close','low']].max(axis=1))&f.low.le(f[['open','close','high']].min(axis=1))
 ok&=f.raw_high.ge(f[['raw_open','raw_close','raw_low']].max(axis=1))&f.raw_low.le(f[['raw_open','raw_close','raw_high']].min(axis=1))
 for c in ['price_eligible','volume_eligible','observed_bar','is_observed_bar']:ok&=f[c].eq(True)
 for c in ['source_invalid','synthetic_event_bar']:ok&=f[c].eq(False)
 ok&=np.isfinite(f.raw_volume)&f.raw_volume.gt(0)&np.isfinite(f.amount)&f.amount.gt(0)&f.volume_unit.eq('shares')&f.amount_unit.eq('CNY')&np.isfinite(f.adjustment_factor)&f.adjustment_factor.gt(0)&np.isfinite(f.volume_factor)&f.volume_factor.gt(0)
 for c in cols:ok&=(f[c]-f['raw_'+c]*f.adjustment_factor).abs().le(1e-10)
 avg=f.amount/f.raw_volume;tol=.5/f.raw_volume+1e-8;ok&=avg.ge(f.raw_low-tol)&avg.le(f.raw_high+tol)
 oks[sid]=ok.to_numpy()
def strict(sid,indices):
 f=frames[sid]; return bool(oks[sid][indices].all() and all(f.iloc[indices][c].notna().all() and f.iloc[indices][c].nunique(dropna=False)==1 for c in identity))
def direct(sid,day):
 f=frames[sid];i=positions[sid].get(day)
 if i is None or not valids[sid][i]:return False,np.nan,None
 first=max(starts[sid][i],i-21);idx=np.arange(first,i+1)
 if len(idx)<22:return False,np.nan,idx
 q=f.iloc[idx];a=float(q.amount.iloc[-1]);ref=float(np.median(q.amount.iloc[:-1]));return strict(sid,idx),np.log(a/ref),idx
# Every published unique peer/date availability and amount ratio independently rebuilt from source.
projected={};maxerr=0
for x in peers.itertuples():
 known,v,idx=direct(x.sid,x.day);assert known==x.available,(x.sid,x.day,known,x.reason)
 if len(idx) if idx is not None else False:
  assert len(idx)==x.n and str(frames[x.sid].index[idx[0]].date())==x.support_start and str(frames[x.sid].index[idx[-1]].date())==x.support_end
 if np.isfinite(v):assert abs(v-x.v)<1e-12;maxerr=max(maxerr,abs(v-x.v))
 projected[x.sid,x.day]=(known,v)
# LOO coverage must include exactly the fixed original-industry roster minus own stock for each contribution.
roster=mapping['mapping'];assert len(roster)==1709 and len(set(roster.values()))==90
lookup={k:g for k,g in cover.groupby(['sid','signal_day','bar_day'])};grouped={k:g for k,g in dd.groupby(['sid','signal_day'])};w=.9**np.arange(20,-1,-1);w=w/w.sum();scoreerr=0;prefix_computations=0
for p in points.itertuples():
 g=grouped[p.sid,p.day].sort_values('bar_day');assert len(g)==21 and max(g.bar_day)<=p.day;es=[];eold=[];ownok=[]
 for j,x in enumerate(g.itertuples()):
  f=frames[p.sid];i=positions[p.sid][x.bar_day];start=starts[p.sid][i];assert i-start>=64
  # Direct bounded source-prefix arithmetic. Only i-64..i close and i-21..i amount are used.
  c=f.close.iloc[i-64:i+1].to_numpy(float);rr=np.diff(np.log(c));r=float(rr[-1]);scale=max(float(np.median(abs(rr[:-1])))*1.4826,1e-8);u=float(np.tanh(r/scale));ref=float(np.median(f.amount.iloc[i-21:i]));v=float(np.log(float(f.amount.iloc[i])/ref));assert abs(u-x.u)<1e-11 and abs(v-x.v)<1e-12 and abs(scale-x.scale)<1e-12
  expected={s for s,sec in roster.items() if sec==roster[p.sid] and s!=p.sid};sub=lookup[p.sid,p.day,x.bar_day];assert set(sub.peer)==expected and p.sid not in set(sub.peer);assert len(sub)==len(expected)
  available=[]
  for z in sub.itertuples():
   known,zv=projected[z.peer,x.bar_day];assert known==z.available
   if known:available.append(zv)
  assert len(available)==x.peer_available;h=float(np.median(available)) if available else np.nan;assert abs(h-x.h_peer)<1e-12;assert abs(x.weight-w[j])<1e-15
  b=float(np.tanh(v-h));e=u*(1+.5*abs(u)*b);old=u*(1+.5*abs(u)*np.tanh(v));assert abs(e-x.e_peer)<1e-11 and abs(old-x.e_original)<1e-11
  assert np.sign(e)==np.sign(u) and abs(e)<=1.5;es.append(e);eold.append(old);ownok.append(direct(p.sid,x.bar_day)[0]);prefix_computations+=1
 E=float(np.dot(w,es));score=50+50*np.tanh(2*E);oldscore=50+50*np.tanh(2*np.dot(w,eold));scoreerr=max(scoreerr,abs(score-p.score_peer_mechanical));assert abs(score-p.score_peer_mechanical)<1e-10 and abs(oldscore-p.score_original)<1e-10
 assert p.peer_supported==(p.strict85_known and all(ownok));assert (np.isfinite(p.score_peer_supported))==p.peer_supported
# Independently reconstruct strict85 from H1 common calendar, not own available observations.
cal=pd.DatetimeIndex(np.load('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz',allow_pickle=False)['dates'])
for p in points.itertuples():
 ix=cal.get_loc(pd.Timestamp(p.day));target=cal[ix-84:ix+1];f=frames[p.sid];indices=f.index.get_indexer(target);known=len(indices)==85 and min(indices)>=0 and strict(p.sid,indices);assert known==p.strict85_known
# Frozen file seals, inputs unchanged.
for f,h in json.loads((N/'FEATURE_SEAL.json').read_text())['files'].items():assert hashlib.sha256((N/f).read_bytes()).hexdigest()==h
for f,h in json.loads((N/'SOURCE_HASHES_BEFORE.json').read_text()).items():assert hashlib.sha256(pathlib.Path(f).read_bytes()).hexdigest()==h
result={'status':'PASS','fixed_points':22,'daily_contributions':462,'unique_peer_date_source_checks':len(peers),'leave_one_out_membership_rows':len(cover),'fixed_source_members':len(paths),'strict85_supported':int(points.peer_supported.sum()),'strict85_unknown':int((~points.peer_supported).sum()),'max_peer_v_error':maxerr,'max_score_error':scoreerr,'own_formula_bounded_prefix_calculations':prefix_computations,'min_available_peers':int(dd.peer_available.min()),'min_coverage_fraction':float(dd.peer_fraction.min()),'account_runs':0,'new_ranks':0,'new_future_labels':0,'limits':['Fixed later-selected 1709/90 roster is NON-PIT.','Available-peer conditional medians may change with membership, IPO, missing bars, and source/factor exclusions; not full-industry medians.','Engineering prefix/future tests do not prove historical publication availability or executable next-open returns.','22 cases are fixed known examples, not accuracy, win rate, economic return or out-of-sample evidence.','Strict-equivalence search is bounded persisted-formula inspection, not exhaustive proof of all prior conversations.'],'selected':points[['sid','day','score_original','score_peer_mechanical','peer_supported','peer_fraction_min']].to_dict('records')}
(O/'PEER_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2))
