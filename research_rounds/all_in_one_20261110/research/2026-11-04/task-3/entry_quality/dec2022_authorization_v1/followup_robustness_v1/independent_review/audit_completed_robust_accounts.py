"""Read-only rolling audit of completed native paths; no Account or engine run."""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D,getcontext
import sys,json,gzip,hashlib,math,bisect
import numpy as np
import pandas as pd
getcontext().prec=65
P=Path(__file__).resolve().parents[1];O=Path(__file__).resolve().parent;T=P.parent.parent/'trend_exit_controls_v1';sys.path.insert(0,str(P));from variant_provider import VariantProvider
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');SM={r['symbol']:r for r in json.loads((W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json').read_text())};FACT={};FSHA={};Z=D(0);provider=None;calendar=sorted(pd.read_csv('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/mainline-absolute-Q4-20261031/recovery.csv',index_col=0).index.tolist());calindex={x:i for i,x in enumerate(calendar)}
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
RECEIPTS={};RECEIPT_PATHS={}
def oracle_predicate(q,arm):
 rr=q['RS20']<=0 if q['ready_R'] else None;pp=q['close']<q['EMA20'] if q['ready_P'] else None
 v=False if arm=='BASE' else rr if arm=='R_ONLY' else pp if arm=='P_ONLY' else (rr and pp) if q['ready_R'] and q['ready_P'] else None
 return dict(R_weak=rr,P_weak=pp,predicate_state='UNKNOWN' if v is None else 'TRUE' if v else 'FALSE',denies_mobile=v is True,unknown_keeps_native=True)
def receipt_at(window,sid,day,meta):
 key=(window,sid)
 if key not in RECEIPTS:
  if window=='strong':paths=[SM[sid]['refs']['receipts']]
  else:
   if not RECEIPT_PATHS:
    for mp in meta['input_identity']['receipt_union_sources']:
     if Path(mp).name!='MANIFEST.json':continue
     for z in read(mp):RECEIPT_PATHS.setdefault(z['sid'],[]).append(z['output_path'])
   paths=RECEIPT_PATHS[sid]
  rows={}
  for p in paths:
   FSHA[p]=sha(p)
   for z in read(p):
    assert z['confirmed_day'] not in rows
    rows[z['confirmed_day']]=z
  RECEIPTS[key]=rows
 return RECEIPTS[key].get(day)
RULEFILE=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json');RULES=read(RULEFILE)
def rule_at(records,day):
 found=[r for r in records if r['from']<=day and (r.get('to') is None or day<r['to'])];assert len(found)==1,(day,records);return found[0]
def fee_parts(schedule,side,local,shares,sid,paid,accrued):
 from decimal import ROUND_CEILING,ROUND_HALF_UP
 result={};rate_accrual={}
 for c in schedule['components']:
  if c.get('side','both') not in ['both',side]:continue
  name=c['name'];amount=c.get('amount_basis','notional');base=local if amount=='notional' else n(shares) if amount=='shares' else n(shares)*n(RULES['security_metadata'][sid]['par_value']);rate=base*n(c['rate']);minimum=n(c.get('minimum_local',0));perorder=c.get('basis','order')=='order';total=max(minimum,accrued.get(name,Z)+rate if perorder else rate)
  if c.get('maximum_local') is not None:total=min(total,n(c['maximum_local']))
  if c.get('rounding_unit') is not None:
   unit=n(c['rounding_unit']);total=(total/unit).to_integral_value(rounding=ROUND_CEILING if c.get('rounding_mode','nearest')=='ceil' else ROUND_HALF_UP)*unit
  result[name]=max(Z,total-paid.get(name,Z)) if perorder else total;rate_accrual[name]=rate
 return result,rate_accrual
def independent_cost_check(book,spec,C):
 paid={};accrued={};factor=n(spec['cost_multiplier']);slip=D('.0005')*factor;FSHA[str(RULEFILE)]=sha(RULEFILE)
 for a in book['audit']:
  if a['kind'] not in ['fill','reserve']:continue
  if a['kind']=='fill':
   receipt=a['receipt'];day=receipt['at'][:10];sid=receipt['security_id'];side=receipt['side'];local=n(receipt['gross_cny']);q=receipt['shares'];oid=a['order_id'];assert n(a['fx_rate'])==1
  else:day=a['at'][:10];sid=a['sid'];side='buy';local=n(a['gross_budget_cny']);q=a['target_shares'];oid=None
  venue=rule_at(RULES['venue_versions'][sid],day)['venue'];schedule=rule_at(RULES['fee_versions'][venue],day)['schedule'];assert a['fee_schedule']==schedule['schedule_id'];bp=paid.setdefault(oid,{}) if oid else {};ba=accrued.setdefault(oid,{}) if oid else {};expected,rates=fee_parts(schedule,side,local,q,sid,bp,ba)
  if oid:
   assert set(expected)==set(a['fee_components'])
   for name,value in expected.items():near(n(a['fee_components'][name]),value*factor,'independent_actual_fee_component',C);bp[name]=bp.get(name,Z)+value
   for name,value in rates.items():ba[name]=ba.get(name,Z)+value
   near(sum((v*factor for v in expected.values()),Z),receipt['fees_cny'],'independent_actual_fee_total',C);near(a['price'],n(a['raw_open'])*(1+slip if side=='buy' else 1-slip),'independent_actual_adverse_OPEN_price',C)
  else:near(sum((v*factor for v in expected.values()),Z),a['fee_reserved_cny'],'independent_actual_reserve_fee',C)
def audit(arm,window):
 global provider
 out=P/'runs'/arm/window;done=read(out/'DONE.json');assert done['completed'] and read(out/'TIMING.json')['completed'];C=Counter();meta=read(out/'RUN_METADATA.json');spec=meta['spec'];mode=spec['mode'];provider=VariantProvider(spec['R'],spec['EMA']);sources={str(out/'RUN_METADATA.json'):sha(out/'RUN_METADATA.json'),str(out/'DONE.json'):sha(out/'DONE.json'),str(out/'TIMING.json'):sha(out/'TIMING.json')}
 for p,h in meta['source_freeze'].items():assert sha(p)==h,(p,h);C['frozen_source_SHA']+=1
 assert meta['label']==arm and meta['window']==window and meta['fresh_cash']==1000000 and meta['no_checkpoint_import'] and not meta['yearly_reset']
 baseline=read(T/'runs/BASELINE'/window/'RUN_METADATA.json');assert {k:v for k,v in meta['input_identity'].items() if k!='seconds'}=={k:v for k,v in baseline['input_identity'].items() if k!='seconds'}
 book=read(out/'pair/B.json.gz');daily=read(out/'pair/daily.jsonl.gz');sources.update({str(out/'pair'/f):sha(out/'pair'/f) for f in ['B.json.gz','daily.jsonl.gz']});assert len(daily)==(726 if window=='2022_2024' else 242)
 logs=read(out/'pair/mobile-authorization-policy.jsonl.gz');heldlogs=[z for z in logs if z['phase']=='held_mobile_after_native_hard_exits'];rolelogs=[z for z in logs if z['phase']=='new_mobile_role_before_pending'];lm={(z['at'],z['sid']):z for z in heldlogs};assert len(lm)==len(heldlogs);assert len(heldlogs)+len(rolelogs)==len(logs)
 assert meta['context_provider_parameter_sha256']==provider.manifest_sha256;sources[str(out/'pair/mobile-authorization-policy.jsonl.gz')]=sha(out/'pair/mobile-authorization-policy.jsonl.gz')
 decisions={d['at']:d for d in book['decisions']}
 for z in rolelogs:
  day=z['at'][:10];q=provider.at(z['sid'],day);assert sameq(q,z['context']);de=oracle_predicate(q,mode);assert de==z['decision'] and z['allowed']==(not de['denies_mobile']);assert z['role']=='mobile' and not z['original_receipt_mutated'] and not z['original_core_permission_mutated']
  rec=receipt_at(window,z['sid'],day,meta);assert rec and rec['receipt_id']==z['CP1_id'];C['fresh_original_receipt_same_CLOSE']+=1
  if not z['allowed']:
   dc=decisions[z['at']];assert not any(i['sid']==z['sid'] and i['role']=='mobile' for i in dc['intents']);C['denied_mobile_has_no_native_intent']+=1
 independent_cost_check(book,spec,C)
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
      if part['reason'].startswith('mobile_authorization_'):
       assert part['reason']=='mobile_authorization_'+mode;assert book['metadata'][str(lid)]['role']=='mobile';ss=[z for z in tool_signals[lid] if z['at']<tm];assert ss and rq['at']<=ss[0]['at'];toolactual+=1;C['actual_tool_causal_request']+=1
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
    if a['reason'].startswith('mobile_authorization_'):
     z=lm[(tm,sid)];before=set(pending.get(sid,set()));assert before==set(z['prior_pending_layer_ids']);assert ids==before|set(z['added_mobile_exit_layer_ids']);assert not(before&set(z['added_mobile_exit_layer_ids']));tool_before[tm,sid]=before
     for lid in z['added_mobile_exit_layer_ids']:tool_signals[lid].append(z)
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
   if mode!='BASE' and d['on'] and bool(r.i_target) and any(book['metadata'][str(lid)]['role']=='mobile' and x['sid']==sid for lid,x in held.items()):expecthooks.add((at,sid))
  maxinv=max(maxinv,abs(inv-n(d['inventory'])));near(inv,d['inventory'],'all_cold_inventory',C);near(n(1000000)+tradecash+divs+inv,d['nav'],'all_daily_independent_NAV',C);assert n(d['available'])>=0;near(fees,d['fees_cny'],'all_daily_fees',C)
  actualkeys={key for key in lm if key[0]==at};assert actualkeys==expecthooks,(arm,window,at,actualkeys^expecthooks)
  for key in actualkeys:
   z=lm[key];sid=key[1];r,qd=row(sid,day);expected=provider.at(sid,day);assert sameq(z['context'],expected),(key,z['context'],expected);assert z['native_ACT_on'] and z['native_I_target'] and z['core_exit_ids_added']==[];decision=oracle_predicate(expected,mode);assert z['decision']==decision
   if expected['ready_R'] or expected['ready_P']:assert math.isclose(expected['close'],float(r['close']),rel_tol=1e-11,abs_tol=1e-11) and expected['source_segment']==float(r.segment_id)
   before=tool_before.get(key,set(pending.get(sid,set())));assert set(z['prior_pending_layer_ids'])==before;live={lid for lid,x in held.items() if x['sid']==sid and book['metadata'][str(lid)]['role']=='mobile'};assert set(z['live_mobile_layer_ids'])==live;assert set(z['added_mobile_exit_layer_ids'])==(live-before if decision['denies_mobile'] else set());assert (z['request_reason'] is not None)==bool(z['added_mobile_exit_layer_ids']);seenlogs.add(key);C['all_hook_eligibility_price_ids']+=1
 assert j==len(events) and seenlogs==set(lm)
 for x in book['layers']:
  y=layers[x['id']];assert y['q']==x['qty'];near(y['cash'],x['cash'],'final_all_layer_trade_cash',C);near(y['div'],x['dividend'],'final_all_layer_AR',C)
 basis=sum((x['basis'] for x in layers.values()),Z);unreal=inv-basis;near(realized+writeoff+unreal+divs,n(book['ending_NAV'])-1000000,'final_realized_unrealized_AR_wealth',C);near(sum((x['cash']+x['div'] for x in layers.values()),Z)+inv,n(book['ending_NAV'])-1000000,'final_lifecycle_wealth',C)
 assert book['ending_NAV']==daily[-1]['nav'] and book['ending_cash']==daily[-1]['available'];C['final_NAV_cash']+=1
 result=dict(status='PASS_COMPLETED_ACCOUNT_WITH_LIMITS',arm=arm,label=arm,spec=spec,mode=mode,auditor_script_sha256=sha(__file__),window=window,daily=len(daily),trades=len(book['trades']),layers=len(layers),checks=dict(C),ending_NAV=book['ending_NAV'],net_wealth=str(n(book['ending_NAV'])-1000000),trade_realized=str(realized),corporate_zero_qty_basis_writeoff=str(writeoff),open_unrealized=str(unreal),recognized_dividend_AR_cumulative=str(divs),total_fees=str(fees),partial_layer_sale_occurrences=partials,tool_requests=sum(bool(z['added_mobile_exit_layer_ids']) for z in heldlogs),mobile_role_logs=len(rolelogs),mobile_denials=sum(not z['allowed'] for z in rolelogs),actual_tool_parts=toolactual,tool_then_other_reason_parts=toolthenother,actual_exit_part_reasons=dict(actualreasons),request_to_fill_session_steps=dict(delays),max_cold_inventory_difference=str(maxinv),source_sha256=sources,frozen_metadata_sources=meta['source_freeze'],raw_price_source_sha256=FSHA.copy(),limits=['Independent integer share/FIFO sellability, split/bonus/fractional proxy units, fee-inclusive per-layer basis, sold-basis allocation and recognized dividend entitlement replay. Not a new strategy/account engine.','All daily NAV/cashflow/AR/cold original-facts mark bridges and actual tool eligibility/liveIDs/pending priority checked. AR is wealth; no claim that realized P&L or AR is settled spendable cash.','Actual sell clock follows original order-created event, including earlier CP orders extended by tool and later I/ACT reason changes. No trigger-CLOSE sale permitted.','T+1 replay uses frozen A-share one-market-session buy sellability plus each recorded corporate-action new-share sellability. Original HLV/capacity execution proxy limits remain; fills are local model receipts.','New10/40 arrays/old20 exact reuse and nativeprefix audits reused; effective provider selected from frozen metadata. Costfee/price arithmetic independently checked against original historical rule versions.','No counterfactual attribution of NAV change to a particular original layer. Scope-stage wealth and newly opened layer life returns must remain separate.'],new_accounts=0)
 return result
index={};freeze=read(P/'ROBUSTNESS_FREEZE.json')
for spec in freeze['parameter_variants']+freeze['cost_variants']:
 arm=spec['label']
 for window in ['2022_2024','strong']:
  path=P/'runs'/arm/window
  if not all((path/name).exists() for name in ['DONE.json','TIMING.json']):continue
  if not(read(path/'DONE.json')['completed'] and read(path/'TIMING.json')['completed']):continue
  dst=O/(arm+'_'+window+'_ACCOUNT_AUDIT.json')
  if dst.exists():
   result=read(dst)
   for p,h in result['source_sha256'].items():assert sha(p)==h
  else:
   print('AUDITING_ROBUST',arm,window,flush=True);result=audit(arm,window);dst.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('ROBUST_ACCOUNT_AUDIT_PASS',arm,window,result['ending_NAV'],flush=True)
  index[arm+'|'+window]=dict(receipt=str(dst),sha256=sha(dst),ending_NAV=result['ending_NAV'],status=result['status'])
(O/'COMPLETED_ACCOUNT_AUDIT_INDEX.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n');print('ROLLING_ROBUST_COMPLETE',len(index),flush=True)
