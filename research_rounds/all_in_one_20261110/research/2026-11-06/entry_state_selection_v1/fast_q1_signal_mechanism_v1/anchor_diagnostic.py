"""One structural hypothesis, feature-only extraction before outcome join; no economic replay."""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
O=Path(__file__).resolve().parent;R=O.parent;F=R/'fast_entry_equity_2022_v1';U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031');H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz');S={}
def src(p):p=Path(p);S[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
hyp={'status':'DESIGN_HYPOTHESIS_NOT_PREREGISTERED_ECONOMIC_TEST','primary_formula':'current known I-root birth protection floor > previous complete known I-root birth protection floor; exact native adjusted-price basis and lineage; no return/PVR cutoff','reason':'one positive fill consumes one I epoch, but next lower-base I epoch resets this right without remembering the prior native protection anchor','secondary_fields':'previous final ratcheted floor is descriptive only, not an alternate candidate to choose by profit','startup_test':'seven fixed 2024/26 cases must be examined before any proposal to test economics','no_new_economic_path':True}
(O/'ANCHOR_HYPOTHESIS.json').write_text(json.dumps(hyp,indent=2))
with np.load(src(H),allow_pickle=False) as h:cal=pd.DatetimeIndex(h['dates'])
cal=cal[cal<='2026-06-30'];p=pd.read_csv(src(F/'report/INITIAL_AND_FULL_ROUNDS.csv'),low_memory=False);p=p[p.arm.eq('AB_FAST_SMALL')].copy();p['day']=pd.to_datetime(p.signal_day);st=pd.read_parquet(src(F/'STARTUP_MARKET_INPUTS.parquet'));targets=pd.concat([p[['sid','day']],st[['sid','day']]]).drop_duplicates();sm=json.loads(src(U/'STOCK_MANIFEST.json').read_text());rows=[]
for m in sm:
 sid=m['symbol'];ds=set(targets.loc[targets.sid.eq(sid),'day']);
 if not ds:continue
 fp=src(m['refs']['facts']);sp=src(next(x for x in m['source_sha256'] if x.endswith('/signal.parquet')));assert S[str(fp)]==m['output_sha256'][str(fp)];assert S[str(sp)]==m['source_sha256'][str(sp)]
 f=pd.read_parquet(fp).reindex(cal);lin=pd.read_parquet(sp,columns=['source_kind','source_path','segment_id']).reindex(cal);root=None;rootfloor=None;lastfloor=None;previous=None;prevI=None;prevlin=None
 for day,on,floor,seg,lk in zip(cal,f.i_target,f.i_floor,f.segment_id,lin.itertuples(index=False,name=None)):
  known=pd.notna(on) and on in [0,1] and pd.notna(seg) and all(pd.notna(x) for x in lk) and seg==lk[2];adj=known and prevlin is not None and lk==prevlin
  if not known or not adj:root=None;rootfloor=None;lastfloor=None;previous=None
  if known and on==0:
   if root is not None and lastfloor is not None:previous=(root,rootfloor,lastfloor,day)
   root=None;rootfloor=None;lastfloor=None
  elif known and on==1:
   if adj and prevI==0:
    root=day;rootfloor=float(floor) if pd.notna(floor) and np.isfinite(floor) and floor>0 else None;lastfloor=rootfloor
   if root is not None and pd.notna(floor) and np.isfinite(floor) and floor>0:lastfloor=float(floor)
  if day in ds:
   pp=previous if previous is not None else (None,None,None,None);k=root is not None and rootfloor is not None and pp[1] is not None;cl='HIGHER' if k and rootfloor>pp[1] else 'LOWER' if k and rootfloor<pp[1] else 'EQUAL' if k else 'UNKNOWN_PREVIOUS_ROOT_OR_LINEAGE'
   rows.append(dict(sid=sid,day=day,I_root_day=root,I_birth_floor=rootfloor,previous_I_root_day=pp[0],previous_I_birth_floor=pp[1],previous_I_last_floor=pp[2],previous_I_end_day=pp[3],birth_anchor_comparison=cl,known_cross_root=k,current_I_floor=float(floor) if pd.notna(floor) else None,above_previous_last_floor=bool(rootfloor>pp[2]) if k else None))
  prevlin=lk if known else None;prevI=int(on) if known else None
x=pd.DataFrame(rows);assert not x.duplicated(['sid','day']).any();x.to_csv(O/'ANCHOR_FEATURES.csv',index=False)
n=p.merge(x,on=['sid','day'],validate='one_to_one');n['quarter']=n.day.dt.to_period('Q').astype(str);n.to_csv(O/'ANCHOR_PERMITS.csv',index=False);sx=st.merge(x,on=['sid','day'],validate='one_to_one');sx.to_csv(O/'ANCHOR_STARTUP.csv',index=False)
def stat(g):
 c=g[g.initial_evidence_usable];return dict(permits=len(g),execution_unknown=int(g.status.str.contains('UNKNOWN').sum()),nofill=int(g.status.str.contains('NOFILL').sum()),financial_unknown_closed=int((g.initial_closed&~g.initial_evidence_usable).sum()),usable=len(c),wins=int(c.initial_net.gt(0).sum()),win_rate=float(c.initial_net.gt(0).mean()) if len(c) else None,net=float(c.initial_net.sum()),mean_net=float(c.initial_net.mean()) if len(c) else None,tail50=int(c.initial_return.ge(.5).sum()))
res=[]
for period,g in [('ALL',n)]+list(n.groupby('quarter')):
 for label,z in g.groupby('birth_anchor_comparison'):res.append(dict(period=period,label=label,**stat(z)))
pd.DataFrame(res).to_csv(O/'ANCHOR_STRATA.csv',index=False)
source=src(Path(__file__));(O/'ANCHOR_SOURCE_HASHES.json').write_text(json.dumps(S,indent=2));print(pd.DataFrame(res).to_string(index=False),flush=True)
