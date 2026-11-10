"""Read-only native Q/epoch/CP input export and conditional sizing preflight.
No Account/Runner, model calculate/derive, lifecycle, portfolio or PnL is executed.
Only files under this new research directory are written.
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
CASES=[('002174.SZ','2022-11-07'),('002518.SZ','2022-05-12'),('600612.SH','2022-08-11'),('600096.SH','2022-02-17'),('002458.SZ','2022-03-29'),('600028.SH','2022-01-07'),('000009.SZ','2022-05-11'),('000039.SZ','2022-10-17'),('000021.SZ','2022-05-11')]

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
 tpath=W/'cp1-evidence-trace-20261031/trace.py';model=source(RR/'continuous-protection-lines-20261028/code/model.py')
 tenv=dict(hashlib=hashlib,json=json,np=np,pd=pd,math=math,collections=collections,BEGIN='2022-01-01',END='2026-06-30',SCALE='CP1-original:'+sha(model)[:16])
 extract(tpath,{'ident','trace'},tenv)
 old22=read(source(W/'2022-normal-reference-20261031/inputs/MANIFEST.json'));old22={x['sid']:x for x in old22 if not x['industry']}
 raw={};cp={};epochs={};canonical=[];trace_checks=[]
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
  rs,_,checks=tenv['trace'](sid,q,z,events,ff.e0_target.reindex(q.index).astype(bool))
  expected=z.loc[START:END].index[z.loc[START:END].receipt.eq(True)]
  assert [x['confirmed_day'] for x in rs]==[str(d.date()) for d in expected]
  assert len({x['receipt_id'] for x in rs})==len(rs)
  previous=read(source(old22[sid]['output_path'],old22[sid]['output_sha256']))
  new22=[x for x in rs if x['confirmed_day']<'2023-01-01'];assert len(new22)==len(previous)
  for a,bb in zip(new22,previous):
   for k,v in bb.items():assert a[k]==v,(sid,k,'2022 receipt identity differs')
  for x in rs:
   canonical.append(dict(sid=sid,day=pd.Timestamp(x['confirmed_day']),cp_id=x['receipt_id'],cp_candidate=x['original_candidate'],cp_trace_known=not bool(x['trace_unknown']),trace_unknown='|'.join(x['trace_unknown']),scale_id=x['scale_id'],source_segment=x['source_segment'],original_E0_episode_id=x['original_E0_episode_id'],decision_evidence_key=x['decision_evidence_key'],formation_start_exclusive=x['formation_start_exclusive'],formation_end_inclusive=x['formation_end_inclusive'],anchor_observation_id=x['anchor_observation_id'],confirmation_observation_id=x['confirmation_observation_id'],previous_market_receipt_id=x['previous_market_receipt_id'],evidence_signature=x['evidence_signature'],new_advance_price_event_ids=json.dumps(x['new_advance_price_event_ids'])))
  # Native epoch counter is run over the full common clock, retaining as-of state.
  # A separate lineage audit must not reset an unknown native epoch into a fresh one.
  last=None;counter=0;root_known=False;root_reason='NO_KNOWN_ACTIVE_ROOT';prev_exact=None;prev_i=None;rows={}
  exact=ff[['i_target','segment_id']].reindex(cal);asof=ff[['i_target','segment_id']].reindex(cal,method='ffill');rz=raw[sid][['source_kind','source_path','segment_id']].reindex(cal)
  af=asof.to_dict('records');ef=exact.to_dict('records');rf=rz.to_dict('records')
  targets=set(cal22)
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
  trace_checks.append(dict(sid=sid,receipts=len(rs),receipts2022=len(new22),trace_unknown=sum(bool(x['trace_unknown']) for x in rs),original2022_exact=True))
  if (n+1)%200==0:print('FULLWARM_CACHE',n+1,round(timer.monotonic()-began,2),flush=True)
 for r in im:
  for p,h in r['source_sha256'].items():source(p,h)
  for p,h in r['output_sha256'].items():source(p,h)
 cpd=pd.DataFrame(canonical);assert not cpd.duplicated(['sid','day']).any();assert cpd.cp_id.is_unique;assert cpd.decision_evidence_key.is_unique
 cpd.to_parquet(O/'CANONICAL_CP_2022_2026.parquet',index=False);cpmap=cpd.set_index(['sid','day']).to_dict('index')
 print('CANONICAL_READY',len(cpd),round(timer.monotonic()-began,2),flush=True)
 pv=pd.read_parquet(source(R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet'));pv=pv.set_index(['sid','day'])
 ab=pd.read_csv(source(E/'SEALED_ALL_BIRTH_EVENTS.csv'),parse_dates=['day'],low_memory=False);ab=ab[ab.event_type.isin(['A_SECTOR_BIRTH','B_STOCK_BIRTH_DURING_SECTOR'])].copy();assert not ab.duplicated(['sid','day']).any();abmap=ab.set_index(['sid','day']).to_dict('index')
 windows={x.sid:(pd.Timestamp(x.window_start),pd.Timestamp(x.window_end)) for x in startup.itertuples()}
 dates=sorted(set(cal22)|{d for a,bb in windows.values() for d in cal if a<=d<=bb});rows22=[];case_rows=[]
 for n,d in enumerate(dates):
  clock,stocks,sectors=f.packet(datetime.combine(d.date(),time(15,10),TZ),'I');ss={s.sector_id:s for s in sectors};buyable=m.market_buyable(clock.decision_at)
  for s in stocks:
   sid=s.security_id;keep22=d.year==2022;keepcase=sid in windows and windows[sid][0]<=d<=windows[sid][1]
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
 assert len(all22)==len(ids)*len(cal22) and not all22.duplicated(['sid','day']).any()
 candidates=all22[all22.event_Q.fillna(False)|all22.cp_fresh.fillna(False)|all22.AB_event_id.notna()].copy()
 all22.to_parquet(O/'ALL_MARKET_INPUTS_2022.parquet',index=False);candidates.to_parquet(O/'ENTRY_CANDIDATES_2022.parquet',index=False);cases.to_parquet(O/'STARTUP_MARKET_INPUTS.parquet',index=False)
 # Original independent size helper, with the fixed new 2% / .25% constraint.
 sys.path.insert(0,str(RR/'rs-h1-execution-20261025/code'))
 from market_rules import version_on,market_identity_on,RuleUnavailable
 from sector_account import QuantityRule,FeeComponent,FeeSchedule
 env=dict(D=D,version_on=version_on,market_identity_on=market_identity_on,RuleUnavailable=RuleUnavailable,QuantityRule=QuantityRule,FeeComponent=FeeComponent,FeeSchedule=FeeSchedule,SLIP=SLIP,meta={},rules=read(source(RR/'rs-h1-execution-20261025/inputs-v2/market-rules.json')),proxies=read(source(RR/'rs-h1-execution-20261025/inputs-v2/economic-protocol.json'))['approved_proxy_ids'])
 extract(E/'relative_priority_v1/simulate.py',{'getmeta','fee','size'},env)
 fixed=set((sid,pd.Timestamp(d)) for sid,d in CASES)
 for x in startup.itertuples():
  for attr in ['first_AB_day','first_i_buy_in_window','first_CP_in_window']:fixed.add((x.sid,pd.Timestamp(getattr(x,attr))))
 lookup=pd.concat([all22,cases]).drop_duplicates(['sid','day']).set_index(['sid','day']);checks=[]
 for sid,d in sorted(fixed):
  base=lookup.loc[(sid,d)].to_dict();base.update(sid=sid,day=d);z=raw[sid].loc[d] if d in raw[sid].index else {};nextd=cal[di[d]+1] if di[d]+1<len(cal) else None;oz=raw[sid].loc[nextd] if nextd is not None and nextd in raw[sid].index else {};vol=raw[sid].raw_volume;v=vol[vol.gt(0)];cap=(v.rolling(20,min_periods=20).mean()*.01).reindex(raw[sid].index).ffill().get(d,np.nan)
  for role in ['I','CP']:
   out=dict(base,role=role,next_open_day=nextd,nominal_budget=float(INIT),plan_risk_budget=float(RISK));floor=base['i_floor'];cand=base['cp_candidate']
   out['role_market_eligible']=bool((tri(base['AB_I_qualified']) is True and pd.notna(base['AB_event_id'])) or (tri(base['event_Q']) is True and base['epoch_lineage_known'])) if role=='I' else bool(tri(base['cp_fresh']) is True and tri(base['continuing_Q']) is True and tri(base['cp_trace_known']) is True and pd.notna(base['cp_id']))
   if role=='CP':floor=max(floor,cand) if finite(floor) and finite(cand) else None
   if not flag(z) or not finite(z.get('raw_close')) or z.get('raw_close',0)<=0 or not finite(z.get('adjustment_factor')) or z.get('adjustment_factor',0)<=0:out['close_check']='INVALID_CLOSE_UNKNOWN'
   elif not finite(floor) or floor<=0:out['close_check']='ROLE_FLOOR_UNKNOWN'
   elif not finite(cap):out['close_check']='PRIOR_VOLUME_UNKNOWN_AT_CLOSE'
   else:
    fl=D(str(floor))/D(str(z['adjustment_factor']));cl=D(str(z['raw_close']));out['role_floor_signal']=floor;out['close_floor_raw']=float(fl)
    if cl<=fl:out['close_check']='CLOSE_AT_OR_BELOW_PROTECTION'
    else:
     try:
      q,bf,risk,_,_=env['size'](sid,d,cl*(1+SLIP),fl,INIT,RISK,int(cap));out.update(close_check='PASS' if q else 'MINIMUM_LOT_OR_RISK_REJECT_AT_CLOSE',close_q=q,close_fee=float(bf),close_plan_risk=float(risk))
     except (RuleUnavailable,KeyError,ValueError) as exc:out.update(close_check='DATED_RULE_UNKNOWN_AT_CLOSE',close_error=str(exc))
   if out['close_check']!='PASS':out['open_check']='NOT_REACHED_CLOSE_NOT_PASS'
   elif not finite(oz.get('raw_open')) or oz.get('raw_open',0)<=0:out['open_check']='MISSING_NEXT_OPEN_UNKNOWN'
   elif lineage(oz)!=lineage(z):out['open_check']='SOURCE_CHANGED_AT_ENTRY_UNKNOWN'
   elif not finite(oz.get('adjustment_factor')) or not np.isclose(oz['adjustment_factor'],z['adjustment_factor'],rtol=1e-11):out['open_check']='FACTOR_AT_ENTRY_REQUIRES_NET80_BRIDGE_REVIEW'
   else:
    op=D(str(oz['raw_open']));fl=D(str(floor))/D(str(z['adjustment_factor']))
    if op<=fl:out['open_check']='NEXT_OPEN_BELOW_PROTECTION_NOFILL'
    else:
     try:
      q,bf,risk,_,_=env['size'](sid,nextd,op*(1+SLIP),fl,INIT,RISK,int(cap));out.update(open_check='CONDITIONAL_OPEN_PROXY_PASS' if q else 'MINIMUM_LOT_NOT_FUNDED_NOFILL',open_q=q,open_fee=float(bf),open_plan_risk=float(risk),next_raw_open=float(op))
     except (RuleUnavailable,KeyError,ValueError) as exc:out.update(open_check='DATED_RULE_AT_ENTRY_UNKNOWN',open_error=str(exc))
   checks.append(out)
 pd.DataFrame(checks).to_csv(O/'CASE_PREFLIGHT.csv',index=False)
 # All imported local source modules, including native data and admission adapters.
 for mod in list(sys.modules.values()):
  pp=getattr(mod,'__file__',None)
  if pp and (str(pp).startswith(str(RR)) or str(pp).startswith(str(W))) and str(pp).endswith('.py'):source(pp)
 source(Path(__file__))
 for p,h in SOURCES.items():assert sha(p)==h,(p,'end source drift')
 save('INPUT_SOURCE_HASHES.json',SOURCES);save('INPUT_EXTRACTED_DEFINITIONS.json',EXTRACTED);save('CANONICAL_CP_CHECKS.json',trace_checks)
 summary=dict(passed=True,no_accounts=True,no_lifecycles=True,no_numeric_model_recomputation=True,all2022_rows=len(all22),trading_days2022=len(cal22),stocks=1709,candidate_rows=len(candidates),startup_rows=len(cases),preflight_rows=len(checks),canonical_receipts=len(cpd),canonical2022=int(cpd.day.dt.year.eq(2022).sum()),canonical_trace_unknown=int((~cpd.cp_trace_known).sum()),original2022_receipt_exact=True,event_Q={str(k):int(v) for k,v in all22.event_Q.value_counts(dropna=False).items()},continuing_Q={str(k):int(v) for k,v in all22.continuing_Q.value_counts(dropna=False).items()},epoch_lineage_unknown_candidates=int((~candidates.epoch_lineage_known).sum()),seconds=timer.monotonic()-began,limits=['Original S0 Q retains stock/sector H1 readability, original sector E0, static current cap/classification and market availability proxies. PVR is an independent extra queue requirement.','Epoch equality follows native I/segment transition counter. Lineage reliability is separate and never manufactures a new epoch after a data gap.','CP receipt identity follows original E0 episode/segment/scale/anchor/confirmation trace. Original CP numeric input validity uses I, while canonical episode name uses original E0.','Sizing preflight is a new 2%/.25% per-role contract, no real tradability or full lifecycle inference.','Source lineage/receipt UNKNOWN is preserved; missing input is not a negative result.'])
 save('INPUT_PREFLIGHT_SUMMARY.json',summary)
 outputs=['CANONICAL_CP_2022_2026.parquet','ALL_MARKET_INPUTS_2022.parquet','ENTRY_CANDIDATES_2022.parquet','STARTUP_MARKET_INPUTS.parquet','CASE_PREFLIGHT.csv','INPUT_SOURCE_HASHES.json','INPUT_EXTRACTED_DEFINITIONS.json','CANONICAL_CP_CHECKS.json','INPUT_PREFLIGHT_SUMMARY.json']
 save('INPUT_OUTPUT_HASHES.json',{n:sha(O/n) for n in outputs});print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':main()
