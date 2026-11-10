"""Offline descriptive diagnostic only. No model/engine/Data import, no history replay, no network."""
from pathlib import Path
from decimal import Decimal as D, ROUND_CEILING, ROUND_HALF_UP
from collections import defaultdict, Counter
import json, csv, hashlib, sys, math
sys.dont_write_bytecode=True
import pandas as pd
import numpy as np
R=Path('/Users/bytedance/Documents/Codex/2026-11-09/sector51_924_entry_review_v1'); O=Path(__file__).parent
B=R/'mainline_candidate_v11_structural_maturity_entry_execution_fix_v2/once_20250120'; A=R/'mainline_v11_account_audit_v2'; END='2025-01-20'; Z=D(0); hashes={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 p=Path(p); hashes[str(p)]=sha(p); return json.loads(p.read_text())
def save(n,v):
 (O/(n+'.json')).write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str)+'\n')
 if isinstance(v,list) and v:
  with (O/(n+'.csv')).open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in v for k in r)));w.writeheader();w.writerows({k:json.dumps(x,ensure_ascii=False,default=str) if isinstance(x,(list,dict)) else x for k,x in r.items()} for r in v)
def dec(v):return D(str(v))
def pos(v):
 try:return dec(v).is_finite() and dec(v)>0
 except:return False
def tri(v):return -1 if pd.isna(v) else int(v)
sources=read(B/'SOURCE_HASHES.json'); outseal=read(B/'OUTPUT_HASHES.json')
for name,h in outseal.items():assert sha(B/name)==h,('saved_output_drift',name)
def sealed(p):
 p=str(p);assert p in sources and sha(p)==sources[p],('unsealed_or_drift',p);hashes[p]=sources[p];return p
orders=read(B/'ORDERS.json'); holds=read(B/'HOLDINGS.json'); caps=read(B/'CAPITAL_LOTS.json'); eq=read(B/'EQUITY_EVENTS.json'); sector=read(B/'SECTOR_DAILY.json'); led=read(B/'DAY_LEDGER.json'); seedrisk=read(B/'SEED_FLOOR_RISK.json'); evs=read(B/'ENTRY_CP_EVENTS.json'); cpevs=read(B/'CP_EVENTS.json'); admission=read(B/'EVENT_ADMISSION.json')
routes=read(A/'STRICT_ENTRY_SEMANTICS.json'); rounds=read(A/'V11_ACTUAL_ROUNDS.json'); assert routes['verdict']=='PASS_SAVED_ENTRY_SEMANTICS'
assert len(led)==93 and led[-1]['day']==END
calendar=[r['day'] for r in led]; dix={d:i for i,d in enumerate(calendar)}
manifest={x['symbol']:x for x in read(sealed(next(p for p in sources if p.endswith('/universe-cp1-inputs-20261031/STOCK_MANIFEST.json'))))}
fees=read(sealed(next(p for p in sources if p.endswith('/inputs-v2/market-rules.json'))));proxies=read(sealed(next(p for p in sources if p.endswith('/inputs-v2/economic-protocol.json'))))['approved_proxy_ids']
def version(rs,d):
 ss=[r for r in rs if r['from']<=d and (not r.get('to') or d<r['to'])];assert len(ss)==1;return ss[0]
def fee(s,d,q,p):
 if not q:return Z
 venue=version(fees['venue_versions'][s],d)['venue']; schedule=version(fees['fee_versions'][venue],d)['schedule'];v=Z
 for c in schedule['components']:
  if c.get('side','both') not in ('both','sell'):continue
  basis=c.get('amount_basis','notional');amount=q*p if basis=='notional' else D(q) if basis=='shares' else D(q)*dec(fees['security_metadata'][s]['par_value'])
  f=max(dec(c.get('minimum_local','0')),amount*dec(c['rate']))
  if c.get('maximum_local') is not None:f=min(f,dec(c['maximum_local']))
  if c.get('rounding_unit'):
   u=dec(c['rounding_unit']);f=(f/u).to_integral_value(rounding=ROUND_CEILING if c.get('rounding_mode')=='ceil' else ROUND_HALF_UP)*u
  v+=f
 return v
byround=defaultdict(list); bylot=defaultdict(list); roundmap={r['round_id']:r for r in rounds};hmap={(h['round_id'],h['day']):[] for h in holds}
for h in holds:hmap[h['round_id'],h['day']].append(h)
capmap={(c['lot_id'],c['day']):c for c in caps};secmap={(s['sector51'],s['day']):s for s in sector};riskmap={r['round_id']:r for r in seedrisk}
consumed={(e['sid'],e['original_signal_day']):e for e in evs if e['event']=='CONSUMED'}
routecp={x['order_seq']:x for x in routes['actual_seed_routes'] if x['route']=='CP'};seeds=[x for x in orders if x['order_seq'] in routecp];assert len(seeds)==319
inventory={};allocations={}
for o in orders:
 byround[o['round_id']].append(o)
 if o['side'].startswith('BUY'):inventory[o['lot_id']]=o['qty']
 else:
  al=o.get('lot_quantities') or {l:inventory[l] for l in o['lots']};assert sum(al.values())==o['qty'];allocations[o['order_seq']]=al
  for l,q in al.items():
   bylot[l].append(dict(order_seq=o['order_seq'],day=o['day'],qty=q,price=o['price'],cash_delta=dec(o['cash_delta'])*q/o['qty'],fee=dec(o['fee'])*q/o['qty'],reason=o['reason'])); inventory[l]-=q
cashterms={}
for p in sources:
 path=Path(p)
 if path.suffix!='.json' or not any(x in path.name.upper() for x in ['EVENT','ADDITIONAL','EXTRA','EXACT_CASH','MANIFEST']):continue
 if 'RAW' in path.name.upper() or 'CNINFO' in path.name.upper():continue
 def visit(x):
  if isinstance(x,dict):
   if all(k in x for k in ['sid','ex_date','record_date','pay_date','d_cash','factor_old','factor_new']):cashterms[x['sid'],x['ex_date']]=x
   for v in x.values():
    if isinstance(v,(dict,list)):visit(v)
  elif isinstance(x,list):
   for v in x:visit(v)
 visit(read(sealed(p)))
admitted={(a['sid'],a['ex_date']) for a in admission};frames={};facts={};actions={};sourceissues=[]
def load(s):
 if s not in frames:
  m=manifest[s]; rp=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'))
  frames[s]=pd.read_parquet(sealed(rp)).loc[:END];facts[s]=pd.read_parquet(sealed(m['refs']['facts'])).loc[:END]
  aps=[p for p in sources if p.endswith('/inputs-v1/actions/'+s+'.json')];assert len(aps)==1
  actions[s]={e['effective_date']:e for e in read(sealed(aps[0]))['events'] if e['effective_date']<=END}
 return frames[s]
ids=sorted({s['sid'] for s in seeds}); qroot='/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/'
kp=sealed(qroot+'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/KNOWN3.parquet');rp=sealed(qroot+'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/RIGHT3.parquet');pp=sealed(qroot+'pvr_persistence_breadth_v1/STOCK_DAILY.parquet')
k=pd.read_parquet(kp,columns=ids).loc[:END];rr=pd.read_parquet(rp,columns=ids).loc[:END];pv=pd.read_parquet(pp,columns=['sid','day','state']);pv=pv[pv.sid.isin(ids)&pv.day.le(pd.Timestamp(END))].pivot(index='day',columns='sid',values='state').reindex(index=k.index,columns=ids);known=k&pv.ge(0);stock=pd.DataFrame(np.where(known,np.where(rr&known,1,0),-1),index=k.index,columns=ids)
def quote(s,d,origin,lastfac):
 f=load(s);t=pd.Timestamp(d)
 if t not in f.index:return None,'MISSING_ROW'
 z=f.loc[t]
 if tuple(str(z.get(c)) for c in ['source_kind','source_path','segment_id'])!=tuple(origin):return None,'SOURCE_CHANGE_OR_UNKNOWN'
 if not all(tri(z.get(c))==1 for c in ['observed_bar','price_eligible','volume_eligible']) or not all(tri(z.get(c))==0 for c in ['source_invalid','synthetic_event_bar']):return None,'QUOTE_UNOBSERVABLE'
 if not all(pos(z.get(c)) for c in ['raw_open','raw_close','raw_high','raw_low','adjustment_factor']):return None,'PRICE_FACTOR_UNKNOWN'
 fac=dec(z.adjustment_factor)
 act=actions[s].get(d); ce=cashterms.get((s,d))
 if act and (s,d) not in admitted:return None,'UNADMITTED_ACTION'
 if lastfac is not None and abs(fac/lastfac-1)>D('1e-11'):
  if (s,d) not in admitted or ce is None:return None,'UNADMITTED_FACTOR_CHANGE'
  if abs(lastfac/dec(ce['factor_old'])-1)>D('1e-11') or abs(fac/dec(ce['factor_new'])-1)>D('1e-11'):return None,'FACTOR_BRIDGE_MISMATCH'
 return z,None
def q_at(rid,lid,d,phase):
 day=calendar[dix[d]-1] if phase=='OPEN' and dix[d]>0 else None if phase=='OPEN' else d
 hs=hmap.get((rid,day),[]);return sum(h['qty'] for h in hs),sum(h['qty'] for h in hs if h['lot_id']==lid),hs
rows=[]; paths=[];cashrows=[];observations=[]
for s0 in seeds:
 sid=s0['sid'];rid=s0['round_id'];lid=s0['lot_id'];f=load(sid);rd=roundmap[rid];slot=consumed[sid,s0['signal_day']]['final_slot'];assert slot['id']==s0['entry_evidence_id']
 floor=dec(slot['floor']);entryi=dec(riskmap[rid]['known_protection']);entryday=s0['day'];fac=dec(f.loc[pd.Timestamp(entryday)].adjustment_factor);initialfac=fac;origin=slot['origin'];oseq=byround[rid];sells=bylot[lid];entryraw=dec(s0['price'])/D('1.0005');first=None;problem=None;daily=[]
 for d in calendar[dix[entryday]:]:
  z,err=quote(sid,d,origin,fac)
  if err:problem=dict(day=d,reason=err);break
  fac=dec(z.adjustment_factor);st=stock.loc[pd.Timestamp(d),sid];ff=facts[sid].loc[pd.Timestamp(d)] if pd.Timestamp(d) in facts[sid].index else {}
  for phase,col in [('OPEN','raw_open'),('CLOSE','raw_close')]:
   raw=dec(z[col]);adj=raw*fac
   daily.append(dict(day=d,phase=phase,raw=raw,adj=adj,factor=fac))
   if not (d==entryday and phase=='OPEN') and first is None and adj<=floor:first=dict(day=d,phase=phase,raw=raw,adj=adj,factor=fac)
 r=dict(round_id=rid,sid=sid,name=s0['name'],sector51=s0['sector51'],seed_day=entryday,signal_day=s0['signal_day'],seed_order_seq=s0['order_seq'],seed_lot_id=lid,seed_qty=s0['qty'],seed_raw_fill=dec(s0['price']),seed_all_in=-dec(s0['cash_delta']),entry_factor=initialfac,entry_evidence_id=slot['id'],entry_receipt_day=slot['receipt_day'],entry_cp_floor=floor,entry_I=entryi,cp_minus_I=floor-entryi,entry_open_to_I_raw=entryraw-entryi/initialfac,entry_open_to_CP_raw=entryraw-floor/initialfac,entry_I_distance_pct=100*(1-entryi/(entryraw*initialfac)),entry_CP_distance_pct=100*(1-floor/(entryraw*initialfac)),CP_above_I=floor>entryi,actual_add_orders=[{k:o[k] for k in ['order_seq','day','qty','price','lot_id','cp_id']} for o in oseq if o['side']=='BUY_ADD'],actual_seed_sales=sells,actual_round_exit=rd['exit_day'],actual_round_final_qty=rd['final_qty'],actual_round_pnl=rd['marked_net_pnl'],actual_round_add_count=rd['add_count'],source_stop=problem,first_entry_CP_breach=first,original_strategy_protection=False)
 # Full actual seed attribution: order fee allocated pro rata across sold lots; no claim it is separate account PnL.
 seeddiv=Z
 for e in eq:
  if e.get('round_id')==rid and e['event']=='ACCRUE_NET80':
   term=cashterms.get((sid,e['day']))
   if term:
    sq=q_at(rid,lid,term['record_date'],'CLOSE')[1]; seeddiv+=D(sq)*dec(term['d_cash'])*D('.8')
 actual_seed_net=dec(s0['cash_delta'])+sum((dec(x['cash_delta']) for x in sells),Z)+seeddiv
 endhs=hmap.get((rid,END),[]);actual_seed_net+=sum((dec(h['market_value']) for h in endhs if h['lot_id']==lid),Z)
 r.update(actual_seed_net_allocated_fees_and_dividend=actual_seed_net,actual_seed_dividend=seeddiv,actual_seed_final_qty=sum(h['qty'] for h in endhs if h['lot_id']==lid))
 if first:
  d=first['day'];phase=first['phase'];rq,sq,hs=q_at(rid,lid,d,phase);afterq,aftersq,afterhs=q_at(rid,lid,d,'CLOSE');known_d=calendar[dix[d]-1] if phase=='OPEN' else d
  ff=facts[sid].loc[pd.Timestamp(known_d)] if pd.Timestamp(known_d) in facts[sid].index else {}; sec=secmap[s0['sector51'],known_d]
  prevseed=[h for h in hs if h['lot_id']==lid]; ii=dec(prevseed[0]['protection_signal']) if prevseed else None
  cf=sum((dec(o['cash_delta']) for o in oseq if o['day']<d or phase=='CLOSE' and o['day']==d),Z);dv=sum((dec(e['receivable_delta']) for e in eq if e.get('round_id')==rid and e['event']=='ACCRUE_NET80' and e['day']<=d),Z);sellp=first['raw']*D('.9995');net=cf+dv+rq*sellp-fee(sid,d,rq,sellp)
  before_sales=[x for x in sells if x['day']<d or phase=='CLOSE' and x['day']==d];before_adds=[o for o in oseq if o['side']=='BUY_ADD' and (o['day']<d or phase=='CLOSE' and o['day']==d)]
  r.update(breach_seed_qty=sq,breach_round_qty=rq,breach_after_actual_OPEN_seed_qty=aftersq,breach_after_actual_OPEN_round_qty=afterq,breach_I=ii,breach_still_above_I=first['adj']>ii if ii else None,breach_known_state_day=known_d,breach_known_I_target=tri(ff.get('i_target')),breach_known_stock_state=int(stock.loc[pd.Timestamp(known_d),sid]),breach_known_sector_state=sec['state'],breach_known_M=sec['M'],breach_known_F=sec['F'],breach_known_S=sec['S'],breach_round_net=net,breach_prior_seed_sold_qty=sum(x['qty'] for x in before_sales),breach_prior_ADD_count=len(before_adds),breach_seed_locked_exit=prevseed[0]['locked_exit'] if prevseed else None)
  start=dix[d]+(phase=='CLOSE');exe=None;execstop=None
  for xd in calendar[start:]:
   if xd<=entryday:continue
   points=[v for v in daily if v['day']==xd and v['phase']=='OPEN']
   if not points:execstop='NO_VERIFIED_OPEN_BEFORE_SOURCE_STOP';break
   z=f.loc[pd.Timestamp(xd)];xp=points[0]
   # Original model has one stock-specific dated ST directional gate. No new general limit rule.
   if sid=='002602.SZ' and xd>='2024-11-08':
    prior=f[f.index<pd.Timestamp(xd)];prior=prior[prior.raw_close.gt(0)&prior.observed_bar.eq(True)&prior.price_eligible.eq(True)];ref=dec(prior.iloc[-1].raw_close)
    if (sid,xd) in cashterms:ref-=dec(cashterms[sid,xd]['d_ref'])
    lo=(ref*D('.95')).quantize(D('.01'),rounding=ROUND_HALF_UP)
    if len({dec(z[c]) for c in ['raw_open','raw_high','raw_low','raw_close']})==1 and dec(z.raw_open)==lo:continue
   exe=xp;break
  r['diagnostic_exit_OPEN']=exe;r['diagnostic_exit_stop']=execstop
  if exe:
   xd=exe['day'];xraw=exe['raw'];xf=exe['factor'];xp=xraw*D('.9995');xq,xsq,xhs=q_at(rid,lid,xd,'OPEN')
   remaining_sales=[x for x in sells if x['day']>=xd];remaining=sum(x['qty'] for x in remaining_sales)+r['actual_seed_final_qty'];assert remaining==xsq,(rid,remaining,xsq)
   baseline_remaining_proceeds=sum((dec(x['cash_delta']) for x in remaining_sales),Z)+sum((dec(h['market_value']) for h in endhs if h['lot_id']==lid),Z)
   # Baseline pro-rata fee allocation versus an isolated remaining-seed sale is explicit; ADD holdings unchanged only as descriptive reference.
   diagproceeds=xsq*xp-fee(sid,xd,xsq,xp); future_seed_div=Z
   for e in eq:
    if e.get('round_id')==rid and e['event']=='ACCRUE_NET80':
     term=cashterms.get((sid,e['day']))
     if term and term['record_date']>=xd:
      qq=q_at(rid,lid,term['record_date'],'CLOSE')[1];future_seed_div+=D(qq)*dec(term['d_cash'])*D('.8')
   baseline_remaining_proceeds+=future_seed_div
   delta=diagproceeds-baseline_remaining_proceeds if xsq else Z
   exits=[x for x in remaining_sales if x['qty']];lastseed=max((x['day'] for x in exits),default=None) if not r['actual_seed_final_qty'] else None
   r.update(diagnostic_exit_seed_remaining_qty=xsq,diagnostic_exit_round_qty=xq,diagnostic_exit_raw_with_slip=xp,diagnostic_exit_seed_fee=fee(sid,xd,xsq,xp),diagnostic_exit_seed_proceeds=diagproceeds,actual_remaining_seed_proceeds_and_future_dividend=baseline_remaining_proceeds,remaining_seed_proceeds_delta=delta,remaining_seed_comparison_has_ADD=bool(rd['add_count']),seed_sold_before_diagnostic_qty=s0['qty']-xsq,seed_actual_last_exit=lastseed,diagnostic_earlier_sessions=dix[lastseed]-dix[xd] if lastseed else None,CP_floor_to_execution_gap_raw=floor/xf-xraw,CP_floor_to_execution_gap_seed_amount=(floor/xf-xraw)*xsq,CP_floor_to_execution_adverse_gap_seed_amount=max(Z,floor/xf-xraw)*xsq,close_to_next_OPEN_gap_raw=(first['adj']/xf-xraw) if phase=='CLOSE' else None,entry_CP_failure_then_original_continues=bool(xsq and ((lastseed and lastseed>xd) or r['actual_seed_final_qty'])))
   # Price-only fixed original share-count reference, not account PnL. Factor changes are handled by same adjusted scale.
   lastmark=f.loc[pd.Timestamp(END)] if r['actual_seed_final_qty'] else None
   orig_weighted_adj=sum((x['qty']*dec(x['price'])*dec(f.loc[pd.Timestamp(x['day'])].adjustment_factor) for x in sells),Z)
   if lastmark is not None:orig_weighted_adj+=r['actual_seed_final_qty']*dec(lastmark.raw_close)*dec(lastmark.adjustment_factor)
   orig_weighted_adj/=s0['qty']
   r['fixed_original_seed_price_spread_adjusted_share_units']=D(s0['qty'])*(xp*xf-orig_weighted_adj)/initialfac
   path_end=rd['exit_day'] or END; before=[v for v in daily if (v['day'],v['phase']=='CLOSE')<=(path_end,False)];after=[v for v in daily if (v['day'],v['phase']=='CLOSE')>=(xd,False) and (v['day'],v['phase']=='CLOSE')<=(path_end,False)]
   if before:
    peak=max(before,key=lambda v:v['adj']);r['actual_round_window_MFE_OPEN_CLOSE_pct']=100*(peak['adj']/(entryraw*initialfac)-1);r['actual_round_window_MFE_point']=peak
   if after:
    peak=max(after,key=lambda v:v['adj']);r['post_diagnostic_max_rebound_until_actual_round_exit_pct']=100*(peak['adj']/exe['adj']-1);r['post_diagnostic_max_rebound_point']=peak
   allafter=[v for v in daily if (v['day'],v['phase']=='CLOSE')>=(xd,False)]
   if allafter:
    peak=max(allafter,key=lambda v:v['adj']);r['post_diagnostic_max_rebound_to_cutoff_pct']=100*(peak['adj']/exe['adj']-1);r['post_diagnostic_max_rebound_to_cutoff_point']=peak
 # Diagnose the predefined max(I_t, fixed entryCP) on the observed ORIGINAL path only.
 first_i=None;first_max=None;held_min=None
 for v in daily:
  if v['day']==entryday and v['phase']=='OPEN':continue
  rq0,sq0,hh=q_at(rid,lid,v['day'],v['phase']);seedh=next((h for h in hh if h['lot_id']==lid),None)
  ip=dec(seedh['protection_signal']) if seedh else None;mx=max(ip,floor) if ip is not None else None
  info=dict(round_id=rid,sid=sid,seed_lot_id=lid,**v,actual_seed_qty=sq0,actual_round_qty=rq0,actual_I=ip,fixed_entryCP=floor,reference_max_I_entryCP=mx,CP_breached=v['adj']<=floor,I_breached=v['adj']<=ip if ip is not None else None,reference_max_breached=v['adj']<=mx if mx is not None else None)
  observations.append(info)
  if sq0:
   held_min=v['adj'] if held_min is None else min(held_min,v['adj'])
   if first_i is None and ip is not None and v['adj']<=ip:first_i=info
   if first_max is None and mx is not None and v['adj']<=mx:first_max=info
 r.update(entry_cp_raw=floor/initialfac,entry_I_raw=entryi/initialfac,original_I_first_price_breach_while_seed_held=first_i,reference_max_I_entryCP_first_breach_while_seed_held=first_max,minimum_observed_adjusted_price_while_seed_held=held_min,source_stop_after_actual_seed_exit=bool(problem and sells and not r['actual_seed_final_qty'] and problem['day']>sells[-1]['day']))
 # Check every stored original round net for this round independently from cashflows, entitlements and dated fees.
 for dd in sorted({h['day'] for h in holds if h['round_id']==rid}):
  hh=hmap[rid,dd];qq=sum(h['qty'] for h in hh);pp=dec(hh[0]['raw_mark'])*D('.9995');cf=sum((dec(o['cash_delta']) for o in oseq if o['day']<=dd),Z);div=sum((dec(e['receivable_delta']) for e in eq if e.get('round_id')==rid and e['event']=='ACCRUE_NET80' and e['day']<=dd),Z);nn=cf+div+qq*pp-fee(sid,dd,qq,pp)
  for h in hh:assert abs(nn-dec(capmap[h['lot_id'],dd]['round_net']))<D('1e-15'),('original_round_net_mismatch',rid,dd)
 r['status']='BREACHED_WHILE_SEED_HELD' if first and r.get('breach_seed_qty',0)>0 else 'BREACHED_AFTER_SEED_GONE' if first else 'UNKNOWN_BEFORE_BREACH' if problem else 'NO_BREACH_TO_CUTOFF'
 r['sensitivity_scope']='Fixed entry receipt only; max(actual I, entryCP) is reference, not original protection or new account simulation.'
 rows.append(r)
 for o in oseq:paths.append(dict(o))
 print(json.dumps(dict(progress=len(rows),sid=sid,seed=entryday,status=r['status'],delta=str(r.get('remaining_seed_proceeds_delta')),pnl=rd['marked_net_pnl']),ensure_ascii=False),flush=True) if len(rows)%50==0 else None
save('LOT_DIAGNOSTICS',rows);save('ACTUAL_ORDER_PATHS',paths);save('OBSERVED_PRICE_AND_ORIGINAL_I_PATH',observations)
def summary(rs):
 breached=[r for r in rs if r['status']=='BREACHED_WHILE_SEED_HELD'];continued=[r for r in rs if r.get('entry_CP_failure_then_original_continues')];comp=[r for r in rs if r.get('diagnostic_exit_seed_remaining_qty',0)>0]
 return dict(rounds=len(rs),actual_round_positive_count=sum(dec(r['actual_round_pnl'])>0 for r in rs),actual_round_negative_count=sum(dec(r['actual_round_pnl'])<0 for r in rs),unknown_only_after_seed_exit=sum(r['status']=='UNKNOWN_BEFORE_BREACH' and r['source_stop_after_actual_seed_exit'] for r in rs),statuses=dict(Counter(r['status'] for r in rs)),entry_CP_above_I=sum(r['CP_above_I'] for r in rs),actual_round_pnl=sum((dec(r['actual_round_pnl']) for r in rs),Z),actual_seed_pnl=sum((dec(r['actual_seed_net_allocated_fees_and_dividend']) for r in rs),Z),breached_while_seed_held=len(breached),breach_above_actual_I=sum(r.get('breach_still_above_I') is True for r in breached),breach_while_I_stock_sector_all_true=sum(r.get('breach_known_I_target')==1 and r.get('breach_known_stock_state')==1 and r.get('breach_known_sector_state')==1 for r in breached),original_continues_after_diagnostic_exit=len(continued),original_continues_round_losers=sum(dec(r['actual_round_pnl'])<0 for r in continued),original_continues_round_winners=sum(dec(r['actual_round_pnl'])>0 for r in continued),comparable_remaining_seed=len(comp),remaining_seed_positive_delta_count=sum(r['remaining_seed_proceeds_delta']>0 for r in comp),remaining_seed_negative_delta_count=sum(r['remaining_seed_proceeds_delta']<0 for r in comp),remaining_seed_delta_sum=sum((r['remaining_seed_proceeds_delta'] for r in comp),Z),remaining_seed_delta_positive=sum((max(Z,r['remaining_seed_proceeds_delta']) for r in comp),Z),remaining_seed_delta_negative=sum((min(Z,r['remaining_seed_proceeds_delta']) for r in comp),Z),gap_adverse_amount_sum=sum((r['CP_floor_to_execution_adverse_gap_seed_amount'] for r in comp),Z),comparison_with_ADD=sum(r['remaining_seed_comparison_has_ADD'] for r in comp),comparison_after_partial_seed=sum(r['seed_sold_before_diagnostic_qty']>0 for r in comp))
cohorts=[('ALL_CP_ROUTE',rows),('LATE_SEED_AFTER_NOV6',[r for r in rows if r['seed_day']>'2024-11-06']),('SEPT24_OPEN',[r for r in rows if r['seed_day']=='2024-09-24']),('SEPT23_30_OPEN',[r for r in rows if '2024-09-23'<=r['seed_day']<='2024-09-30']),('PV_OCT24_OPEN',[r for r in rows if r['sector51']=='光伏风电设备' and r['seed_day']=='2024-10-24']),('PV_OCT23_29_OPEN',[r for r in rows if r['sector51']=='光伏风电设备' and '2024-10-23'<=r['seed_day']<='2024-10-29'])]
sums=[dict(cohort=n,**summary(rs)) for n,rs in cohorts];save('COHORT_SUMMARY',sums)
for n,rs in cohorts:
 for closed in [True,False]:sums.append(dict(cohort=n+'_CLOSED' if closed else n+'_OPEN',**summary([r for r in rs if (not r['actual_round_final_qty'])==closed])))
save('COHORT_SUMMARY',sums)
ss=[dict(sector51=s,**summary([r for r in rows if r['sector51']==s])) for s in sorted({r['sector51'] for r in rows})];save('SECTOR_SUMMARY',ss)
qa=dict(result='PASS_DESCRIPTIVE_SAVED_PATH',actual_CP_route_seeds=319,source_files_read=len(hashes),sourcehashes_verified=True,source_stops=[dict(round_id=r['round_id'],**r['source_stop']) for r in rows if r['source_stop']],all_orders_allocated=True,original_round_net_crosschecked_against_capital_lots=True,observation_rows=len(observations),unknown_before_original_seed_exit=sum(bool(r['source_stop']) and not r['source_stop_after_actual_seed_exit'] for r in rows),no_future_after=END,strategy_imported=False,Data_instantiated=False,history_replayed=False,new_rule_implemented=False,network_used=False,fees='Original dated schedule, separate remaining-seed hypothetical fee versus actual proportional lot fee allocation',scope='Actual CP route MATURE only, original frozen entry slot; later CP receipts and ADD do not replace diagnostic object.')
save('QA',qa);save('SOURCE_HASHES',hashes);print(json.dumps(sums[:6],ensure_ascii=False,default=str),flush=True)
