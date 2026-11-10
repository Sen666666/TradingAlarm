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
start=time.monotonic();c=pd.read_csv(V/'ALL_CANDIDATES.csv',parse_dates=['day']);c=c[c.arm.eq('M3')&c.day.isin(pd.to_datetime(['2026-04-09','2026-06-11']))&c.industry.eq('半导体')].copy()
assert len(c)==86
save('POST_RESULT_CORRECTION.json',dict(created_utc=str(pd.Timestamp.now(tz='UTC')),basis='Parent instructed causal queue correction after prior top2 rejected minimum lots. Not selected on future returns.',fixed_contract='2% nominal first cap/0.25% planned risk reference, unchanged fees. Research assumptions not user lasting constraints.',queue='Complete same right3+I-eligible+known20amount t-close order. Known close min lot legality first; next common open revalidate raw price/floor/fees/capacity. Fail/UNKNOWN continues, eligible only consumes2 seats. No next-close observation used, no future reranking. This is independent entry proxy, not account funding or historical tradability proof.',targets=['2026-04-09 M3 semiconductor all44 right3','2026-06-11 M3 semiconductor all42 right3'],no_pnl_calculation=True))
rows=[];hashes={};raw={};facts={}
for event,g in c.groupby('event_id',sort=False):
 slots=0;day=g.day.iloc[0];od=pd.Timestamp('2026-04-10' if str(day.date())=='2026-04-09' else '2026-06-12')
 g=g.sort_values(['rank_amount20','sid'],ascending=[False,True],na_position='last')
 for rank,r in enumerate(g.itertuples(),1):
  out=r._asdict();out.update(queue_rank=rank,selected_v2=False,decision_clock=str(day.date())+' close',execution_clock=str(od.date())+' open',next_open_historical_orderability='UNKNOWN',status='I_OR_RANK_INELIGIBLE')
  if not r.I_valid or not r.rank_known:rows.append(out);continue
  sid=r.sid;m=sm[sid];sp=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'));pp=m['refs']['facts'];raw[sid]=pd.read_parquet(sp);facts[sid]=pd.read_parquet(pp);hashes[sp]=sha(sp);hashes[pp]=sha(pp);p=raw[sid];f=facts[sid]
  a=p.loc[day];floor=D(str(r.I_floor))/D(str(a.adjustment_factor));op=D(str(a.raw_close));cl=calc(sid,day,op,floor);out.update({'close_'+k:v for k,v in cl.items()})
  if cl['check']!='PASS_CONDITIONAL_PROXY':out['status']='REJECT_AT_CLOSE';rows.append(out);continue
  if od not in p.index or not np.isfinite(p.loc[od,'raw_open']) or p.loc[od,'raw_open']<=0:out['status']='NEXT_OPEN_UNKNOWN';rows.append(out);continue
  b=p.loc[od];identity=['source_kind','source_path','segment_id']
  if any(str(a[k])!=str(b[k]) for k in identity) or not np.isclose(a.adjustment_factor,b.adjustment_factor,rtol=1e-11):out['status']='NEXT_SOURCE_OR_ACTION_UNKNOWN';rows.append(out);continue
  vol=p.loc[p.index<od,'raw_volume'];vol=vol[vol.gt(0)]
  if len(vol)<20:out['status']='PRIOR_VOLUME_UNKNOWN';rows.append(out);continue
  capacity=int(vol.iloc[-20:].mean()*.01);n=calc(sid,od,D(str(b.raw_open)),floor,capacity);out.update({'next_'+k:v for k,v in n.items()});out['next_raw_open']=float(b.raw_open);out['floor_raw']=float(floor)
  if n['check']!='PASS_CONDITIONAL_PROXY':out['status']='REJECT_AT_OPEN';rows.append(out);continue
  out['status']='LEGAL_CONDITIONAL_PROXY';out['selected_v2']=slots<2
  if out['selected_v2']:slots+=1
  rows.append(out)
z=pd.DataFrame(rows);z.to_csv(O/'SEMICONDUCTOR_ALL_QUEUE_CHECKS.csv',index=False);z[z.selected_v2].to_csv(O/'SEMICONDUCTOR_SELECTED_V2.csv',index=False)
summary=[]
for ev,g in z.groupby('event_id'):
 summary.append(dict(event=ev,right3=len(g),I_valid=int(g.I_valid.sum()),original_top2=g[g.selected][['sid','name','status']].to_dict('records'),passed_close=int(g.get('close_check',pd.Series(dtype=str)).eq('PASS_CONDITIONAL_PROXY').sum()),legal_next_open_proxy=int(g.status.eq('LEGAL_CONDITIONAL_PROXY').sum()),selected=g[g.selected_v2][['sid','name','queue_rank','next_quantity','next_raw_open','next_minimum_cash','next_minimum_reference_loss']].to_dict('records'),status=g.status.value_counts().to_dict()))
save('SUMMARY.json',dict(rows=summary,seconds=time.monotonic()-start,account_runs=0,returns_examined=0,all86_candidates_retained=True));hashes.update({str(p):sha(p) for p in [Path(__file__),V/'ALL_CANDIDATES.csv',B/'inputs-v2/market-rules.json',B/'inputs-v2/economic-protocol.json',B/'code/sector_account.py',B/'code/market_rules.py']});assert all(sha(p)==h for p,h in hashes.items());save('SOURCE_HASHES.json',hashes);print(json.dumps(summary,ensure_ascii=False,indent=2))
