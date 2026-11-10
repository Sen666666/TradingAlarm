"""Physical input-prefix checks only; no lifecycle, Account, or model calculation."""
from pathlib import Path
import importlib.util,sys,hashlib,json,collections,math
from datetime import datetime,time
from dataclasses import replace
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('native_input_preparation_helpers',O/'prepare_inputs.py');P=importlib.util.module_from_spec(sp);sys.modules[sp.name]=P;sp.loader.exec_module(P)
M=P.load_module('prefix_native_context',P.W/'mainline-I-quarter-2025Q3-20261031/adapter.py');M.O=P.W/'mainline-absolute-Q4-20261031'
manifest={r['symbol']:r for r in P.read(P.source(P.U/'STOCK_MANIFEST.json'))}
start=pd.read_csv(P.source(P.R/'dynamic_entry_formation_mechanism_v1/STARTUP_CLOCK_CASES.csv'))
roster=pd.read_csv(P.source(P.R/'pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv'))
checks=[(s,pd.Timestamp('2022-06-30'),'LEXICAL_3') for s in sorted(roster.sid)[:3]]+[(r.sid,pd.Timestamp(r.first_AB_day),'FIXED_STARTUP_FIRST_AB') for r in start.itertuples()]
full=pd.concat([pd.read_parquet(P.source(O/'ALL_MARKET_INPUTS_2022.parquet')),pd.read_parquet(P.source(O/'STARTUP_MARKET_INPUTS.parquet'))]).drop_duplicates(['sid','day']).set_index(['sid','day'])
canon=pd.read_parquet(P.source(O/'CANONICAL_CP_2022_2026.parquet'))
H=P.source(Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz'))
with np.load(H,allow_pickle=False) as z:dates=pd.DatetimeIndex(z['dates']);cols={str(s):j for j,s in enumerate(z['symbols'])};scores=z['score'].copy()
fullcal=dates[dates<=P.END]
model=P.source(P.RR/'continuous-protection-lines-20261028/code/model.py')
baseenv=dict(hashlib=hashlib,json=json,np=np,pd=pd,math=math,collections=collections,SCALE='CP1-original:'+P.sha(model)[:16],BEGIN='2022-01-01')
P.extract(P.W/'cp1-evidence-trace-20261031/trace.py',{'ident','trace'},baseenv)
records={r['series_id']:r for r in P.read(P.source(M.P/'manifest.json'))['series']}
result=[]
for sid,cut,label in checks:
 r=manifest[sid]
 for p,h in r['source_sha256'].items():P.source(p,h)
 for p,h in r['output_sha256'].items():P.source(p,h)
 f0=pd.read_parquet(r['refs']['facts']).loc[:cut].copy();cpin=pd.read_parquet(r['refs']['CP1_input']).loc[:cut].copy();cp=pd.read_parquet(r['refs']['CP1']).loc[:cut].copy()
 signal=next(p for p in r['source_sha256'] if p.endswith('/signal.parquet'));raw=pd.read_parquet(signal).loc[:cut].copy()
 ep=next(p for p in r['source_sha256'] if p.endswith('/events.parquet'));events=pd.read_parquet(ep).loc[:cut].copy().reindex(cpin.index)
 for frame in [f0,cpin,cp,raw,events]:assert len(frame)==0 or frame.index.max()<=cut
 b=M.BP.C.load_bundle(M.BP.C.OLD/'inputs-v2/input-manifest.json',materialize=False);P.source(b.manifest_path);b.lines=tuple(x for x in b.lines if x.security_id==sid);assert len(b.lines)==1;sec=b.lines[0].sector_id
 b.series={k:v for k,v in b.series.items() if k in {sid,sec}};b.sector_series={k:v for k,v in b.sector_series.items() if k==sec}
 for k,item in b.series.items():item.record=records[k]
 mask=dates<=cut;b._h1_cache=(dates[mask],cols,scores[mask].copy());assert b._h1_cache[0].max()<=cut
 sf=pd.read_parquet(P.source(M.O/'industry-facts'/(sec+'.parquet'))).loc[:cut].copy();assert sf.index.max()<=cut
 for k,ff in [(sid,f0),(sec,sf)]:b.series[k].states=ff[['e0_ready','e0_target','segment_id']].rename(columns={'e0_ready':'ready','e0_target':'target'})
 m=M.E.FastMarket.__new__(M.E.FastMarket);m.bundle=b;m.rules=P.read(P.source(P.RR/'pvr-act-comparison-20261027/execution-rules-v2.json'));m.protocol=P.read(P.source(M.BP.C.OLD/'inputs-v2/economic-protocol.json'));m.lines={x.security_id:x for x in b.lines};m.sessions={k:tuple(sorted(datetime.fromisoformat(t) for t in v)) for k,v in m.rules['calendars'].items()}
 f=M.E.Facts.__new__(M.E.Facts);f.b=b;f.market=m;f.f={sid:f0,sec:sf};f.cache={};f.day=None
 clock,stocks,sectors=f.packet(datetime.combine(cut.date(),time(15,10),P.TZ),'I');stock=stocks[0];ss={x.sector_id:x for x in sectors};native=getattr(M.C,'_elig',M.BP.A.eligibility)
 event=native(stock,ss,clock,'S0');cont=native(replace(stock,buy_allowed=m.market_buyable(clock.decision_at)[sid]),ss,clock,'S0');gold=full.loc[(sid,cut)]
 def same(a,bb):return (pd.isna(a) and pd.isna(bb)) or a==bb
 assert same(event.q,gold.event_Q) and same(cont.q,gold.continuing_Q),(sid,cut,'Q differs')
 assert '|'.join(event.reasons)==gold.event_Q_reasons and '|'.join(cont.reasons)==gold.continuing_Q_reasons,(sid,cut,'reasons differ')
 env=dict(baseenv,END=str(cut.date()));# function globals must be bound to the physical-prefix environment
 P.extract(P.W/'cp1-evidence-trace-20261031/trace.py',{'ident','trace'},env)
 rr,_,_=env['trace'](sid,cpin,cp,events,f0.e0_target.reindex(cpin.index).astype(bool));old=canon[canon.sid.eq(sid)&canon.day.le(cut)].sort_values('day')
 assert len(rr)==len(old)
 for x,y in zip(rr,old.itertuples()):
  assert x['receipt_id']==y.cp_id and x['decision_evidence_key']==y.decision_evidence_key and x['evidence_signature']==y.evidence_signature
  assert x['formation_start_exclusive']==y.formation_start_exclusive and x['formation_end_inclusive']==y.formation_end_inclusive
  assert x['original_candidate']==y.cp_candidate and (not bool(x['trace_unknown']))==y.cp_trace_known
 # Independent scalar walk, with no as-of or lineage source beyond cut.
 cal=fullcal[fullcal<=cut];counter=0;last=None;prev_i=None;prevlin=None;knownroot=False;reason='NO_KNOWN_ACTIVE_ROOT'
 for day in cal:
  j=f0.index.searchsorted(day,side='right')-1;ar=f0.iloc[j] if j>=0 else None
  key=(P.tri(ar.i_target),int(ar.segment_id)) if ar is not None else (False,-1)
  if key!=last:counter+=1;last=key
  ex=f0.loc[day] if day in f0.index else None;rz=raw.loc[day] if day in raw.index else None;cur=P.tri(ex.i_target) if ex is not None else None
  known=ex is not None and cur is not None and rz is not None and all(pd.notna(rz[k]) for k in ['source_kind','source_path','segment_id']) and int(ex.segment_id)==int(rz.segment_id)
  lin=P.lineage(rz) if rz is not None else None;adj=known and prevlin is not None and lin==prevlin
  if cur is False:knownroot=False;reason='I_OFF'
  elif cur is True and prev_i is False and adj:knownroot=True;reason='KNOWN_I_0_TO_1'
  elif cur is True and not adj:knownroot=False;reason='MISSING_OR_CHANGED_LINEAGE'
  elif cur is None:knownroot=False;reason='CURRENT_I_UNKNOWN'
  prevlin=lin if known else None;prev_i=cur
 epoch=f'{sid}|{key[1]}|{counter}'
 assert epoch==gold.i_epoch and knownroot==gold.epoch_lineage_known and reason==gold.epoch_lineage_reason,(sid,cut,'epoch differs')
 result.append(dict(sid=sid,cut=str(cut.date()),label=label,event_Q=event.q,continuing_Q=cont.q,Q_and_reasons_exact=True,canonical_receipts=len(rr),receipt_ids_intervals_signatures_exact=True,native_epoch=epoch,epoch_lineage_known=knownroot,epoch_exact=True,all_price_signal_frames_and_H1_physically_truncated=True,no_models_or_lifecycles=True))
 print('PREFIX_PASS',sid,str(cut.date()),len(rr),flush=True)
P.source(Path(__file__));P.save('INPUT_PHYSICAL_PREFIX.json',dict(passed=True,cases=result,accounts=0,lifecycles=0,numeric_model_calculations=0));P.save('INPUT_PREFIX_SOURCE_HASHES.json',P.SOURCES)
seal=P.read(O/'INPUT_OUTPUT_HASHES.json');seal.update({n:P.sha(O/n) for n in ['INPUT_PHYSICAL_PREFIX.json','INPUT_PREFIX_SOURCE_HASHES.json']});P.save('INPUT_OUTPUT_HASHES.json',seal)
