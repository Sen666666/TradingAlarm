"""Read-only PVR ledger projection. Never construct/run Account or Runner.
Writes only ORIGINAL_OPEN_RESOURCES.json and RISK_RECONSTRUCTION_QA.json here.
Requires pre-extracted ORIGINAL_OPEN_RESERVATION_SNAPSHOTS.json.
"""
import sys,json,gzip,hashlib,math,copy,collections,bisect
from pathlib import Path
from decimal import Decimal as D
import pandas as pd
import numpy as np
ROOT=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
HERE=Path(__file__).resolve().parent
RUN=ROOT/'account_comparison_continuous_v1/run_1200000'
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
MP=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/manifest.json')
sys.path.insert(0,str(ROOT/'account_comparison_continuous_v1/factors'))
from continuous_factors import OpenFactorTimeline
Z=D(0)
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def loadlines(p):
 with gzip.open(p,'rt') as f:
  return [r for line in f if (r:=json.loads(line))['account']=='PVR']
def group(xs,key):
 out=collections.defaultdict(list)
 for x in xs:out[key(x)].append(x)
 return out
def day(x):return str(x)[:10]
sources={}
def checked(p,expected=None):
 p=Path(p);h=sha(p)
 if expected is not None:assert h==expected,('source_hash',str(p),h,expected)
 sources[str(p)]=h
 return p
def resource(lots,orders,marks,pool=None,sector=None):
 ls=[l for l in lots if l['qty'] and (pool is None or l['pool']==pool) and (sector is None or l['sector']==sector)]
 os=[o for o in orders if (pool is None or o['pool']==pool) and (sector is None or o['sector']==sector)]
 return [sum(l['qty']*float(marks[l['sid']]) for l in ls)+sum(o['qty']*o['limit'] for o in os),
 sum(l['qty']*max(0.,float(marks[l['sid']])-l['raw_floor']) for l in ls)+sum(o['qty']*max(0.,o['limit']-o['floor']) for o in os),
 sum(o['qty']*(o['limit']+o['fee_per_share']) for o in os)]
def near(a,b,tol=1e-6):return abs(float(a)-float(b))<=tol
def main():
 snaps=read(checked(HERE/'ORIGINAL_OPEN_RESERVATION_SNAPSHOTS.json'))
 p=json.load(gzip.open(checked(RUN/'pair/PVR.json.gz'),'rt'))
 daily=loadlines(checked(RUN/'pair/daily.jsonl.gz'))
 funding=group(loadlines(checked(RUN/'pair/funding.jsonl.gz')),lambda r:day(r['at']))
 events=group(loadlines(checked(RUN/'pair/industry.jsonl.gz')),lambda r:r['day'])
 journal=group(p['journal'],lambda r:day(r['at']))
 reserves={r['order_id']:r for r in p['audit'] if r['kind']=='reserve'}
 orders=p['budget']['orders']
 decisions={day(r['at']):r for r in p['decisions']}
 prev=None;states={};rows=[];unknown=[];close_checks=[];migration_rows=[];reserve_checks=[];industry_rows={};silent_episode_resets=[];migration_counts=collections.Counter()
 manifest={r['series_id']:r for r in read(checked(MP))['series']}
 sm={r['symbol']:r for r in read(checked(U/'STOCK_MANIFEST.json'))}
 im=read(checked(U/'INDUSTRY_MANIFEST.json'))
 for r in im:
  f=pd.read_parquet(checked(r['refs']['state'],r['output_sha256'][r['refs']['state']]))
  industry_rows[r['series']]={v['day']:v for v in f.loc[f.day.between('2022-01-01','2026-05-15')].to_dict('records')}
  past=f.loc[f.day<'2022-01-01'];last=past.iloc[-1].to_dict()
  if pd.isna(last['E0_episode']):continue
  st=dict(episode=last['E0_episode'],active=False,level=0,attempt=None)
  if pd.notna(last['attempt_id']):
   ar=past.loc[past.attempt_id==last['attempt_id']];first=ar.loc[ar.action=='probe'].iloc[0]
   st.update(active=True,level=int(last['stage'])-1,attempt=str(last['E0_episode'])+':'+str(first['receipt_id']))
  states[r['series']]=st
 ids={l['sid'] for r in daily for l in r['layers']}|{r['sid'] for r in p['journal'] if r['kind']=='real_reserve'}
 data={};facts={}
 for n,sid in enumerate(sorted(ids)):
  rec=manifest[sid]
  raw=pd.read_parquet(checked(rec['raw']['path'],rec['raw']['sha256']))
  if 'trade_date' in raw:raw=raw.set_index('trade_date')
  elif 'date' in raw:raw=raw.set_index('date')
  raw.index=pd.DatetimeIndex(pd.to_datetime(raw.index))
  raw=raw.loc[:'2026-05-15']
  if 'is_observed_bar' in raw:raw['observed_bar']=raw.is_observed_bar
  def bc(name,default):
   return raw[name].astype(str).str.lower().isin(['true','1','1.0']) if name in raw else pd.Series(default,index=raw.index)
  ohlc=raw[['open','high','low','close']].apply(pd.to_numeric,errors='coerce')
  finite=np.isfinite(ohlc).all(axis=1)&ohlc.gt(0).all(axis=1)
  geometry=ohlc.high.ge(ohlc.low)&ohlc.high.ge(ohlc[['open','close']].max(axis=1))&ohlc.low.le(ohlc[['open','close']].min(axis=1))
  anomaly=raw.source_anomaly.fillna('').astype(str).str.strip().ne('') if 'source_anomaly' in raw else pd.Series(False,index=raw.index)
  raw['valid_price']=finite&geometry&bc('observed_bar',True)&~bc('synthetic_event_bar',False)&~bc('source_invalid',False)&~anomaly
  raw['observed_bar']=bc('observed_bar',True)
  ap=rec['adjustment']['actions'];acts=read(checked(ap['path'],ap['sha256']))['events'];acts=[e for e in acts if e['effective_date']<='2026-05-15']
  factrec=sm[sid];fp=factrec['refs']['facts']
  facts[sid]=pd.read_parquet(checked(fp,factrec['output_sha256'][fp]))[['factor','raw_close']]
  good=raw.loc[raw.valid_price.astype(bool) & raw.observed_bar.astype(bool)]
  data[sid]=dict(raw=raw,good=good,actions=acts,factor=OpenFactorTimeline(raw,acts,method=rec['adjustment']['method'],end='2026-05-15'))
  if n%200==0:print('LOADED',n,len(ids),flush=True)
 def mark(sid,d,phase):
  a=data[sid];t=pd.Timestamp(d);f=a['raw'];col='open' if phase=='OPEN' else 'close'
  if t in f.index and pd.notna(f.loc[t,col]) and math.isfinite(float(f.loc[t,col])) and f.loc[t,col]>0 and (phase=='OPEN' or (bool(f.loc[t,'valid_price']) and bool(f.loc[t,'observed_bar']))):return D(str(f.loc[t,col]))
  good=a['good'];pos=good.index.searchsorted(t,side='left' if phase=='OPEN' else 'right')-1
  if pos<0:raise ValueError('No prior mark '+sid+' '+d)
  md=good.index[pos];price=D(str(good.iloc[pos].close))
  # OPEN derived ex-reference; original close latest_mark handling is verified below.
  if True:
   for e in sorted(a['actions'],key=lambda e:e['effective_date']):
    if str(md.date())<e['effective_date']<=d:price=(price-D(str(e.get('signal_cash_per_old_share',e['cash_per_old_share']))))/D(str(e.get('signal_split_ratio',e['split_ratio'])))
  return price
 daily_by={day(r['at']):r for r in daily}
 for snap in snaps['rows']:
  d=day(snap['at']);errors=[];lots=copy.deepcopy(prev['layers']) if prev else [];decision_nav=D(prev['nav']) if prev else D(1200000)
  j=journal[d];resj=[r for r in j if r['kind']=='real_reserve'];sellj=[r for r in j if r['kind']=='real_sell_fill'];buyj=[r for r in j if r['kind']=='real_buy_fill']
  # Native layer split: aggregate floor, then allocate residual by original live-layer order.
  for ev in j:
   if ev['kind']!='actual_split':continue
   ls=[l for l in lots if l['sid']==ev['sid'] and l['qty']];ratio=D(ev['ratio']);target=int(D(sum(l['qty'] for l in ls))*ratio)
   qs=[int(D(l['qty'])*ratio) for l in ls]
   for k in range(target-sum(qs)):qs[k%len(qs)]+=1
   for l,q in zip(ls,qs):l['qty']=q;l['unit_cost']/=float(ratio)
  byid={l['id']:l for l in lots}
  for ev in sellj:
   for part in ev['parts']:byid[part['layer']]['qty']-=part['shares']
  lots=[l for l in lots if l['qty']]
  marks={l['sid']:mark(l['sid'],d,'OPEN') for l in lots}
  for l in lots:
   line=D(str(l['last_core_line'])) if l['kind']=='core' else D(l['floor'])
   l['raw_floor']=float(line/data[l['sid']]['factor'].factor(d))
  inventory=sum((D(l['qty'])*marks[l['sid']] for l in lots),Z)
  if inventory!=D(snap['components']['inventory']):errors.append(dict(check='open_inventory_exact',actual=str(inventory),expected=snap['components']['inventory']))
  # Evidence-based original full fills: no mutable partial-order state is reused.
  oj={r['sid']:r for r in resj};os=[];prev_dec=decisions.get(day(prev['at']),{}) if prev else {}
  intentmap={(i['sid'],i['role']):i for i in prev_dec.get('intents',[])}
  endorders=[]
  for rr in resj:
   b=copy.deepcopy(orders[rr['budget_order']]);au=reserves[rr['order']];bf=next((v for v in buyj if v['budget_order']==rr['budget_order']),None)
   if bf is None or bf['shares']!=rr['shares']:errors.append(dict(check='full_fill_immutable_order',order=rr['budget_order']));continue
   b['qty']=rr['shares'];b['limit']=float(D(rr['price']));b['fee_per_share']=float(D(au['fee_reserved_cny'])/D(b['qty']))
   i=intentmap.get((rr['sid'],rr['role']))
   if i is None:errors.append(dict(check='reserve_intent_missing',order=rr['budget_order']));continue
   floor=float(D(i['floor'])/data[rr['sid']]['factor'].factor(d))
   if not near(floor,b['floor'],1e-10):errors.append(dict(check='order_floor',order=rr['budget_order'],derived=floor,stored=b['floor']))
   b['floor']=floor
   if b['pool']!=rr['pool']:errors.append(dict(check='order_pool',order=rr['budget_order']))
   endorders.append(b)
  immutable_by_sid={b['stock']:b for b in endorders};reserved_exact_so_far=Z
  for fr in funding[d]:
   if '09:30' not in fr['at']:continue
   result=fr['result'];sid=fr['sid'];i=intentmap.get((sid,fr['role']))
   # These are before migrate in original OPEN/preview/route.
   if result in {'missing_open','open_at_or_below_protection','open_minimum_exceeds_frozen_contract','industry_invalidated','no_fresh_stock_CP1'}:continue
   if i is None:
    errors.append(dict(check='funding_intent_missing',sid=sid,result=result));continue
   sector=sector_by_sid[sid]
   # Native security -> sector map from frozen selection (populated below).
   sector=sector_by_sid[sid];st=states.get(sector)
   if fr['role']=='mobile' and st and st['active'] and st['level']>0:
    migration_counts['eligible_evaluations']+=1;migration_counts['eligible_success_candidates' if result=='reserved' else 'eligible_failed_candidates']+=1
    blocked=any(o['sector']==sector and o['attempt']==st['attempt'] and o['pool']=='probe' for o in os)
    if blocked:migration_counts['blocked_by_pending_probe']+=1
    if not blocked:
     migration_counts['unblocked_evaluations']+=1
     moved=[l['id'] for l in lots if l['sector']==sector and l['attempt']==st['attempt'] and l['pool']=='probe']
     for l in lots:
      if l['id'] in moved:l['pool']='confirmed'
     if moved:
      migration_counts['moving_evaluations']+=1;migration_counts['moving_success_candidates' if result=='reserved' else 'moving_failed_candidates']+=1
      migration_rows.append(dict(day=d,sid=sid,result=result,failed_candidate=result!='reserved',layers=moved))
   if result=='reserved':
    b=immutable_by_sid.get(sid)
    if b is None:continue
    fee=D(reserves[oj[sid]['order']]['fee_reserved_cny']);cap=b['qty']*b['limit'];risk=b['qty']*max(0.,b['limit']-b['floor'])
    pf=sum(o['qty']*o['fee_per_share'] for o in os);nav=float(D(snap['components']['nav']))-pf-float(fee)
    pc,pr,_=resource(lots,os,marks,b['pool']);sc,sr,_=resource(lots,os,marks,sector=sector)
    frac=.02 if b['pool']=='probe' else (.02,.1,.2)[st['level']]
    checks=dict(probe_capital=(b['pool']!='probe' or pc+cap<=.10*nav+1e-6),probe_risk=(b['pool']!='probe' or pr+risk<=.005*nav+1e-6),sector_capital=sc+cap<=frac*nav+1e-6,sector_risk=sr+risk<=.01*nav+1e-6)
    pre_available=D(snap['components']['available'])+D(snap['reservation_total_exact'])-reserved_exact_so_far
    gross=D(reserves[oj[sid]['order']]['gross_budget_cny'])
    checks['cash_original_10pct_reserve']=float(gross+fee)<=float(pre_available-decision_nav*D('.1'))+1e-6
    held=sum(l['qty'] for l in lots if l['sid']==sid)
    checks['stock_capital']=held*float(mark(sid,d,'OPEN'))+cap<=.10*float(decision_nav)+1e-6
    checks['order_attempt']=st is not None and b['attempt']==st['attempt'] and b['episode']==st['episode']
    reserved_exact_so_far+=gross+fee
    reserve_checks.append(dict(day=d,order=b['oid'],checks=checks))
    if not all(checks.values()):errors.append(dict(check='original_reservation_retained_guards',order=b['oid'],checks=checks))
    os.append(b)
  if len(os)!=len(resj):errors.append(dict(check='funding_order_count',actual=len(os),expected=len(resj)))
  total=resource(lots,os,marks)
  if not near(total[2],snap['reservation_total_exact']):errors.append(dict(check='reserve_bridge',actual=total[2],expected=snap['reservation_total_exact']))
  sectors=sorted({l['sector'] for l in lots}|{o['sector'] for o in os})
  quantities=collections.Counter()
  for l in lots:quantities[l['sid']]+=l['qty']
  rr=dict(day=d,status='EXACT_VERIFIED' if not errors else 'UNKNOWN',decision_NAV_exact=str(decision_nav),balance_components=snap['components'],reservation_fees_exact=snap['reservation_fees_exact'],probe=resource(lots,os,marks,'probe'),confirmed=resource(lots,os,marks,'confirmed'),all_resources=total,sectors={s:resource(lots,os,marks,sector=s) for s in sectors},stocks={s:dict(quantity=q,open_mark_exact=str(marks[s])) for s,q in sorted(quantities.items())},lots=lots,orders=os,errors=errors)
  # Quantity conservation through full-day buys; compare source close lot quantities, not inferred cost.
  cd=daily_by[d];qmap={l['id']:l['qty'] for l in lots}
  for b in buyj:qmap[b['layer']]=qmap.get(b['layer'],0)+b['shares']
  cq={l['id']:l['qty'] for l in cd['layers']}
  # Independent pool bridge: original fills/cancel-ack, then original close industry transitions.
  projected=copy.deepcopy(lots);remaining=list(os);st_after=copy.deepcopy(states)
  def migrate_projected(sec):
   st=st_after.get(sec)
   if not st or not st['active'] or st['level']==0:return
   if any(o['sector']==sec and o['attempt']==st['attempt'] and o['pool']=='probe' for o in remaining):return
   for l in projected:
    if l['sector']==sec and l['attempt']==st['attempt'] and l['pool']=='probe':l['pool']='confirmed'
  for bf in buyj:
   bo=next(o for o in remaining if o['oid']==bf['budget_order'])
   projected.append(dict(id=bf['layer'],qty=bf['shares'],sid=bf['sid'],sector=bo['sector'],attempt=bo['attempt'],pool=bo['pool']))
   remaining.remove(bo);migrate_projected(bo['sector'])
  for sec,ir in industry_rows.items():
   ir=ir[d];old=st_after.get(sec)
   if ir['E0_valid'] and (old is None or old['episode']!=ir['E0_episode']):
    st_after[sec]=dict(active=False,level=0,attempt=None,episode=ir['E0_episode'])
    if not any(e['sector']==sec for e in events[d]):silent_episode_resets.append(dict(day=d,sector=sec,old_active=old['active'] if old else None,old_episode=old['episode'] if old else None,new_episode=ir['E0_episode']))
  for e in events[d]:
   st_after[e['sector']]=dict(active=e['result']!='invalidated',level=e['financial_level'],attempt=e['attempt'],episode=e['episode'])
   if e['result']!='invalidated':migrate_projected(e['sector'])
  projected_pools={l['id']:l['pool'] for l in projected if l['qty']}
  actual_pools={l['id']:l['pool'] for l in cd['layers']}
  pool_bridge=projected_pools==actual_pools
  if not pool_bridge:errors.append(dict(check='close_layer_pool_bridge',differences={str(k):dict(projected=projected_pools.get(k),actual=actual_pools.get(k)) for k in set(projected_pools)|set(actual_pools) if projected_pools.get(k)!=actual_pools.get(k)}))
  if qmap!=cq:errors.append(dict(check='close_layer_quantity_bridge',actual=qmap,expected=cq))
  cl=copy.deepcopy(cd['layers']);cm={l['sid']:mark(l['sid'],d,'CLOSE') for l in cl}
  for l in cl:
   f=facts[l['sid']];factor=D(str(f.iloc[f.index.searchsorted(pd.Timestamp(d),side='right')-1]['factor']))
   l['raw_floor']=float((D(str(l['last_core_line'])) if l['kind']=='core' else D(l['floor']))/factor)
  cc={pool:resource(cl,[],cm,pool) for pool in ['probe','confirmed']}
  closepass=all(all(near(a,b) for a,b in zip(cc[pool],cd['pool_'+pool])) for pool in cc)
  if not closepass:errors.append(dict(check='close_pool_resources',derived=cc,original={pool:cd['pool_'+pool] for pool in cc}))
  cinv=sum((D(l['qty'])*cm[l['sid']] for l in cl),Z)
  if cinv!=D(cd['inventory']):errors.append(dict(check='close_inventory_exact',derived=str(cinv),original=cd['inventory']))
  if errors:rr['status']='UNKNOWN';unknown.append(dict(day=d,errors=errors))
  close_checks.append(dict(day=d,passed=closepass and qmap==cq and cinv==D(cd['inventory']) and pool_bridge,pool_bridge=pool_bridge))
  rr.update(at=snap['at'],probe_capital=rr['probe'][0],probe_risk=rr['probe'][1],sector_resources={s:dict(capital=v[0],risk=v[1],reserve=v[2]) for s,v in rr['sectors'].items()},stock_quantities=dict(quantities),marks={s:str(m) for s,m in marks.items()},original_pending_fees=snap['reservation_fees_exact'])
  rows.append(rr)
  states=st_after
  prev=cd
  if len(rows)%100==0:print('DAYS',len(rows),'UNKNOWN',len(unknown),flush=True)
 qa=dict(passed=not unknown,dates=len(rows),exact_verified_dates=len(rows)-len(unknown),unknown_dates=unknown,close_checks=close_checks,reservation_checks=reserve_checks,open_pool_migrations=migration_rows,open_pool_migration_counts=dict(migration_counts),silent_new_episode_resets=silent_episode_resets,sources=sources,no_account_or_runner_constructed=True,no_account_executed=True,original_files_modified=False,resource_order=['capital','floating_risk','pending_cash_reserve'],notes=['Prior-close layers, original native split integer distribution, then original per-layer sells.','Targeted non-pro-rata issuance leaves holder shares unchanged; its signal terms enter causal factor/mark.','Original all-reserve-before-fills clock; no fill refunds used.','Original policy lacks account 3% and confirmed 60% caps.','Risk arithmetic reproduces original floats with 1e-6 audit tolerance; balances use exact Decimal strings.','Failure-before-migration result names classified from original preview and route; remaining mobile funding entries processed in logged order.'])
 for name,obj in [('ORIGINAL_OPEN_RESOURCES.json',dict(account='PVR',rows=rows)),('RISK_RECONSTRUCTION_QA.json',qa)]:
  (HERE/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str,allow_nan=False))
 print('COMPLETE',len(rows),len(unknown),len(migration_rows),flush=True)
# Sector assignments are immutable and directly recoverable from original lot metadata and orders.
if __name__=='__main__':
 p0=json.load(gzip.open(RUN/'pair/PVR.json.gz','rt'));sector_by_sid={o['stock']:o['sector'] for o in p0['budget']['orders'].values()}
 # Add all traded/held securities, and then original frozen universe line assignments.
 manifest0=read(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/inputs-v2/input-manifest.json'))
 for s in manifest0.get('selection',{}).get('lines',[]):sector_by_sid[s['security_id']]=s['sector_id']
 # Funding-only security sectors are present in original opportunities.
 with gzip.open(RUN/'pair/opportunities.jsonl.gz','rt') as f:
  for line in f:
   o=json.loads(line)
   if o['account']=='PVR':sector_by_sid[o['sid']]=o['sector']
 del p0
 main()
