def fixed_predicate(a,i,x,at,pool):
 b=a.budget;sid=i["sid"];sector=a.sector_by_sid[sid];s=b.sectors[sector];p=float(x["price"]);floor=float(x["floor"])
 pc,pr,_=b.resources(pool);sc,sr,_=b.resources(sector=sector);_,ar,reserve=b.resources();pending_fees=sum(o.qty*o.fee_per_share for o in b.orders.values() if o.status in ['open','cancel_pending']);frac=.02 if pool=='probe' else (.02,.1,.2)[s.level]
 def allowed(q,detail=False):
  fee=float(LR.fees(q,x['price'],x['schedule'],'buy',i['quote'].par_value));nav=b.nav-pending_fees-fee;cap=q*p;risk=q*max(0.,p-floor);fails=[]
  if cap+fee>min(float(a.available-a.current_nav*D('.1')),b.cash-reserve)+1e-9:fails.append('cash_or_original_reserve')
  if pool=='probe' and pc+cap>.10*nav+1e-9:fails.append('pool_capital')
  if pool=='probe' and pr+risk>.005*nav+1e-9:fails.append('probe_risk')
  if sc+cap>frac*nav+1e-9:fails.append('sector_capital')
  if sr+risk>.01*nav+1e-9:fails.append('sector_risk')
  known_open=x.get('known_open',x['price']/(D(1)+LR.SLIP));held_at_open=float(a.quantity(sid))*float(known_open)
  if held_at_open+cap>.10*float(a.current_nav)+1e-9:fails.append('stock_capital')
  return fails if detail else not fails
 return allowed
