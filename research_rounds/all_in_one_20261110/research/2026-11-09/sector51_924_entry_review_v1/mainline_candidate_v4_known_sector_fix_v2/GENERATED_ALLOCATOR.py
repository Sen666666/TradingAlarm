def alloc_open(self,d,pending):
  self.begin_open(d,pending);self._ref_spent={};self.info_open(d);nav=self.nav(d,'raw_open');sv={s:self.qvalue(a,d,'raw_open') for s,a in self.active.items()};reqs=[]
  for a in self.active.values():
   if a.get('plan'):reqs.append(a['plan'])
   a['plan']=None
  reqs=self.request_key_groups(reqs+pending);released=self.execute_transfers(d,reqs,nav,sv);cash=self.cash;reserved=[];main_filled=ZERO
  for rank,r in enumerate(reqs):
   s=r['sid'];x=self.noncash(r,d,'raw_open',nav,sv);q=x['q'];p=x['p'];caps=dict(x['caps'],cash_reserve=max(ZERO,cash-D('.10')*nav),reference_cap=self.reference_cap(r,sv),event_cap=self.event_cap(r));reason=x['reason'];a=self.active.get(s);qr=self.d.getmeta(s,d)[0]
   rawq=r.get('econ_q',qr.buy_minimum) if r['kind']=='SEED' else q;rawcost=rawq*p+self.d.fee(s,d,rawq,p,'buy') if rawq else ZERO
   if reason=='PASS':
    if r['kind']=='SEED':
     if rawcost>min(caps.values()):reason='MIN_LOT_CAPITAL_REJECT:'+min(caps,key=caps.get)
    else:
     q=self.d.size(s,d,p,min(caps.values()),min(q,r['planned_q'],r.get('_ref_q',q)))
     if not q:reason='ADD_NO_LEGAL_Q:'+min(caps,key=caps.get)
   violated=sorted(k for k,v in caps.items() if rawcost>v)
   row=dict(day=day(d),phase='OPEN',sid=s,round_id=a['id'] if a else None,event=r['kind'],signal_day=r['signal_day'],plan_day=r['plan_day'],decision=reason,allocation_rank=rank+1,M=r['M'],E=str(r['E']),M_streak=r['M_streak'],cp_id=r.get('cp_id'),close_net=r.get('close_net'),open_net=str(x['net']) if x['net'] is not None else None,planned_q=r['planned_q'],executed_q=q if reason=='PASS' else 0,violated_caps=violated,reference_close_q=r.get('_ref_q'),reference_close_rank=r.get('_ref_rank'),allocation_phase=r.get('allocation_phase'),event_id=r.get('event_id'),frozen_econ_q=r.get('econ_q'),**{k:str(v) for k,v in caps.items()});self.candidates.append(row);self.request_details.append(row)
   if r['kind']=='SEED':
    t=self.live_tickets().get(s)
    if t:
     rules.retry_open_outcome(t,filled=reason=='PASS',structural_pass=x['structural'],all_in_cost=rawcost,caps=caps);self.pause_unknown_ticket(t,r,reason);self.ticket_event(t,d,'OPEN_OUTCOME',decision=reason,violated_caps=violated)
    elif reason!='PASS':
     t=rules.ticket_from_seed(r,rawcost,caps,structural_pass=x['structural'])
     if t:
      t['current_factor']=dec(self.d.z(s,d)['adjustment_factor']);t['last_verified_day']=day(d);self.tickets[s]=t;self.pause_unknown_ticket(t,r,reason);self.ticket_event(t,d,'CAPITAL_REJECT_RETAINED',decision=reason,violated_caps=violated)
   if reason!='PASS':continue
   cost=q*p+self.d.fee(s,d,q,p,'buy');cash-=cost;self.reserve_phase_cash(r,cost);sv[s]=sv.get(s,ZERO)+cost;reserved.append((r,q,p,x['net'],cost));main_filled+=cost if r['M']==1 else ZERO
  for r,q,p,net,cost in reserved:
   s=r['sid']
   if r['kind']=='SEED':
    self.seq[s]+=1;rid=f'{s}|{self.seq[s]}|{r["signal_day"]}';a=dict(id=rid,sid=s,signal_day=r['signal_day'],birth_type=r['birth_type'],nav0=r['nav0'],seed_day=day(d),cashflow=ZERO,dividend=ZERO,fees=ZERO,lots=[],ifloor=r['ifloor'],factor=dec(self.d.z(s,d)['adjustment_factor']),origin=r['origin'],exit=None,plan=None,cp=None,add_count=0,confirmed_history=False);self.active[s]=a;self.archive[rid]=a
   else:a=self.active[s]
   cp=a['cp'] if r['kind']=='ADD' else None;fl=max(a['ifloor'],cp['floor']) if cp else a['ifloor'];lid=f'{a["id"]}|{len(self.orders)+1}'
   if cp:
    stop=fl/a['factor']*(1-SLIP);stop_net=q*stop-self.d.fee(s,d,q,stop,'sell');loss=cost-stop_net
    self.floor_risk.append(dict(day=day(d),sid=s,round_id=a['id'],cp_id=cp['id'],pre_add_close_net=r.get('close_net'),pre_add_open_net=str(net),add_qty=q,buy_all_in=str(cost),known_protection_signal=str(fl),hypothetical_raw_sell=str(stop),incremental_known_floor_loss=str(loss),not_profit_covered=loss>net,not_stop_execution_guarantee=True))
   a['lots'].append(dict(id=lid,kind=r['kind'],q=q,bought=day(d),floor=fl,cp_id=cp['id'] if cp else None));self.order(a,d,'BUY_'+r['kind'],q,p,'MAINLINE_CP_ADD' if cp else 'NEW_OR_RETAINED_A_B_MIN_UNIT',signal_day=r['signal_day'],lot_id=lid,cp_id=cp['id'] if cp else None,close_net=r.get('close_net'),open_net=str(net) if net is not None else None,frozen_attempt_NAV=str(a['nav0']),all_in_cost=str(cost),M=r['M'],E=str(r['E']))
   if cp:
    assert a.get('confirmed_history'), 'FILLED_ADD_MUST_INFORMATION_CONFIRM';cp['consumed']=True;a['add_count']+=1;self.eventlog(a,d,'OPEN','CONSUMED_ON_FILL',cp);a['cp']=None
  assert self.cash==cash
  self.transfers.append(dict(day=day(d),phase='OPEN',event='RECEIVER_FUNDING',released_cash=str(released),M_actual_buy_cost=str(main_filled),cash_after_all_buys=str(self.cash),cash_above_frozen_reserve=str(self.cash-D('.10')*nav)))
  sec={k:ZERO for k in self.d.sector_ids}
  for s,a in self.active.items():sec[self.d.sid_sector[s]]+=self.qvalue(a,d,'raw_open')
  actual_nav=self.nav(d,'raw_open')
  for k,v in sec.items():self.open_exposure.append(dict(day=day(d),sector51=k,market_value=str(v),NAV=str(actual_nav),weight_pct=str(100*v/actual_nav),frozen_allocation_NAV=str(nav)))
