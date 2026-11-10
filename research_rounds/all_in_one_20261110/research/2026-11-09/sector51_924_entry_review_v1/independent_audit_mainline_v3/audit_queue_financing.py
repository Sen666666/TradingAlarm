"""Independent M3 queue/reference reservation and actual net financing audit; no engine import."""
from pathlib import Path
O=Path(__file__).resolve().parent
source=(O/'audit_confirmation_cp.py').read_text().split('report=dict(')[0]
exec(compile(source,str(O/'audit_confirmation_cp.py'),'exec'),globals())
refs=read(run/'REFERENCE_DAILY.json');rqs=read(run/'REFERENCE_REQUESTS.json');capslots=read(run/'CAPITAL_LOTS.json');refday=byday(refs);rqday=byday(rqs);capday=byday(capslots);fundday=byday(read(run/'FUNDING_REQUESTS.json'));td=byday(read(run/'TRANSFERS.json'));secday={(x['day'],x['sector51']):x for x in sector_daily};bylot={x['lot_id']:x for x in orders if x['side'].startswith('BUY')};summary=[]
for s in {r['sid'] for r in rqs}-set(raw):raw[s]=pd.read_parquet(next(p for p in manifest[s]['source_sha256'] if p.endswith('/signal.parquet')))
def floor_sell(q,held,qr):
 q=min(max(0,int(q)),held)
 return held if q==held and qr.get('allow_full_exit_odd',False) else q//qr['sell_step']*qr['sell_step']
def cover(s,dt,p,gap,maximum,held):
 qr=version(rules['quantity_versions'][s],dt)['rule'];maximum=floor_sell(maximum,held,qr)
 if not maximum:return 0
 q=floor_sell(min(maximum,max(1,int(gap/p))),held,qr)
 if q==0:q=floor_sell(min(maximum,qr['sell_step']),held,qr)
 while q<maximum and q*p-fee(s,dt,q,p,'sell')<gap:
  q0=floor_sell(min(maximum,q+qr['sell_step']),held,qr);q=q0 if q0>q else maximum
 return q
def values(st,dt,field):
 sv=defaultdict(lambda:D(0));sc=defaultdict(lambda:D(0))
 for x in st.values():sv[x['sid']]+=x['q']*price(x['sid'],dt,field)
 for s,v in sv.items():sc[mapping[s]]+=v
 return sv,sc
def refcap(x,rr,sc,spent):
 if x['M']==0:return D('Infinity')
 if x['M']!=1 or x.get('reference_close_q',x.get('reference_q',0))<=0:return D(0)
 sec=mapping[x['sid']];r=rr[sec];return max(D(0),min(D(r['T'])-sc[sec],D(r['buy_envelope'])-spent.get(sec,D(0))))
def budgets(x,dt,field,nav,sv,st):
 s=x['sid'];typ=x.get('event',x.get('kind'));t=x['signal_day'];qheld=sum(v['q'] for v in st.values() if v['sid']==s)
 if typ=='ADD':
  rid=x.get('round_id') or next(v['rid'] for v in st.values() if v['sid']==s);n0=D(attempts[rid]['nav0']);closed=actual_close[t]['st'];closeheld=quantity(closed,rid);b0=min(D('.02')*n0,max(D(0),D('.04')*n0-closeheld*price(s,t,'raw_close')));budget=min(b0,max(D(0),D('.04')*n0-qheld*price(s,dt,field)))
 else:budget=D('.02')*D(ld[t]['NAV'])
 return dict(attempt_budget=budget,stock_cap=max(D(0),D('.1')*nav-sv.get(s,D(0))))
def capacity(s,t):return int(raw[s].raw_volume[raw[s].raw_volume.gt(0)].loc[:pd.Timestamp(t)].tail(20).mean()*.01)
def noncash_q(x,dt,nav,sv,st,snap,check_net=False):
 s=x['sid'];typ=x['event'];p=price(s,dt,'raw_open')*D('1.0005');caps=budgets(x,dt,'raw_open',nav,sv,st);qr=version(rules['quantity_versions'][s],dt)['rule'];qheld=sum(v['q'] for v in st.values() if v['sid']==s);struct=True
 if typ=='ADD':
  rid=x['round_id'];cid=x['cp_id'];n=net(st,snap['flows'],snap['div'],rid,s,dt,'raw_open');oldhs=[h for h in hday.get(x['plan_day'],[]) if h['round_id']==rid];ifl=next((D(h['protection_signal']) for h in oldhs if h['kind']=='SEED'),D(0));struct=qheld>0 and not any(h['locked_exit'] and h['lot_id'] in st for h in oldhs) and cpok(rid,cid,s,dt,'raw_open',snap['latest'],snap['invalid']) and n>0 and price(s,dt,'raw_open')*price(s,dt,'adjustment_factor')>max(ifl,D(cpcreated[cid]['candidate']));q=size(s,dt,p,min(caps.values()),min(x['planned_q'],capacity(s,x['plan_day']))) if struct else 0
  if check_net and x['open_net'] is not None:equal('all_OPEN_ADD_net',D(x['open_net']),n,[dt,s])
 else:
  ff=facts[s].loc[pd.Timestamp(x['signal_day']):pd.Timestamp(x['plan_day'])];eligible=ff[ff.i_target.eq(True)&ff.i_floor.gt(0)];ifl=D(str(eligible.i_floor.max()));struct=not qheld and price(s,dt,'raw_open')*price(s,dt,'adjustment_factor')>ifl; q=qr['buy_minimum'] if struct and qr['buy_minimum']<=x['planned_q'] and qr['buy_minimum']<=capacity(s,x['plan_day']) else 0
  if q and q*p+fee(s,dt,q,p,'buy')>min(caps.values()):q=0
 return q,struct,p,caps
# CLOSE plans: dynamic gap queue, no paper-share sale, exact dated minimum net-cover donors.
plans={}
for dt in sorted(ld):
 rr={r['sector51']:r for r in refday[dt]};requests=rqday.get(dt,[]);st=actual_close[dt]['st'];sv,sc=values(st,dt,'raw_close');remaining=list(requests);ordered=[];spent=defaultdict(lambda:D(0))
 while remaining:
  mains=[r for r in remaining if r['M']==1];pool=mains or remaining;heads=[]
  for sec in sorted({mapping[r['sid']] for r in pool}):heads.append(min((r for r in pool if mapping[r['sid']]==sec),key=lambda r:(r['kind']!='ADD',cpcreated[r['cp_id']]['day'] if r['kind']=='ADD' else r['signal_day'],r['sid'])))
  def key(r):
   sec=mapping[r['sid']];sr=rr[sec];gap=max(D(0),D(sr['T'])-sc[sec]) if r['M']==1 and sr['E'] is not None and D(str(sr['E']))>0 and sr['status']=='PASS' else D(0);ev=secday[(dt,sec)];return (-gap,-ev['M_streak'],-D(str(r['E'])),cpcreated[r['cp_id']]['day'] if r['kind']=='ADD' else r['signal_day'],r['sid'])
  r=min(heads,key=key) if mains else min(pool,key=lambda r:(r['signal_day'],r['sid']));remaining.remove(r);ordered.append(r);s=r['sid'];sec=mapping[s];cap=max(D(0),min(D(rr[sec]['T'])-sc[sec],D(rr[sec]['buy_envelope'])-spent[sec])) if r['M']==1 else D('Infinity') if r['M']==0 else D(0)
  if r['M']==1 and (rr[sec]['status']!='PASS' or rr[sec]['E'] is None or D(str(rr[sec]['E']))<=0):cap=D(0)
  equal('CLOSE_reference_cap',D(r['reference_cap']),cap,[dt,s]);q=r['reference_q'];p=price(s,dt,'raw_close')*D('1.0005');cost=q*p+fee(s,dt,q,p,'buy') if q else D(0);equal('CLOSE_reference_cost',D(r['all_in_cost']),cost,[dt,s]);equal('CLOSE_q_not_above_original_plan',q<=r['base_planned_q'],True,[dt,s]);equal('CLOSE_allin_within_refcap',cost<=cap,True,[dt,s])
  bc=budgets(r,dt,'raw_close',D(ld[dt]['NAV']),sv,st);rawq=r['base_planned_q'];expected=size(s,dt,p,min(*bc.values(),cap),rawq) if r['kind']=='ADD' else version(rules['quantity_versions'][s],dt)['rule']['buy_minimum'];expected=expected if expected*p+fee(s,dt,expected,p,'buy')<=min(*bc.values(),cap) else 0
  if r['decision'] in ['PASS','REFERENCE_CAP']:equal('CLOSE_reference_legal_max_q',q,expected,[dt,s])
  if q and r['M']==1:sv[s]+=cost;sc[sec]+=cost;spent[sec]+=cost
 equal('CLOSE_dynamic_queue_ranks',[r['rank'] for r in ordered],list(range(1,len(ordered)+1)),dt)
 desired=sum((D(r['all_in_cost']) for r in requests if r['M']==1),D(0));nxt=nextday(dt);cash=D(ld[dt]['cash']);hs=hday.get(dt,[]);bys=defaultdict(list)
 for h in hs:bys[h['sid']].append(h)
 for s,ll in bys.items():
  q=sum(h['qty'] for h in ll if h['locked_exit'] and nxt>h['bought']);p=price(s,dt,'raw_close')*D('.9995');cash+=q*p-fee(s,nxt,q,p,'sell') if q else D(0)
 initial=max(D(0),desired+D('.1')*D(ld[dt]['NAV'])-cash) if desired>0 else D(0);gap=initial;sc={s:D(rr[s]['actual_value']) for s in rr};receivers={mapping[r['sid']] for r in requests if r['M']==1 and r['reference_q']>0};pool=[r for r in capday.get(dt,[]) if r['mobile_qty']>0 and r['sector51'] not in receivers];expected_plans=[]
 while pool and gap>0:
  def dk(r):
   sec=r['sector51'];tier=0 if r['donor_reason']=='UNCONFIRMED_NON_MAINLINE_SEED' else 1 if r['donor_reason']=='WEAK_SECTOR_ADD_LAYER' else 2;floor=max(D(rr[sec]['T']),D(rr[sec]['fixed']));return (tier,r['stock_state']!=0 if tier==0 else False,D(str(r['E'])) if tier==0 else -max(D(0),sc[sec]-floor) if tier==2 else D(0),D(str(r['E'])) if tier==2 else D(0),r['bought'],r['sid'],r['lot_id'])
  r=min(pool,key=dk);pool.remove(r);s=r['sid'];sec=r['sector51'];mark=price(s,dt,'raw_close');p=mark*D('.9995');held=sum(x['q'] for x in st.values() if x['sid']==s);qr=version(rules['quantity_versions'][s],nxt)['rule'];floor=max(D(rr[sec]['T']),D(rr[sec]['fixed']));maxq=floor_sell(min(r['mobile_qty'],int(max(D(0),sc[sec]-floor)/mark)),held,qr)
  if r['donor_reason']=='MAINLINE_REFERENCE_SURPLUS_ADD' and rr[sec]['status']!='PASS':continue
  q=(maxq if maxq==r['qty'] else 0) if r['kind']=='SEED' else cover(s,nxt,p,gap,maxq,held)
  if not q:continue
  amount=q*p-fee(s,nxt,q,p,'sell');expected_plans.append(dict(sid=s,lot_id=r['lot_id'],max_q=q,reason=r['donor_reason'],close_estimated_net=str(amount)));sc[sec]-=q*mark;gap=max(D(0),gap-amount)
 actual=[r for r in td.get(dt,[]) if r['phase']=='CLOSE' and r['event']=='DONOR_PLANNED'];plans[dt]=actual
 equal('CLOSE_minimum_net_cover_donor_sequence',[{k:r[k] for k in ['sid','lot_id','max_q','reason','close_estimated_net']} for r in actual],expected_plans,dt)
 dp=next(r for r in td[dt] if r['phase']=='CLOSE' and r['event']=='DEMAND_PLAN')
 for k,v in dict(M_desired_cost=desired,cash_after_known_protection=cash,initial_gap=initial,remaining_gap=gap).items():equal('CLOSE_financing_'+k,D(dp[k]),v,dt)
# OPEN: frozen ranks, all capital caps, exact net sale timing, no close-zero promotion.
for dt in sorted(ld):
 req=fundday.get(dt,[]);snap=copy.deepcopy(actual_open[dt]);st=copy.deepcopy(snap['st']);sv,sc=values(st,dt,'raw_open');prev=day0=str(cal[cal.get_loc(pd.Timestamp(dt))-1].date());rr={r['sector51']:r for r in refday.get(prev,[])};prevrows={r['lot_id']:r for r in capday.get(prev,[])};cash=D(ld[prev]['cash']) if prev in ld else D(1200000);recv=D(ld[prev]['receivable']) if prev in ld else D(0)
 for x in ed.get(dt,[]):
  if x['event']=='ACCRUE_NET80':recv+=D(x['receivable_delta'])
 mandatory=[o for o in od.get(dt,[]) if o['side'].startswith('SELL') and not o.get('transfer_rank')];cash+=sum((D(o['cash_delta']) for o in mandatory),D(0));nav=cash+recv+sum(sv.values(),D(0));equal('OPEN_frozen_request_ranks',[x['reference_close_rank'] for x in req],sorted(x['reference_close_rank'] for x in req),dt)
 prevreq={x['sid']:x for x in rqday.get(prev,[])}
 for x in req:equal('OPEN_prior_CLOSE_same_request',x['reference_close_q'],prevreq[x['sid']]['reference_q'],[dt,x['sid']]);equal('OPEN_no_same_day_plan',x['plan_day'],prev,[dt,x['sid']])
 dsv=sv.copy();dsc=sc.copy();spent=defaultdict(lambda:D(0));desired=D(0)
 for x in req:
  if x['M']!=1:continue
  s=x['sid'];sec=mapping[s];q,struct,p,bc=noncash_q(x,dt,nav,dsv,st,snap);cap=refcap(x,rr,dsc,spent);q=min(q,x['reference_close_q']);q=(q if q and q*p+fee(s,dt,q,p,'buy')<=cap else 0) if x['event']=='SEED' else size(s,dt,p,min(*bc.values(),cap),q) if q else 0;cost=q*p+fee(s,dt,q,p,'buy') if q else D(0);desired+=cost;dsv[s]+=cost;dsc[sec]+=cost;spent[sec]+=cost
 gap=max(D(0),desired+D('.1')*nav-cash) if desired>0 else D(0);initial=gap;proceeds=D(0);execrows=[x for x in td.get(dt,[]) if x['event']=='DONOR_EXECUTION'];equal('OPEN_uses_only_prior_donor_plan',[(x['sid'],x['lot_id'],x['max_q']) for x in execrows],[(x['sid'],x['lot_id'],x['max_q']) for x in plans.get(prev,[])],dt)
 sold=[o for o in od.get(dt,[]) if o.get('transfer_rank')]
 for x in execrows:
  s=x['sid'];sec=mapping[s];lid=x['lot_id'];l=st.get(lid);q=0
  if gap>0 and l is not None and dt>l['bought']:
   mark=price(s,dt,'raw_open');p=mark*D('.9995');held=sum(v['q'] for v in st.values() if v['sid']==s);fixed_open=sum((min(v['q'],prevrows.get(k,{}).get('frozen_qty',0))*price(v['sid'],dt,'raw_open') for k,v in st.items() if mapping[v['sid']]==sec),D(0));floor=max(D(x['close_sector_floor']),fixed_open);qr=version(rules['quantity_versions'][s],dt)['rule'];maxq=floor_sell(min(x['max_q'],max(0,l['q']-x['frozen_lot_qty']),int(max(D(0),sc[sec]-floor)/mark)),held,qr);q=(maxq if maxq==l['q'] else 0) if l['kind']=='SEED' else cover(s,dt,p,gap,maxq,held)
  equal('OPEN_only_shrink_legal_net_cover',x['executed_q'],q,[dt,lid]);tr=next((o for o in sold if o['transfer_rank']==x['rank']),None);equal('OPEN_donor_order_iff_positive_q',tr is not None,q>0,[dt,lid])
  if q:
   amount=q*p-fee(s,dt,q,p,'sell');equal('OPEN_donor_actual_net',D(tr['cash_delta']),amount,[dt,lid]);proceeds+=amount;cash+=amount;snap['flows'][l['rid']]+=amount;gap=max(D(0),gap-amount);sc[sec]-=q*mark;sv[s]-=q*mark;l['q']-=q
   if not l['q']:del st[lid]
  equal('OPEN_donor_remaining_gap',D(x['remaining_gap']),gap,[dt,lid])
 transfer=next(x for x in td[dt] if x['event']=='TRANSFER_CASH')
 for k,v in dict(M_desired_cost=desired,initial_gap=initial,net_cash_released=proceeds,remaining_gap=gap).items():equal('OPEN_transfer_'+k,D(transfer[k]),v,dt)
 spent=defaultdict(lambda:D(0));filled=[]
 for x in req:
  s=x['sid'];sec=mapping[s];q0,struct,p,bc=noncash_q(x,dt,nav,sv,st,snap,True);caps=dict(bc,cash_reserve=max(D(0),cash-D('.1')*nav),reference_cap=refcap(x,rr,sc,spent));rawq=version(rules['quantity_versions'][s],dt)['rule']['buy_minimum'] if x['event']=='SEED' else q0;cost0=rawq*p+fee(s,dt,rawq,p,'buy') if rawq else D(0)
  for k,v in caps.items():equal('OPEN_exact_reservation_'+k,D(x[k]),v,[dt,s])
  equal('OPEN_all_violated_caps',x['violated_caps'],sorted(k for k,v in caps.items() if cost0>v),[dt,s]);q=(q0 if q0 and cost0<=min(caps.values()) else 0) if x['event']=='SEED' else size(s,dt,p,min(caps.values()),min(q0,x['planned_q'],x['reference_close_q'])) if q0 else 0
  equal('OPEN_exact_legal_funded_q',x['executed_q'],q,[dt,s]);equal('OPEN_close_quantity_not_enlarged',x['executed_q']<=x['reference_close_q'] or x['M']==0,True,[dt,s])
  if q:
   cost=q*p+fee(s,dt,q,p,'buy');cash-=cost;sv[s]+=cost;sc[sec]+=cost;spent[sec]+=cost;filled.append((s,'BUY_'+x['event'],q));equal('OPEN_actual_cash_reserve',cash>=D('.1')*nav,True,[dt,s])
 equal('OPEN_reservations_equal_actual_buys',[(o['sid'],o['side'],o['qty']) for o in od.get(dt,[]) if o['side'].startswith('BUY')],filled,dt)
 receiver=next(x for x in td[dt] if x['event']=='RECEIVER_FUNDING');equal('OPEN_cash_reconciles_after_all_buys',D(receiver['cash_after_all_buys']),cash,dt);summary.append(dict(day=dt,frozen_NAV=str(nav),M_legal_demand=str(desired),net_donor_cash=str(proceeds),actual_buys=len(filled),cash_before_PAY_CLOSE=str(cash)))
report=dict(result='PASS' if not errors else 'FAIL',days=len(ld),checks=dict(checks),check_count=sum(checks.values()),error_count=len(errors),errors=errors,daily=summary,basis='Independent actual-lot CP chronology, dynamic CLOSE reference queue, dated legal quantities and analytical all-cap reservations; re-created exact CLOSE donor order/max, OPEN shrinking and real net proceeds before buying. No strategy engine import.')
(O/(run.name+'_QUEUE_FINANCING_AUDIT.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(result=report['result'],checks=report['check_count'],errors=errors[:15]),ensure_ascii=False))
