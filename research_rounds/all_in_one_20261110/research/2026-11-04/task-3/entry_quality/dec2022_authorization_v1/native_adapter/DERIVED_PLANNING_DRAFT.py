def planning(self,at):
 clock,stocks,sectors=self.facts.packet(at,'I');sd={s.security_id:s for s in stocks};ss={s.sector_id:s for s in sectors};buyable=self.market.market_buyable(at);day=pd.Timestamp(at.date());event={};continuing={}
 for sid,s in sd.items():
  row=self.facts.row(sid,at);key=(bool(row.i_target),int(row.segment_id)) if row is not None else (False,-1)
  if self.last_epoch.get(sid)!=key:self.epoch[sid]+=1;self.global_watch.pop(sid,None);self.last_epoch[sid]=key
  ep=(key[1],self.epoch[sid]);event[sid]=BP.A.eligibility(s,ss,clock,'S0');continuing[sid]=BP.A.eligibility(replace(s,buy_allowed=buyable[sid]),ss,clock,'S0')
  if event[sid].q is True:self.global_watch[sid]=ep
 ordered=sorted(sd,key=lambda sid:(-(sd[sid].rank.read(clock) if sd[sid].rank and sd[sid].rank.read(clock) is not None else -1),sid))
 for a in self.accounts.values():
  C.activate(a);a.expire_day_buys(at);a.current_nav=a.balance(at,self.market.marks(at,a.positions))['nav'];M.E.risk_policy.step(a,at,'ACT20_BREAK');a.pending=[]
  for sid in tuple(a.positions):
   row=self.facts.row(sid,at);cp=self.cp[sid].loc[day] if day in self.cp[sid].index else None;quote=self.market.quote(sid,at);assert quote
   if not a.risk_state['on'] or not bool(row.i_target):
    if not bool(row.i_target):
     for x in a.live(sid):
      if x['kind']=='core':a.jmeta[x['id']]['pending_I_exit_reference']=True
    a.sell(sid,clock,quote,[x['id'] for x in a.live(sid)],'ACT_pause' if not a.risk_state['on'] else 'I_structure_exit');continue
   for x in a.live(sid):
    if x['kind']=='core':
     known_floor=self.facts.floor(sid,at,'I')
     if known_floor is not None:a.jmeta[x['id']]['last_core_line']=str(known_floor)
     continue
    if x['kind']!='add' or x['id'] in a.sell_layers.get(sid,set()):continue
    if D(str(row.close))<=x['floor']:a.sell(sid,clock,quote,[x['id']],'CP1_add_protection')
    else:
     floor=self.facts.floor(sid,at,'I')
     if floor is not None:x['floor']=max(x['floor'],floor)
     if cp is not None and bool(cp.receipt):x['floor']=max(x['floor'],D(str(cp.candidate)))
   self._mobile_authorization_exit(a,sid,at,row,clock,quote)
  a.sync(at);self.industry(a,at)
  for rank,sid in enumerate(ordered):
   cpr=self.receipts[sid].get(gidday(at));roles=[];why=[];held=bool(a.quantity(sid));epoch=self.global_watch.get(sid);sector=self.sector_by_sid[sid]
   if event[sid].q is True and not held and a.core_epoch.get(sid)!=epoch:roles.append('core')
   if cpr and continuing[sid].q is True:roles.append('mobile')
   if not a.risk_state['on']:why.append('ACT_paused')
   if sid in a.exits:why.append('exit_pending')
   if sid in a.buys:why.append('buy_pending')
   if event[sid].q is not True and not (cpr and continuing[sid].q is True):why.extend(event[sid].reasons or ['no_fresh_signal_or_Q'])
   self.opportunities.append(dict(account=a.label,day=gidday(at),sid=sid,sector=sector,rank=rank,core_Q=event[sid].q,mobile_Q=continuing[sid].q,CP1_id=cpr['receipt_id'] if cpr else None,roles=roles,held=held,barriers=why))
   if why or not roles:continue
   q=self.market.quote(sid,at);floor=self.facts.floor(sid,at,'I')
   if q is None or floor is None:continue
   for role in roles:
    if role=='mobile' and not self._mobile_role_allowed(a,sid,at,self.facts.row(sid,at),cpr):continue
    fline=max(floor,D(str(self.cp[sid].loc[day,'candidate']))) if role=='mobile' else floor;budget=min(a.current_nav*D('.02'),max(Z,a.current_nav*D('.1')-a.quantity(sid)*q.raw_price));i=dict(sid=sid,clock=clock,quote=q,budget=budget,cap=q.quantity.buy_floor(int(budget/q.raw_price)),weight=1.,group=0,score=sd[sid].rank.read(clock),kind='add' if role=='mobile' else 'core',role=role,floor=fline,epoch=epoch,reason='fresh_CP1_mobile' if role=='mobile' else 'I_early_core',rank=rank,CP1_id=cpr['receipt_id'] if role=='mobile' else None,CP1_trace=cpr if role=='mobile' else None)
    if role=='core':LR.resize_core(i,a.current_nav,self.facts.factor(sid,at))
    if not i.get('size_reject') and i['cap']>0:a.pending.append(i)
    else:self.funding.append(dict(account=a.label,at=at,sid=sid,role=role,result=i.get('size_reject','no_nominal_gap')))
  a.decisions.append(dict(at=at,nav=a.current_nav,on=a.risk_state['on'],intents=[{k:v for k,v in i.items() if k not in ['quote','clock','CP1_trace']} for i in a.pending]));bal=a.sync(at);a.check();self.daily.append(dict(account=a.label,at=at,**bal,on=a.risk_state['on'],positions={s:p.shares for s,p in a.positions.items()},layers=[dict(x,**a.jmeta[x['id']]) for x in a.layers if x['qty']],pending_sells=tuple(a.exits),pending_intents=len(a.pending),counts=dict(a.counts),pool_probe=a.budget.resources('probe'),pool_confirmed=a.budget.resources('confirmed'),shared_loss=a.budget.shared_loss));self.daily_bridge(a,at,bal)
