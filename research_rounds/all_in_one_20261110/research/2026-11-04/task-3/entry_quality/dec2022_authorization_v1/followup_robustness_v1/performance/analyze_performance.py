"""Read frozen outputs and audited partial sidecars; no account or order replay.

Current snapshot cash+quantity*known raw close+recognized AR is the native
per-layer wealth identity. Only read that identity and difference snapshots.
"""
from pathlib import Path
from decimal import Decimal as D, getcontext
from collections import defaultdict
import bisect, csv, gzip, hashlib, json
import pandas as pd

getcontext().prec=65
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
ENTRY=ROOT.parent
PREV=ROOT/'account_comparison/results_v1'
OLD=ENTRY/'trend_exit_controls_v1'
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
META=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json')
Z=D(0); INITIAL=D(1000000); SRC={}; FRAMES={}; QUOTES={}; TOL=D('0.000001')
ARMS=['BASELINE','R_ONLY','P_ONLY','JOINT']
PERIODS={
 '2022_2024':[
 ('full_2022_2024','2022-01-01','2024-12-31'),('2022','2022-01-01','2022-12-31'),
 ('Dec2022','2022-12-01','2022-12-31'),('2023','2023-01-01','2023-12-31'),('2024','2024-01-01','2024-12-31'),
 ('from_2024_09_24','2024-09-24','2024-12-31'),('after_2024_10_08','2024-10-09','2024-12-31'),
 ('repair_2022_Apr_Jun','2022-04-01','2022-06-30'),('from_2022_10_10','2022-10-10','2022-12-30'),
 ('2023_Jan_Apr','2023-01-01','2023-04-30'),('2024_Feb_May','2024-02-01','2024-05-31')],
 'strong':[
 ('strong','2025-07-01','2026-06-30'),('2025_observed_H2','2025-07-01','2025-12-31'),
 ('2026_observed_H1','2026-01-01','2026-06-30'),('2025_Q3','2025-07-01','2025-09-30'),
 ('2025_Q4','2025-10-01','2025-12-31'),('2026_Q1','2026-01-01','2026-03-31'),('2026_Q2','2026-04-01','2026-06-30')]}

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p, gz=False, lines=False):
 p=Path(p);SRC[str(p.resolve())]=sha(p)
 with (gzip.open(p,'rt') if gz else p.open()) as f:return [json.loads(x) for x in f] if lines else json.load(f)
def save(name,x):
 with (OUT/name).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
def eq(a,b,label):assert abs(D(str(a))-D(str(b)))<TOL,(label,str(a),str(b))
def dec(x):return D(str(x))
def runpath(arm,win):return (OLD if arm=='BASELINE' else ROOT)/'runs'/arm/win
def quote(sid,day):
 key=(sid,day)
 if key not in QUOTES:
  if sid not in FRAMES:
   row=MANIFEST[sid];p=Path(row['refs']['facts']);h=sha(p);assert h==row['output_sha256'][str(p)]
   SRC[str(p)]=h;FRAMES[sid]=pd.read_parquet(p,columns=['raw_close'])
  f=FRAMES[sid];i=f.index.searchsorted(pd.Timestamp(day),side='right')-1;assert i>=0
  r=f.iloc[i];assert str(f.index[i].date())<=day and r.raw_close>0
  QUOTES[key]=dec(r.raw_close)
 return QUOTES[key]
def summary(rr,field='wealth'):
 return dict(members=len(rr),net=sum((r[field] for r in rr),Z),positive=sum((max(Z,r[field]) for r in rr),Z),negative=sum((min(Z,r[field]) for r in rr),Z))
def concentration(rr,key):
 rr=sorted(rr,key=lambda x:x['wealth'],reverse=True);pos=[x for x in rr if x['wealth']>0]
 total=sum((x['wealth'] for x in rr),Z);positive=sum((x['wealth'] for x in pos),Z)
 return dict(grouping=key,groups=len(rr),positive_groups=len(pos),negative_groups=sum(x['wealth']<0 for x in rr),net=total,
  gross_positive=positive,gross_negative=sum((min(Z,x['wealth']) for x in rr),Z),
  positive_share_HHI=None if not positive else sum(((x['wealth']/positive)**2 for x in pos),Z),
  top={str(n):dict(groups=[x['group'] for x in pos[:n]],positive_contribution=sum((x['wealth'] for x in pos[:n]),Z),
      share_of_gross_positive=None if not positive else sum((x['wealth'] for x in pos[:n]),Z)/positive,
      descriptive_net_after_subtracting_these_contributions=total-sum((x['wealth'] for x in pos[:n]),Z)) for n in [1,5,10]},
  limitation='Descriptive subtraction of observed P&L only: no stock deletion, no capital redeployment, no new account, no investable exclusion return.')
def add_components(a,b):
 for k in ['real','unreal','AR','wealth']:a[k]+=b[k]
def zero():return dict(real=Z,unreal=Z,AR=Z,wealth=Z)
def grouped(rows,key):
 g=defaultdict(zero)
 for r in rows:add_components(g[r[key]],r)
 return [dict(group=k,**v) for k,v in sorted(g.items())]

def load(arm,win):
 rp=runpath(arm,win);done=read(rp/'DONE.json');timing=read(rp/'TIMING.json');assert done['completed'] and timing['completed']
 audit=read((OLD if arm=='BASELINE' else ROOT)/'independent_review'/f'{arm}_{win}_ACCOUNT_AUDIT.json');assert audit['status']=='PASS_COMPLETED_ACCOUNT_WITH_LIMITS'
 layers=read(PREV/f'{arm}_{win}_LAYERS.json');daily=read(PREV/f'{arm}_{win}_DAILY_WEALTH_SPLIT.json')
 raw=read(rp/'pair/daily.jsonl.gz',gz=True,lines=True);book=read(rp/'pair/B.json.gz',gz=True)
 assert len(raw)==len(daily);byid={x['layer_in_this_book']:x for x in layers};native={x['id']:x for x in book['layers']}
 ps=VALID['native_daily_mark_wealth_and_partial_basis'][arm+'|'+win]['partial_basis_state_points']
 def state(lid,at):
  ss=ps.get(str(lid));
  if ss is None:return None
  j=bisect.bisect_right([s['at'] for s in ss],at)-1
  return None if j<0 else ss[j]
 closures=defaultdict(list)
 for l in layers:
  assert META_ROWS[l['sid']]['sector_id']==l['H2_entry_context']['sector']
  if l['closed'] is not None:closures[l['closed'][:10]].append(l)
 states={};components=[];deltas=[];caps=[];maxres=Z
 for d,known in zip(raw,daily):
  day=d['at'][:10];assert day==known['day'];change=[];held_cap={}
  for h in d['layers']:
   lid=h['id'];l=byid[lid];partial=state(lid,d['at']);real=dec(partial['strict_realized']) if partial is not None else Z
   basis=dec(partial['basis']) if partial is not None else dec(l['cost']);eq(real-basis,h['cash'],'native held basis')
   mark=dec(h['qty'])*quote(h['sid'],day);ar=dec(h['dividend']);value=dict(real=real,unreal=mark-basis,AR=ar,wealth=dec(h['cash'])+mark+ar)
   prev=states.get(lid,zero());change.append(dict(lid=lid,sid=h['sid'],sector=META_ROWS[h['sid']]['sector_id'],**{k:value[k]-prev[k] for k in value}));states[lid]=value
   held_cap[lid]=dict(mark=mark,basis=basis)
  for l in closures.get(day,[]):
   lid=l['layer_in_this_book'];n=native[lid];value=dict(real=dec(n['cash']),unreal=Z,AR=dec(n['dividend']),wealth=dec(n['cash'])+dec(n['dividend']))
   prev=states.get(lid,zero());change.append(dict(lid=lid,sid=l['sid'],sector=META_ROWS[l['sid']]['sector_id'],**{k:value[k]-prev[k] for k in value}));states[lid]=value
  assert len({x['lid'] for x in change})==len(change),'Layer simultaneously held and closed at CLOSE'
  total={k:sum((v[k] for v in states.values()),Z) for k in ['real','unreal','AR','wealth']}
  for k,mk in [('real','strict_realized'),('unreal','open_unrealized'),('AR','AR')]:eq(total[k],known[mk],'audited daily '+k)
  eq(total['wealth'],dec(d['nav'])-INITIAL,'native snapshot wealth');maxres=max(maxres,abs(total['wealth']-(dec(d['nav'])-INITIAL)))
  eq(sum((x['mark'] for x in held_cap.values()),Z),d['inventory'],'native capital inventory')
  components.append(dict(states));deltas.append(change);caps.append(held_cap)
 # The values in states are immutable per update; boundary shallow copies are safe.
 actual_parts=[]
 for l in layers:
  lid=l['layer_in_this_book'];ss=ps.get(str(lid));parts=l['actual_sale_parts']
  for p in parts:
   if ss is None:
    assert len(parts)==1 and l['closed'] is not None;allocated=dec(l['cost']);real=dec(p['net_cash'])-allocated
   else:
    matching=[(j,s) for j,s in enumerate(ss) if s['at']==p['at']];assert len(matching)==1
    j,s=matching[0];real=dec(s['strict_realized'])-(dec(ss[j-1]['strict_realized']) if j else Z);allocated=dec(p['net_cash'])-real
   actual_parts.append(dict(lid=lid,sid=l['sid'],sector=META_ROWS[l['sid']]['sector_id'],at=p['at'],reason=p['reason'],shares=p['shares'],net_cash=dec(p['net_cash']),sold_basis=allocated,strict_realized=real,order_created_at=p['order_created_at']))
 for day,changes in zip([x['day'] for x in daily],deltas):eq(sum((x['real'] for x in changes),Z),sum((x['strict_realized'] for x in actual_parts if x['at'][:10]==day),Z),'daily actual sell.parts realized')
 return dict(arm=arm,win=win,layers=layers,byid=byid,daily=daily,raw=raw,book=book,components=components,deltas=deltas,caps=caps,parts=actual_parts,maxres=maxres)

def period(r,label,start,end):
 daily=r['daily'];ix=[i for i,d in enumerate(daily) if start<=d['day']<=end];assert ix
 fi,li=ix[0],ix[-1];prior=daily[fi-1] if fi else dict(NAV=INITIAL,exposure=Z,inventory=Z,available=INITIAL,strict_realized=Z,open_unrealized=Z,AR=Z)
 last=daily[li];selected=[daily[i] for i in ix];prevs=[daily[i-1] if i else dict(NAV=INITIAL,exposure=Z,inventory=Z) for i in ix]
 meanNAV=sum((dec(x['NAV']) for x in selected),Z)/len(ix);meanprevNAV=sum((dec(x['NAV']) for x in prevs),Z)/len(ix)
 trades=[t for t in r['book']['trades'] if start<=t['at'][:10]<=end];buy=sum((dec(t['gross_cny']) for t in trades if t['side']=='buy'),Z);sell=sum((dec(t['gross_cny']) for t in trades if t['side']=='sell'),Z)
 peak=dec(prior['NAV']);dd=Z
 for x in selected:peak=max(peak,dec(x['NAV']));dd=max(dd,1-dec(x['NAV'])/peak)
 net=dec(last['NAV'])-dec(prior['NAV']);m=dict(arm=r['arm'],window=r['win'],period=label,start=start,end=end,first_observed=selected[0]['day'],last_observed=selected[-1]['day'],observations=len(ix),
  NAV_begin=prior['NAV'],NAV_end=last['NAV'],net_wealth_change=net,return_fraction=dec(last['NAV'])/dec(prior['NAV'])-1,
  strict_realized_change=dec(last['strict_realized'])-dec(prior['strict_realized']),open_unrealized_change=dec(last['open_unrealized'])-dec(prior['open_unrealized']),AR_change=dec(last['AR'])-dec(prior['AR']),
  period_rebased_max_DD=dd,maximum_account_DD_from_entire_account_path_peak=max(dec(x['drawdown_from_full_path_peak']) for x in selected),
  mean_CLOSE_NAV=meanNAV,mean_previous_CLOSE_NAV=meanprevNAV,mean_CLOSE_exposure=sum((dec(x['exposure']) for x in selected),Z)/len(ix),mean_previous_CLOSE_exposure=sum((dec(x['exposure']) for x in prevs),Z)/len(ix),
  mean_CLOSE_inventory=sum((dec(x['inventory']) for x in selected),Z)/len(ix),mean_previous_CLOSE_inventory=sum((dec(x['inventory']) for x in prevs),Z)/len(ix),
  fees=sum((dec(t['fees_cny']) for t in trades),Z),buy_gross=buy,sell_gross=sell,buy_plus_sell_gross=buy+sell,
  buy_gross_over_mean_CLOSE_NAV=buy/meanNAV,sell_gross_over_mean_CLOSE_NAV=sell/meanNAV,two_sided_gross_over_mean_CLOSE_NAV=(buy+sell)/meanNAV,
  conventional_oneway_turnover_over_mean_CLOSE_NAV=(buy+sell)/2/meanNAV,
  actual_buycash=sum((dec(t['gross_cny'])+dec(t['fees_cny']) for t in trades if t['side']=='buy'),Z),actual_sell_net=sum((dec(t['gross_cny'])-dec(t['fees_cny']) for t in trades if t['side']=='sell'),Z),
  buy_fills=sum(t['side']=='buy' for t in trades),sell_fills=sum(t['side']=='sell' for t in trades),ACT_paused_closes=sum(not x['ACT_on'] for x in selected))
 a=r['components'][fi-1] if fi else {};b=r['components'][li];oldids=set(r['caps'][fi-1]) if fi else set();cohortrows=[];capital=defaultdict(lambda:dict(previous_CLOSE_mark_yuan_observations=Z,previous_CLOSE_basis_yuan_observations=Z,CLOSE_mark_yuan_observations=Z,held_CLOSE_observations=0))
 for i in ix:
  for phase,snapshot in [('previous_CLOSE',r['caps'][i-1] if i else {}),('CLOSE',r['caps'][i])]:
   for lid,c in snapshot.items():
    capital[lid][phase+'_mark_yuan_observations']+=c['mark']
    if phase=='previous_CLOSE':capital[lid]['previous_CLOSE_basis_yuan_observations']+=c['basis']
    else:capital[lid]['held_CLOSE_observations']+=1
 for l in r['layers']:
  lid=l['layer_in_this_book'];aa=a.get(lid,zero());bb=b.get(lid,zero());delta={k:bb[k]-aa[k] for k in bb}
  new=start<=l['opened'][:10]<=end
  if lid not in oldids and not new and not any(delta.values()):continue
  cohort='old_inventory_previous_CLOSE' if lid in oldids else 'new_'+l['actual_entry_action'] if new else 'other_prior_flat'
  cohortrows.append(dict(key=l['key'],lid=lid,sid=l['sid'],name=META_ROWS[l['sid']]['name'],sector=META_ROWS[l['sid']]['sector_id'],industry=META_ROWS[l['sid']]['industry'],role=l['role'],actual_entry_action=l['actual_entry_action'],decision_at=l['decision_at'],opened=l['opened'],closed=l['closed'],cohort=cohort,**delta,capitaltime=capital[lid],actual_new_buycash=dec(l['cost']) if new else Z))
 eq(sum((x['wealth'] for x in cohortrows),Z),net,'period old/new layer wealth')
 for k,mk in [('real','strict_realized_change'),('unreal','open_unrealized_change'),('AR','AR_change')]:eq(sum((x[k] for x in cohortrows),Z),m[mk],'period component '+k)
 groups={}
 for field in ['cohort','role']:
  groups[field]={}
  for g in sorted({x[field] for x in cohortrows}):
   rr=[x for x in cohortrows if x[field]==g];groups[field][g]=dict(summary(rr),**{k:sum((x[k] for x in rr),Z) for k in ['real','unreal','AR','actual_new_buycash']},capitaltime={k:sum((x['capitaltime'][k] for x in rr),Z) for k in next(iter(capital.values())).keys()})
 stock=grouped(cohortrows,'sid');sector=grouped(cohortrows,'sector')
 for x in stock:x.update(name=META_ROWS[x['group']]['name'],industry=META_ROWS[x['group']]['industry'],sector=META_ROWS[x['group']]['sector_id'])
 for x in sector:x.update(industry=SECTOR_NAMES[x['group']])
 time_rows=[]
 for i in ix:
  d=daily[i];ch=r['deltas'][i];dt=pd.Timestamp(d['day']);iso=dt.isocalendar();time_rows.append(dict(day=d['day'],week=f'{iso.year}-W{iso.week:02d}',month=d['day'][:7],**{k:sum((x[k] for x in ch),Z) for k in ['real','unreal','AR','wealth']}))
 allgroups={'stock':stock,'sector':sector,'day':grouped(time_rows,'day'),'week':grouped(time_rows,'week'),'month':grouped(time_rows,'month')}
 conc={k:concentration(v,k) for k,v in allgroups.items()}
 for k,v in allgroups.items():eq(sum((x['wealth'] for x in v),Z),net,'concentration complete '+k)
 pp=[p for p in r['parts'] if start<=p['at'][:10]<=end];exits={}
 for reason in sorted({x['reason'] for x in pp}):
  qq=[x for x in pp if x['reason']==reason];exits[reason]=dict(sale_parts=len(qq),layers=len({x['lid'] for x in qq}),stocks=len({x['sid'] for x in qq}),shares=sum(x['shares'] for x in qq),net_cash=sum((x['net_cash'] for x in qq),Z),sold_basis=sum((x['sold_basis'] for x in qq),Z),strict_realized=sum((x['strict_realized'] for x in qq),Z))
 eq(sum((x['strict_realized'] for x in pp),Z),m['strict_realized_change'],'actual exit component bridge');eq(sum((x['net_cash'] for x in pp),Z),m['actual_sell_net'],'actual exit net proceeds')
 semistock={x['group']:x for x in stock};semirows=[dict(SEMIBY[s],**{k:semistock.get(s,zero())[k] for k in ['real','unreal','AR','wealth']},actual_layer_count=sum(x['sid']==s for x in cohortrows),capitaltime_previous_CLOSE_mark=sum((x['capitaltime']['previous_CLOSE_mark_yuan_observations'] for x in cohortrows if x['sid']==s),Z)) for s in SEMIBY]
 semitotal={k:sum((x[k] for x in semirows),Z) for k in ['real','unreal','AR','wealth']}
 semi=dict(frozen_members=len(semistock),frozen_semiconductor_members=len(semirows),actually_contributing_members=sum(x['wealth']!=0 for x in semirows),components=semitotal,account_net=net,rest_of_account_net=net-semitotal['wealth'],rows=semirows,semantic_definition='Frozen metadata industry exactly 半导体 / URFI881121; all126 in frozen1709, including zero/no-trade/unavailable members')
 m.update(cohort_summary=groups,exit_actual_realized_by_reason=exits,concentration=conc,semiconductor=semitotal)
 return m,dict(layer_rows=cohortrows,group_rows=allgroups,actual_exit_parts=pp,semiconductor=semi)

if __name__=='__main__':
 OUT=HERE/'results_v1';assert not OUT.exists(),'Preserve all prior results';OUT.mkdir()
 try:
  META_ROWS=read(META);MANIFEST={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};VALID=read(PREV/'VALIDATION.json');assert VALID['status']=='PASS_ALL_FIXED_32_PERIODS'
  SEMI=read(HERE/'SEMICONDUCTOR_COHORT_FREEZE.json');SEMIBY={r['sid']:r for r in SEMI['all_metadata_members'] if r['in_frozen1709']};assert len(SEMIBY)==126
  SECTOR_NAMES={r['sector_id']:r['industry'] for r in META_ROWS.values()};matrix=[];checks=[];concs=[];semis=[]
  for win in PERIODS:
   for arm in ARMS:
    r=load(arm,win)
    for label,start,end in PERIODS[win]:
     m,detail=period(r,label,start,end);matrix.append(m);name=f'{arm}_{label}'
     save(name+'_DETAIL.json',detail);concs.append(dict(arm=arm,window=win,period=label,concentration=m['concentration']));semis.append(dict(arm=arm,window=win,period=label,**detail['semiconductor']))
    checks.append(dict(arm=arm,window=win,observations=len(r['daily']),max_native_NAV_component_residual=r['maxres'],actual_sale_parts=len(r['parts']),snapshot_identity_exact=True))
    print('FINISHED',arm,win,flush=True)
  assert len(matrix)==72
  prior=read(PREV/'PERIOD_ACCOUNT_MATRIX.json');by={(x['arm'],x['period']):x for x in matrix}
  for p in prior:
   q=by[p['arm'],p['period']]
   for old,new in [('NAV_begin','NAV_begin'),('NAV_end','NAV_end'),('net_wealth_change','net_wealth_change'),('period_rebased_max_drawdown','period_rebased_max_DD'),('fees','fees'),('turnover_gross','buy_plus_sell_gross'),('mean_close_exposure','mean_CLOSE_exposure')]:eq(p[old],q[new],'sealed32 '+old)
  save('FIXED_PERIOD_PERFORMANCE.json',matrix);save('CONCENTRATION_SUMMARY.json',concs);save('SEMICONDUCTOR_ALL_FIXED_PERIODS.json',semis)
  fields=[k for k,v in matrix[0].items() if not isinstance(v,dict)]
  with (OUT/'FIXED_PERIOD_PERFORMANCE.csv').open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(matrix)
  save('VALIDATION.json',dict(status='PASS_READ_ONLY_72_FIXED_ROWS',completed_existing_paths=8,new_accounts=0,new_account_events=0,periods=72,original32_metrics_exact=True,checks=checks,partial_basis_source='Unchanged previously audited native sidecar, not rederived ledger',stock_and_sector_and_day_week_month_wealth_bridges=True))
  save('DEFINITIONS.json',dict(turnover='Gross actual fills exclude fees: buy and sell individually / arithmetic mean selected daily CLOSE NAV; total two-sided=(buy+sell)/mean NAV; conventional one-way=(buy+sell)/2/mean NAV. No annualization. Actual buycash/sellnet separately include fees.',exposure='Arithmetic mean actual inventory/NAV at previous original market CLOSE and at current CLOSE separately. First account observation prior is original 1m cash/0inventory. Capitaltime unit is yuan*market CLOSE observations, not calendar days.',drawdown='Period-rebased peak begins at actual previous CLOSE NAV; account DD peak begins at original 1m account inception and never resets by calendar year.',wealth='Actual native snapshot cash+quantity*last-known rawclose+recognized dividendAR; closed original terminal cash+AR at/after actual close only. Per-period strictreal/openunreal/AR differences sum true NAV difference. No future terminal labels filled into open snapshots.',classification='Current frozen sector mapping, not historical PIT. Cohort old = actual held previous CLOSE; new first/add/reentry = own actual participation history. Actual exit realized classification uses actual sale.parts reasons, not terminal label.',concentration='All positive stock/sector/day/week/month contributions independently summed in specified full period. Top1/5/10 shares denominator is gross positive contributions in same grouping. Remaining net is descriptive subtraction of those observed contributions, not deletion/backtest/capital reallocation.',year_coverage='2022/23/24 complete original observed years. 2025 only Jul-Dec and 2026 only Jan-Jun within independent strong account; explicitly partial years. No extrapolation.',windows='All original32 fixed period rows plus prespecified repair/late2022/early2023/Feb-May2024 and four strong quarters and two observed halfyears, 72rows total; keep every row.',semiconductor='Exact frozen metadata industry 半导体 sectorURFI881121, intersect original1709=126 names. Cohort frozen before contribution lookup, no winner-selected names. Members with zero trades/missing period quotes remain zero actual allocation, not price performance.'))
 except BaseException as e:save('FAILURE.json',dict(error=repr(e),new_accounts=0,preserve_partial=True));raise
 finally:
  SRC[str(Path(__file__).resolve())]=sha(__file__);save('SOURCE_SHA256.json',SRC)
  save('DELIVERABLE_SHA256.json',{str(p.resolve()):sha(p) for p in OUT.iterdir() if p.is_file() and p.name!='DELIVERABLE_SHA256.json'})
