from pathlib import Path
p=Path(__file__).parent/'diagnose_saved_path.py';s=p.read_text()
s=s.replace('rows=[]; paths=[];cashrows=[]','rows=[]; paths=[];cashrows=[];observations=[]')
s=s.replace("   if d==entryday and phase=='OPEN':continue\n   raw=", "   raw=")
s=s.replace("   if first is None and adj<=floor:first=", "   if not (d==entryday and phase=='OPEN') and first is None and adj<=floor:first=")
s=s.replace(" r['status']='BREACHED_WHILE_SEED_HELD'", """ # Diagnose the predefined max(I_t, fixed entryCP) on the observed ORIGINAL path only.
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
 r['status']='BREACHED_WHILE_SEED_HELD'""")
s=s.replace("save('LOT_DIAGNOSTICS',rows);save('ACTUAL_ORDER_PATHS',paths)","save('LOT_DIAGNOSTICS',rows);save('ACTUAL_ORDER_PATHS',paths);save('OBSERVED_PRICE_AND_ORIGINAL_I_PATH',observations)")
s=s.replace("return dict(rounds=len(rs),statuses=", "return dict(rounds=len(rs),actual_round_positive_count=sum(dec(r['actual_round_pnl'])>0 for r in rs),actual_round_negative_count=sum(dec(r['actual_round_pnl'])<0 for r in rs),unknown_only_after_seed_exit=sum(r['status']=='UNKNOWN_BEFORE_BREACH' and r['source_stop_after_actual_seed_exit'] for r in rs),statuses=")
s=s.replace("all_orders_allocated=True,no_future_after=", "all_orders_allocated=True,original_round_net_crosschecked_against_capital_lots=True,observation_rows=len(observations),unknown_before_original_seed_exit=sum(bool(r['source_stop']) and not r['source_stop_after_actual_seed_exit'] for r in rows),no_future_after=")
p.write_text(s)
