from pathlib import Path
from decimal import Decimal as D
import pandas as pd,numpy as np,json,sys,hashlib,time
O=Path(__file__).resolve().parent;V=O.parent;R=V.parent
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025');sys.path.insert(0,str(B/'code'))
from market_rules import version_on,market_identity_on,RuleUnavailable
from sector_account import QuantityRule,FeeComponent,FeeSchedule
NAV=D(1200000);BUDGET=NAV*D('.02');RISK=NAV*D('.0025');SLIP=D('.0005')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
rules=read(B/'inputs-v2/market-rules.json');proxies=read(B/'inputs-v2/economic-protocol.json')['approved_proxy_ids'];sm={x['symbol']:x for x in read(U/'STOCK_MANIFEST.json')};meta={}
def getmeta(sid,d):
 key=(sid,str(d.date()))
 if key not in meta:
  day=key[1];ident=market_identity_on(rules,sid,day,proxies);v=version_on(rules['fee_versions'][ident['venue']],day,proxies)['schedule'];qr=QuantityRule(**version_on(rules['quantity_versions'][sid],day,proxies)['rule']);meta[key]=(qr,FeeSchedule(v['schedule_id'],tuple(FeeComponent(**x) for x in v['components'])),D(str(rules['security_metadata'][sid]['par_value'])))
 return meta[key]
def fee(q,p,fs,side,par):return sum(fs.incremental(side,D(q)*p,{}, {},1,shares=q,par_value=par).values(),D(0))
def calc(sid,d,op,floor,capacity=10**12):
 qr,fs,par=getmeta(sid,d);px=op*(1+SLIP);minimum=qr.buy_minimum;cost=D(minimum)*px+fee(minimum,px,fs,'buy',par);loss=max(D(0),D(minimum)*(px-floor*(1-SLIP))+fee(minimum,px,fs,'buy',par)+fee(minimum,floor*(1-SLIP),fs,'sell',par));reasons=[]
 if op<=floor:reasons.append('raw_price_at_or_below_protection')
 if cost>BUDGET:reasons.append('minimum_notional_budget')
 if loss>RISK:reasons.append('minimum_planned_loss_budget')
 if minimum>capacity:reasons.append('prior20_capacity')
 q=0
 if not reasons:
  q=qr.buy_floor(min(int(BUDGET/px),capacity))
  while q>0:
   co=D(q)*px+fee(q,px,fs,'buy',par);lo=max(D(0),D(q)*(px-floor*(1-SLIP))+fee(q,px,fs,'buy',par)+fee(q,floor*(1-SLIP),fs,'sell',par))
   if co<=BUDGET and lo<=RISK:break
   q=qr.buy_floor(q-1)
 return dict(minimum=minimum,minimum_cash=float(cost),minimum_reference_loss=float(loss),check='PASS_CONDITIONAL_PROXY' if not reasons else '|'.join(reasons),quantity=q)

start=time.monotonic();c=pd.read_csv(V/'ALL_CANDIDATES.csv',parse_dates=['day']);assert len(c)==28558
save('POST_RESULT_CORRECTION.json',dict(created_utc=str(pd.Timestamp.now(tz='UTC')),scope='ALL original windows, events and right3 candidates; no new threshold or performance sorting',correction='Previous top2 truncation could exclude legal lower-ranked names. At t close scan original liquidity rank, require current-I and known minimum-lot/nominal/risk/capacity, freeze first2 PASS names; no next-open replacement. Added after initial results and after two-case mechanism verification.',initial_nominal_max=24000,slot_planned_risk_max=3000,shadow_cumulative_slot_nominal_max=48000,parameters_are_research_not_user_constraints=True,first_and_add_rule='same nominal2% baseline shadow, maxone profitable freshCP add; only entry queue corrected',fixed_future_pool_nonPIT=True,unknown_and_left_censored_branches_separate=True,full_account_run=False))
raw={};facts={};hashes={};rows=[]
for event,g in c.groupby('event_id',sort=False):
 slots=0;day=g.day.iloc[0];g=g.sort_values(['rank_amount20','sid'],ascending=[False,True],na_position='last')
 for rank,r in enumerate(g.itertuples(),1):
  out=r._asdict();out.update(queue_rank=rank,selected_close_frozen=False,status='I_OR_RANK_INELIGIBLE')
  if not r.I_valid or not r.rank_known:rows.append(out);continue
  sid=r.sid;m=sm[sid]
  if sid not in raw:
   sp=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'));pp=m['refs']['facts'];raw[sid]=pd.read_parquet(sp);facts[sid]=pd.read_parquet(pp);hashes[sp]=sha(sp);hashes[pp]=sha(pp)
  p=raw[sid];a=p.loc[day];floor=D(str(r.I_floor))/D(str(a.adjustment_factor));op=D(str(a.raw_close));vol=p.loc[p.index<=day,'raw_volume'];vol=vol[vol.gt(0)]
  if len(vol)<20:out['status']='PRIOR_VOLUME_UNKNOWN_AT_CLOSE';rows.append(out);continue
  capacity=int(vol.iloc[-20:].mean()*.01)
  try:cl=calc(sid,day,op,floor,capacity)
  except (RuleUnavailable,KeyError,ValueError) as ex:out['status']='DATED_RULE_UNKNOWN_AT_CLOSE';out['reason']=str(ex);rows.append(out);continue
  out.update({'close_'+k:v for k,v in cl.items()});out['known_close_raw']=float(op);out['close_floor_raw']=float(floor);out['prior20_capacity']=capacity
  past=p.loc[vol.iloc[-20:].index];out['capacity_prior20_source_count']=len(past[['source_kind','source_path','segment_id']].drop_duplicates());out['capacity_prior20_factor_count']=past.adjustment_factor.nunique()
  if cl['check']!='PASS_CONDITIONAL_PROXY':out['status']='REJECT_AT_CLOSE';rows.append(out);continue
  out['status']='PRICE_SIZE_PROXY_PASS_AT_CLOSE';out['selected_close_frozen']=slots<2
  if out['selected_close_frozen']:slots+=1
  rows.append(out)
 if len(rows)//2000 != (len(rows)-len(g))//2000:print('QUEUE',len(rows),round(time.monotonic()-start,1),flush=True)
z=pd.DataFrame(rows);z.to_csv(O/'ALL_CANDIDATES_CLOSE_CHECKS.csv',index=False);sel=z[z.selected_close_frozen];sel.to_csv(O/'SEALED_CLOSE_SELECTED.csv',index=False)
summary=z.groupby(['window','arm','event_type']).agg(right3_rows=('sid','size'),I_valid=('I_valid','sum'),selected_at_close=('selected_close_frozen','sum')).reset_index();summary.to_csv(O/'COVERAGE.csv',index=False)
for pp in [Path(__file__),V/'ALL_CANDIDATES.csv',B/'inputs-v2/market-rules.json',B/'inputs-v2/economic-protocol.json',B/'code/sector_account.py',B/'code/market_rules.py']:hashes[str(pp)]=sha(pp)
assert all(sha(p)==h for p,h in hashes.items());save('SELECTION_SEAL.json',dict(created_utc=str(pd.Timestamp.now(tz='UTC')),hashes={str(O/n):sha(O/n) for n in ['POST_RESULT_CORRECTION.json','ALL_CANDIDATES_CLOSE_CHECKS.csv','SEALED_CLOSE_SELECTED.csv','COVERAGE.csv']},source_hashes=hashes,rows=len(z),selected=len(sel),no_next_open_fields_available_to_selection=True));save('SUMMARY.json',dict(all_candidates=len(z),selected=len(sel),elapsed_seconds=time.monotonic()-start,passes_at_close=int(z.status.eq('PRICE_SIZE_PROXY_PASS_AT_CLOSE').sum()),status=z.status.value_counts().to_dict(),no_account=True));print(summary.to_string(index=False));print('SELECTED',len(sel),'SECONDS',time.monotonic()-start)
