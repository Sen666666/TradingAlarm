from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import json, hashlib
import pandas as pd
O=Path(__file__).resolve().parent;P=O.parent;C=P/'continuous_candidate_v1';F=C/'full_20241031_once';R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
ms={m['symbol']:m for m in read(U/'STOCK_MANIFEST.json')}
ro=pd.read_csv(P/'CORE_CLASSIFICATION.csv');ids=sorted(ro[ro.sector51.eq('证券保险')].symbol)
Q=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2';k=pd.read_parquet(Q/'KNOWN3.parquet')[ids];rt=pd.read_parquet(Q/'RIGHT3.parquet')[ids]
pv=pd.read_parquet(R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet',columns=['sid','day','state']).pivot(index='day',columns='sid',values='state').reindex(index=k.index,columns=ids)
known=k&pv.ge(0);right=known&rt;cal=k.index
sector=pd.read_csv(P/'CORE_DAILY_51CLASS_SIGNALS.csv',parse_dates=['day']);sector=sector[sector.sector51.eq('证券保险')].set_index('day')
orders=read(F/'ORDERS.json'); ledger={r['day']:r for r in read(F/'DAY_LEDGER.json')};cpe=read(F/'CP_EVENTS.json');cpcreated={x['cp_id']:x for x in cpe if x['event']=='CREATED_AFTER_SEED'}
used={x['sid'] for x in orders};raw={s:pd.read_parquet(next(p for p in ms[s]['source_sha256'] if p.endswith('/signal.parquet'))) for s in used};facts={s:pd.read_parquet(ms[s]['refs']['facts']) for s in used};cp={s:pd.read_parquet(ms[s]['refs']['CP1']) for s in used}
checks=[];errors=[];outside=[];single=[];cpdetail=[]
def check(label,ok,context):
 checks.append(label)
 if not ok:errors.append({'check':label,'context':context})
seed={r['round_id']:r for r in orders if r['side']=='BUY_SEED'}
for tr in orders:
 s=tr['sid'];dt=pd.Timestamp(tr['day']);z=raw[s].loc[dt];p=D(tr['price'])
 if D(str(z.raw_high))==D(str(z.raw_low)):single.append(tr['order_seq'])
 if not D(str(z.raw_low))<=p<=D(str(z.raw_high)):outside.append({k:tr[k] for k in ['order_seq','sid','day','side','price']}|{'raw_low':str(z.raw_low),'raw_high':str(z.raw_high)})
 if not tr['side'].startswith('BUY'):continue
 t=pd.Timestamp(tr['signal_day']);prior=cal[cal.get_loc(t)-1];nxt=cal[cal.get_loc(t)+1];st=int(sector.at[t,'state']);sp=int(sector.at[prior,'state']);stocknow=1 if known.at[t,s] and right.at[t,s] else 0 if known.at[t,s] else -1;stockprev=1 if known.at[prior,s] and right.at[prior,s] else 0 if known.at[prior,s] else -1
 check('exact_next_common_open',nxt==dt,tr['order_seq'])
 check('frozen_attempt_NAV',D(tr['frozen_attempt_NAV'])==D(ledger[seed[tr['round_id']]['signal_day']]['NAV']),tr['order_seq'])
 cap=int(raw[s].raw_volume[raw[s].raw_volume.gt(0)].loc[:t].tail(20).mean()*.01);check('prior_capacity',tr['qty']<=cap,tr['order_seq'])
 if tr['side']=='BUY_SEED':
  A=(sp==0 and st==1 and stocknow==1);B=(sp==1 and st==1 and stockprev==0 and stocknow==1);check('fresh_A_or_B',A or B,tr['order_seq']);f=facts[s].loc[t];check('seed_I_eligible',f.i_target==1 and f.i_floor>0,tr['order_seq']);check('seed_close_above_I',raw[s].at[t,'raw_close']*raw[s].at[t,'adjustment_factor']>f.i_floor,tr['order_seq'])
 else:
  prior3=cal[cal.get_loc(t)-3];shared=known.loc[t]&known.loc[prior3];n0=int(right.loc[prior].sum());n1=int(right.loc[t].sum());diff=int((shared&right.loc[t]&~right.loc[prior3]).sum()-(shared&~right.loc[t]&right.loc[prior3]).sum());check('ADD_strength_source',n0>=26 and n1>=26 and diff>0,tr['order_seq'])
  e=cpcreated[tr['cp_id']];ct=pd.Timestamp(e['day']);seedday=pd.Timestamp(seed[tr['round_id']]['day']);check('postseed_CP',seedday<=ct<=t,tr['order_seq']);check('CP_original_receipt',bool(cp[s].at[ct,'receipt']),tr['order_seq']);fl=D(e['candidate']);check('CP_original_candidate',fl==D(str(cp[s].at[ct,'candidate'])),tr['order_seq'])
  vals=[]
  for d,z0 in raw[s].loc[ct:dt].iterrows():
   if d>ct:vals.append(D(str(z0.raw_open))*D(str(z0.adjustment_factor))>fl)
   if d<dt:vals.append(D(str(z0.raw_close))*D(str(z0.adjustment_factor))>fl)
  check('CP_unbreached_until_ADD',all(vals),tr['order_seq'])
  cpdetail.append({'sid':s,'seed':str(seedday.date()),'CP_close':e['day'],'plan_close':tr['signal_day'],'ADD_open':tr['day'],'sector_n_previous':n0,'sector_n_current':n1,'diff':diff})
prefix={}
for name in ['ORDERS','HOLDINGS','DAY_LEDGER','CP_EVENTS','CANDIDATES']:
 full=[r for r in read(F/(name+'.json')) if r['day']<='2024-09-23'];old=read(C/'prefix_20240923_once'/(name+'.json'));prefix[name]=full==old;check('prefix_economic_invariance_'+name,full==old,name)
sourcebad=[p for p,h in read(F/'SOURCE_HASHES.json').items() if sha(p)!=h];check('full_source_hashes_unchanged',not sourcebad,sourcebad)
rep={'status':'PASS' if not errors else 'FAIL','check_count':len(checks),'errors':errors,'CP_details':cpdetail,'original_prefix_identical':prefix,'one_price_bar_orders':single,'slippage_proxy_outside_observed_daily_range':outside,'execution_caveat':'Eight cost-proxy prices exceed observed daily high or fall below low. They are conservative raw OPEN plus/minus 5bp execution-cost proxies, not literal historical exchange fills. Tick/grid and exchange limit queue not certified. Do not change execution by retrospectively filtering with same-day H/L.','scope':'Audit only. No new economic strategy execution. Current universe and classification, frozen source coordinates, and date-level notices remain not point-in-time.'}
(O/'CAUSAL_EXECUTION_AUDIT.json').write_text(json.dumps(rep,ensure_ascii=False,indent=2)+'\n');print(json.dumps(rep,ensure_ascii=False,indent=2))
