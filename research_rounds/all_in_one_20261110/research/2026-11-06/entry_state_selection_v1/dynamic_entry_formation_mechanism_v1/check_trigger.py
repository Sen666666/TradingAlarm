"""Bounded causal close-feasibility and mechanism cases for C_I; no trade paths/account."""
from pathlib import Path
from decimal import Decimal as D
import ast,sys,json,hashlib
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;R=O.parent;E=R/'m3_stock_birth_during_sector_v1';RUN=E/'relative_priority_equity_run_2022_v1'
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
sys.path.insert(0,str(B/'code'))
from market_rules import version_on,market_identity_on,RuleUnavailable
from sector_account import QuantityRule,FeeComponent,FeeSchedule
NAV=D('1200000');INIT=D('24000');SLOT=D('48000');RISK=D('3000');SLIP=D('.0005');END=pd.Timestamp('2026-06-30')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str)+'\n')
manifest={x['symbol']:x for x in read(U/'STOCK_MANIFEST.json')};rules=read(B/'inputs-v2/market-rules.json');proxies=read(B/'inputs-v2/economic-protocol.json')['approved_proxy_ids']
raw={};facts={};cp={};capacity={};meta={};closecache={};load_count=0;hashes={}
sourcepath=E/'relative_priority_v1/simulate.py';source=sourcepath.read_text();tree=ast.parse(source)
names={'finite','true','false','lineage','flags','DayFrame','load','getmeta','fee','size','checkclose'};extracted={}
for n in tree.body:
 if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names:
  code=ast.get_source_segment(source,n);extracted[n.name]=hashlib.sha256(code.encode()).hexdigest();exec(compile(code,str(sourcepath)+':unchanged_definition','exec'),globals())
assert set(extracted)==names
pc=pd.read_csv(O/'I_BIRTH_CLOCK_PREFLIGHT.csv',float_precision='round_trip')
checks=[]
for r in pc.itertuples():
 if not r.baseline_flat_knownPVR:checks.append(dict(day=r.day,sid=r.sid,close_check='NOT_BASELINE_FLAT_KNOWN_PVR'));continue
 t=pd.Timestamp(r.day);load(r.sid);f=facts[r.sid].get(t)
 ck=checkclose(dict(sid=r.sid,day=t,i_floor=f.i_floor))
 checks.append(dict(day=r.day,sid=r.sid,**ck))
c=pc.merge(pd.DataFrame(checks),on=['day','sid'],validate='one_to_one')
feas=c[c.close_check.eq('PASS')].sort_values(['day','sector','PVR_score','sid'],ascending=[True,True,False,True]).copy();feas['close_feasible_rank']=feas.groupby(['day','sector']).cumcount()+1
c=c.merge(feas[['day','sid','close_feasible_rank']],on=['day','sid'],how='left',validate='one_to_one')
c['baseline_residual_slot_proxy']=c.close_check.eq('PASS')&c.close_feasible_rank.le(c.remaining_slots)
c.to_csv(O/'I_BIRTH_CLOSE_FEASIBILITY.csv',index=False)
z=pd.read_csv(O/'BASELINE_ENTRY_FEATURES.csv',float_precision='round_trip')
join=c[c.baseline_residual_slot_proxy].merge(z,on=['sid','I_root'],suffixes=('_C','_AB'),validate='one_to_many')
assert (pd.to_datetime(join.day_C)<pd.to_datetime(join.signal_day)).all()
join.to_csv(O/'SAME_I_LATER_BASELINE_LINK.csv',index=False)
# Posthoc cases explicitly chosen to illustrate both existing winning/losing paths across sectors.
chosen=[('002174.SZ','2022-11-07'),('002518.SZ','2022-05-12'),('600612.SH','2022-08-11'),('600096.SH','2022-02-17'),('002458.SZ','2022-03-29')]
rows=[]
for sid,day in chosen:
 r=c[c.sid.eq(sid)&c.day.eq(day)].iloc[0];links=join[join.sid.eq(sid)&join.day_C.eq(day)];load(sid);f=pd.read_parquet(manifest[sid]['refs']['facts']);p=raw[sid].frame
 t=pd.Timestamp(day) # next common date comes from frozen full h1 below
 H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
 with np.load(H,allow_pickle=False) as h:cal=pd.DatetimeIndex(h['dates'])
 nd=cal[cal.get_loc(t)+1];n=p.loc[nd];at=p.loc[t]
 for b in links.to_dict('records'):
  nd2=pd.Timestamp(b['entry_day']);newfactor=float(n.adjustment_factor);basefactor=float(p.loc[nd2,'adjustment_factor'])
  # Comparable native adjusted OPEN ratio only, no hypothetical C PnL.
  price_ratio=float(n.raw_open)*newfactor/(float(b['entry_price'])/1.0005*basefactor)
  rows.append(dict(sid=sid,name=r['name'],sector=r.sector,C_signal=day,C_next_open_day=str(nd.date()),C_raw_next_open=n.raw_open,C_native_adjusted_next_open=float(n.raw_open)*newfactor,C_close_q=r.close_q,C_close_plan_risk=r.close_plan_risk,C_close_pass=r.close_check,C_residual_slot_proxy=bool(r.baseline_residual_slot_proxy),baseline_signal=b['signal_day'],baseline_entry=b['entry_day'],baseline_exit=b['exit_day'],baseline_core_net=b['core_net'],baseline_core_return=b['core_return'],baseline_evidence_usable=b['evidence_usable_closed'],C_to_later_AB_comparable_open_ratio=price_ratio,next_open_source_same=lineage(n)==lineage(at),next_open_factor_same=bool(np.isclose(newfactor,float(at.adjustment_factor),rtol=1e-11)),C_is_not_executed=True))
pd.DataFrame(rows).to_csv(O/'POSTHOC_TIMING_CASES.csv',index=False)
# Fixed clock/boundary examples selected without PnL: true late-I, industry full, baseline unknown.
bound=[('600028.SH','2022-01-07'),('000009.SZ','2022-05-11'),('000039.SZ','2022-10-17'),('000021.SZ','2022-05-11')]
c.set_index(['sid','day']).loc[bound].reset_index().to_csv(O/'FIXED_CLOCK_BOUNDARY_CASES.csv',index=False)
summary={'raw_C_I_receipts':len(c),'baseline_flat_known_PVR':int(c.baseline_flat_knownPVR.sum()),'close_check_counts':c.close_check.value_counts().to_dict(),'close_pass_residual_slot_proxy':int(c.baseline_residual_slot_proxy.sum()),'same_I_later_baseline_rounds':len(join),'same_I_later_baseline_usable_closed':int(join.evidence_usable_closed.sum()),'same_I_later_baseline_tail50':int(join.tail50.sum()),'not_C_winrate':'Later baseline outcome labels show delayed same-root participation only, not new C outcomes. No future label affects C or priority.','C_consumer_definition':'I_t=1,I_prev=0 with same-source adjacent known observations; S_prev=S_t=M_prev=M_t=1; original I qualified, known PVR, live own-arm FLAT. Original A/B first, residual industry capacity max(0,2-K_AB); C close-pass sorted original PVR then sid. Receipt one-use only; next-open failure no refill; unknown no qualification.','raw_825_and_baseline_state_proxies_not_new_dynamic_state':True,'economic_runs':0,'native_close_functions_sha256':extracted}
save(O/'TRIGGER_PREFLIGHT_SUMMARY.json',summary)
# Each loaded native source remains exact to manifest.
for sid in raw:
 m=manifest[sid];expected={**m['source_sha256'],**m['output_sha256']}
 for p in [next(p for p in m['source_sha256'] if p.endswith('/signal.parquet')),m['refs']['facts'],m['refs']['CP1']]:assert hashes[p]==expected[p]
extra=[Path(__file__),sourcepath,O/'I_BIRTH_CLOCK_PREFLIGHT.csv',O/'BASELINE_ENTRY_FEATURES.csv',RUN/'DYNAMIC_RUN_ONCE.json',B/'inputs-v2/market-rules.json',B/'inputs-v2/economic-protocol.json',B/'code/market_rules.py',B/'code/sector_account.py']
hashes.update({str(p):sha(p) for p in extra});save(O/'TRIGGER_SOURCE_HASHES.json',hashes)
save(O/'OUTPUT_HASHES.json',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'})
print(json.dumps(summary,indent=2));print(pd.DataFrame(rows).to_string(index=False))
