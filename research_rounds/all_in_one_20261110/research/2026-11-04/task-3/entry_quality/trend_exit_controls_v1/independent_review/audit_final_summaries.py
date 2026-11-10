"""Thin final NAV/report and full-entry tail/Oct8 bridge audit; no engines."""
from pathlib import Path
from decimal import Decimal as D,getcontext
from collections import Counter
import json,gzip,csv,hashlib,math,re
import pandas as pd
getcontext().prec=70
P=Path(__file__).resolve().parents[1];O=Path(__file__).resolve().parent;Q=P/'execution_review/account_comparison/results_v2';C=Counter();S={};Z=D(0)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 p=Path(p);S[str(p)]=sha(p)
 with (gzip.open(p,'rt') if p.suffix=='.gz' else p.open()) as f:return [json.loads(x) for x in f] if '.jsonl' in p.name else json.load(f)
def eq(a,b,label):assert abs(D(str(a))-D(str(b)))<D('1e-8'),(label,a,b);C[label]+=1
def key(sid,role,receipt,decision,opened):return json.dumps([sid,role,receipt,pd.Timestamp(decision).isoformat(),pd.Timestamp(opened).isoformat()],ensure_ascii=False,separators=(',',':'))
def oldkey(x):return key(x['sid'],x['role'],x.get('receipt'),x['decision_at'],x['opened'])
periods={'full_2022_2024':('2022-01-01','2024-12-31'),'bear2022':('2022-01-01','2022-12-31'),'year2023':('2023-01-01','2023-12-31'),'year2024':('2024-01-01','2024-12-31'),'from924':('2024-09-24','2024-12-31'),'after1008':('2024-10-09','2024-12-31'),'strong':('2025-07-01','2026-06-30')};arms=['BASELINE','EARLY_EMA20','EARLY_EMA60','EARLY_BOLL20_MID','EARLY_BOLL20_LOWER'];nav=read(P/'NAV_SUMMARY.json');assert len(nav)==35;N={(x['arm'],x['period']):x for x in nav};runs={}
for arm in arms:
 for window in ['2022_2024','strong']:
  root=P/'runs'/arm/window;book=read(root/'pair/B.json.gz');daily=read(root/'pair/daily.jsonl.gz');rows=read(Q/(arm+'_'+window+'_LAYERS.json'));bm={x['id']:x for x in book['layers']};buy={x['layer']:x for x in book['trades'] if x['side']=='buy'};journal={x['layer']:x for x in book['journal'] if x['kind']=='real_buy_fill'};bykey={}
  for x in rows:
   lid=x['layer_in_this_book'];b=buy[lid];native=bm[lid];m=book['metadata'][str(lid)];j=journal[lid];kk=key(native['sid'],m['role'],j.get('CP1_id'),m['budget_order'].split('|')[1],native['opened']);assert kk==x['key'] and kk not in bykey;bykey[kk]=x;assert x['qty']==native['qty'];eq(x['cost'],D(b['gross_cny'])+D(b['fees_cny']),'v2_each_original_cost');eq(x['AR'],native['dividend'],'v2_each_AR');eq(x['net'],D(native['cash'])+D(x['value'])+D(native['dividend']),'v2_each_net_cash_value_AR');assert (x['closed'] is None)==bool(x['qty']);C['v2_full_entry_keys']+=1
   if x['qty']:eq(x['strict_realized'],0,'v2_open_no_remaining_partial_realized');eq(x['open_unrealized'],D(x['value'])-D(x['cost']),'v2_open_basis')
   else:eq(x['strict_realized'],native['cash'],'v2_closed_allparts_realized');eq(x['open_unrealized'],0,'v2_closed_unrealized')
  assert len(rows)==len(bm);receipt=read(O/(arm+'_'+window+'_ACCOUNT_AUDIT.json'));eq(sum((D(x['net']) for x in rows),Z),receipt['net_wealth'],'v2_all_layers_wealth');eq(sum((D(x['strict_realized']) for x in rows),Z),receipt['trade_realized'],'v2_all_layers_realized');eq(sum((D(x['open_unrealized']) for x in rows),Z),receipt['open_unrealized'],'v2_all_layers_unrealized')
  gpeak=D(1000000);globaldd=[]
  for d in daily:gpeak=max(gpeak,D(d['nav']));globaldd.append((1-D(d['nav'])/gpeak)*100)
  for label,(lo,hi) in periods.items():
   ii=[i for i,d in enumerate(daily) if lo<=d['at'][:10]<=hi]
   if not ii:continue
   x=N[arm,label];start=D(daily[ii[0]-1]['nav']) if ii[0] else D(1000000);end=D(daily[ii[-1]]['nav']);tr=[t for t in book['trades'] if lo<=t['at'][:10]<=hi];peak=start;dd=Z
   for i in ii:v=D(daily[i]['nav']);peak=max(peak,v);dd=max(dd,(1-v/peak)*100)
   assert (x['first_day'],x['last_day'],x['days'])==(daily[ii[0]]['at'][:10],daily[ii[-1]]['at'][:10],len(ii))
   for field,val in dict(starting_NAV=start,ending_NAV=end,wealth_change=end-start,return_pct=(end/start-1)*100,max_local_drawdown_pct=dd,max_since_account_start_drawdown_pct=max(globaldd[i] for i in ii),mean_exposure_pct=sum((D(daily[i]['inventory'])/D(daily[i]['nav'])*100 for i in ii),Z)/len(ii),trade_count=len(tr),buy_count=sum(t['side']=='buy' for t in tr),sell_count=sum(t['side']=='sell' for t in tr),fees=sum((D(t['fees_cny']) for t in tr),Z),gross_turnover=sum((D(t['gross_cny']) for t in tr),Z)).items():eq(x[field],val,'NAV35_'+field)
   C['fixed_period_row']+=1
  runs[arm,window]=dict(book=book,daily=daily,rows=rows,bykey=bykey)
for x in nav:
 base=N['BASELINE',x['period']]
 for a,b in [('wealth_change','wealth_change_difference_vs_base'),('ending_NAV','ending_NAV_difference_vs_base'),('return_pct','return_pct_difference_vs_base'),('max_local_drawdown_pct','local_DD_difference_pp')]:eq(D(str(x[a]))-D(str(base[a])),x[b],'NAV35_delta')
csvrows=list(csv.DictReader((P/'NAV_SUMMARY.csv').open()));assert len(csvrows)==35
for x,y in zip(nav,csvrows):
 for k,v in x.items():
  if k in ['arm','window','period','first_day','last_day']:assert y[k]==v
  else:eq(y[k],v,'NAV_CSV_cell')
frozen=read(P.parent/'entry_exit_scale/analysis_summary/FIXED_ORIGINAL_TAILS.json');tail_summary=read(Q/'FIXED_ORIGINAL_TAIL_SUMMARY.json');post_summary=read(Q/'POST_OCT8_OLD_NEW_SUMMARY.json');match303=read(Q/'ORIGINAL303_MATCH_SUMMARY.json');tail_checks={}
def check_tail(arm,window,controls,path,summary):
 result=read(path);rr=result['rows'];assert len(rr)==len(controls);base=runs['BASELINE',window];run=runs[arm,window];status=Counter();baseline=Z;candidate=Z;nb=na=empty=emptyb=earlyempty=0
 for t,control in zip(rr,controls):
  orig=control['original'];assert t['original_fixed_member']==orig;kk=oldkey(orig);assert t['entry_key']==kk;b=base['bykey'].get(kk);a=run['bykey'].get(kk);assert t['baseline_current_exact_match']==b and t['candidate_exact_entry_match']==a
  st='matched_baseline_and_candidate' if b and a else 'same_entry_not_participated_candidate' if b else 'baseline_unmatched_candidate_entry_present' if a else 'baseline_unmatched_both_absent';assert st==t['status'];status[st]+=1;nb+=b is not None;na+=a is not None
  start=pd.Timestamp(orig['opened']).isoformat();end=pd.Timestamp(orig['closed'] or base['daily'][-1]['at']).isoformat();overlap=[x['key'] for x in run['rows'] if x['sid']==orig['sid'] and x['opened']<end and (x['closed'] is None or x['closed']>start)];assert t['candidate_holding_overlap_original_tail_interval_keys']==overlap and t['candidate_no_actual_holding_during_original_tail_interval']==(not overlap);empty+=not overlap;emptyb+=bool(b is not None and not overlap)
  e=bool(b is not None and a is not None and a['closed'] is not None and a['closed']<(b['closed'] or pd.Timestamp(base['daily'][-1]['at']).isoformat()));after=[]
  if e:after=[x['key'] for x in run['rows'] if x['sid']==a['sid'] and x['key']!=kk and x['opened']<(b['closed'] or pd.Timestamp(base['daily'][-1]['at']).isoformat()) and (x['closed'] is None or x['closed']>a['closed'])]
  assert t['matched_entry_exited_earlier']==e and t['candidate_other_holding_after_exact_layer_exit_before_baseline_end_keys']==after and t['candidate_no_further_holding_after_early_exit']==((not after) if e else None);earlyempty+=bool(e and not after)
  if b is not None:baseline+=D(b['net']);candidate+=D(a['net']) if a else Z;eq(t['raw_contribution_delta'],(D(a['net']) if a else Z)-D(b['net']),'tail_each_raw_delta')
  else:assert t['raw_contribution_delta'] is None
  C['fixed_control_membership_overlap']+=1
 expect=dict(original_frozen_members=len(rr),baseline_current_matches=nb,candidate_exact_matches=na,statuses=dict(status),completely_no_holding_in_original_tail_interval=empty,baseline_matched_cohort_completely_no_holding_in_original_tail_interval=emptyb,matched_tail_earlier_exit_then_no_further_holding=earlyempty,baseline_matched_cohort_net=baseline,candidate_same_entry_contribution_for_baseline_matched_cohort=candidate)
 assert result['summary']==summary
 for k,v in expect.items():
  if isinstance(v,(dict,int)):assert v==summary[k],(k,v,summary[k])
  else:eq(v,summary[k],'tail_summary_amount')
 return dict(members=len(rr),baseline_matches=nb,candidate_matches=na)
for arm in arms:
 for window in ['2022_2024','strong']:tail_checks[arm+'|'+window]=check_tail(arm,window,frozen[window],Q/(arm+'_'+window+'_FIXED_ORIGINAL_TAILS.json'),tail_summary[arm+'|'+window])
 run=runs[arm,'2022_2024'];book=run['book'];cut=next(d for d in run['daily'] if d['at'][:10]=='2024-10-08');split=read(Q/(arm+'_POST_OCT8_OLD_NEW_WEALTH.json'));assert {k:v for k,v in split.items() if k not in ['old_inventory_details','new_layers']}==post_summary[arm];rm={x['layer_in_this_book']:x for x in run['rows']};new=[x for x in run['rows'] if x['opened']>pd.Timestamp(cut['at']).isoformat()];assert split['new_layers']==new;old=Z
 for x,z in zip(cut['layers'],split['old_inventory_details']):
  r=rm[x['id']];assert r['key']==z['key'] and r['sid']==z['sid'] and x['qty']==z['cutoff_quantity'];start=D(z['cutoff_layer_wealth']);eq(start,D(x['cash'])+D(x['dividend'])+(D(z['ending_layer_wealth'])-D(z['period_wealth_change'])-D(x['cash'])-D(x['dividend'])),'old_line_wealth_identity');eq(z['ending_layer_wealth'],r['net'],'old_end_life_net');eq(z['period_wealth_change'],D(r['net'])-start,'old_period_delta');old+=D(z['period_wealth_change'])
 # Independent aggregate old starting wealth: Oct8 total wealth minus all then-flat layers.
 oldids={x['id'] for x in cut['layers']};flat_before=[r for r in run['rows'] if r['opened']<=pd.Timestamp(cut['at']).isoformat() and r['layer_in_this_book'] not in oldids];old_start=D(cut['nav'])-1000000-sum((D(r['net']) for r in flat_before),Z);eq(old,sum((D(z['ending_layer_wealth']) for z in split['old_inventory_details']),Z)-old_start,'old_independent_aggregate_start');newnet=sum((D(x['net']) for x in new),Z);eq(newnet,split['post_cutoff_new_actual_layers']['net'],'post_new_layers_net');eq(old,split['old_inventory_period_wealth_change'],'post_old_inventory_change');eq(old+newnet,D(book['ending_NAV'])-D(cut['nav']),'post_old_new_NAV_bridge');C['post_Oct8_arm_bridge']+=1
 controls=[{'original':r['original_fixed_member']} for r in read(Q/'BASELINE_ORIGINAL303_FULL_ENTRY_MATCH.json')['rows']];assert len(controls)==303;check_tail(arm,'2022_2024',controls,Q/(arm+'_ORIGINAL303_FULL_ENTRY_MATCH.json'),match303[arm])
# Report main tables use displayed rounding, independently checked against NAV35.
report=(P/'REPORT.txt').read_text();S[str(P/'REPORT.txt')]=sha(P/'REPORT.txt');labels=['原退出','另加EMA20','另加EMA60','另加Boll中轨/MA20','另加Boll下轨']
for arm,label in zip(arms,labels):
 line=next(s for s in report.splitlines() if s.startswith(label) and len(re.findall(r'[-+]?\d+\.\d+',s))>=4);nums=[D(x) for x in re.findall(r'[-+]?\d+\.\d+',line)];a=N[arm,'full_2022_2024'];b=N[arm,'strong'];expected=[D(a['ending_NAV'])/10000,D(str(a['max_local_drawdown_pct'])),D(b['ending_NAV'])/10000,D(str(b['max_local_drawdown_pct']))]
 for got,want in zip(nums[-4:],expected):assert abs(got-want)<=D('.00051');C['REPORT_main_table_cell']+=1
notes=[]
if '略低0.231个百分点' in report:notes.append('REPORT lower strong DD exact improvement0.230304939pp; recommends约0.23 instead of subtracting displayed rounded11.660−11.429=0.231.')
out=dict(status='PASS_THIN_NUMERIC_WITH_REPORT_ROUNDING_NOTE' if notes else 'PASS_THIN_NUMERIC',checks=dict(C),fixed_NAV_period_rows=35,fixed_tail_controls_checked=885,original303_cross_arm_controls_checked=1515,tail_scope_counts=tail_checks,report_notes=notes,source_sha256=S,limits=['Reuse completed full10 native financial/source audits. No accounts, indicators or strategy reruns.','Full-entry keys include sid/role/receipt/decision/fill clock; layer IDs never matched across books.','PostOct8 aggregate old inventory start independently reconciles Oct8 NAV minus prior-flat wealth; individual old rows quote values are producer-mark identities, full cold mark provenance reused from prior full account audits.','Tail and original303 matching are endpoint membership/contribution diagnostics; not pure exit causality or equivalent to each arm own later new-layer cohort.'],new_accounts=0)
(O/'FINAL_NAV_TAIL_BRIDGE_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='source_sha256'},ensure_ascii=False,indent=2))
