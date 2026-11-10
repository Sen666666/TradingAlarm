"""Original MOBILE fills/preceding market CLOSE G1 only; no Account/strategy run."""
from pathlib import Path
from decimal import Decimal as D,getcontext
from collections import defaultdict,Counter
import bisect,csv,gzip,hashlib,json,math
import pandas as pd

getcontext().prec=50
O=Path(__file__).resolve().parent;Q=O.parents[1]
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
Z=D(0);SRC={};frames={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,gz=False,lines=False):
 p=Path(p);SRC[str(p.resolve())]=sha(p)
 with (gzip.open(p,'rt') if gz else p.open()) as f:return [json.loads(s) for s in f] if lines else json.load(f)
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,(D,pd.Timestamp)):return str(x)
 if hasattr(x,'item'):x=x.item()
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def csvsave(n,rr):
 with (O/n).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(clean(rr))
def eq(a,b,label):assert abs(D(str(a))-D(str(b)))<D('1e-17'),(label,a,b)

sm={r['symbol']:r for r in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
def facts(sid):
 if sid not in frames:
  m=sm[sid];p=Path(m['refs']['facts']);assert sha(p)==m['output_sha256'][str(p)];SRC[str(p)]=sha(p)
  frames[sid]=pd.read_parquet(p,columns=['g_grade','g_ready','raw_close','factor','segment_id'])
 return frames[sid]
def at(f,day):
 i=f.index.searchsorted(pd.Timestamp(day),side='right')-1
 return (None,None) if i<0 else (str(f.index[i].date()),f.iloc[i])
def classify(ready,grade,exact):
 if not exact:return 'UNKNOWN_NO_EXACT_PREVIOUS_CLOSE'
 if ready is None:return 'UNKNOWN_GRADE_READY'
 if ready is False:return 'UNREADY'
 if grade is None:return 'UNKNOWN_NAN_GRADE'
 if grade<0:return 'NEGATIVE'
 if grade==0:return 'ZERO'
 if grade==1:return 'ONE'
 if grade>=2:return 'WARM_GE2'
 return 'OTHER_READY_BELOW2'

cohorts={};carry=[];clock_receipts=[];cross={};inputs={}
for window,lo,hi,label in [('2022_2024','2022-01-04','2024-12-31','A_2022_2024_NEW_FILLS'),('strong','2026-01-01','2026-06-30','B_2026H1_NEW_FILLS')]:
 base=Q/'trend_exit_controls_v1/runs/BASELINE'/window/'pair';book=read(base/'B.json.gz',True);daily=read(base/'daily.jsonl.gz',True,True);clocks=[d['at'] for d in daily]
 states={r['layer']:r for r in read(Q/'structural_failure_v1/state_semantics'/(window+'_ROWS.json'))}
 rich={r['layer_in_this_book']:r for r in read(Q/'dec2022_authorization_v1/account_comparison/results_v1'/('BASELINE_'+window+'_LAYERS.json'))}
 native={r['id']:r for r in book['layers']};selected=[]
 cut=None
 if window=='strong':cut=next(d for d in daily if d['at'][:10]=='2025-12-31');carryids={r['id'] for r in cut['layers'] if r['kind']=='add'}
 else:carryids=set()
 sellparts=defaultdict(list)
 for ti,t in enumerate(book['trades']):
  if t['side']=='sell':
   for pi,p in enumerate(t['parts']):sellparts[p['layer']].append(dict(trade_index=ti,part_index=pi,at=t['at'],shares=p['shares'],net_cash=p['net_cash'],allocated_fee=D(p['shares'])*D(t['price'])-D(p['net_cash']),price=t['price']))
 for ti,t in enumerate(book['trades']):
  if t['side']!='buy' or t['kind']!='add':continue
  main=lo<=t['at'][:10]<=hi;iscarry=t['layer'] in carryids
  if not main and not iscarry:continue
  lid=t['layer'];sid=t['security_id'];s=states[lid];r=rich[lid];n=native[lid]
  assert s['role']==r['role']=='mobile'
  idx=bisect.bisect_left(clocks,t['at'])-1;prev=None if idx<0 else clocks[idx];prevday=None if prev is None else prev[:10]
  intent=book['metadata'][str(lid)]['budget_order'].split('|')[1];matched=prev is not None and pd.Timestamp(prev)==pd.Timestamp(intent)
  assert pd.Timestamp(s['opened'])==pd.Timestamp(t['at']) and pd.Timestamp(s['decision_at'])==pd.Timestamp(intent)
  srcday,f=(None,None) if prevday is None else at(facts(sid),prevday)
  ready=None if f is None or pd.isna(f.g_ready) else bool(f.g_ready);grade=None if f is None or pd.isna(f.g_grade) or not math.isfinite(float(f.g_grade)) else float(f.g_grade)
  exact=srcday==prevday;old=s['original_stock_state'];grade_matches=grade==old.get('g_grade') and ready==old.get('g_ready')
  if matched and exact:assert grade_matches,(window,lid,grade,old.get('g_grade'))
  gross=D(t['gross_cny']);bf=D(t['fees_cny']);sf=sum((p['allocated_fee'] for p in sellparts[lid]),Z);cost=gross+bf
  real=D(s['strict_realized']);unreal=D(s['open_unrealized']);ar=D(s['recognized_dividend_AR']);net=D(s['net']);value=D(r['value']);basis=D(s['remaining_basis'])
  eq(cost,s['cost'],'actual buycost');eq(bf,s['buy_fee'],'buyfee');eq(sf,s['sell_fee'],'allocated sellfee');eq(real+unreal+ar,net,'component net');eq(net,r['net'],'rich original net');eq(D(n['cash'])+value+D(n['dividend']),net,'native cash+endmark+AR');eq(real-D(n['cash']),basis,'real/cash/basis');eq(unreal,value-basis,'unreal/endmark/basis')
  closed=n['qty']==0;assert closed==(s['qty']==0)
  row=dict(cohort=label if main else 'B_2025_YEAR_END_CARRY',original_account_window=window,endpoint_at=daily[-1]['at'],layer=lid,sid=sid,name=s['name'],industry=s['industry'],sector=s['sector'],
   actual_fill_at=t['at'],actual_fill_shares=t['shares'],book_buy_trade_index=ti,previous_A_market_CLOSE_at=prev,intent_decision_at=intent,previous_CLOSE_equals_intent=matched,ROWS_identity_exact=True,
   grade_source_day=srcday,exact_previous_CLOSE_observation=exact,G1_grade=grade,G1_grade_ready=ready,G1_bucket=classify(ready,grade,exact),ROWS_original_grade=old.get('g_grade'),ROWS_grade_matches_direct_facts=grade_matches,
   actual_buy_gross=gross,actual_buy_fee=bf,actual_input_gross_plus_buy_fee=cost,actual_allocated_sell_fee_by_endpoint=sf,total_actual_fees_by_endpoint=bf+sf,
   original_strict_realized=real,original_open_unrealized=unreal,original_dividend_AR=ar,original_endpoint_net_contribution=net,closed_by_endpoint=closed,ending_qty=n['qty'],ending_mark_value=value,remaining_paid_basis=basis,
   closed_at=n['closed'],signal_fill_cross_calendar_year=pd.Timestamp(intent).year!=pd.Timestamp(t['at']).year,
   holding_cross_calendar_year=pd.Timestamp(t['at']).year < pd.Timestamp(n['closed'] if closed else daily[-1]['at']).year,
   actual_sell_parts=sellparts[lid],original_stock_structure=book['metadata'][str(lid)].get('stock_structure'),watch_epoch=s.get('watch_epoch'),
   provenance='Grade is direct frozen facts at actual fill preceding original A market CLOSE, not fill-day CLOSE. Money is original account endpoint, not filtered strategy return.')
  if main:selected.append(row)
  if iscarry:
   h=next(h for h in cut['layers'] if h['id']==lid);fd,ff=at(facts(sid),cut['at'][:10]);known=fd==cut['at'][:10]
   startmark=D(h['qty'])*D(str(ff.raw_close)) if known else None;startwealth=D(h['cash'])+startmark+D(h['dividend']) if known else None
   cr=dict(row,cohort='B_2025_YEAR_END_CARRY',carry_cutoff_at=cut['at'],carry_cutoff_qty=h['qty'],carry_cutoff_original_layer_snapshot=h,carry_mark_source_day=fd,carry_cutoff_exact_raw_mark_known=known,carry_cutoff_raw_mark=None if not known else str(ff.raw_close),carry_cutoff_mark_value=startmark,carry_cutoff_layer_wealth=startwealth,
    original_2026H1_wealth_change_from_carry=None if startwealth is None else net-startwealth,actual_allocated_sell_fee_2026H1=sum((p['allocated_fee'] for p in sellparts[lid] if '2026-01-01'<=p['at'][:10]<='2026-06-30'),Z),
    carry_scope='Not a 2026 new fill. G1 is original 2025 acquisition clock; life contribution through Jun30 and optional Dec31-to-Jun30 wealth change are separately named. Exact Dec31 same-day raw source only; otherwise period wealth UNKNOWN. No native mark model invoked.')
   carry.append(cr)
 cohorts[label]=selected
 clock_receipts.append(dict(cohort=label,actual_mobile_fills=len(selected),previous_market_CLOSE_equals_intent=sum(r['previous_CLOSE_equals_intent'] for r in selected),clock_mismatches=[r for r in selected if not r['previous_CLOSE_equals_intent']],direct_fact_exact_previous_day=sum(r['exact_previous_CLOSE_observation'] for r in selected),ROWS_grade_exact=sum(r['ROWS_grade_matches_direct_facts'] for r in selected),ready_counts=dict(Counter(str(r['G1_grade_ready']) for r in selected)),ending_NAV=book['ending_NAV'],endpoint_at=daily[-1]['at']))
 cross[label]=dict(holding_cross_year=[r for r in selected if r['holding_cross_calendar_year']],signal_fill_cross_year=[r for r in selected if r['signal_fill_cross_calendar_year']])
 inputs[window]=dict(book=str((base/'B.json.gz').resolve()),daily=str((base/'daily.jsonl.gz').resolve()),ROWS=str((Q/'structural_failure_v1/state_semantics'/(window+'_ROWS.json')).resolve()))

save('ACTUAL_FILL_PREVIOUS_CLOSE_CLOCK_AUDIT.json',clock_receipts)
save('A_2022_2024_MOBILE_ROWS.json',cohorts['A_2022_2024_NEW_FILLS']);save('B_2026H1_NEW_MOBILE_ROWS.json',cohorts['B_2026H1_NEW_FILLS']);save('B_2025_CARRY_MOBILE_ROWS.json',carry);save('CROSS_YEAR_LAYERS_AND_SIGNAL_FILL.json',cross)
for name,rr in [('A_2022_2024_MOBILE_ROWS.csv',cohorts['A_2022_2024_NEW_FILLS']),('B_2026H1_NEW_MOBILE_ROWS.csv',cohorts['B_2026H1_NEW_FILLS']),('B_2025_CARRY_MOBILE_ROWS.csv',carry)]:
 flat=[{k:(json.dumps(clean(v),ensure_ascii=False) if isinstance(v,(dict,list)) else v) for k,v in r.items()} for r in rr];csvsave(name,flat)

def summary(cohort,group,rr):
 return dict(cohort=cohort,grade_group=group,layers=len(rr),actual_fill_shares=sum(r['actual_fill_shares'] for r in rr),actual_input_gross_plus_buy_fee=sum((r['actual_input_gross_plus_buy_fee'] for r in rr),Z),actual_buy_gross=sum((r['actual_buy_gross'] for r in rr),Z),actual_buy_fee=sum((r['actual_buy_fee'] for r in rr),Z),actual_allocated_sell_fee_by_endpoint=sum((r['actual_allocated_sell_fee_by_endpoint'] for r in rr),Z),total_actual_fees_by_endpoint=sum((r['total_actual_fees_by_endpoint'] for r in rr),Z),original_strict_realized=sum((r['original_strict_realized'] for r in rr),Z),original_open_unrealized=sum((r['original_open_unrealized'] for r in rr),Z),original_dividend_AR=sum((r['original_dividend_AR'] for r in rr),Z),original_endpoint_net_contribution=sum((r['original_endpoint_net_contribution'] for r in rr),Z),fully_closed_layers=sum(r['closed_by_endpoint'] for r in rr),open_layers=sum(not r['closed_by_endpoint'] for r in rr),holding_cross_year_layers=sum(r['holding_cross_calendar_year'] for r in rr),signal_fill_cross_year_layers=sum(r['signal_fill_cross_calendar_year'] for r in rr))
ss=[]
for cohort,rr in cohorts.items():
 ss.append(summary(cohort,'ALL_MOBILE',rr))
 groups=[('LT2_READY',[r for r in rr if r['G1_bucket'] in ['NEGATIVE','ZERO','ONE','OTHER_READY_BELOW2']])]
 groups.extend((name,[r for r in rr if r['G1_bucket']==name]) for name in ['NEGATIVE','ZERO','ONE','WARM_GE2','UNREADY','UNKNOWN_GRADE_READY','UNKNOWN_NAN_GRADE','UNKNOWN_NO_EXACT_PREVIOUS_CLOSE','OTHER_READY_BELOW2'])
 groups.extend(('WARM_'+str(g),[r for r in rr if r['G1_bucket']=='WARM_GE2' and r['G1_grade']==g]) for g in [2,3,4])
 for name,gg in groups:ss.append(summary(cohort,name,gg))
save('SUMMARY.json',ss);csvsave('SUMMARY.csv',ss)
save('CARRY_SUMMARY.json',dict(original_2025_year_end_mobile_carry_layers=len(carry),original_grade_acquisition_clock='2025 fill preceding A market CLOSE, never treated as 2026 new fill',lifetime_through_Jun30=summary('B_2025_YEAR_END_CARRY','ALL_MOBILE_CARRY',carry),carry_with_exact_Dec31_raw_mark=sum(r['carry_cutoff_exact_raw_mark_known'] for r in carry),carry_with_unknown_Dec31_mark=sum(not r['carry_cutoff_exact_raw_mark_known'] for r in carry),original_2026H1_carry_wealth_change_sum_known_only=sum((r['original_2026H1_wealth_change_from_carry'] for r in carry if r['original_2026H1_wealth_change_from_carry'] is not None),Z)))
save('SOURCE_MANIFEST.json',dict(source_sha256=SRC,script_sha256=sha(__file__),facts_symbols_read=len(frames),inputs=inputs,new_accounts=0,new_models=0,new_backtests=0,strategy_imports=0))
save('VALIDATION.json',dict(status='PASS_ORIGINAL_BOOK_AND_FROZEN_FACTS_STATIC_EXTRACTION',clock_audits=clock_receipts,carry_layers=len(carry),component_and_native_wealth_identities_checked=True,grade_timing='actual fill immediately preceding original A market CLOSE, not fill-day CLOSE and not one bar before intent',endpoints_separate=True,LT2_group_overlaps_negative_zero_one_not_disjoint_from_them=True,new_accounts=0,new_models=0,new_backtests=0,new_strategy_returns=0))
print(json.dumps(clean(dict(clock=clock_receipts,carry=len(carry),facts_symbols=len(frames),summaries=[r for r in ss if r['grade_group'] in ['LT2_READY','NEGATIVE','ZERO','ONE','WARM_GE2']])) ,ensure_ascii=False))
