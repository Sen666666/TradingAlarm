"""Four CLOSE-only static capital bounds. No Engine.run, no strategy/account replay."""
from pathlib import Path
import sys,json,csv,hashlib,importlib.util,collections,math
from decimal import Decimal as D
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent; R=O.parent
P=R/'mainline_candidate_v2_pending_quote_pause/checkpoint_20240930'
DATES=['2024-09-20','2024-09-23','2024-09-26','2024-09-27']
NEXT=dict(zip(DATES,['2024-09-23','2024-09-24','2024-09-27','2024-09-30']))
Z=D(0);SLIP=D('.0005');H={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 p=Path(p);H[str(p)]=sha(p);return json.loads(p.read_text())
def load(n):return read(P/(n+'.json'))
def dump(n,x):(O/(n+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def csvout(n,rows):
 if not rows:return
 cols=list(dict.fromkeys(k for r in rows for k in r))
 with (O/(n+'.csv')).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=cols);w.writeheader()
  for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()})
def S(xs):return sum(xs,Z)
def isfinite(v):
 try:return math.isfinite(float(v))
 except:return False
def true(v):return v is not None and v in (True,1)
def known_bool(v):return v is not None and v in (True,False,0,1)
bpath=R/'joint51_candidate_v9_facts/engine.py'
spec=importlib.util.spec_from_file_location('diagnostic_frozen_base',bpath);b=importlib.util.module_from_spec(spec);sys.modules[spec.name]=b;spec.loader.exec_module(b)
pd=b.pd
feeobj=object.__new__(b.Data);feeobj.rules=read(b.B/'inputs-v2/market-rules.json');feeobj.proxies=read(b.B/'inputs-v2/economic-protocol.json')['approved_proxy_ids'];feeobj.meta={}
for p in [bpath,b.B/'code/market_rules.py',b.B/'code/sector_account.py',R/'mainline_candidate_v1/engine.py',R/'mainline_candidate_v1/FROZEN_CONTRACT_DRAFT.md',R/'mainline_candidate_v2_pending_quote_pause/engine.py',R/'mainline_candidate_v2_pending_quote_pause/CONTRACT.md']:H[str(p)]=sha(p)
fee=feeobj.fee
logs={n:load(n) for n in ['DAY_LEDGER','HOLDINGS','CANDIDATES','ORDERS','ATTEMPTS','FUNDING_REQUESTS','INFORMATION_CONFIRMATIONS','TRANSFERS','SECTOR_DAILY','RETRY_TICKETS','EQUITY_EVENTS','CP_EVENTS']}
# Exports are verified against their original seal. These files are never written.
seal=read(P/'OUTPUT_HASHES.json')
for n in logs:assert H[str(P/(n+'.json'))]==seal[n+'.json'],n
manifest={x['symbol']:x for x in read(b.U/'STOCK_MANIFEST.json')}
# Read only required as-of rows from pre-existing frozen sources; no new indicator calculation.
ids=sorted({x['sid'] for x in logs['HOLDINGS'] if x['day'] in DATES})
raw={};facts={};cp={}
for sid in ids:
 m=manifest[sid];ex={**m['source_sha256'],**m['output_sha256']}
 paths=[next(p for p in m['source_sha256'] if p.endswith('/signal.parquet')),m['refs']['facts'],m['refs']['CP1']]
 for target,p in zip([raw,facts,cp],paths):
  H[p]=sha(p);assert H[p]==ex[p],p
  target[sid]=pd.read_parquet(p).reindex(pd.to_datetime(DATES))
Q=b.R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2'
kp=Q/'KNOWN3.parquet';rp=Q/'RIGHT3.parquet';sp=b.R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet'
for p in [kp,rp,sp]:H[str(p)]=sha(p)
k=pd.read_parquet(kp,columns=ids).reindex(pd.to_datetime(DATES));r=pd.read_parquet(rp,columns=ids).reindex(pd.to_datetime(DATES))
ps=pd.read_parquet(sp,columns=['sid','day','state']);ps=ps[ps.sid.isin(ids)&ps.day.isin(pd.to_datetime(DATES))].pivot(index='day',columns='sid',values='state').reindex(index=k.index,columns=ids)
sk=k&ps.ge(0);st=(r&sk).astype(int).where(sk,-1)
allround=[];alllot=[];allsec=[];allreq=[];sums=[];allbounds=[];allt=[];alltd=[];maxneterr=Z
byorder={x['lot_id']:x for x in logs['ORDERS'] if x['side'].startswith('BUY')}
def water(cores,Es,budget):
 total=S(cores.values())
 if budget<total:return None,None,'INFEASIBLE_CORE_EXCEEDS_BUDGET'
 if not Es:return None,{},'NO_POSITIVE_E_MAINLINE'
 lo=Z;hi=max(Z,budget)/S(Es.values())+max((cores[s]/Es[s] for s in Es),default=Z)
 for _ in range(180):
  mid=(lo+hi)/2
  if S(max(cores[s],mid*Es[s]) for s in Es)>budget:hi=mid
  else:lo=mid
 return lo,{s:max(cores[s],lo*Es[s]) for s in Es},'STATIC_REFERENCE_ONLY'
for day in DATES:
 d=pd.Timestamp(day);nxt=pd.Timestamp(NEXT[day]);led=next(x for x in logs['DAY_LEDGER'] if x['day']==day)
 nav=D(led['NAV']);cash=D(led['cash']);recv=D(led['receivable']);floor=nav*D('.1')
 hs=[x for x in logs['HOLDINGS'] if x['day']==day];se={x['sector51']:x for x in logs['SECTOR_DAILY'] if x['day']==day}
 gates={x['round_id']:x for x in logs['CANDIDATES'] if x['day']==day and x.get('event')=='ADD_GATE'}
 confirms={x['round_id']:x for x in logs['INFORMATION_CONFIRMATIONS'] if x['day']<=day and x['decision']=='INFORMATION_CONFIRMED'}
 provisionals={x['round_id'] for x in logs['INFORMATION_CONFIRMATIONS'] if x['day']==day and x['decision']=='INFORMATION_CLOSE_PASS'}
 plan=next(x for x in logs['TRANSFERS'] if x['day']==day and x['phase']=='CLOSE' and x['event']=='DEMAND_PLAN')
 groups=collections.defaultdict(list)
 for h in hs:groups[h['round_id']].append(h)
 lotrows=[];roundrows=[];reqs=collections.defaultdict(list);stat=collections.defaultdict(lambda:Z)
 for a in plan['receivers']:
  sid=a['sid'];sector=next(x['sector51'] for x in logs['SECTOR_DAILY'] if False) if False else None
  # Static classification comes from the original frozen 51-class map.
  if sid not in globals().get('mapsec',{}):
   ro=read(R/'joint51_candidate_v9_facts/CLASSIFICATION_ALL1709.csv') if False else pd.read_csv(R/'joint51_candidate_v9_facts/CLASSIFICATION_ALL1709.csv')
   mapsec=ro.set_index('symbol').sector51.to_dict()
  rr=dict(day=day,sector51=mapsec[sid],**a,original_close_plan=True,next_open_unobserved=True)
  allreq.append(rr);reqs[mapsec[sid]].append(rr)
 assert S(D(x['cost']) for x in plan['receivers'])==D(plan['M_desired_cost'])
 for rid,ls in groups.items():
  sid=ls[0]['sid'];sector=ls[0]['sector51'];s=se[sector];g=gates[rid];q=sum(x['qty'] for x in ls);mark=D(ls[0]['raw_mark']);net=D(g['close_net'])
  cf=S(D(x['cash_delta']) for x in logs['ORDERS'] if x['round_id']==rid and x['day']<=day)
  div=S(D(x['receivable_delta']) for x in logs['EQUITY_EVENTS'] if x.get('round_id')==rid and x['day']<=day and x['event']=='ACCRUE_NET80')
  calc=cf+div+q*mark*(1-SLIP)-fee(sid,d,q,mark*(1-SLIP),'sell')
  maxneterr=max(maxneterr,abs(net-calc));assert abs(net-calc)<D('1e-16')
  confirmed=rid in confirms;winner=confirmed and s['M']==1 and net>0
  if not confirmed:cat='TRIAL_UNCONFIRMED'
  elif s['M']==-1:cat='CONFIRMED_MAINLINE_UNKNOWN'
  elif net<=0:cat='CONFIRMED_CURRENT_NET_NONPOSITIVE'
  elif s['M']!=1:cat='CONFIRMED_NON_MAINLINE_POSITIVE'
  else:cat='CURRENT_MAINLINE_WINNER'
  zz=raw[sid].loc[d];ff=facts[sid].loc[d];cc=cp[sid].loc[d];unknown=[]
  if s['M']==-1 or not isfinite(s['E']):unknown.append('M_OR_E_UNKNOWN')
  if int(st.at[d,sid])==-1:unknown.append('STOCK_M3_UNKNOWN')
  if not b.valid(zz) or not all(isfinite(zz.get(z)) and zz[z]>0 for z in ['raw_close','adjustment_factor']):unknown.append('CLOSE_QUOTE_OR_FACTOR_UNKNOWN')
  if not known_bool(ff.get('i_target')) or (true(ff.get('i_target')) and (not isfinite(ff.get('i_floor')) or ff['i_floor']<=0)):unknown.append('I_UNKNOWN')
  if not known_bool(cc.get('receipt')):unknown.append('CP_RECEIPT_UNKNOWN')
  if not all(pd.notna(zz.get(z)) and str(zz.get(z))!='' for z in ['source_kind','source_path','segment_id']):unknown.append('SOURCE_UNKNOWN')
  assert D(str(zz.raw_close))==mark
  adds=sorted([x for x in ls if x['kind']=='ADD'],key=lambda x:(x['bought'],byorder[x['lot_id']]['order_seq']))
  earliest=adds[0]['lot_id'] if adds else None
  histadds=sorted([x for x in logs['ORDERS'] if x['round_id']==rid and x['side']=='BUY_ADD' and x['day']<=day],key=lambda x:x['order_seq'])
  firsthist=histadds[0]['lot_id'] if histadds else None
  allmv=S(D(x['market_value']) for x in ls);seedmv=S(D(x['market_value']) for x in ls if x['kind']=='SEED');addmv=allmv-seedmv
  rs=dict(day=day,sid=sid,round_id=rid,sector51=sector,category=cat,M=s['M'],E=s['E'],confirmed_history_asof=confirmed,confirmation_last_day=confirms.get(rid,{}).get('day'),provisional_close=rid in provisionals,current_net_liquidation_profit=net,net_reconstruction_error=net-calc,market_value=allmv,seed_value=seedmv,ADD_value=addmv,current_mainline_winner=winner,earliest_surviving_ADD_lot=earliest,historical_first_ADD_lot=firsthist,earliest_survivor_is_historical_first=earliest==firsthist if earliest else None,unknown_reasons=unknown)
  roundrows.append(rs);allround.append(rs);stat[cat]+=allmv
  for h in ls:
   qr=feeobj.getmeta(sid,nxt)[0];lq=h['qty'];sellq=qr.sell_floor(lq,q) if nxt>pd.Timestamp(h['bought']) else 0
   curq=qr.sell_floor(lq,q) if d>pd.Timestamp(h['bought']) else 0
   seed=h['kind']=='SEED';core1=seed;core2=winner and (seed or h['lot_id']==earliest)
   original_trial_donor=not confirmed and rid not in provisionals and not histadds and s['M']==0 and s['state'] in [0,1] and int(st.at[d,sid]) in [0,1] and isfinite(s['E'])
   exit_locked=bool(h['locked_exit']);freeze=bool(unknown) or sellq<=0
   base=dict(**h,category=cat,round_net_profit=net,confirmed_history_asof=confirmed,current_mainline_winner=winner,core1_all_actual_seed=core1,core2_winner_seed_first_survivor=core2,original_trial_seed_donor=original_trial_donor,unknown_reasons=unknown,quote_source_known=not any('QUOTE' in x or 'SOURCE' in x for x in unknown),current_close_T1_sellable_qty=curq,next_open_T1_conditional_sellable_qty=sellq,sell_legal_step=qr.sell_step,exit_priority=exit_locked,freeze_unknown_or_quantity=freeze,buy_order_seq=byorder[h['lot_id']]['order_seq'])
   for scheme,isc in [('CORE1_ALL_SEED',core1),('CORE2_WINNER_SEED_FIRST_ADD',core2)]:
    # All other seeds stay separate: only original explicitly eligible trial seeds can donate.
    eligible=not isc and not freeze and not exit_locked and (not seed or original_trial_donor)
    base[scheme+'_mobile_qty']=sellq if eligible else 0
    base[scheme+'_core_value']=D(h['market_value']) if isc and not exit_locked else Z
    base[scheme+'_fixed_reason']='PROTECTED_CORE' if isc and not exit_locked else 'MANDATORY_EXIT' if exit_locked else '|'.join(unknown) if unknown else 'NONCORE_SEED_NOT_ORIGINAL_DONOR' if seed and not original_trial_donor else 'NO_LEGAL_T1_Q' if sellq<=0 else 'MOBILE_STATIC_UPPER_ONLY'
    qq=sellq if eligible else 0;netcash=qq*mark*(1-SLIP)-fee(sid,nxt,qq,mark*(1-SLIP),'sell') if qq else Z
    base[scheme+'_mobile_net_cash']=netcash;base[scheme+'_mobile_mark']=qq*mark
    base[scheme+'_mobile_sell_cost']=qq*mark-netcash
   lotrows.append(base);alllot.append(base)
  stat['all_actual_seed']+=seedmv;stat['all_actual_ADD']+=addmv
  if winner:
   stat['winner_seed']+=seedmv;stat['winner_earliest_surviving_ADD']+=D(adds[0]['market_value']) if adds else Z
 assert S(D(x['market_value']) for x in hs)==D(led['market_value'])
 assert S(stat[x] for x in ['TRIAL_UNCONFIRMED','CONFIRMED_MAINLINE_UNKNOWN','CONFIRMED_CURRENT_NET_NONPOSITIVE','CONFIRMED_NON_MAINLINE_POSITIVE','CURRENT_MAINLINE_WINNER'])==D(led['market_value'])
 Es={sec:D(str(x['E'])) for sec,x in se.items() if x['M']==1 and isfinite(x['E']) and x['E']>0};sumE=S(Es.values())
 for sector,s in se.items():
  req=reqs[sector];cost=S(D(x['cost']) for x in req);sectorlots=[x for x in lotrows if x['sector51']==sector]
  rec=dict(day=day,sector51=sector,M=s['M'],Q=s['Q'],S=s['S'],F=s['F'],E=s['E'],M_streak=s['M_streak'],N=s['N'],K=s['K'],n=s['n'],U=s['U'],rs5=s['rs5'],rs10=s['rs10'],rs20=s['rs20'],current_market_value=D(s['market_value']),current_account_weight_pct=D(s['account_weight_pct']),raw_E_fraction=Es.get(sector,Z)/sumE if sumE else None,raw_E_90pct_NAV_T=nav*D('.9')*Es.get(sector,Z)/sumE if sumE else None,raw_E_90pct_account_weight=90*Es.get(sector,Z)/sumE if sumE else None,legal_request_cost=cost,legal_request_count=sum(x['q']>0 for x in req),legal_SEED_cost=S(D(x['cost']) for x in req if x['kind']=='SEED'),legal_ADD_cost=S(D(x['cost']) for x in req if x['kind']=='ADD'),raw_E_status='ELIGIBLE' if sector in Es else 'M_TRUE_ZERO_E' if s['M']==1 and isfinite(s['E']) and s['E']==0 else 'UNKNOWN' if s['M']==-1 or not isfinite(s['E']) else 'NOT_M',trial_value=S(D(x['market_value']) for x in sectorlots if x['category']=='TRIAL_UNCONFIRMED'),winner_value=S(D(x['market_value']) for x in sectorlots if x['current_mainline_winner']),confirmed_nonM_positive_value=S(D(x['market_value']) for x in sectorlots if x['category']=='CONFIRMED_NON_MAINLINE_POSITIVE'),confirmed_nonpositive_value=S(D(x['market_value']) for x in sectorlots if x['category']=='CONFIRMED_CURRENT_NET_NONPOSITIVE'))
  allsec.append(rec)
 summ=dict(day=day,next_common_OPEN=NEXT[day],NAV=nav,cash=cash,receivable_unavailable=recv,cash_floor=floor,cash_above_floor=max(Z,cash-floor),cash_floor_shortfall=max(Z,floor-cash),market_value=D(led['market_value']),M_positive_E_sectors=len(Es),M_zero_E_sectors=sum(s['M']==1 and isfinite(s['E']) and s['E']==0 for s in se.values()),M_unknown_sectors=sum(s['M']==-1 for s in se.values()),sum_positive_E=sumE,legal_M_demand=D(plan['M_desired_cost']),**dict(stat))
 sums.append(summ)
 for scheme in ['CORE1_ALL_SEED','CORE2_WINNER_SEED_FIRST_ADD']:
  core={sec:S(x[scheme+'_core_value'] for x in lotrows if x['sector51']==sec) for sec in se}
  mobilemark={sec:S(x[scheme+'_mobile_mark'] for x in lotrows if x['sector51']==sec) for sec in se}
  mobilenet={sec:S(x[scheme+'_mobile_net_cash'] for x in lotrows if x['sector51']==sec) for sec in se}
  # Mandatory known exits are none in these four snapshots; assert to avoid implicit treatment.
  assert not any(x['exit_priority'] for x in lotrows)
  fixed={sec:D(se[sec]['market_value'])-mobilemark[sec] for sec in se}
  outside=S(v for sec,v in fixed.items() if sec not in Es)
  budgetgross=nav-floor-recv-outside
  sellcost=S(mobilemark.values())-S(mobilenet.values())
  budgetnet=budgetgross-sellcost
  lower={sec:fixed[sec] for sec in Es} # Includes core exactly once; other frozen holdings add disjointly.
  lam,T,status=water(lower,Es,budgetgross);lamlow,Tlow,statuslow=water(lower,Es,budgetnet)
  demand={sec:min(max(Z,T.get(sec,Z)-D(se[sec]['market_value'])),S(D(x['cost']) for x in reqs[sec])) if T else Z for sec in se}
  totald=S(demand.values())
  # Shares cannot be created from continuous gaps. This sums whole legal requests after clipping each sector envelope.
  reqlegal=collections.defaultdict(lambda:Z);qsmall=collections.defaultdict(int)
  for sec in se:
   remaining=demand[sec]
   for rrr in reqs[sec]:
    if not rrr['q']:continue
    sid=rrr['sid'];cost=D(rrr['cost']);qty=rrr['q']
    # infer the known raw close from cost via original fee-consistent notional. For unheld seeds read only current CLOSE.
    if sid in raw:mark=D(str(raw[sid].loc[d].raw_close))
    else:
     mp=manifest[sid];path=next(p for p in mp['source_sha256'] if p.endswith('/signal.parquet'));H[path]=sha(path);assert H[path]==mp['source_sha256'][path]
     zz=pd.read_parquet(path,columns=['raw_close']);mark=D(str(zz.loc[d,'raw_close']))
    price=mark*(1+SLIP);assert qty*price+fee(sid,d,qty,price,'buy')==cost
    if rrr['kind']=='SEED':buyq=qty if cost<=remaining else 0
    else:buyq=feeobj.size(sid,d,price,remaining,qty)
    bc=buyq*price+fee(sid,d,buyq,price,'buy') if buyq else Z;remaining-=bc;reqlegal[sec]+=bc;qsmall[sec]+=int(buyq>0)
  donor_target_net=collections.defaultdict(lambda:Z);donor_target_mark=collections.defaultdict(lambda:Z);donor_target_q=collections.defaultdict(int)
  # A diagnostic maximum restricted to sector surplus above T, with fixed oldest-lot bookkeeping.
  for sec in se:
   excess=max(Z,D(se[sec]['market_value'])-(T.get(sec,fixed[sec]) if T else D(se[sec]['market_value'])))
   for lr in sorted([x for x in lotrows if x['sector51']==sec],key=lambda x:(x['bought'],x['sid'],x['buy_order_seq'])):
    maxq=lr[scheme+'_mobile_qty'];sid=lr['sid'];mark=D(lr['raw_mark']);qr=feeobj.getmeta(sid,nxt)[0]
    heldq=sum(h['qty'] for h in hs if h['sid']==sid)
    qq=qr.sell_floor(min(maxq,max(0,int(excess/mark))),heldq) if totald>0 else 0
    qq=min(maxq,qq)
    net=qq*mark*(1-SLIP)-fee(sid,nxt,qq,mark*(1-SLIP),'sell') if qq else Z
    excess-=qq*mark;donor_target_net[sec]+=net;donor_target_mark[sec]+=qq*mark;donor_target_q[sec]+=qq
    alltd.append(dict(day=day,scheme=scheme,sector51=sec,sid=sid,lot_id=lr['lot_id'],kind=lr['kind'],available_mobile_q=maxq,target_surplus_capped_q=qq,raw_close=mark,estimated_sell_price=mark*(1-SLIP),estimated_net_cash=net,fee=fee(sid,nxt,qq,mark*(1-SLIP),'sell') if qq else Z,slippage_loss=qq*mark*SLIP,T1_checked_for=NEXT[day],future_OPEN_not_used=True,current_winner=lr['current_mainline_winner'],core_protected=lr[scheme+'_core_value']>0,fixed_reason=lr[scheme+'_fixed_reason']))
  target_upper=max(Z,cash+S(donor_target_net.values())-floor)
  broadupper=max(Z,cash+S(mobilenet.values())-floor)
  # Surplus-capped draw is a legal quantity witness, not optimal-order or actual next-OPEN execution.
  bd=dict(day=day,scheme=scheme,NAV=nav,cash=cash,receivable_unavailable=recv,cash_floor=floor,core_total=S(core.values()),other_fixed_total=S(fixed.values())-S(core.values()),all_fixed_total=S(fixed.values()),fixed_outside_positive_M_E=outside,positive_M_fixed_lower=S(lower.values()),gross_target_budget=budgetgross,full_mobile_sale_cost_stress=sellcost,net_stress_target_budget=budgetnet,lambda_gross=lam,lambda_net_stress=lamlow,status=status,status_net_stress=statuslow,all_mobile_mark=S(mobilemark.values()),all_mobile_net_cash=S(mobilenet.values()),cash_only_new_buy_lower=max(Z,cash-floor),all_mobile_sale_new_buy_upper=broadupper,total_positive_T_gap_legal_demand_upper=totald,actual_legal_lot_demand_within_T=S(reqlegal.values()),target_surplus_legal_sale_mark=S(donor_target_mark.values()),target_surplus_legal_sale_net=S(donor_target_net.values()),target_constrained_new_buy_cash_upper=target_upper,no_donor_if_no_requests=totald==0,request_and_cash_joint_upper=min(S(reqlegal.values()),target_upper),all_mobile_bound_is_not_strategy_permission=True)
  allbounds.append(bd)
  for sec in se:
   sr=next(x for x in allsec if x['day']==day and x['sector51']==sec)
   tr=dict(**sr,scheme=scheme,core_lower=core[sec],other_fixed=fixed[sec]-core[sec],total_fixed_lower=fixed[sec],mobile_mark=mobilemark[sec],mobile_net_cash=mobilenet[sec],T_gross=T.get(sec,fixed[sec]) if T else None,T_net_stress=Tlow.get(sec,fixed[sec]) if Tlow else None,T_pct_NAV=(T.get(sec,fixed[sec])/nav*100) if T else None,target_status='E_ALLOCATED' if sec in Es else 'FIXED_HOLD_ONLY_NO_E_ALLOCATION',positive_T_gap=max(Z,T.get(sec,Z)-D(se[sec]['market_value'])) if T else Z,legal_demand_upper=demand[sec],legal_lot_demand_within_T=reqlegal[sec],legal_receiver_orders_within_T=qsmall[sec],target_surplus_donor_q=donor_target_q[sec],target_surplus_donor_net=donor_target_net[sec],no_request_target_remains_cash=sec in Es and S(D(x['cost']) for x in reqs[sec])==0,core_included_once=True)
   allt.append(tr)
  print('BOUND',day,scheme,json.dumps(bd,default=str,ensure_ascii=False),flush=True)
# Full seals before and after, restricted to consumed inputs. Every preexisting consumed source must remain identical.
for path,h in H.items():assert sha(path)==h,('SOURCE_CHANGED',path)
H[str(R/'joint51_candidate_v9_facts/CLASSIFICATION_ALL1709.csv')]=sha(R/'joint51_candidate_v9_facts/CLASSIFICATION_ALL1709.csv')
for name,rows in [('FOUR_DAY_ACCOUNT_SUMMARY',sums),('A_ALL50_RAW_E_NORMALIZATION',allsec),('B_ALL50_CORE_TARGETS',allt),('B_CAPITAL_BOUNDS',allbounds),('ROUND_CLASSIFICATION_ASOF',allround),('LOT_CAPITAL_CLASSIFICATION_ASOF',alllot),('ORIGINAL_CLOSE_LEGAL_REQUESTS',allreq),('TARGET_SURPLUS_LOT_SALE_WITNESS',alltd)]:
 dump(name,rows);csvout(name,rows)
qa=dict(result='PASS_STATIC_DIAGNOSTIC_ONLY',dates=DATES,all_sector_rows=len(allsec),target_sector_rows=len(allt),lot_rows=len(alllot),round_rows=len(allround),max_current_net_profit_reconstruction_error=maxneterr,source_hashes_verified_unchanged=len(H),historical_strategy_runs=0,future_OPEN_prices_read=0,new_financial_parameters=0,original_files_written=0,strict_current_winner='M TRUE AND historical independent information confirmation by this date AND current fee-net whole-round liquidation profit > 0',core1='All current actual seed lots, regardless of winner status. Not a claim every seed is mature.',core2='Only current winner seed plus earliest still-held actual ADD lot; exact remaining quantity. Nonwinner seeds separately fixed unless original unconfirmed non-M donor test passes.',budget='NAV minus 10% frozen close NAV minus receivable minus fixed outside positive-E M; cores inside eligible M included exactly once via max(fixed_s,lambda*E_s). Full mobile-sale fee stress is a lower planning budget, not an instruction to liquidate.',execution='All sale values use observed CLOSE*(1-0.0005), dated next-OPEN quantity and fee rules; no future OPEN. Physical legal upper bounds conditional on quote/action/source/protection rechecks, actual fills unknown.',warning='No request implies no financing sale. T is reference ceiling, not a filled target. Requested all-in cost and legal lots cap actionable demand; no requirement to fill all sectors. Current50/1692 classification remains non-PIT.')
dump('QA',qa);dump('SOURCE_HASHES',H)
dump('OUTPUT_HASHES',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'})
print('COMPLETE',json.dumps(qa,default=str,ensure_ascii=False),flush=True)
