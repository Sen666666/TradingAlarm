"""Saved-book arithmetic and cache reads only. No runner/model imports."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict, Counter
import json, gzip, hashlib, time
import pandas as pd

O=Path(__file__).resolve().parent;P=O.parent;W=P.parent;Z=D(0)
LO='2026-01-01';HI='2026-06-30';BEFORE='2025-12-31'
SECTORS={'URFI881121':'半导体','URFI881172':'电子化学品','URFI881270':'元件'}
SRC={};F={};CP={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):SRC[str(p)]=sha(p);return json.loads(Path(p).read_text())
def rows(p):
 SRC[str(p)]=sha(p)
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def book(p):
 SRC[str(p)]=sha(p)
 with gzip.open(p,'rt') as f:return json.load(f)
def n(x):return D(str(x))
def day(x):return str(x)[:10]
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,D):return str(x)
 if x is None:return None
 if not isinstance(x,(str,bool,int)):
  try:
   if pd.isna(x):return None
  except (TypeError,ValueError):pass
 return x.item() if hasattr(x,'item') else x
def save(name,x):
 p=O/name;t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n');t.replace(p)
META=read('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json')
SM={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
IM={x['series']:x for x in read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')}
def frame(sid):
 if sid not in F:
  p=Path(SM[sid]['refs']['facts']);assert sha(p)==SM[sid]['output_sha256'][str(p)];SRC[str(p)]=sha(p);F[sid]=pd.read_parquet(p)
 return F[sid]
def row(sid,d):
 f=frame(sid);i=f.index.searchsorted(pd.Timestamp(d),side='right')-1
 if i<0:return None,None
 return f.iloc[i],str(f.index[i].date())
def price(sid,d):
 r,at=row(sid,d);assert r is not None
 return n(r.raw_close)
def state(sid,d):
 r,at=row(sid,d)
 if r is None:return dict(day=d,observed=False)
 if sid not in CP:
  p=Path(SM[sid]['refs']['CP1']);assert sha(p)==SM[sid]['output_sha256'][str(p)];SRC[str(p)]=sha(p);CP[sid]=pd.read_parquet(p)
 z=CP[sid].loc[pd.Timestamp(d)] if pd.Timestamp(d) in CP[sid].index else None
 return clean(dict(day=d,source_observation=at,exact_observation=at==d,
   **{k:r[k] if at==d else None for k in ['close','i_target','i_buy','i_floor','e0_target','e0_floor','g_grade','g_ready','g_acute_down']},
   CP1={k:z[k] for k in ['receipt','candidate','delta_frontier','m','v']} if z is not None else None))

def main():
 begun=time.monotonic();root=P/'runs/2025_26/pair';b=book(root/'B.json.gz');daily=rows(root/'daily.jsonl.gz');dd={day(x['at']):x for x in daily}
 layers=read(P/'analysis/2025_26/PVR_SLOT1/LAYERS.json');lm={x['layer']:x for x in layers};chain=read(P/'analysis/2025_26/PVR_SLOT1/FUNDED_RANK_STAGE_CHAIN.json')
 actions=read(P/'analysis/2025_26/PVR_SLOT1/ENTRY_ACTIONS.json');exits=read(P/'analysis/2025_26/PVR_SLOT1/EXITS.json')
 op=[x for x in rows(root/'opportunities.jsonl.gz') if LO<=x['day']<=HI and x['sector'] in SECTORS]
 funding=[x for x in rows(root/'funding.jsonl.gz') if LO<=day(x['at'])<=HI]
 intents={(day(x['at']),i['sid'],i['role']):i for x in b['decisions'] for i in x['intents']}
 traded=b['trades'];sellat=defaultdict(list)
 for t in traded:
  if t['side']=='sell':
   for z in t['parts']:sellat[z['layer']].append(t['at'])
 boundary=dd[BEFORE];end=dd[HI]
 assert not [x for x in boundary['layers'] if any(day(t)<=BEFORE for t in sellat[x['id']])]
 assert not [x for x in b['layers'] if x['qty'] and sellat[x['id']]],'open partial-sales need separate basis accounting'
 # Cached prices only; native close marks permit an as-of source observation.
 values={};risk={};flows=defaultdict(lambda:Z);div=defaultdict(lambda:Z);netcurve={};txi=0
 tx=sorted(traded,key=lambda x:x['at']);divs=sorted([x['receivable'] for x in b['audit'] if x['kind']=='dividend_accrual'],key=lambda x:x['ex_at']);di=0
 for r in daily:
  d=day(r['at']);v={s:D(q)*price(s,d) for s,q in r['positions'].items() if q};values[d]=v
  assert abs(sum(v.values(),Z)-n(r['inventory']))<D('.00001')
  while txi<len(tx) and day(tx[txi]['at'])<=d:
   t=tx[txi];flows[t['security_id']]+=(n(t['gross_cny']) if t['side']=='sell' else -n(t['gross_cny']))-n(t['fees_cny']);txi+=1
  while di<len(divs) and day(divs[di]['ex_at'])<=d:div[divs[di]['security_id']]+=n(divs[di]['net_local']);di+=1
  nc={s:flows[s]+div[s]+v.get(s,Z) for s in set(flows)|set(v)|set(div)};netcurve[d]=nc
  assert abs(sum(nc.values(),Z)-(n(r['nav'])-D(1000000)))<D('.00001')
  if d<LO:continue
  rr=defaultdict(lambda:Z);details=[]
  for x in r['layers']:
   z,sd=row(x['sid'],d);floor=n(x['last_core_line'] if x['role']=='core' else x['floor'])/n(z.factor);mark=price(x['sid'],d)
   q=D(x['qty']);v=q*mark;nr=q*max(Z,mark-floor);rr[x['sector']]+=nr
   details.append(dict(layer=x['id'],sid=x['sid'],name=META[x['sid']]['name'],sector=x['sector'],role=x['role'],pool=x['pool'],capital=v,risk=nr,
      mark=mark,actual_floor_raw=floor,source_observation=sd,quantity=x['qty'],I_valid=bool(z.i_target) if sd==d else None))
  assert abs(sum(rr.values(),Z)-n(r['pool_probe'][1])-n(r['pool_confirmed'][1]))<D('.02'),(d,'risk bridge')
  risk[d]=(dict(rr),details)
 industry={};cachedstate={};cachedcp={};curve=[];summary=[]
 for sec,name in SECTORS.items():
  m=IM[sec];pp=Path(m['refs']['CP1_input']);sp=Path(m['refs']['state']);cp=Path(m['refs']['CP1'])
  for p in [pp,sp,cp]:assert sha(p)==m['output_sha256'][str(p)];SRC[str(p)]=sha(p)
  f=pd.read_parquet(pp);st=pd.read_parquet(sp).set_index('day');cz=pd.read_parquet(cp);industry[sec]=f;cachedstate[sec]=st;cachedcp[sec]=cz
  base=n(f.loc[:BEFORE].close.iloc[-1]);fs=f.loc[LO:HI];ids={s for s in SM if META[s]['sector_id']==sec}
  ds=[d for d in dd if LO<=d<=HI]
  for d in ds:
   r=dd[d];v=sum((x for s,x in values[d].items() if s in ids),Z);state_=st.loc[d]
   bt=[t for t in traded if day(t['at'])==d and t['security_id'] in ids]
   curve.append(dict(day=d,sector=sec,industry=name,index_close=n(f.loc[d,'close']),index_return_since_2025end_pct=(n(f.loc[d,'close'])/base-1)*100,
     industry_stage=state_.stage_name,industry_E0=bool(state_.E0_valid),industry_action=state_.action,industry_CP1=bool(state_.receipt),cached_amount_m=cz.loc[d,'m'],cached_amount_v=cz.loc[d,'v'],
     NAV=r['nav'],portfolio_exposure_pct=n(r['inventory'])/n(r['nav'])*100,available_pct=n(r['available'])/n(r['nav'])*100,
     probe_pct=n(r['pool_probe'][0])/n(r['nav'])*100,confirmed_pct=n(r['pool_confirmed'][0])/n(r['nav'])*100,
     industry_capital=v,industry_weight_pct=v/n(r['nav'])*100,industry_nominal_risk=risk[d][0].get(sec,Z),
     buy_gross=sum((n(t['gross_cny']) for t in bt if t['side']=='buy'),Z),sell_gross=sum((n(t['gross_cny']) for t in bt if t['side']=='sell'),Z),
     largest_industry_stocks=sorted([dict(sid=s,name=META[s]['name'],value=x,weight_pct=x/n(r['nav'])*100) for s,x in values[d].items() if s in ids],key=lambda x:-x['value'])[:3]))
  v0=sum((v for s,v in values[BEFORE].items() if s in ids),Z);v1=sum((v for s,v in values[HI].items() if s in ids),Z)
  buys=[t for t in traded if LO<=day(t['at'])<=HI and t['security_id'] in ids and t['side']=='buy'];sells=[t for t in traded if LO<=day(t['at'])<=HI and t['security_id'] in ids and t['side']=='sell']
  realised=sum((n(x['cash']) for x in b['layers'] if x['sid'] in ids and x['closed'] and LO<=day(x['closed'])<=HI),Z)
  def unreal(r):return sum((n(x['cash'])+D(x['qty'])*price(x['sid'],day(r['at'])) for x in r['layers'] if x['sid'] in ids),Z)
  dv=sum((n(x['net_local']) for x in divs if x['security_id'] in ids and LO<=day(x['ex_at'])<=HI),Z)
  net=sum((netcurve[HI].get(s,Z)-netcurve[BEFORE].get(s,Z) for s in ids),Z);du=unreal(end)-unreal(boundary)
  assert abs(realised+du+dv-net)<D('.00001'),(sec,'realised/unrealised bridge')
  own=[x for x in curve if x['sector']==sec];peak=max(own,key=lambda x:x['industry_weight_pct']);nu=sum((n(t['gross_cny']) for t in buys),Z)-sum((n(t['gross_cny']) for t in sells),Z)
  initial={x['id'] for x in boundary['layers'] if x['sid'] in ids};new=[x for x in layers if x['sid'] in ids and LO<=day(x['opened'])<=HI]
  newnet=sum((n(x['net']) for x in new),Z)
  fr=[x for x in op if x['sector']==sec and x['CP1_id']];assert len({(x['sid'],x['day'],x['CP1_id']) for x in fr})==len(fr)
  qualified=[x for x in fr if x['mobile_Q'] is True];confirmed=[x for x in qualified if st.loc[x['day'],'stage_name'] in ('confirmed','expanded')]
  fillkeys={(x['sid'],x['signal_day'],x['receipt']) for x in new if x['role']=='mobile'}
  reserved={(x['sid'],day(next(t['signal_at'] for t in traded if t['side']=='buy' and t['layer']==x['layer'])),x['CP1_id']) for x in b['journal'] if x['kind']=='real_buy_fill' and LO<=day(x['at'])<=HI and x['sid'] in ids and x['role']=='mobile'}
  # Admissions include zero fills and are counted by decision-intent key, not final qty.
  reserve_rows=[]
  for x in b['journal']:
   if x['kind']=='real_reserve' and LO<=day(x['at'])<=HI and x['sid'] in ids:
    i=next((i for k,i in intents.items() if k[1]==x['sid'] and i.get('budget_order')==x['budget_order']),None)
    # budget_order is mutated after planning, so use explicit order-ID decision date.
    signal=x['budget_order'].split('|')[1][:10];reserve_rows.append(dict(x,signal_day=signal))
  summary.append(dict(sector=sec,industry=name,stock_identity_count=len(ids),price_return_H1_pct=(n(fs.close.iloc[-1])/base-1)*100,
    price_trough_day=str(fs.close.idxmin().date()),price_trough=n(fs.close.min()),price_return_trough_to_end_pct=(n(fs.close.iloc[-1])/n(fs.close.min())-1)*100,
    first_H1_industry_buy=buys[0]['at'] if buys else None,first_full_account_industry_buy=next((t['at'] for t in traded if t['side']=='buy' and t['security_id'] in ids),None),
    H1_buy_fills=len(buys),H1_sell_fills=len(sells),H1_new_layers=len(new),H1_new_stocks=len({x['sid'] for x in new}),carry_live_layers=len(initial),
    buy_gross=sum((n(t['gross_cny']) for t in buys),Z),buy_cash_including_fees=sum((n(t['gross_cny'])+n(t['fees_cny']) for t in buys),Z),sell_gross=sum((n(t['gross_cny']) for t in sells),Z),
    inventory_before=v0,inventory_end=v1,net_active_gross_funding=nu,mark_rights_inventory_residual=v1-v0-nu,
    mean_weight_pct=sum((x['industry_weight_pct'] for x in own),Z)/len(own),peak_weight=peak['industry_weight_pct'],peak_day=peak['day'],end_weight=own[-1]['industry_weight_pct'],
    interval_net_contribution=net,closed_trading_PnL_excluding_dividends=realised,unrealized_price_PnL_change=du,unrealized_price_PnL_before=unreal(boundary),unrealized_price_PnL_end=unreal(end),recognized_H1_dividends=dv,
    new_2026_fill_layer_lifecycle_net=newnet,carry_wealth_change=net-newnet,
    fresh_CP1_receipts=len(fr),Q_pass=len(qualified),industry_confirmed_or_expanded=len(confirmed),ACT_paused_confirmed=sum('ACT_paused' in x['barriers'] for x in confirmed),
    actual_mobile_filled_receipts=len(fillkeys),actual_reservations=len(reserve_rows),filled_new_layers=len(new),zero_fill_reservations=sum(x['budget_order'] not in {j['budget_order'] for j in b['journal'] if j['kind']=='real_buy_fill'} for x in reserve_rows),
    last_close_right_boundary_qualified=sum(x['day']==HI for x in confirmed),first_stage_events=st.loc[LO:HI].reset_index().query("action in ['probe','confirmed','expanded','end_attempt']").to_dict('records')))
 save('DAILY_ALIGNED_CAPITAL.json',curve);save('INDUSTRY_SUMMARY.json',summary)
 # Whole126 snapshot price denominator, deterministic hindsight controls.
 sec='URFI881121';ids=sorted(s for s in SM if META[s]['sector_id']==sec);returns=[]
 for sid in ids:
  f=frame(sid);prior=f.loc[:BEFORE];post=f.loc[LO:HI]
  ok=len(prior)>0 and len(post)>0 and str(post.index[-1].date())==HI and prior.segment_id.iloc[-1]==post.segment_id.iloc[-1]
  returns.append(dict(sid=sid,name=META[sid]['name'],status='comparable' if ok else 'missing_boundary_or_source_change',price_return_pct=(n(post.close.iloc[-1])/n(prior.close.iloc[-1])-1)*100 if ok else None,
     ever_held_in_H1=any(r['positions'].get(sid,0)>0 for r in daily if LO<=day(r['at'])<=HI),first_H1_fill=next((t['at'] for t in traded if t['side']=='buy' and t['security_id']==sid and LO<=day(t['at'])<=HI),None),
     peak_H1_weight_pct=max((values[d].get(sid,Z)/n(dd[d]['nav'])*100 for d in dd if LO<=d<=HI),default=Z),H1_contribution=netcurve[HI].get(sid,Z)-netcurve[BEFORE].get(sid,Z)))
 comparable=[x for x in returns if x['status']=='comparable'];top=sorted(comparable,key=lambda x:(-x['price_return_pct'],x['sid']))[:5]
 positive=max(returns,key=lambda x:x['H1_contribution']);negative=min(returns,key=lambda x:x['H1_contribution']);selected=list(dict.fromkeys([x['sid'] for x in top]+[positive['sid'],negative['sid']]))
 paths=[]
 for sid in selected:
  f=frame(sid);prior=f.loc[:BEFORE];base=n(prior.close.iloc[-1]) if len(prior) else None;own=[x for x in op if x['sid']==sid];ff=[x for x in funding if x['sid']==sid]
  firstI=next((str(t.date()) for t,z in f.loc[LO:HI].iterrows() if bool(z.i_buy)),None)
  cp=CP.get(sid)
  if cp is None:state(sid,HI);cp=CP[sid]
  firstCP=next((str(t.date()) for t,z in cp.loc[LO:HI].iterrows() if bool(z.receipt)),None)
  def event(x):
   if x is None:return None
   d=x.get('day',day(x.get('at','')));out=dict(x);out['industry_state']=cachedstate[sec].loc[d].to_dict();out['asof_stock_signal']=state(sid,d)
   z,_=row(sid,d);out['price_return_since_2025end_pct']=(n(z.close)/base-1)*100 if base is not None else None
   return out
  firsteligible=next((x for x in own if x['roles']),None);firstconfirmed=next((x for x in own if x['CP1_id'] and x['mobile_Q'] is True and cachedstate[sec].loc[x['day'],'stage_name'] in ('confirmed','expanded')),None)
  firstopen=next((x for x in ff if '09:30:00' in x['at']),None)
  paths.append(dict(stock=next(x for x in returns if x['sid']==sid),selection='top5 retrospective H1 original-sector price returns or deterministic largest actual positive/negative H1 contribution',
    first_I_event_H1=firstI,first_raw_CP1_H1=firstCP,first_original_eligible_roles=event(firsteligible),first_market_confirmed_mobile_opportunity=event(firstconfirmed),first_actual_opening_route_record=event(firstopen),
    first_close_sizing_reject=next((x for x in ff if '15:10:00' in x['at']),None),
    original_opportunity_counts=dict(all_stock_days=len(own),fresh_CP1=sum(bool(x['CP1_id']) for x in own),CP1_Q=sum(bool(x['CP1_id']) and x['mobile_Q'] is True for x in own),market_confirmed=sum(bool(x['CP1_id']) and x['mobile_Q'] is True and cachedstate[sec].loc[x['day'],'stage_name'] in ('confirmed','expanded') for x in own)),
    raw_opening_reasons=dict(Counter(x['result'] for x in ff if '09:30:00' in x['at'])),
    actual_entries=[x for x in actions if x['sid']==sid and LO<=day(x['at'])<=HI],
    funded_signal_chain=[dict(x,asof_stock=state(sid,x['signal_day'])) for x in chain if x['sid']==sid and LO<=day(x['actual_fill_at'])<=HI],
    actual_exit_requests_and_fills=[x for x in exits if x['sid']==sid and (LO<=day(x['request_at'])<=HI or (x['first_actual_sell'] and LO<=day(x['first_actual_sell'])<=HI))]))
 save('SEMICONDUCTOR_ALL_STOCKS_HINDSIGHT_DENOMINATOR.json',returns);save('FIXED_TOP_RETURN_AND_FUNDED_CONTROLS.json',paths)
 # Representative AFTER-CLOSE states: hard ceiling/slack arithmetic, not instant order replay.
 ss=next(x for x in summary if x['sector']==sec);trough=ss['price_trough_day'];st=cachedstate[sec]
 stages=[x['day'] for x in ss['first_stage_events'] if x['day']>=trough and x['action'] in ('confirmed','expanded')]
 dates=sorted(set([next(d for d in dd if d>=LO),'2026-03-31',trough,ss['peak_day'],HI]+stages));snaps=[]
 for d in dates:
  r=dd[d];nav=n(r['nav']);c=next(x for x in curve if x['day']==d and x['sector']==sec);stage=c['industry_stage'];frac=D('.02') if stage=='probe' else D('.10') if stage=='confirmed' else D('.20') if stage=='expanded' else Z
  assert n(r['order_reserved'])==0,'cannot infer close pending-sector allocation'
  owners=sorted(risk[d][1],key=lambda x:-x['capital'])[:10]
  snaps.append(dict(day=d,clock='actual close after planning, not exact pre-opening state',NAV=nav,industry_stage=stage,index_return_H1_pct=c['index_return_since_2025end_pct'],
    actual_portfolio_capital=n(r['inventory']),actual_exposure_pct=c['portfolio_exposure_pct'],actual_available=n(r['available']),
    cash_reserve_reference_10pct=nav*D('.1'),available_above_close_reserve=n(r['available'])-nav*D('.1'),
    probe_capital=n(r['pool_probe'][0]),probe_capital_cap=nav*D('.1'),probe_risk=n(r['pool_probe'][1]),probe_risk_cap=nav*D('.005'),
    confirmed_capital=n(r['pool_confirmed'][0]),confirmed_capital_cap=nav*D('.6'),
    semiconductor_capital=c['industry_capital'],semiconductor_stage_new_commitment_cap=nav*frac,semiconductor_capital_slack=nav*frac-c['industry_capital'],
    semiconductor_actual_risk=c['industry_nominal_risk'],semiconductor_risk_cap=nav*D('.01'),semiconductor_risk_slack=nav*D('.01')-c['industry_nominal_risk'],
    sector_risk_to_sector_mark_fraction=c['industry_nominal_risk']/c['industry_capital'] if c['industry_capital'] else None,
    top10_capital_owners=owners,semiconductor_lot_details=[x for x in risk[d][1] if x['sector']==sec],
    original_newbuy_rule_probe_sector_cap=nav*D('.02'),
    exact_preopen_constraint_relaxation_preview='not performed; full pre-candidate resource state not saved in this PVR log; no new state restorer',
    industry_cached_amount_context={k:cachedcp[sec].loc[d,k] for k in ['s','m','v','B']},
    industry_cross_stock_breadth='not present in saved industry/state/account fields; no new breadth indicator computed'))
 save('REPRESENTATIVE_CLOSE_RESOURCE_STATES.json',snaps)
 save('SOURCE_SHA256.json',SRC)
 total=(n(end['nav'])/n(boundary['nav'])-1)*100
 out=dict(scope='PVR_SLOT1 saved Jan-Jun2026 only; original strict sectors, no financial run',days=sum(LO<=d<=HI for d in dd),
   initial_H1_NAV=boundary['nav'],terminal_NAV=end['nav'],H1_account_return_pct=total,
   H1_mean_portfolio_exposure_pct=sum((n(x['inventory'])/n(x['nav'])*100 for x in daily if LO<=day(x['at'])<=HI),Z)/sum(LO<=d<=HI for d in dd),
   industry_summary=summary,semiconductor_top5_hindsight_price=top,positive_control=positive,negative_control=negative,
   no_new_indicators=True,new_account_runs=0,exact_relaxed_order_previews=0,all_close_stock_cashflow_NAV_bridges=True,realized_unrealized_dividend_bridges=True,
   open_partial_sale_at_both_boundaries=0,source_rights_and_daily_proxy_limits_unchanged=True,Jul_Oct_economic_validation=False,seconds=time.monotonic()-begun)
 save('SUMMARY.json',out);save('ARTIFACT_SHA256.json',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='ARTIFACT_SHA256.json'})
 print(json.dumps(clean({k:v for k,v in out.items() if k not in ['industry_summary']}),ensure_ascii=False));print('SECTORS',json.dumps(clean(summary),ensure_ascii=False))

if __name__=='__main__':
 try:main()
 except BaseException as e:save('ERROR.json',dict(error=repr(e),new_accounts=0));raise
