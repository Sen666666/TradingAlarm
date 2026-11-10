def opening(self,a,at):
 C.activate(a)
 for sid in sorted(a.exits):
  win=self.market.window(sid,at,'sell',1)
  if win:a.fill_exit(sid,win)
 a.settle_due(at);a.sync(at);funded=[];done=set()
 capture_preopen(self,a,at)
 for i in sorted([i for i in a.pending if i['clock'].earliest_execution_at==at],key=lambda x:(x['rank'],x['role']!='core')):
  sid=i['sid']
  if sid in done or sid in a.buys or sid in a.exits:continue
  raw=self.market.raw[sid];day=pd.Timestamp(at.date())
  if day not in raw.index or not np.isfinite(raw.loc[day].open) or raw.loc[day].open<=0:self.funding.append(dict(account=a.label,at=at,sid=sid,role=i['role'],result='missing_open'));continue
  x,why=LR.preview(i,D(str(raw.loc[day].open)),self.facts.factor(sid,at),self.market.quantity(sid,at),self.market.fees(sid,at))
  if why:self.funding.append(dict(account=a.label,at=at,sid=sid,role=i['role'],result=why));continue
  x['known_open']=D(str(raw.loc[day].open))
  capture_pre(self,a,i,x,at)
  route,why=self.route(a,i,x,at)
  capture_post(self,a,i,x,at,route,why)
  if why:self.funding.append(dict(account=a.label,at=at,sid=sid,role=i['role'],result=why));continue
  q,pool=route;a.reserve_quantity(i,q,x['price'],x['schedule'],at);a.sync(at);done.add(sid);funded.append((sid,i,x,q));self.funding.append(dict(account=a.label,at=at,sid=sid,role=i['role'],result='reserved',pool=pool,shares=q,price=x['price'],CP1_id=i.get('CP1_id')))
 # Execution proxies are consulted only after all H1-ranked funding decisions.
 for sid,i,x,q in funded:
  win=self.market.window(sid,at,'buy',1)
  if win:assert win.execution_price==x['price'];a.fill_buy(sid,win)
  else:self.funding.append(dict(account=a.label,at=at,sid=sid,role=i['role'],result='no_execution_window_after_reservation'))
 a.settle_due(at);a.sync(at);a.minimum_available=min(a.minimum_available,a.available);a.check()
