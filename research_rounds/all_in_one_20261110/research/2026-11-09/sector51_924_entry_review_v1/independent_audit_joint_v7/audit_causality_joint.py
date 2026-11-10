"""Independent broad-sector, CP causality and certified-prefix audit; no strategy execution."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter,defaultdict
import json,hashlib,sys
import pandas as pd
import numpy as np
O=Path(__file__).resolve().parent;P=O.parent;C=P/'joint51_candidate_v1';F=Path(sys.argv[1]);R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031');read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
ro=pd.read_csv(C/'CLASSIFICATION_ALL1709.csv');eligible=ro[ro.eligible];ids=sorted(eligible.symbol);mapping=eligible.set_index('symbol').sector51.to_dict();sector_members={s:sorted(eligible[eligible.sector51.eq(s)].symbol) for s in sorted(eligible.sector51.unique())};Q=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2';k=pd.read_parquet(Q/'KNOWN3.parquet')[ids];rt=pd.read_parquet(Q/'RIGHT3.parquet')[ids];pvs=pd.read_parquet(R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet',columns=['sid','day','state']);pv=pvs[pvs.sid.isin(ids)].pivot(index='day',columns='sid',values='state').reindex(index=k.index,columns=ids);known=k&pv.ge(0);right=known&rt;cal=k.index
orders=read(F/'ORDERS.json');led=read(F/'DAY_LEDGER.json');ledger={r['day']:r for r in led};holdings=read(F/'HOLDINGS.json');cpe=read(F/'CP_EVENTS.json');cands=read(F/'CANDIDATES.json');seed={r['round_id']:r for r in orders if r['side']=='BUY_SEED'};cpcreated={x['cp_id']:x for x in cpe if x['event']=='CREATED_AFTER_SEED'};ms={m['symbol']:m for m in read(U/'STOCK_MANIFEST.json')};used={x['sid'] for x in orders};raw={s:pd.read_parquet(next(p for p in ms[s]['source_sha256'] if p.endswith('/signal.parquet'))) for s in used};facts={s:pd.read_parquet(ms[s]['refs']['facts']) for s in used};cp={s:pd.read_parquet(ms[s]['refs']['CP1']) for s in used};checks=Counter();errors=[];outside=[];single=[];cpdetail=[];all_source_failures=[]
def check(label,ok,context):
 checks[label]+=1
 if not ok:errors.append(dict(check=label,context=context))
def lin(z):return tuple(str(z[c]) for c in ['source_kind','source_path','segment_id'])
def truth(v):return pd.notna(v) and v in (True,1)
def valid(z):return all(truth(z[c]) for c in ['observed_bar','price_eligible','volume_eligible']) and not truth(z['source_invalid']) and not truth(z['synthetic_event_bar'])
def stock(s,d):return int(right.at[d,s]) if known.at[d,s] else -1
# Scalar, independent state reconstruction over each industry and actual common dates.
states={};coverage=read(C/'ALL50_DAILY_RECOGNITION.json')
for row in coverage:
 sector=row['sector51'];t=pd.Timestamp(row['day']);i=cal.get_loc(t);ss=sector_members[sector];N=len(ss);kn=known.loc[t,ss];rr=right.loc[t,ss];prior=cal[i-1];before=cal[i-3];shared=kn&known.loc[before,ss];K=int(kn.sum());n=int(rr.sum());J=int(shared.sum());entered=int((shared&rr&~right.loc[before,ss]).sum());left=int((shared&~rr&right.loc[before,ss]).sum());diff=entered-left;u=N-K;lo=n>=3 and ((3*n>=N and J>0 and diff>0) or 2*n>=N);hi=n+u>=3 and ((3*(n+u)>=N and (diff>0 or J==0)) or 2*(n+u)>=N);st=1 if lo else -1 if hi else 0;n0=int(right.loc[prior,ss].sum());strength=2*n>=N and 2*n0>=N and diff>0;expect=dict(N=N,K=K,n=n,U=u,paired_K=J,entered3=entered,left3=left,diff=diff,state=st,strength=strength)
 states[(sector,t)]=expect
 for field,value in expect.items():
  if field in row:check('all50_source_'+field,row[field]==value,dict(day=row['day'],sector51=sector,field=field,actual=row[field],expected=value))
for x in read(F/'SECTOR_DAILY.json'):
 y=states[(x['sector51'],pd.Timestamp(x['day']))]
 for f,v in y.items():check('ledger_sector_'+f,x[f]==v,dict(day=x['day'],sector51=x['sector51'],field=f))
core=pd.read_csv(P/'CORE_DAILY_51CLASS_SIGNALS.csv',parse_dates=['day'])
for _,x in core.iterrows():
 y=states.get((x.sector51,x.day))
 if y:
  for f in ['N','K','n','U','state']:check('original_core_sector_'+f,int(x[f])==y[f],dict(day=str(x.day.date()),sector51=x.sector51,field=f))
for tr in orders:
 s=tr['sid'];dt=pd.Timestamp(tr['day']);z=raw[s].loc[dt];p=D(tr['price']);t=pd.Timestamp(tr['signal_day']) if tr['signal_day'] else None
 if D(str(z.raw_high))==D(str(z.raw_low)):single.append(tr['order_seq'])
 if not D(str(z.raw_low))<=p<=D(str(z.raw_high)):outside.append({k:tr[k] for k in ['order_seq','sid','day','side','price']}|dict(raw_low=str(z.raw_low),raw_high=str(z.raw_high)))
 if not tr['side'].startswith('BUY'):continue
 prior=cal[cal.get_loc(t)-1];nxt=cal[cal.get_loc(t)+1];sec=mapping[s];st=states[(sec,t)]['state'];sp=states.get((sec,prior))
 if sp is None:
  ss=sector_members[sec];nn=int(right.loc[prior,ss].sum());KK=int(known.loc[prior,ss].sum());before=cal[cal.get_loc(prior)-3];shared=known.loc[prior,ss]&known.loc[before,ss];JJ=int(shared.sum());dd=int((shared&right.loc[prior,ss]&~right.loc[before,ss]).sum()-(shared&~right.loc[prior,ss]&right.loc[before,ss]).sum());N=len(ss);UU=N-KK;ll=nn>=3 and ((3*nn>=N and JJ>0 and dd>0) or 2*nn>=N);hh=nn+UU>=3 and ((3*(nn+UU)>=N and (dd>0 or JJ==0)) or 2*(nn+UU)>=N);sp={'state':1 if ll else -1 if hh else 0}
 check('exact_next_common_open',nxt==dt,tr['order_seq']);check('signal_valid_source',valid(raw[s].loc[t]),tr['order_seq']);check('entry_source_lineage',lin(raw[s].loc[t])==lin(z),tr['order_seq']);v=raw[s].raw_volume[raw[s].raw_volume.gt(0)].loc[:t].tail(20);cap=int(v.mean()*.01);check('prior20_volume_capacity',len(v)==20 and tr['qty']<=cap,tr['order_seq']);f=facts[s].loc[t];check('I_known_positive_at_plan',truth(f.i_target) and np.isfinite(f.i_floor) and f.i_floor>0,tr['order_seq'])
 if tr['side']=='BUY_SEED':
  A=sp['state']==0 and st==1 and stock(s,t)==1;B=sp['state']==1 and st==1 and stock(s,prior)==0 and stock(s,t)==1;check('fresh_A_or_B',A or B,tr['order_seq']);check('seed_close_above_I',D(str(raw[s].at[t,'raw_close']))*D(str(raw[s].at[t,'adjustment_factor']))>D(str(f.i_floor)),tr['order_seq']);check('seed_open_above_carried_I',D(str(z.raw_open))*D(str(z.adjustment_factor))>D(str(f.i_floor)),tr['order_seq'])
 else:
  n0=int(right.loc[prior,sector_members[sec]].sum());n1=states[(sec,t)]['n'];diff=states[(sec,t)]['diff'];N=len(sector_members[sec]);check('ADD_own_sector_two_half_plus_diff',2*n0>=N and 2*n1>=N and diff>0,tr['order_seq']);e=cpcreated[tr['cp_id']];ct=pd.Timestamp(e['day']);seedday=pd.Timestamp(seed[tr['round_id']]['day']);check('postseed_CP',seedday<=ct<=t,tr['order_seq']);check('CP_original_receipt',truth(cp[s].at[ct,'receipt']),tr['order_seq']);fl=D(e['candidate']);check('CP_original_candidate',fl==D(str(cp[s].at[ct,'candidate'])),tr['order_seq']);check('CP_identity_source',e['round_id']==tr['round_id'] and e['sid']==s,tr['order_seq']);vals=[];ls=[]
  for d,z0 in raw[s].loc[ct:dt].iterrows():
   ls.append(lin(z0)==lin(raw[s].loc[ct]))
   if d>ct:vals.append(D(str(z0.raw_open))*D(str(z0.adjustment_factor))>fl)
   if d<dt:vals.append(D(str(z0.raw_close))*D(str(z0.adjustment_factor))>fl)
  check('CP_unbreached_until_ADD',all(vals),tr['order_seq']);check('CP_unchanged_lineage',all(ls),tr['order_seq']);cpdetail.append(dict(sid=s,sector51=sec,N=N,seed=str(seedday.date()),CP_close=e['day'],plan_close=tr['signal_day'],ADD_open=tr['day'],sector_n_previous=n0,sector_n_current=n1,diff=diff,open_net=tr['open_net'],all_in_cost=tr['all_in_cost']))
# Logs are a lifecycle, not permission to consume without an actual fill.
actual_cp={x['cp_id']:(x['day'],x['sid']) for x in orders if x['side']=='BUY_ADD'};consumed={x['cp_id']:(x['day'],x['sid']) for x in cpe if x['event']=='CONSUMED_ON_FILL'};check('CP_consumption_exactly_actual_ADDs',actual_cp==consumed and len(consumed)==sum(x['event']=='CONSUMED_ON_FILL' for x in cpe),None)
state={};invalid_ids=set()
for x in cpe:
 rid=x['round_id'];typ=x['event'];cid=x['cp_id']
 if typ=='CREATED_AFTER_SEED':
  check('CP_created_from_source',truth(cp[x['sid']].at[pd.Timestamp(x['day']),'receipt']),cid);check('CP_created_after_seed',x['day']>=seed[rid]['day'],cid);state[rid]=cid
 elif typ=='INVALIDATED':
  check('CP_lifecycle_targets_current',state.get(rid)==cid,cid);invalid_ids.add(cid)
 elif typ=='SUPERSEDED':
  check('CP_lifecycle_targets_current',state.get(rid)==cid,cid);state[rid]=None
 elif typ=='CONSUMED_ON_FILL':check('CP_consume_latest_valid',state.get(rid)==cid and cid not in invalid_ids,cid);state[rid]=None
# Carried signal-coordinate protections never loosen; next-day sell needs locked or breached protection.
byday=defaultdict(dict)
for h in holdings:byday[h['day']][h['lot_id']]=h
last={}
for dt,hs in sorted(byday.items()):
 for lid,h in hs.items():
  if lid in last:check('protection_nondecreasing',D(h['protection_signal'])>=D(last[lid]['protection_signal']),[dt,lid])
  s=h['sid'];check('holding_factor_is_current_source',D(h['factor'])==D(str(raw[s].at[pd.Timestamp(dt),'adjustment_factor'])),[dt,lid])
 last.update(hs)
for tr in orders:
 if not tr['side'].startswith('SELL'):continue
 dt=pd.Timestamp(tr['day']);prior=str(cal[cal.get_loc(dt)-1].date());old=byday[prior];s=tr['sid'];px=D(str(raw[s].at[dt,'raw_open']))*D(str(raw[s].at[dt,'adjustment_factor']));rh=[h for h in old.values() if h['round_id']==tr['round_id']];seedfloor=next((D(h['protection_signal']) for h in rh if h['kind']=='SEED'),D(0));whole_breach=px<=seedfloor
 for lid in tr['lots']:
  h=old[lid];check('sell_locked_or_known_protection_breach',bool(h['locked_exit']) or whole_breach or (h['kind']=='ADD' and px<=D(h['protection_signal'])),[tr['order_seq'],lid])
# Full immutable source files and emitted output hashes are integrity checks, not additional strategy runs.
for p,h in read(F/'SOURCE_HASHES.json').items():
 if sha(p)!=h:all_source_failures.append(p)
check('protected_source_hashes_unchanged',not all_source_failures,all_source_failures)
output_bad=[name for name,h in read(F/'OUTPUT_HASHES.json').items() if sha(F/name)!=h];check('output_hashes_unchanged',not output_bad,output_bad)
block=read(F/'UNCERTIFIED_DAY.json');prefix={};certified_last=led[-1]['day']
if block:
 for name in ['ORDERS','HOLDINGS','DAY_LEDGER','CANDIDATES','CP_EVENTS','EQUITY_EVENTS','SECTOR_DAILY']:
  check('no_uncertified_day_'+name,all(x['day']<block['day'] for x in read(F/(name+'.json'))),block['day'])
 check('certified_prefix_stops_before_blocker',certified_last<block['day'],dict(last=certified_last,blocked=block['day']))
pref=F.parent/'prefix_20240923_once'
if pref.exists() and pref.resolve()!=F.resolve():
 for name in ['ORDERS','HOLDINGS','DAY_LEDGER','CANDIDATES','CP_EVENTS','EQUITY_EVENTS','SECTOR_DAILY']:
  prefix[name]=[r for r in read(F/(name+'.json')) if r['day']<='2024-09-23']==read(pref/(name+'.json'));check('export_prefix_'+name,prefix[name],None)
report=dict(status='PASS' if not errors else 'FAIL',run=str(F),check_count=sum(checks.values()),checks=dict(checks),errors=errors,certified_last=certified_last,blocker=block,checkpoint_prefix_comparison=prefix if prefix else 'NOT_PERFORMED_ON_CHECKPOINT_ITSELF_OR_UNAVAILABLE',all50_recognition_rows=len(coverage),CP_details=cpdetail,one_price_bar_orders=single,slippage_proxy_outside_observed_daily_range=outside,source_hash_failures=all_source_failures,scope='Read-only independent signal-source, recorded trade/CP lifecycle and integrity audit. No economic rerun, parameter search or future event admission.',limitations=['OPEN +/- 5bp is a conservative cost proxy. H/L and current volume are inspected ex post only, never used for OPEN permission.','No independent rerun-prefix comparison exists when the run stops before the checkpoint; no partial day appears in certified outputs.','Current sample/classification and date-level company evidence remain non-PIT.'])
(O/(F.name+'_CAUSALITY.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ['checks','CP_details','slippage_proxy_outside_observed_daily_range']},ensure_ascii=False,indent=2));print('CP_ADDS',len(cpdetail),'OUTSIDE_HL',len(outside))
