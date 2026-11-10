import json,gzip,pathlib,hashlib,collections,math
from decimal import Decimal as D
import pandas as pd
R=pathlib.Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');O=pathlib.Path(__file__).parent;B=R/'semiconductor_account_attribution_v1';P=R/'account_comparison_continuous_v1/run_1200000/pair';S=R/'semiconductor_h1_scope_v1'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
sources={}
def source(p):sources[str(p)]=sha(p);return p
rounds=[r for r in read(source(B/'ORIGINAL_ROUNDS_2026.json')) if r['closed']];assert len(rounds)==8 and len(set(r['sid'] for r in rounds))==7
tr=read(source(B/'RAW_FILTERED_TRADES_2026.json'));cp=read(source(B/'ALL_739_CP_EVENT_FUNNEL.json'));op=read(source(B/'RAW_FILTERED_OPPORTUNITIES_2026.json'));pn=read(source(B/'RAW_FILTERED_PENDING_2026.json'));fu=read(source(B/'RAW_FILTERED_FUNDING_2026.json'))
a=json.load(gzip.open(source(P/'PVR.json.gz'),'rt'));sig=pd.read_parquet(source(S/'ENRICHED_DAILY.parquet')); sm={(r['sid'],r['day']):r for r in sig.to_dict('records')};daily=[]
for line in gzip.open(source(P/'daily.jsonl.gz'),'rt'):
 if '2026-' in line and '"PVR"' in line:
  d=json.loads(line)
  if d['account']=='PVR':daily.append(d)
assert len(daily)==85 and all(d['on'] for d in daily)
dm={d['at'][:10]:d for d in daily}; days=sorted(dm)
# Saved diagnostics must still match the previously sealed source account.
old=read(B/'SOURCE_HASHES.json')
for p,h in sources.items():
 if p in old:assert h==old[p],('OLD_SOURCE_CHANGED',p)
rows=[]
for r in sorted(rounds,key=lambda z:(z['entry_day'],z['sid'])):
 sid=r['sid'];entry=r['entry_day'];exit=r['closed_day'];sday=r['signal_day'];name=sm[(sid,sday)]['name'];tb=[t for t in tr if t['security_id']==sid and t['side']=='buy' and entry<=t['at'][:10]<=exit];ids={t['layer'] for t in tb};ts=[t for t in tr if t['security_id']==sid and t['side']=='sell' and any(p['layer'] in ids for p in t['parts'])];assert len(ts)==1
 sell=ts[0];req=[x for x in a['audit'] if x.get('kind')=='exit_request' and x.get('sid')==sid and entry<=x['at'][:10]<exit];assert len(req)==1
 trigger=req[0]['at'][:10];prior=max(d for d in days if d<trigger);layers=[l for l in dm[prior]['layers'] if l['id'] in ids]; sf=sm[(sid,trigger)];factor=D(str(sf['factor']));adjclose=D(str(sf['close']));floors=[{'layer':l['id'],'q':l['qty'],'old_floor_adjusted':l['floor'],'old_floor_raw':str(D(l['floor'])/factor),'close_le_prior_floor':adjclose<=D(l['floor'])} for l in layers]
 reason=sell['reason'];assert (reason=='CP1_add_protection' and all(x['close_le_prior_floor'] for x in floors) and sf['i_target']==1) or (reason=='I_structure_exit' and sf['i_target']==0)
 opens_missing=[d for d in days if trigger<d<exit and (sid,d) not in sm];assert all((sid,d) not in sm for d in opens_missing)
 pc=[x for x in cp if x['sid']==sid and exit<=x['day']<='2026-05-15'];flatpc=[x for x in pc if not x['held']];laterbuys=[t for t in tr if t['security_id']==sid and t['side']=='buy' and t['at'][:10]>exit]
 # Re-entry is eligible after sale OPEN, including same-day CLOSE. Stop flat comparison at next buy.
 nextbuy=min((t['at'][:10] for t in laterbuys),default=None);episodecp=[x for x in flatpc if nextbuy is None or x['day']<nextbuy]
 post_sig=sig[(sig.sid==sid)&(sig.day>exit)&(sig.day<='2026-05-15')]
 exfact=sm[(sid,exit)];base=float(sell['raw_open'])*float(exfact['factor'])
 prices={}
 for day in ['2026-05-15','2026-06-30']:
  z=sm.get((sid,day));prices[day]=None if z is None else {'raw_close':z['raw_close'],'adjusted_close':z['close'],'same_basis_price_return_from_exit_open':z['close']/base-1,'post_exit_descriptive_not_strategy_pnl':True}
 pricewindow=sig[(sig.sid==sid)&(sig.day>exit)&(sig.day<='2026-06-30')];peakrow=pricewindow.loc[pricewindow.close.idxmax()]
 entryop=next(x for x in op if x['sid']==sid and x['day']==sday);entryp=next(x for x in pn if x['sid']==sid and x['day']==sday and x['role']=='mobile');entrysf=sm[(sid,sday)]
 candidates=[x for x in pn if x['sid']==sid and exit<=x['day']<='2026-05-15' and (nextbuy is None or x['day']<nextbuy)]
 fpost=[x for x in fu if x['sid']==sid and exit<x['at'][:10]<='2026-05-15' and '09:30' in x['at'] and (nextbuy is None or x['at'][:10]<=nextbuy)]
 row=dict(sid=sid,name=name,signal_day=sday,entry_day=entry,first_layer=r['first_layer'],buys=tb,sell=sell,net=r['round_pnl'],net_return=r['round_return_on_cumulative_cost'],trigger_day=trigger,trigger_facts={k:sf[k] for k in ['raw_close','close','factor','i_target','i_floor','e0_target','old_receipt','g_grade']},prior_floors=floors,trigger_reason=reason,missing_observed_open_days_before_fill=opens_missing,entry_conditions={'opportunity':entryop,'intent':entryp,'facts':{k:entrysf[k] for k in ['i_target','i_buy','e0_target','old_receipt','sector_E0','sector_stage','sector_authorization','PVR_score']}},post_exit_prices=prices,post_exit_max_observed_close={'day':peakrow.day,'raw_close':peakrow.raw_close,'same_basis_price_return':peakrow.close/base-1},post_exit_flat_cp_count=len(episodecp),post_exit_flat_cp_categories=dict(collections.Counter(x['category'] for x in episodecp)),post_exit_flat_cp_events=episodecp,post_exit_pending_count=len(candidates),post_exit_open_funding_events=fpost,post_exit_open_reasons=dict(collections.Counter(x['result'] for x in fpost)),next_actual_buy=nextbuy,post_exit_sig_days=len(post_sig),post_exit_sig_I_buy_days=int(post_sig.i_buy.eq(True).sum()),all_subsequent_CP_to_account_end=len(pc))
 rows.append(row)
assert abs(sum(x['net'] for x in rows)+8699.4948422433545)<1e-6
# Preserve numeric and unknown distinctions, and no strategies or account initialization.
def norm(v):
 if isinstance(v,dict):return {str(k):norm(x) for k,x in v.items()}
 if isinstance(v,(list,tuple)):return [norm(x) for x in v]
 if hasattr(v,'item'):return norm(v.item())
 if isinstance(v,float) and not math.isfinite(v):return None
 return v
def dump(name,v):(O/name).write_text(json.dumps(norm(v),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
assert all(sha(pathlib.Path(p))==h for p,h in sources.items())
dump('EIGHT_COMPLETE_PATHS.json',rows);dump('SOURCE_HASHES.json',sources);dump('QA.json',dict(rounds=8,stocks=7,net=sum(x['net'] for x in rows),first_buy_role='fresh_CP1_mobile',all_85_ACT_on=True,CP_exits=sum(x['trigger_reason']=='CP1_add_protection' for x in rows),I_exits=sum(x['trigger_reason']=='I_structure_exit' for x in rows),account_end='2026-05-15',price_only_end='2026-06-30',new_accounts=0,source_unchanged=True))
brief=[]
for r in rows:
 brief.append({k:r[k] for k in ['sid','name','signal_day','entry_day','trigger_day','trigger_reason','net','prior_floors','missing_observed_open_days_before_fill','post_exit_prices','post_exit_flat_cp_count','post_exit_flat_cp_categories','post_exit_open_reasons','next_actual_buy']})
dump('SUMMARY.json',brief);dump('OUTPUT_HASHES.json',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'});print(json.dumps(norm(brief),ensure_ascii=False,indent=2))
