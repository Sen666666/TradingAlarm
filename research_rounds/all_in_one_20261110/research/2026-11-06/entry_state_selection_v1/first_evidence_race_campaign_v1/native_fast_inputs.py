"""Native daily market Q/epoch inputs, no economic execution.
Source context and original admission calls are copied verbatim from the sealed
prepare_inputs.py. Only date/output selection and canonical receipt loading differ.
Never invokes old main or writes old directories. Full 1709-stock pool, full warm epochs.
"""
from pathlib import Path
from decimal import Decimal as D
from dataclasses import replace
from datetime import datetime, time
from zoneinfo import ZoneInfo
import ast, sys, json, hashlib, importlib.util, collections, math, argparse, time as timer
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent;R=O.parent;E=R/'m3_stock_birth_during_sector_v1'
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');U=W/'universe-cp1-inputs-20261031'
END=pd.Timestamp('2026-06-30');START=pd.Timestamp('2022-01-01');TZ=ZoneInfo('Asia/Shanghai')
SOURCES={};EXTRACTED={};NAV=D('1200000');INIT=D('24000');RISK=D('3000');SLIP=D('.0005')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def source(p,expected=None):
 p=Path(p);h=sha(p)
 if expected is not None:assert h==expected,(str(p),'source hash mismatch')
 if str(p) in SOURCES:assert SOURCES[str(p)]==h
 SOURCES[str(p)]=h;return p
def save(name,obj):
 p=O/name;assert p.parent==O
 p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
def load_module(name,p):
 p=source(p);sp=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(sp);sys.modules[name]=m;sp.loader.exec_module(m);return m
def extract(p,names,env):
 p=source(p);s=p.read_text();found=set()
 for n in ast.parse(s).body:
  if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names:
   x=ast.get_source_segment(s,n);EXTRACTED[str(p)+':'+n.name]=hashlib.sha256(x.encode()).hexdigest();exec(compile(x,str(p)+':definition_only','exec'),env);found.add(n.name)
 assert found==set(names)
def finite(x):
 try:return bool(np.isfinite(x))
 except (TypeError,ValueError):return False
def tri(x):return None if pd.isna(x) or x not in (0,1,True,False) else bool(x)
def flag(z):return all(tri(z.get(k)) is True for k in ['observed_bar','price_eligible','volume_eligible']) and all(tri(z.get(k)) is False for k in ['source_invalid','synthetic_event_bar'])
def lineage(z):return tuple(str(z.get(k)) for k in ['source_kind','source_path','segment_id'])

ORIGINAL=R/"fast_entry_equity_2022_v1"

def main():
 began=timer.monotonic();sm=read(source(U/'STOCK_MANIFEST.json'));im=read(source(U/'INDUSTRY_MANIFEST.json'));manifest={x['symbol']:x for x in sm}
 roster=pd.read_csv(source(R/'pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv')).set_index('sid');ids=sorted(roster.index);assert len(ids)==1709
 startup=pd.read_csv(source(R/'dynamic_entry_formation_mechanism_v1/STARTUP_CLOCK_CASES.csv'));startup_ids=set(startup.sid)
 H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz');source(H)
 with np.load(H,allow_pickle=False) as hh:cal=pd.DatetimeIndex(hh['dates'])
 cal=cal[cal<=END];cal22=cal[(cal>=START)&(cal.year==2022)];di={d:i for i,d in enumerate(cal)}
 # Native module import is definition-only plus in-memory method wrappers. Its context
 # calls load_bundle(materialize=False); no signals or account paths are evaluated.
 M=load_module('fast_entry_native_context',W/'mainline-I-quarter-2025Q3-20261031/adapter.py')
 M.O=W/'mainline-absolute-Q4-20261031'
 # Construct exactly the native Q-only fields. Do not materialize raw OHLC/account
 # execution arrays just to call market_buyable and Facts.packet.
 b=M.BP.C.load_bundle(M.BP.C.OLD/'inputs-v2/input-manifest.json',materialize=False)
 keep=set(ids);b.lines=tuple(x for x in b.lines if x.security_id in keep);sectors={x.sector_id for x in b.lines}
 b.series={k:v for k,v in b.series.items() if k in keep|sectors};b.sector_series={k:v for k,v in b.sector_series.items() if k in sectors}
 records={x['series_id']:x for x in read(M.P/'manifest.json')['series']}
 for sid,item in b.series.items():item.record=records[sid]
 with np.load(H,allow_pickle=False) as hh:b._h1_cache=(pd.DatetimeIndex(hh['dates']),{str(s):j for j,s in enumerate(hh['symbols'])},hh['score'].copy())
 m=M.E.FastMarket.__new__(M.E.FastMarket);m.bundle=b;m.rules=read(RR/'pvr-act-comparison-20261027/execution-rules-v2.json');m.protocol=read(M.BP.C.OLD/'inputs-v2/economic-protocol.json');m.lines={x.security_id:x for x in b.lines}
 m.sessions={k:tuple(sorted(datetime.fromisoformat(t) for t in vv)) for k,vv in m.rules['calendars'].items()}
 f=M.E.Facts.__new__(M.E.Facts);f.b=b;f.market=m;f.f={};f.cache={};f.day=None;f.structure_lookup={}
 for sid in sectors:
  pp=M.O/'industry-facts'/(sid+'.parquet');source(pp);ff=pd.read_parquet(pp).loc[:END];f.f[sid]=ff;b.series[sid].states=ff[['e0_ready','e0_target','segment_id']].rename(columns={'e0_ready':'ready','e0_target':'target'})
 print('NATIVE_Q_CONTEXT_READY',round(timer.monotonic()-began,2),flush=True)
 for pp in [b.manifest_path,M.P/'manifest.json',M.IC/'FREEZE.json',RR/'pvr-act-comparison-20261027/execution-rules-v2.json',RR/'rs-h1-execution-20261025/inputs-v2/economic-protocol.json']:source(pp)
 def refs(x,base):
  if isinstance(x,dict):
   if 'path' in x and 'sha256' in x and isinstance(x['path'],str):
    p=Path(x['path']);p=p if p.is_absolute() else base/p
    if p.is_file():source(p,x['sha256'])
   for z in x.values():refs(z,base)
  elif isinstance(x,list):
   for z in x:refs(z,base)
 refs(b.manifest,b.manifest_path.parent)
 for item in b.series.values():refs(item.record,M.P)
 # Capture the exact original admission implementation used at runtime.
 A=M.BP.A
 import inspect
 source(inspect.getsourcefile(A.eligibility))
 native_elig=getattr(M.C,'_elig',A.eligibility)
 source(inspect.getsourcefile(native_elig))
 source(ORIGINAL/"prepare_inputs.py")
 raw={};cp={};epochs={}
 for n,sid in enumerate(ids):
  r=manifest[sid]
  for p,h in r['source_sha256'].items():source(p,h)
  for p,h in r['output_sha256'].items():source(p,h)
  ff=pd.read_parquet(r['refs']['facts']).loc[:END];q=pd.read_parquet(r['refs']['CP1_input']).loc[:END];z=pd.read_parquet(r['refs']['CP1']).loc[:END]
  assert ff.index.equals(q.index) and q.index.equals(z.index)
  for c in ['close','segment_id','i_target','i_floor']:pd.testing.assert_series_equal(ff[c],q[c],check_exact=True,check_dtype=False,check_freq=False)
  assert q.e0_valid.equals(ff.i_target.astype(bool))
  f.f[sid]=ff;b.series[sid].states=ff[['e0_ready','e0_target','segment_id']].rename(columns={'e0_ready':'ready','e0_target':'target'})
  sp=next(p for p in r['source_sha256'] if p.endswith('/signal.parquet'));raw[sid]=pd.read_parquet(sp).loc[:END];cp[sid]=z
  ep=next(p for p in r['source_sha256'] if p.endswith('/events.parquet'));events=pd.read_parquet(ep).reindex(q.index)
  last=None;counter=0;root_known=False;root_reason='NO_KNOWN_ACTIVE_ROOT';prev_exact=None;prev_i=None;rows={}
  exact=ff[['i_target','segment_id']].reindex(cal);asof=ff[['i_target','segment_id']].reindex(cal,method='ffill');rz=raw[sid][['source_kind','source_path','segment_id']].reindex(cal)
  af=asof.to_dict('records');ef=exact.to_dict('records');rf=rz.to_dict('records')
  targets=set(cal[(cal>=START)&(cal<=END)])
  if sid in startup_ids:
   sw=startup[startup.sid.eq(sid)].iloc[0];targets|={d for d in cal if pd.Timestamp(sw.window_start)<=d<=pd.Timestamp(sw.window_end)}
  for d,ar,er,rr in zip(cal,af,ef,rf):
   target=tri(ar['i_target']) if finite(ar['segment_id']) else False;seg=int(ar['segment_id']) if finite(ar['segment_id']) else -1;key=(target,seg)
   if key!=last:counter+=1;last=key
   lin=lineage(rr);known=tri(er['i_target']) is not None and finite(er['segment_id']) and all(pd.notna(rr.get(k)) for k in ['source_kind','source_path','segment_id']) and int(er['segment_id'])==int(rr['segment_id'])
   current=tri(er['i_target']);adjacent=known and prev_exact is not None and lin==prev_exact
   if current is False:root_known=False;root_reason='I_OFF'
   elif current is True and prev_i is False and adjacent:root_known=True;root_reason='KNOWN_I_0_TO_1'
   elif current is True and not adjacent:root_known=False;root_reason='MISSING_OR_CHANGED_LINEAGE'
   elif current is None:root_known=False;root_reason='CURRENT_I_UNKNOWN'
   if d in targets:rows[d]=dict(i_epoch=f'{sid}|{seg}|{counter}',epoch_lineage_known=bool(root_known),epoch_lineage_reason=root_reason,i_target=current,source_kind=rr.get('source_kind'),source_path=rr.get('source_path'),raw_segment=rr.get('segment_id'),source_adjacent_known=bool(adjacent))
   prev_exact=lin if known else None;prev_i=current
  epochs[sid]=rows
  if (n+1)%200==0:print("FULLWARM_EPOCH",n+1,round(timer.monotonic()-began,2),flush=True)
 cpd=pd.read_parquet(source(ORIGINAL/"CANONICAL_CP_2022_2026.parquet"));assert len(cpd)==99031 and cpd.cp_id.is_unique and not cpd.duplicated(["sid","day"]).any()
 cpmap=cpd.set_index(["sid","day"]).to_dict("index")
 pv=pd.read_parquet(source(R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet'));pv=pv.set_index(['sid','day'])
 ab=pd.read_csv(source(E/'SEALED_ALL_BIRTH_EVENTS.csv'),parse_dates=['day'],low_memory=False);ab=ab[ab.event_type.isin(['A_SECTOR_BIRTH','B_STOCK_BIRTH_DURING_SECTOR'])].copy();assert not ab.duplicated(['sid','day']).any();abmap=ab.set_index(['sid','day']).to_dict('index')
 windows={x.sid:(pd.Timestamp(x.window_start),pd.Timestamp(x.window_end)) for x in startup.itertuples()}
 dates=list(cal[(cal>=START)&(cal<=END)]);rows22=[];case_rows=[]
 for n,d in enumerate(dates):
  clock,stocks,sectors=f.packet(datetime.combine(d.date(),time(15,10),TZ),'I');ss={s.sector_id:s for s in sectors};buyable=m.market_buyable(clock.decision_at)
  for s in stocks:
   sid=s.security_id;keep22=True;keepcase=sid in windows and windows[sid][0]<=d<=windows[sid][1]
   if not (keep22 or keepcase):continue
   ev=native_elig(s,ss,clock,'S0');co=native_elig(replace(s,buy_allowed=buyable[sid]),ss,clock,'S0');ff=f.f[sid];fr=ff.loc[d] if d in ff.index else None;cr=cp[sid].loc[d] if d in cp[sid].index else None;ap=abmap.get((sid,d),{});pr=pv.loc[(sid,d)] if (sid,d) in pv.index else None;cpid=cpmap.get((sid,d),{})
   fresh=tri(cr.receipt) if cr is not None else None
   assert not fresh or cpid
   row=dict(sid=sid,day=d,name=roster.loc[sid,'name'],industry=roster.loc[sid,'industry'],sector=roster.loc[sid,'sector_id'],event_Q=ev.q,continuing_Q=co.q,event_Q_reasons='|'.join(ev.reasons),continuing_Q_reasons='|'.join(co.reasons),i_buy=tri(fr.i_buy) if fr is not None else None,e0_ready=tri(fr.e0_ready) if fr is not None else None,e0_target=tri(fr.e0_target) if fr is not None else None,g_ready=tri(fr.g_ready) if fr is not None else None,g_grade=float(fr.g_grade) if fr is not None and finite(fr.g_grade) else None,i_floor=float(fr.i_floor) if fr is not None and finite(fr.i_floor) else None,cp_fresh=fresh,cp_candidate=float(cr.candidate) if cr is not None and finite(cr.candidate) else None,cp_id=cpid.get('cp_id'),cp_trace_known=cpid.get('cp_trace_known') if fresh else None,cp_trace_unknown=cpid.get('trace_unknown'),PVR_score=float(pr.score) if pr is not None and finite(pr.score) else None,PVR_known=bool(pr is not None and finite(pr.score) and pr.state>=0 and pr.valid_observation),native_H1_score=s.rank.read(clock) if s.rank else None,sector_H1_score=ss[co.sector_id].rank.read(clock) if co.sector_id in ss and ss[co.sector_id].rank else None,AB_event_id=ap.get('event_id'),AB_event_type=ap.get('event_type'),AB_I_qualified=tri(ap.get('I_qualified')),AB_PVR_known=tri(ap.get('PVR_known')),**epochs[sid][d])
   if keep22:rows22.append(row)
   if keepcase:case_rows.append(row)
  if (n+1)%40==0:print('Q_DAYS',n+1,len(dates),round(timer.monotonic()-began,2),flush=True)
 all22=pd.DataFrame(rows22);cases=pd.DataFrame(case_rows)
 for df in [all22,cases]:
  for c in ['event_Q','continuing_Q','i_buy','i_target','cp_fresh','cp_trace_known','AB_I_qualified','AB_PVR_known']:df[c]=df[c].astype('boolean')
 assert len(all22)==len(ids)*len(dates) and not all22.duplicated(['sid','day']).any()
 assert not all22.duplicated(['sid','day']).any()
 comparisons=[]
 for name in ['ALL_MARKET_INPUTS_2022.parquet','ENTRY_CANDIDATES_2022.parquet']:
  original=pd.read_parquet(source(ORIGINAL/name)).set_index(['sid','day']).sort_index()
  new=all22.set_index(['sid','day']).loc[original.index,original.columns].sort_index()
  for col in original.columns:
   pd.testing.assert_series_equal(original[col],new[col],check_dtype=False,check_exact=True,check_names=True)
   comparisons.append(dict(source=name,column=col,rows=len(original),exact=True))
 oldall=pd.read_parquet(ORIGINAL/'ALL_MARKET_INPUTS_2022.parquet')
 assert len(all22[all22.day.dt.year.eq(2022)])==len(oldall)
 candidates=all22[all22.day.dt.year.eq(2022)&(all22.event_Q.fillna(False)|all22.cp_fresh.fillna(False)|all22.AB_event_id.notna())]
 oldcand=pd.read_parquet(ORIGINAL/'ENTRY_CANDIDATES_2022.parquet')
 assert set(zip(candidates.sid,candidates.day))==set(zip(oldcand.sid,oldcand.day))
 fresh=all22[all22.cp_fresh.fillna(False)]
 assert fresh.cp_id.notna().all() and fresh.cp_id.is_unique
 for mod in list(sys.modules.values()):
  pp=getattr(mod,'__file__',None)
  if pp and (str(pp).startswith(str(RR)) or str(pp).startswith(str(W))) and str(pp).endswith('.py'):source(pp)
 source(Path(__file__))
 for p,h in SOURCES.items():assert sha(p)==h,(p,'source drift')
 all22.to_parquet(O/'NATIVE_FAST_INPUTS.parquet',index=False)
 pd.DataFrame(comparisons).to_csv(O/'NATIVE_FAST_INPUT_RECONCILIATION.csv',index=False)
 qa=dict(passed=True,no_economic_execution=True,no_account_or_lifecycle=True,no_cp_reconstruction=True,canonical_source_receipts=len(cpd),stocks=len(ids),days=len(dates),rows=len(all22),start=str(min(dates).date()),end=str(max(dates).date()),all_daily_rows=True,full_warm_epoch=True,original2022_all_fields_exact=True,original2022_candidate_membership_exact=True,compared_columns=len(comparisons),fresh_receipts=len(fresh),seconds=timer.monotonic()-began)
 save('NATIVE_FAST_INPUT_QA.json',qa);save('NATIVE_FAST_INPUT_SOURCE_HASHES.json',SOURCES)
 save('NATIVE_FAST_INPUT_OUTPUT_HASHES.json',{n:sha(O/n) for n in ['native_fast_inputs.py','NATIVE_FAST_INPUTS.parquet','NATIVE_FAST_INPUT_RECONCILIATION.csv','NATIVE_FAST_INPUT_QA.json','NATIVE_FAST_INPUT_SOURCE_HASHES.json']})
 print(json.dumps(qa,ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':main()
