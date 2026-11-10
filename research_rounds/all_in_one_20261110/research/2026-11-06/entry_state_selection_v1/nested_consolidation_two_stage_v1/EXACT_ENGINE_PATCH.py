def run_stock(sid,window,start,finish,arm,p,f,featuremap,phase_mode=False):
 root=None;coverage_row=dict(sid=sid,window=window,arm=arm,known_signal_days=0,unknown_signal_days=0,suppressed_signals=0,stopped_unknown=False)
 for k in range(cal.get_indexer([cal[cal>=pd.Timestamp(start)][0]])[0],len(cal)):
  d=cal[k]
  if d>END:break
  z=p.iloc[k];inside=d<=pd.Timestamp(finish);exited=False
  if root is None and not inside:break
  if root is not None:
   out=root['out'];bad=open_check(z,root)
   if bad:
    out.update(status='UNKNOWN_'+bad,unknown_day=d);coverage_row['stopped_unknown']=True;break
   if root['exit_pending']:
    if root['q']:
     assert k>root['entry_k'],'T_PLUS_1_VIOLATION'
     try:qr,fs,par=getmeta(sid,d)
     except (RuleUnavailable,KeyError,ValueError) as ex:out.update(status='UNKNOWN_EXIT_DATED_RULE',unknown_day=d,error=str(ex));coverage_row['stopped_unknown']=True;break
     if qr.sell_floor(root['q'],root['q'])!=root['q']:out.update(status='UNKNOWN_EXIT_LOT',unknown_day=d);break
     px=D(str(z.raw_open))*(1-SLIP);sf=fee(root['q'],px,fs,'sell',par);net=D(root['q'])*px-sf-root['spent']
     out.update(status='COMPLETE',exit_day=d,exit_price=float(px),exit_fee=float(sf),net_pnl=float(net),return_on_buy_cash=float(net/root['spent']),outcome='W' if net>0 else 'L' if net<0 else 'B',final_S=root['S'])
    root=None;exited=True
   elif root['pending']:
    root['pending']=False;fl=D(str(root['S']));px=D(str(z.raw_open))*(1+SLIP);prior=p.iloc[k-20:k]
    if z.raw_open*root['factor']<=root['S_native']:out.update(status='NO_BUY_OPEN_BELOW_S')
    elif len(prior)!=20 or not (prior.raw_volume.gt(0)&np.isfinite(prior.raw_volume)&prior.volume_eligible.eq(True)).all():out.update(status='UNKNOWN_ENTRY_CAPACITY')
    else:
     capacity=int(prior.raw_volume.mean()*.01)
     try:q,bf,risk,fs,par=size(sid,d,px,fl,INIT,NAV*D('.0025'),capacity);qr,_,_=getmeta(sid,d)
     except (RuleUnavailable,KeyError,ValueError) as ex:out.update(status='UNKNOWN_ENTRY_DATED_RULE',error=str(ex));q=None
     if q is not None:
      out.update(prior20_capacity=capacity,quantity=q,entry_fee=float(bf),planned_risk=float(risk),entry_price=float(px))
      if not q:out.update(status='NO_BUY_MINIMUM_LOT')
      else:
       assert qr.buy_floor(q)==q and q<=capacity and D(q)*px+bf<=INIT and risk<=NAV*D('.0025')
       root.update(q=q,spent=D(q)*px+bf,entry_k=k);out.update(status='OPEN',accepted=True,entry_day=d,buy_cash=float(root['spent']))
  if root is not None:
   out=root['out'];bad=valid_prices(p.iloc[k:k+1])
   if bad:out.update(status='UNKNOWN_CLOSE_'+bad,unknown_day=d);coverage_row['stopped_unknown']=True;break
   old=root['S'];old_native=root['S_native'];phase_before=root['phase'];structural_failed=bool(z.close<=old_native);probe_failed=bool(phase_mode and root['phase']=='PROBE' and z.close<=root['U1_native']);failed=structural_failed or probe_failed
   lift=None;err=None
   if failed:
    out.update(failure_close=d,failure_close_price=float(z.raw_close),failure_S=old,failure_S_native=old_native,failure_reason='STRUCTURAL_S' if structural_failed else 'PROBE_LOCAL_U',failure_trigger_native=old_native if structural_failed else root['U1_native'],failure_phase=root['phase'])
    if root['q']:root['exit_pending']=True
    else:root=None
   else:
    if phase_mode and root['phase']=='PROBE' and z.close>root['U0_native']:
     root['phase']='TREND';out.update(promotion_day=d,promotion_C=float(z.raw_close))
    lift,err=e0_floor(f,p,d)
    if err:out.update(status='UNKNOWN_'+err,unknown_day=d);coverage_row['stopped_unknown']=True;break
    if lift is not None:
     root['S_native']=max(old_native,lift);root['S']=root['S_native']/root['factor']
   paths.append(dict(sid=sid,window=window,arm=arm,root_day=out['birth_day'],day=d,raw_close=float(z.raw_close),native_close=float(z.close),old_S_native=old_native,new_S_native=root['S_native'] if root is not None else None,old_S=old,new_S=root['S'] if root is not None else None,failed=bool(failed),e0_lift=(lift/float(z.adjustment_factor) if lift is not None else None),e0_lift_native=lift,quantity=out.get('quantity',0),phase_before=phase_before,phase_after=root['phase'] if root is not None else None,structural_failed=structural_failed,probe_failed=probe_failed))
   if inside:
    ft=featuremap[k]
    if (ft['control'] or ft['local']) if arm=='UNION' else ft.get(arm.lower(),False):coverage_row['suppressed_signals']+=1
   continue # Never fail and rebirth on same close, even a no-buy root.
  if not inside:continue
  ft=featuremap[k];known=ft['price_known'] if arm=='CONTROL' else (ft['price_known'] and (ft['control'] or ft['local_known'])) if arm=='UNION' else ft['local_known']
  coverage_row['known_signal_days' if known else 'unknown_signal_days']+=1
  qualifies=(ft['control'] or ft['local']) if arm=='UNION' else ft.get(arm.lower(),False)
  if not known or not qualifies:continue
  origin='CONTROL' if arm=='CONTROL' or (arm=='UNION' and ft['control']) else 'LOCAL'
  floor=ft['control_floor'] if origin=='CONTROL' else ft['l1'];floor_native=ft['control_floor_native'] if origin=='CONTROL' else ft['l1_native']
  out=dict(sid=sid,window=window,arm=arm,origin=origin,birth_day=d,birth_S=floor,birth_S_native=floor_native,birth_C=float(z.raw_close),old20_U=ft['u0'] if ft['u0']>=ft['u1'] else ft['u1'],local_U=ft['u1'],incremental_early=bool(origin=='LOCAL' and ft['early']),accepted=False,status='PENDING',historical_fill_certainty='UNKNOWN',account=False)
  out.update(phase_mode=phase_mode,U0_native=float(p.iloc[k-20:k-10].high.max()),U1_native=float(p.iloc[k-10:k].high.max()));rounds.append(out);root=dict(out=out,S=floor,S_native=floor_native,identity=identity(z),factor=float(z.adjustment_factor),pending=True,exit_pending=False,q=0,phase='PROBE' if phase_mode and origin=='LOCAL' else 'TREND',U0_native=out['U0_native'],U1_native=out['U1_native'])
 if root is not None and root['out']['status']=='OPEN':root['out'].update(status='UNRESOLVED_END',last_day=min(END,cal[-1]))
 coverage.append(coverage_row)