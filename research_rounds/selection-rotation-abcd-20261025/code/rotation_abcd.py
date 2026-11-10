"""One causal, buffered portfolio replacement policy; no fill/cash invention."""
from decimal import Decimal
import math
import selection_abcd as select

def rank_list(scores):return sorted(scores,key=lambda k:(-round(float(scores[k]),12),k))

class Controller:
 def __init__(self):self.banned_stocks=set();self.banned_sectors=set();self.streaks={};self.last_i=None;self.log=[]
 def advance(self,account,inputs,clock,mode,quotes,marks,fx):
  stocks,sectors,board=select.facts(inputs,clock,mode);dual=mode=='D';day=clock.session_date.isoformat();i=board.i
  if self.last_i is not None and i<=self.last_i:raise ValueError('Rotation advances only once per account/date')
  consecutive=self.last_i is not None and i==self.last_i+1;self.last_i=i
  sec_scores={};stock_scores={};sec_status={};stock_status={};members={}
  for sid,s in sectors.items():
   up=s.trend_up.read(clock);score=s.rank.read(clock) if s.rank else None;gate=board.allowed(sid) if dual else True
   status=None if up is None or score is None or gate is None else bool(up and gate)
   sec_status[sid]=status
   if status:sec_scores[sid]=score
  for sid,s in stocks.items():
   sec=s.sector_id.read(clock);trend=s.trend_up.read(clock);ready=s.common_ready.read(clock);score=s.rank.read(clock) if s.rank else None;gate=board.allowed(sid) if dual else True
   status=None if trend is None or ready is None or score is None or gate is None else bool(trend and ready and gate)
   stock_status[sid]=status
   if status:stock_scores[sid]=score;members.setdefault(sec,[]).append(sid)
  order=rank_list(sec_scores);sr={s:n+1 for n,s in enumerate(order)};so={}
  for sec,ids in members.items():
   seq=rank_list({sid:stock_scores[sid] for sid in ids});so.update({sid:n+1 for n,sid in enumerate(seq)})
  # The rankings include continuing holdings even without a new buy event.
  fresh=select.BUY.get(day,set());eligible=[]
  for sid in fresh:
   if sid in stocks and select.eligibility(stocks[sid],sectors,clock,'S0').q is True:eligible.append(sid)
  for sid in list(self.banned_stocks):
   if sid in account.positions or sid in account.exits or sid in account.buys:continue
   if so.get(sid,10**9)<=2 and sid in eligible:self.banned_stocks.remove(sid)
  for sec in list(self.banned_sectors):
   if any(p.sector_id==sec for p in account.positions.values()) or any(p.quote.sector_id==sec for p in account.exits.values()) or any(p.quote.sector_id==sec for p in account.buys.values()):continue
   if sr.get(sec,10**9)<=3 and any(stocks[s].sector_id.read(clock)==sec for s in eligible):self.banned_sectors.remove(sec)
  # Fresh candidates are then evaluated with the current re-entry bans.
  eligible=[s for s in eligible if s not in self.banned_stocks and stocks[s].sector_id.read(clock) not in self.banned_sectors]
  occupied=account.occupancy(clock.decision_at);held={s:p for s,p in account.positions.items() if p.shares};heldsec={stocks[s].sector_id.read(clock) for s in held if s in stocks};occupied_ids={o.security_id for o in occupied};occupied_sec={o.sector_id for o in occupied}
  bal=account.balance(clock.decision_at,marks,fx);cap=Decimal('.15')*bal['nav'];affordable={}
  for sid in eligible:
   q=quotes.get(sid)
   if q:
    cost=q.read_price(clock.decision_at)*q.fx.read(clock.decision_at)*q.quantity.buy_minimum
    affordable[sid]=cost<=cap
  # Do not sell for a challenger whose minimum original quantity cannot fit the
  # unchanged initial allocation, even if all sale proceeds became available.
  eligible=[s for s in eligible if affordable.get(s,False)]
  candidates=[]
  def meaningful(new,old,is_sector):
   statuses=sec_status if is_sector else stock_status
   if statuses.get(old) is False:return True
   if not dual:
    values=sec_scores if is_sector else stock_scores
    return new in values and old in values and values[new]>values[old]+1e-12
   return any(math.isfinite(board.get(new,k)) and math.isfinite(board.get(old,k)) and board.get(new,k)>board.get(old,k)+1e-12 for k in ['short','long'])
  fresh_sec={stocks[s].sector_id.read(clock) for s in eligible}
  if len(occupied_sec)>=3:
   challenges=[s for s in order[:3] if s not in occupied_sec and s not in self.banned_sectors]
   victims=[s for s in heldsec if sec_status.get(s) is not None]
   if challenges and victims:
    new=challenges[0];old=max(victims,key=lambda s:(sr.get(s,len(order)+1),s));gap=sr.get(old,len(order)+1)-sr[new]
    if gap>=2 and meaningful(new,old,True):candidates.append(dict(kind='sector',incoming=new,outgoing=old,gap=gap,rank_in=sr[new],rank_out=sr.get(old,len(order)+1),fresh_today=new in fresh_sec))
  for sec in sorted(heldsec):
   owned=[s for s in held if s in stocks and stocks[s].sector_id.read(clock)==sec and stock_status.get(s) is not None]
   if len(owned)<2:continue
   challenges=[s for s in members.get(sec,[]) if so.get(s,10**9)<=2 and s not in occupied_ids and s not in self.banned_stocks]
   if not challenges:continue
   new=min(challenges,key=lambda s:(so[s],s));old=max(owned,key=lambda s:(so.get(s,len(members.get(sec,[]))+1),s));gap=so.get(old,len(members.get(sec,[]))+1)-so[new]
   if gap>=2 and meaningful(new,old,False):candidates.append(dict(kind='stock',incoming=new,outgoing=old,sector=sec,gap=gap,rank_in=so[new],rank_out=so.get(old,len(members.get(sec,[]))+1),fresh_today=new in eligible))
  active={}
  for p in candidates:
   key=(p['kind'],p['incoming'],p['outgoing']);active[key]=(self.streaks.get(key,0)+1) if consecutive else 1;p['confirmations']=active[key]
  self.streaks=active
  own_exit=bool(account.exits) or any(s in stocks and stocks[s].trend_up.read(clock) is False for s in held)
  plan=None
  if not own_exit:
   allowed=[p for p in candidates if p['confirmations']>=3 and p['fresh_today']]
   if allowed:plan=sorted(allowed,key=lambda p:(p['kind']!='sector',p['rank_in'],-p['gap'],p['incoming'],p['outgoing']))[0]
  if plan:
   outgoing=[s for s in held if stocks[s].sector_id.read(clock)==plan['outgoing']] if plan['kind']=='sector' else [plan['outgoing']]
   if all(s in quotes for s in outgoing):
    if plan['kind']=='sector':
     self.banned_sectors.add(plan['outgoing'])
     for s in list(account.buys):
      if account.buys[s].quote.sector_id==plan['outgoing']:account.cancel_buy(s)
    else:self.banned_stocks.add(plan['outgoing'])
    for sid in outgoing:account.request_exit(quotes[sid],clock)
    event=dict(**{k:v for k,v in plan.items() if k!='kind'},kind='portfolio_rotation_request',rotation_kind=plan['kind'],at=clock.decision_at,outgoing_stocks=outgoing,initial_cap_cny=str(cap),no_pre_spent_proceeds=True)
    account.audit_log.append(event);self.log.append(event)
   else:plan=None
  return dict(plan=plan,observations=candidates,waiting_for_own_exit=own_exit,banned_stocks=sorted(self.banned_stocks),banned_sectors=sorted(self.banned_sectors),lot_unaffordable_fresh_candidates=sum(not v for v in affordable.values()))
