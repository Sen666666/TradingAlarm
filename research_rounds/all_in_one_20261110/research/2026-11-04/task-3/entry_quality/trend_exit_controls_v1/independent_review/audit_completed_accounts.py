"""Read-only rolling audit of completed native paths; no Account or engine run."""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D,getcontext
import sys,json,gzip,hashlib,math,bisect
import numpy as np
import pandas as pd
getcontext().prec=65
P=Path(__file__).resolve().parents[1];O=Path(__file__).resolve().parent;sys.path.insert(0,str(P));from indicator_provider import IndicatorProvider
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');SM={r['symbol']:r for r in json.loads((W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json').read_text())};FACT={};FSHA={};Z=D(0);provider=IndicatorProvider();manifest=json.loads((P/'indicators/MANIFEST.json').read_text());calendar=sorted(pd.read_csv('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/mainline-absolute-Q4-20261031/recovery.csv',index_col=0).index.tolist());calindex={x:i for i,x in enumerate(calendar)}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 p=Path(p)
 with (gzip.open(p,'rt') if p.suffix=='.gz' else p.open()) as f:return [json.loads(x) for x in f] if '.jsonl' in p.name else json.load(f)
def sameq(a,b):
 if a.keys()!=b.keys():return False
 return all((x==b[k] or isinstance(x,float) and isinstance(b[k],float) and math.isnan(x) and math.isnan(b[k])) for k,x in a.items())
def row(sid,day):
 if sid not in FACT:
  p=SM[sid]['refs']['facts'];h=sha(p);assert h==SM[sid]['output_sha256'][p];FSHA[p]=h;FACT[sid]=pd.read_parquet(p,columns=['close','raw_close','segment_id','i_target'])
 f=FACT[sid];j=f.index.searchsorted(pd.Timestamp(day),side='right')-1;assert j>=0,(sid,day);return f.iloc[j],str(f.index[j].date())
def n(x):return D(str(x))
def near(a,b,key,C):assert abs(n(a)-n(b))<D('1e-7'),(key,a,b);C[key]+=1
def audit(arm,window):
 out=P/'runs'/arm/window;done=read(out/'DONE.json');assert done['completed'];meta=read(out/'RUN_METADATA.json');sources={str(out/'RUN_METADATA.json'):sha(out/'RUN_METADATA.json'),str(out/'DONE.json'):sha(out/'DONE.json')};C=Counter()
 for p,h in meta['source_freeze'].items():assert sha(p)==h,(p,h);C['frozen_source_SHA']+=1
 assert meta['arm']==arm and meta['window']==window and meta['fresh_cash']==1000000 and meta['no_checkpoint_import'] and not meta['yearly_reset']
 baseline=read(P/'runs/BASELINE'/window/'RUN_METADATA.json');assert {k:v for k,v in meta['input_identity'].items() if k!='seconds'}=={k:v for k,v in baseline['input_identity'].items() if k!='seconds'}
 book=read(out/'pair/B.json.gz');daily=read(out/'pair/daily.jsonl.gz');sources.update({str(out/'pair'/f):sha(out/'pair'/f) for f in ['B.json.gz','daily.jsonl.gz']});assert len(daily)==(726 if window=='2022_2024' else 242)
 logs=[] if arm=='BASELINE' else read(out/'pair/trend-exit-policy.jsonl.gz');lm={(z['at'],z['sid']):z for z in logs};assert len(lm)==len(logs)
 if arm!='BASELINE':assert meta['tool_manifest_sha256']==provider.manifest_sha256;sources[str(out/'pair/trend-exit-policy.jsonl.gz')]=sha(out/'pair/trend-exit-policy.jsonl.gz')
 trades={t['receipt_id']:t for t in book['trades']};requests={x['event_id']:x for x in book['audit'] if x['kind']=='exit_request'};events=[]
 for a in book['audit']:
  k=a['kind']
  if k=='fill':at=a['receipt']['at']
  elif k=='dividend_accrual':at=a['receivable']['ex_at']
  elif k in ['split','split_fraction_floor_proxy','pilot_layer_exit']:at=a['at']
  else:continue
  events.append((at,a))
 assert all(events[i][0]<=events[i+1][0] for i in range(len(events)-1))
 layers={};fifo=defaultdict(list);pending={};tool_before={};tool_signals=defaultdict(list);j=0;tradecash=Z;divs=Z;fees=Z;realized=Z;writeoff=Z;seenlogs=set();toolactual=0;toolthenother=0;maxinv=Z;delays=Counter();actualreasons=Counter();partials=0
 for d in daily:
  at=d['at'];day=at[:10]
  while j<len(events) and events[j][0]<=at:
   tm,a=events[j];j+=1;k=a['kind']
   if k=='fill':
    receipt=a['receipt'];t=trades[receipt['receipt_id']];sid=t['security_id'];assert t['at']==tm and tm[11:19]=='09:30:00';q=t['shares'];gross=n(t['gross_cny']);fee=n(t['fees_cny']);near(fee,sum((n(v) for v in a['fee_components'].values()),Z),'all_fee_components',C);near(gross,n(t['price'])*q,'all_gross_price_quantity',C);fees+=fee
    if t['side']=='buy':
     lid=t['layer'];assert lid not in layers;layers[lid]=dict(sid=sid,q=q,basis=gross+fee,cash=-gross-fee,div=Z,opened=tm);tradecash-=gross+fee;assert tm[:10] in calindex;fifo[sid].append([q,calindex[tm[:10]]+1]);C['buy_Tplus1_lots']+=1
    else:
     rq=requests[a['order_id']];assert rq['sid']==sid and rq['at']<tm;delays[calindex[tm[:10]]-calindex[rq['at'][:10]]]+=1;C['actual_order_clock']+=1
     assert q<=sum(s for s,eligible in fifo[sid] if eligible<=calindex[tm[:10]]),(arm,window,sid,tm,'insufficientTplus1');left=q
     for lot in fifo[sid]:
      if lot[1]<=calindex[tm[:10]]:take=min(lot[0],left);lot[0]-=take;left-=take
     assert left==0;fifo[sid]=[lot for lot in fifo[sid] if lot[0]];tradecash+=gross-fee;assert sum(p['shares'] for p in t['parts'])==q;near(sum((n(p['net_cash']) for p in t['parts']),Z),gross-fee,'all_sale_part_cash',C)
     for part in t['parts']:
      lid=part['layer'];x=layers[lid];assert x['sid']==sid and x['q']>=part['shares'];allocated=x['basis']*part['shares']/x['q'];realized+=n(part['net_cash'])-allocated;x['basis']-=allocated;x['q']-=part['shares'];x['cash']+=n(part['net_cash']);partials+=bool(x['q']);actualreasons[part['reason']]+=1
      if part['reason'].startswith('trend_early_'):
       assert arm!='BASELINE' and part['reason']=='trend_early_'+arm[6:];ss=[z for z in tool_signals[lid] if z['at']<tm];assert ss and rq['at']<=ss[0]['at'];toolactual+=1;C['actual_tool_causal_request']+=1
      elif tool_signals[lid]:toolthenother+=1
     if sid in pending and not any(layers[lid]['q'] for lid in pending[sid]):pending.pop(sid)
     C['all_actual_sells_Tplus1_and_parts']+=1
   elif k=='dividend_accrual':
    r=a['receivable'];sid=r['security_id'];value=n(r['net_local']);live=[x for x in layers.values() if x['sid']==sid and x['q']];tot=sum(x['q'] for x in live);assert tot>0
    for x in live:x['div']+=value*x['q']/tot
    divs+=value;C['dividend_entitlement_allocation']+=1
   elif k in ['split','split_fraction_floor_proxy']:
    sid=a['sid'];ratio=n(a['ratio']);old=fifo[sid];newday=a['new_shares_sellable_at'][:10];newidx=bisect.bisect_left(calendar,newday);oldtotal=sum(q for q,t in old)
    if old:
     if k=='split_fraction_floor_proxy':
      target=int(n(oldtotal)*ratio);eligible=max(newidx,max(t for q,t in old))
      if ratio>=1:
       if target>oldtotal:old.append([target-oldtotal,eligible])
      else:fifo[sid]=[[target,eligible]] if target else []
     elif ratio>=1:
      additions=[]
      for q,t in old:
       value=n(q)*(ratio-1);assert value==int(value)
       if value:additions.append([int(value),max(t,newidx)])
      old.extend(additions)
     else:
      for lot in old:value=n(lot[0])*ratio;assert value==int(value);lot[:]=[int(value),max(lot[1],newidx)]
    live=[x for x in layers.values() if x['sid']==sid and x['q']];target=sum(q for q,t in fifo[sid]);qq=[int(n(x['q'])*ratio) for x in live];remain=target-sum(qq);assert 0<=remain<=len(live)
    for index,x in enumerate(live):
     x['q']=qq[index]+(index<remain)
     if not x['q']:writeoff-=x['basis'];x['basis']=Z
    C['corporate_action_lot_and_layer_units']+=1
   elif k=='pilot_layer_exit':
    sid=a['sid'];ids=set(a['layers']);assert ids and all(lid in layers for lid in ids)
    if a['reason'].startswith('trend_early_'):
     z=lm[(tm,sid)];before=set(pending.get(sid,set()));assert before==set(z['prior_pending_layer_ids']);assert ids==before|set(z['added_indicator_layer_ids']);assert not(before&set(z['added_indicator_layer_ids']));tool_before[tm,sid]=before
     for lid in z['added_indicator_layer_ids']:tool_signals[lid].append(z)
     C['tool_native_request_pending_priority']+=1
    pending[sid]=ids
  # Independently verify every actual held-layer state and cold native mark.
  held={lid:x for lid,x in layers.items() if x['q']};snapshot={x['id']:x for x in d['layers']};assert set(held)==set(snapshot)
  bystock=defaultdict(int)
  for lid,x in held.items():
   h=snapshot[lid];assert x['q']==h['qty'];near(x['cash'],h['cash'],'all_held_trade_cash',C);near(x['div'],h['dividend'],'all_held_recognized_AR',C);bystock[x['sid']]+=x['q']
  assert dict(bystock)==d['positions']=={s:sum(q for q,t in lots) for s,lots in fifo.items() if sum(q for q,t in lots)}
  inv=Z;expecthooks=set()
  for sid,q in bystock.items():
   r,qd=row(sid,day);inv+=q*n(r.raw_close)
   if arm!='BASELINE' and d['on'] and bool(r.i_target):expecthooks.add((at,sid))
  maxinv=max(maxinv,abs(inv-n(d['inventory'])));near(inv,d['inventory'],'all_cold_inventory',C);near(n(1000000)+tradecash+divs+inv,d['nav'],'all_daily_independent_NAV',C);assert n(d['available'])>=0;near(fees,d['fees_cny'],'all_daily_fees',C)
  actualkeys={key for key in lm if key[0]==at};assert actualkeys==expecthooks,(arm,window,at,actualkeys^expecthooks)
  for key in actualkeys:
   z=lm[key];sid=key[1];r,qd=row(sid,day);expected=provider.at(sid,day,arm[6:]);assert sameq(z['indicator'],expected),(key,z['indicator'],expected);assert z['native_ACT_on'] and z['native_I_target'];broken=expected['status']=='READY' and expected['causal_close']<expected['line'];assert broken==z['indicator_break']
   if expected['status']=='READY':assert math.isclose(expected['causal_close'],float(r['close']),rel_tol=1e-11,abs_tol=1e-11) and expected['source_segment']==float(r.segment_id)
   before=tool_before.get(key,set(pending.get(sid,set())));assert set(z['prior_pending_layer_ids'])==before;live={lid for lid,x in held.items() if x['sid']==sid};assert set(z['added_indicator_layer_ids'])==(live-before if broken else set());assert (z['request_reason'] is not None)==bool(z['added_indicator_layer_ids']);seenlogs.add(key);C['all_hook_eligibility_price_ids']+=1
 assert j==len(events) and seenlogs==set(lm)
 for x in book['layers']:
  y=layers[x['id']];assert y['q']==x['qty'];near(y['cash'],x['cash'],'final_all_layer_trade_cash',C);near(y['div'],x['dividend'],'final_all_layer_AR',C)
 basis=sum((x['basis'] for x in layers.values()),Z);unreal=inv-basis;near(realized+writeoff+unreal+divs,n(book['ending_NAV'])-1000000,'final_realized_unrealized_AR_wealth',C);near(sum((x['cash']+x['div'] for x in layers.values()),Z)+inv,n(book['ending_NAV'])-1000000,'final_lifecycle_wealth',C)
 assert book['ending_NAV']==daily[-1]['nav'] and book['ending_cash']==daily[-1]['available'];C['final_NAV_cash']+=1
 result=dict(status='PASS_COMPLETED_ACCOUNT_WITH_LIMITS',arm=arm,window=window,daily=len(daily),trades=len(book['trades']),layers=len(layers),checks=dict(C),ending_NAV=book['ending_NAV'],net_wealth=str(n(book['ending_NAV'])-1000000),trade_realized=str(realized),corporate_zero_qty_basis_writeoff=str(writeoff),open_unrealized=str(unreal),recognized_dividend_AR_cumulative=str(divs),total_fees=str(fees),partial_layer_sale_occurrences=partials,tool_requests=sum(bool(z['added_indicator_layer_ids']) for z in logs),actual_tool_parts=toolactual,tool_then_other_reason_parts=toolthenother,actual_exit_part_reasons=dict(actualreasons),request_to_fill_session_steps=dict(delays),max_cold_inventory_difference=str(maxinv),source_sha256=sources,frozen_metadata_sources=meta['source_freeze'],raw_price_source_sha256=FSHA.copy(),limits=['Independent integer share/FIFO sellability, split/bonus/fractional proxy units, fee-inclusive per-layer basis, sold-basis allocation and recognized dividend entitlement replay. Not a new strategy/account engine.','All daily NAV/cashflow/AR/cold original-facts mark bridges and actual tool eligibility/liveIDs/pending priority checked. AR is wealth; no claim that realized P&L or AR is settled spendable cash.','Actual sell clock follows original order-created event, including earlier CP orders extended by tool and later I/ACT reason changes. No trigger-CLOSE sale permitted.','T+1 replay uses frozen A-share one-market-session buy sellability plus each recorded corporate-action new-share sellability. Original HLV/capacity execution proxy limits remain; fills are local model receipts.','Tool data/source formulas reuse completed full immutable indicator audit; no indicators recalculated here.','No counterfactual attribution of NAV change to a particular original layer. Scope-stage wealth and newly opened layer life returns must remain separate.'],new_accounts=0)
 return result
index={}
for arm in ['BASELINE','EARLY_EMA20','EARLY_EMA60','EARLY_BOLL20_MID','EARLY_BOLL20_LOWER']:
 for window in ['2022_2024','strong']:
  path=P/'runs'/arm/window
  if not (path/'DONE.json').exists():continue
  dst=O/(arm+'_'+window+'_ACCOUNT_AUDIT.json')
  if dst.exists():
   result=read(dst)
   for p,h in result['source_sha256'].items():assert sha(p)==h
  else:
   print('AUDITING',arm,window,flush=True);result=audit(arm,window);dst.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('ACCOUNT_AUDIT_PASS',arm,window,result['ending_NAV'],flush=True)
  index[arm+'|'+window]=dict(receipt=str(dst),sha256=sha(dst),ending_NAV=result['ending_NAV'],status=result['status'])
(O/'COMPLETED_ACCOUNT_AUDIT_INDEX.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n');print('ROLLING_COMPLETE',len(index),flush=True)
