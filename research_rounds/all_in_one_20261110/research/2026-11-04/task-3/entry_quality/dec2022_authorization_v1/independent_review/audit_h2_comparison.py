"""Independent raw-book thin check: 32 periods, December clocks/capital, fixed tails."""
from pathlib import Path
from decimal import Decimal as D,getcontext
from collections import Counter,defaultdict
import json,gzip,hashlib,bisect
import pandas as pd
getcontext().prec=65
O=Path(__file__).resolve().parent;P=O.parent;R=P.parent/'trend_exit_controls_v1';C=P/'account_comparison/results_v1';Z=D(0);N=D(1000000);checks=Counter();SOURCE={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,lines=False):
 p=Path(p);SOURCE[str(p.resolve())]=sha(p)
 with (gzip.open(p,'rt') if p.suffix=='.gz' else p.open()) as f:return [json.loads(x) for x in f] if lines else json.load(f)
def near(a,b,k):assert abs(D(str(a))-D(str(b)))<D('0.000001'),(k,a,b);checks[k]+=1
def iso(x):return pd.Timestamp(x).isoformat()
def key(sid,role,receipt,decision,opened):return json.dumps([sid,role,receipt,iso(decision),iso(opened)],ensure_ascii=False,separators=(',',':'))
valid=read(C/'VALIDATION.json');assert valid['status']=='PASS_ALL_FIXED_32_PERIODS'
for p,h in read(C/'SOURCE_SHA256.json').items():assert sha(p)==h;checks['comparison_source_SHA']+=1
for p,h in read(C/'DELIVERABLE_SHA256.json').items():assert sha(p)==h;checks['comparison_deliverable_SHA']+=1
matrix=read(C/'PERIOD_ACCOUNT_MATRIX.json');assert len(matrix)==32
SM={m['symbol']:m for m in read('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};FR={}
def quote(sid,day):
 if sid not in FR:
  p=SM[sid]['refs']['facts'];assert sha(p)==SM[sid]['output_sha256'][p];FR[sid]=pd.read_parquet(p,columns=['raw_close'])
 f=FR[sid];j=f.index.searchsorted(pd.Timestamp(day),side='right')-1;assert j>=0;return D(str(f.raw_close.iloc[j]))
RUN={};decsummary={}
for arm in ['BASELINE','R_ONLY','P_ONLY','JOINT']:
 for win in ['2022_2024','strong']:
  root=R if arm=='BASELINE' else P;out=root/'runs'/arm/win;aud=read(root/'independent_review'/f'{arm}_{win}_ACCOUNT_AUDIT.json');assert aud['status']=='PASS_COMPLETED_ACCOUNT_WITH_LIMITS'
  for p,h in aud['source_sha256'].items():assert sha(p)==h
  b=read(out/'pair/B.json.gz');ds=read(out/'pair/daily.jsonl.gz',True);native={x['id']:x for x in b['layers']};buys={t['layer']:t for t in b['trades'] if t['side']=='buy'};journal={x['layer']:x for x in b['journal'] if x['kind']=='real_buy_fill'};cost={i:D(t['gross_cny'])+D(t['fees_cny']) for i,t in buys.items()};parts=defaultdict(list)
  for t in b['trades']:
   if t['side']=='sell':
    for p in t['parts']:parts[p['layer']].append((t['at'],p))
  partial={i for i,pp in parts.items() if len(pp)>1 or native[i]['qty']>0};states={}
  for i in partial:
   x=native[i];q=buys[i]['shares'];basis=cost[i];st=[];events=[(at,'sell',p) for at,p in parts[i]]+[(a['at'],'split',a) for a in b['audit'] if a['kind'] in ['split','split_fraction_floor_proxy'] and a['sid']==x['sid'] and x['opened']<a['at'] and (not x['closed'] or a['at']<x['closed'])]
   for at,k,p in sorted(events,key=lambda v:v[0]):
    if k=='split':new=D(q)*D(p['ratio']);assert new==int(new);q=int(new)
    else:basis-=basis*D(p['shares'])/q;q-=p['shares']
    st.append((at,basis))
   assert q==x['qty'];states[i]=st
  def basis_at(i,at):
   st=states.get(i,[]);jj=bisect.bisect_right([x[0] for x in st],at)-1;return cost[i] if jj<0 else st[jj][1]
  keys={i:key(x['sid'],b['metadata'][str(i)]['role'],journal[i].get('CP1_id'),b['metadata'][str(i)]['budget_order'].split('|')[1],x['opened']) for i,x in native.items()};assert len(set(keys.values()))==len(keys)
  reported=read(C/f'{arm}_{win}_LAYERS.json');bykey={x['key']:x for x in reported};assert set(keys.values())==set(bykey)
  for i,x in native.items():
   rr=bykey[keys[i]];assert rr['layer_in_this_book']==i and rr['sid']==x['sid'];near(rr['cost'],cost[i],'all_reported_layer_cost');near(rr['net'],D(x['cash'])+D(x['dividend'])+(D(x['qty'])*quote(x['sid'],ds[-1]['at'][:10]) if x['qty'] else Z),'all_reported_layer_endpoint_net')
  daily={};peak=N
  for d in ds:
   at=d['at'];held={x['id']:x for x in d['layers']};flat=[x for x in native.values() if x['opened']<=at and x['closed'] is not None and x['closed']<=at];basis=sum((basis_at(i,at) for i in held),Z);real=sum((D(x['cash']) for x in flat),Z)+sum((D(h['cash'])+basis_at(i,at) for i,h in held.items()),Z);ar=sum((D(x['dividend']) for x in flat),Z)+sum((D(h['dividend']) for h in held.values()),Z);unreal=D(d['inventory'])-basis;near(real+unreal+ar,D(d['nav'])-N,'daily_raw_components_NAV');peak=max(peak,D(d['nav']));daily[at[:10]]=dict(real=real,unreal=unreal,AR=ar,dd=1-D(d['nav'])/peak)
  risk=[a for a in b['audit'] if a['kind']=='risk_checkpoint']
  for row in [x for x in matrix if x['arm']==arm and x['window']==win]:
   ix=[j for j,d in enumerate(ds) if row['calendar_start']<=d['at'][:10]<=row['calendar_end']];sel=[ds[j] for j in ix];prior=ds[ix[0]-1] if ix[0] else None;beg=D(prior['nav']) if prior else N;end=D(sel[-1]['nav']);dd=Z;pk=beg
   for d in sel:pk=max(pk,D(d['nav']));dd=max(dd,1-D(d['nav'])/pk)
   trades=[t for t in b['trades'] if row['calendar_start']<=t['at'][:10]<=row['calendar_end']];rt=[a for a in risk if row['calendar_start']<=a['at'][:10]<=row['calendar_end']];pcomp=daily[prior['at'][:10]] if prior else dict(real=Z,unreal=Z,AR=Z);endcomp=daily[sel[-1]['at'][:10]]
   vals=dict(observations=len(sel),NAV_begin=beg,NAV_end=end,net_wealth_change=end-beg,return_fraction=end/beg-1,period_rebased_max_drawdown=dd,maximum_account_drawdown_from_full_path_peak=max(daily[d['at'][:10]]['dd'] for d in sel),mean_close_exposure=sum((D(d['inventory'])/D(d['nav']) for d in sel),Z)/len(sel),end_exposure=D(sel[-1]['inventory'])/end,mean_available=sum((D(d['available']) for d in sel),Z)/len(sel),fees=sum((D(t['fees_cny']) for t in trades),Z),turnover_gross=sum((D(t['gross_cny']) for t in trades),Z),buy_fills=sum(t['side']=='buy' for t in trades),sell_fills=sum(t['side']=='sell' for t in trades),actual_buycash=sum((D(t['gross_cny'])+D(t['fees_cny']) for t in trades if t['side']=='buy'),Z),actual_sell_net=sum((D(t['gross_cny'])-D(t['fees_cny']) for t in trades if t['side']=='sell'),Z),ACT_paused_closes=sum(not d['on'] for d in sel),ACT_pause_events=sum(a.get('event')=='pause' for a in rt),ACT_resume_events=sum(a.get('event')=='resume' for a in rt));vals['turnover_over_period_begin_NAV']=vals['turnover_gross']/beg
   vals.update(strict_realized_change=endcomp['real']-pcomp['real'],open_unrealized_change=endcomp['unreal']-pcomp['unreal'],AR_change=endcomp['AR']-pcomp['AR'])
   for k,v in vals.items():near(row[k],v,'period_'+k)
   assert row['first_observed_day']==sel[0]['at'][:10] and row['last_observed_day']==sel[-1]['at'][:10];checks['periods']+=1
  RUN[arm,win]=dict(book=b,ds=ds,native=native,cost=cost,keys=keys,bykey=bykey)
  if win=='strong':continue
  dm={d['at'][:10]:d for d in ds};a=dm['2022-11-30'];e=dm['2022-12-30'];old={h['id'] for h in a['layers']};didx={d['at'][:10]:j for j,d in enumerate(ds)};capital=defaultdict(lambda:defaultdict(lambda:Z));comp={}
  for day in ['2022-11-30','2022-12-30']:
   d=dm[day];hh={h['id']:h for h in d['layers']};at=d['at'];cc={}
   for i,x in native.items():
    if x['opened']>at:re=un=ar=Z
    elif i in hh:h=hh[i];ba=basis_at(i,at);re=D(h['cash'])+ba;un=D(h['qty'])*quote(x['sid'],day)-ba;ar=D(h['dividend'])
    else:assert x['closed'] and x['closed']<=at;re=D(x['cash']);un=Z;ar=D(x['dividend'])
    cc[i]=dict(real=re,unreal=un,AR=ar,wealth=re+un+ar)
   comp[day]=cc
  # Actual entry classification uses original chronological fill/split events.
  qstock=defaultdict(int);seen=set();actions={}
  for ev in b['audit']:
   if ev['kind'] in ['split','split_fraction_floor_proxy']:qstock[ev['sid']]=int(D(qstock[ev['sid']])*D(ev['ratio']))
   elif ev['kind']=='fill':
    t=next(t for t in b['trades'] if t['receipt_id']==ev['receipt']['receipt_id']);sid=t['security_id']
    if t['side']=='buy':actions[t['layer']]='first' if sid not in seen else 'add' if qstock[sid]>0 else 'reentry';seen.add(sid);qstock[sid]+=t['shares']
    else:qstock[sid]-=t['shares'];assert qstock[sid]>=0
  for d in [d for d in ds if d['at'][:7]=='2022-12']:
   j=didx[d['at'][:10]]
   for snap,phase in [(ds[j-1],'previous_CLOSE'),(d,'CLOSE')]:
    total=Z
    for h in snap['layers']:
     i=h['id'];mark=D(h['qty'])*quote(h['sid'],snap['at'][:10]);total+=mark;capital[i][phase+'_mark_yuan_observations']+=mark;capital[i][phase+'_held_observations']+=1
     if phase=='previous_CLOSE':capital[i]['previous_CLOSE_basis_yuan_observations']+=basis_at(i,snap['at'])
    near(total,snap['inventory'],'Dec_phase_cold_inventory')
  rows=read(C/f'{arm}_DEC_OWN_CLOCK_CAPITALTIME_ROWS.json');wanted={i for i,x in native.items() if i in old or a['at']<x['opened']<=e['at'] or comp['2022-12-30'][i]['wealth']!=comp['2022-11-30'][i]['wealth']};assert {x['layer_in_this_book'] for x in rows}==wanted
  for x in rows:
   i=x['layer_in_this_book'];assert x['key']==keys[i];assert x['actual_entry_action']==actions[i];co='old_inventory_Nov30' if i in old else 'Dec_new_'+actions[i] if a['at']<native[i]['opened']<=e['at'] else 'other_prior';assert x['cohort']==co
   for k in ['real','unreal','AR','wealth']:near(x['Nov30_components'][k],comp['2022-11-30'][i][k],'Dec_row_start_'+k);near(x['Dec30_components'][k],comp['2022-12-30'][i][k],'Dec_row_end_'+k);near(x['Dec_components'][k],comp['2022-12-30'][i][k]-comp['2022-11-30'][i][k],'Dec_row_delta_'+k)
   for k in ['previous_CLOSE_mark_yuan_observations','previous_CLOSE_basis_yuan_observations','CLOSE_mark_yuan_observations','CLOSE_held_observations','previous_CLOSE_held_observations']:near(x['capitaltime'][k],capital[i][k],'Dec_capital_'+k)
  dsumm=read(C/'DEC_OWN_COHORT_WEALTH_CAPITALTIME_SUMMARY.json')[arm]
  def checkgroup(rr,summary):
   near(summary['layers'],len(rr),'Dec_group_n');near(summary['stocks'],len({x['sid'] for x in rr}),'Dec_group_stocks')
   for name,field in [('Dec_wealth','wealth'),('Dec_realized','real'),('Dec_unrealized','unreal'),('Dec_AR','AR')]:near(summary[name],sum((D(x['Dec_components'][field]) for x in rr),Z),'Dec_group_'+name)
   for k in ['previous_CLOSE_mark_yuan_observations','previous_CLOSE_basis_yuan_observations','CLOSE_mark_yuan_observations']:near(summary[k],sum((D(x['capitaltime'][k]) for x in rr),Z),'Dec_group_'+k)
   near(summary['Dec_new_actual_buycash'],sum((D(x['cost']) for x in rr if x['cohort'].startswith('Dec_new_')),Z),'Dec_group_actual_buycash');near(summary['positive'],sum((max(Z,D(x['Dec_components']['wealth'])) for x in rr),Z),'Dec_group_positive');near(summary['negative'],sum((min(Z,D(x['Dec_components']['wealth'])) for x in rr),Z),'Dec_group_negative')
  checkgroup(rows,dsumm)
  for co,s in dsumm['own_cohorts'].items():checkgroup([x for x in rows if x['cohort']==co],s)
  for role,s in dsumm['by_actual_role'].items():checkgroup([x for x in rows if x['role']==role],s)
  decsummary[arm]=dict(wealth=dsumm['Dec_wealth'],old=dsumm['own_cohorts']['old_inventory_Nov30']['Dec_wealth'],new_buycash=dsumm['Dec_new_actual_buycash'],cohort_counts={k:v['layers'] for k,v in dsumm['own_cohorts'].items()});checks['Dec_accounts']+=1
fixed=read(P.parent/'entry_exit_scale/analysis_summary/FIXED_ORIGINAL_TAILS.json')
for arm in ['BASELINE','R_ONLY','P_ONLY','JOINT']:
 for win in ['2022_2024','strong']:
  b=RUN['BASELINE',win];r=RUN[arm,win];tf=read(C/f'{arm}_{win}_FIXED83_94_TAILS.json');rr=tf['rows'];assert len(rr)==len(fixed[win]);status=Counter();basecash=candcash=Z;nb=na=0
  for row,t in zip(rr,fixed[win]):
   x=t['original'];k=key(x['sid'],x['role'],x.get('receipt'),x['decision_at'],x['opened']);assert row['original_fixed_member']==x and row['entry_key']==k;bm=b['bykey'].get(k);am=r['bykey'].get(k);assert row['baseline_current_exact_match']==bm and row['candidate_exact_entry_match']==am;nb+=bm is not None;na+=am is not None
   st='matched_baseline_and_candidate' if bm and am else 'same_entry_not_participated_candidate' if bm else 'baseline_unmatched_candidate_entry_present' if am else 'baseline_unmatched_both_absent';assert row['status']==st;status[st]+=1
   start=iso(x['opened']);end=iso(x['closed']) if x['closed'] else iso(b['ds'][-1]['at']);overlap=[a['key'] for a in r['bykey'].values() if a['sid']==x['sid'] and a['opened']<end and (a['closed'] is None or a['closed']>start)];assert row['candidate_holding_overlap_original_tail_interval_keys']==overlap;assert row['candidate_no_actual_holding_during_original_tail_interval']==(not overlap)
   if bm:basecash+=D(bm['net']);candcash+=D(am['net']) if am else Z;near(row['raw_contribution_delta'],(D(am['net']) if am else Z)-D(bm['net']),'tail_raw_delta')
   checks['fixed_tail_rows']+=1
  su=tf['summary'];assert nb=={'2022_2024':45,'strong':67}[win] and su['baseline_current_matches']==nb and su['candidate_exact_matches']==na and su['statuses']==dict(status);near(su['baseline_matched_cohort_net'],basecash,'tail_baseline_money');near(su['candidate_same_entry_contribution_for_baseline_matched_cohort'],candcash,'tail_candidate_money')
result=dict(status='PASS_ALL_32_PERIODS_DEC_WEALTH_CAPITAL_AND_FIXED_TAILS',checks=dict(checks),December=decsummary,source_sha256=SOURCE,script_sha256=sha(__file__),new_accounts=0,new_indicator_calculation=0,limits=['Thin original-output audit after all8 full financial ledgers passed. Daily strict components independently derived from actual native cash/basis and the two original partial-sale arithmetic sidecars.','All32 fixed calendar periods checked incl wealth components, returns, local/global DD, exposures, fees, turnover, ACT and fill counts.','December all own rows/capital phases/groups checked; capital observations are yuan x22 native CLOSEs, not exposure-matched traded benchmark or future inputs.','Fixed83/94 full membership and45/67 baseline keys, quantities/net identity, same-stock original holding interval and money checked. Raw same-key contributions are not pure exit effects.'])
(O/'H2_COMPARISON_MATRIX_DEC_TAIL_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(status=result['status'],checks=dict(checks),December=decsummary),ensure_ascii=False,indent=2))
