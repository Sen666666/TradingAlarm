"""Original No60 scale/authorization facts only; no account, rule or replay."""
from pathlib import Path
from decimal import Decimal as D,getcontext
from collections import defaultdict,Counter
import argparse,bisect,csv,hashlib,importlib.util,json,sys
import numpy as np,pandas as pd
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;ENTRY=HERE.parents[1];ROOT=ENTRY/'dec2022_authorization_v1'
PS=ROOT/'followup_robustness_v1/performance/analyze_performance.py'
sp=importlib.util.spec_from_file_location('sealed_original_snapshot_scale',PS);P=importlib.util.module_from_spec(sp);sp.loader.exec_module(P)
getcontext().prec=65;Z=D(0);SRC={};FACTORS={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,gz=False,lines=False):
 p=Path(p);SRC[str(p.resolve())]=sha(p);return P.read(p,gz=gz,lines=lines)
def save(name,x):
 with (OUT/name).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
def dec(x):return D(str(x))
def ep(x):return None if x is None else tuple(x)
def key(x):return json.dumps([x['sid'],x['role'],x.get('receipt'),pd.Timestamp(x['decision_at']).isoformat(),pd.Timestamp(x['opened']).isoformat()],separators=(',',':'),ensure_ascii=False)
def factor(sid,day):
 if sid not in FACTORS:
  m=P.MANIFEST[sid];q=Path(m['refs']['facts']);assert sha(q)==m['output_sha256'][str(q)];SRC[str(q)]=sha(q);FACTORS[sid]=pd.read_parquet(q,columns=['factor'])
 f=FACTORS[sid];i=f.index.searchsorted(pd.Timestamp(day),side='right')-1;assert i>=0 and str(f.index[i].date())<=day;v=dec(f.factor.iloc[i]);assert v>0;return v
def pctile(rr,k):
 a=[float(x[k]) for x in rr if x[k] is not None]
 return None if not a else dict(zip(['p10','median','p90','max'],map(float,np.percentile(a,[10,50,90,100]))))
def summary(rr):
 return dict(layers=len(rr),net=sum((dec(x['outcome_lifecycle_net']) for x in rr),Z),gross_positive=sum((max(Z,dec(x['outcome_lifecycle_net'])) for x in rr),Z),gross_negative=sum((min(Z,dec(x['outcome_lifecycle_net'])) for x in rr),Z),actual_buycash=sum((dec(x['actual_buycash']) for x in rr),Z),entry_nominal_risk=sum((dec(x['actual_initial_nominal_risk']) for x in rr),Z),fixed_tail_members=sum(x['evaluation_fixed_current_tail'] for x in rr),fixed_tail_net=sum((dec(x['outcome_lifecycle_net']) for x in rr if x['evaluation_fixed_current_tail']),Z),initial_nominal_risk_pct_NAV=pctile(rr,'actual_initial_risk_pct_decisionNAV'),buycash_pct_NAV=pctile(rr,'actual_buycash_pct_decisionNAV'),protection_width_pct=pctile(rr,'protection_width_pct'))
def groups(rr,field):return {str(k):summary([x for x in rr if x[field]==k]) for k in sorted({x[field] for x in rr},key=str)}
def pvrbin(v):
 if v is None:return 'UNKNOWN'
 return '<50' if v<50 else '50_to_80' if v<80 else '80_to_90' if v<90 else '90_to_95' if v<95 else '95_to_100'
def corestate(x):
 if x['decision_live_CORE_any_epoch'] and x['watch_epoch'] is None:return 'live_CORE_epoch_unknown'
 if x['decision_live_CORE_same_epoch']:return 'live_CORE_same_epoch'
 if x['decision_live_CORE_any_epoch']:return 'live_CORE_other_epoch'
 return 'no_live_CORE_but_CORE_intent_same_CLOSE' if x['same_CLOSE_CORE_intent'] else 'no_live_CORE_no_CORE_intent'

def process(win):
 r=P.load('BASELINE',win);features=read(ENTRY/'entry_exit_scale/decision_features'/f'{win}_ROWS.json');ff={x['layer']:x for x in features};assert len(ff)==len(r['layers'])
 extended=read(ROOT/'signal_context'/f'{win}_ALL_DECISION_CONTEXT_EXTENDED.json');ext={x['layer']:x for x in extended}
 fixed=read(ENTRY/'entry_exit_scale/analysis_summary/FIXED_ORIGINAL_TAILS.json')[win];fixedkeys={key(x['original']) for x in fixed};fixed_current=fixedkeys&{x['key'] for x in r['layers']};assert len(fixed_current)=={'2022_2024':45,'strong':67}[win]
 rp=P.runpath('BASELINE',win);industry=read(rp/'pair/industry.jsonl.gz',gz=True,lines=True);ind=defaultdict(list)
 for q in industry:ind[q['sector']].append(q)
 for q in ind:ind[q].sort(key=lambda z:z['day'])
 funding=read(rp/'pair/funding.jsonl.gz',gz=True,lines=True);decision_reject=defaultdict(list)
 for x in funding:
  if x['role']=='core':decision_reject[x['at'][:10],x['sid'],x['at']].append(x['result'])
 decisions={x['at'][:10]:x for x in r['book']['decisions']};dmap={x['at'][:10]:(i,x) for i,x in enumerate(r['raw'])}
 intents={};authorized_before={};authcounts=defaultdict(set)
 for d in r['book']['decisions']:
  for i in d['intents']:
   kk=(d['at'][:10],i['sid'],i['role'],i.get('CP1_id'));assert kk not in intents;intents[kk]=i
   if i['role']=='mobile':
    sk=(i['sid'],ep(i['epoch']));assert i['CP1_id'] not in authcounts[sk];authorized_before[kk]=len(authcounts[sk]);authcounts[sk].add(i['CP1_id'])
 # Original audited current CLOSE layers include the actually known per-role
 # reference line. CORE last_core_line is a risk reference, not a separate stop.
 daily=[];snapshots={}
 for j,d in enumerate(r['raw']):
  day=d['at'][:10];nav=dec(d['nav']);stocks=defaultdict(lambda:dict(mark=Z,basis=Z,unrealized=Z,paid_basis_to_line=Z,mark_to_line=Z,CORE_mark=Z,mobile_mark=Z,layers=0,CORE_layers=0,mobile_layers=0));sectors=defaultdict(lambda:dict(mark=Z,basis=Z,paid_basis_to_line=Z,mark_to_line=Z,layers=0));roles=defaultdict(lambda:dict(mark=Z,basis=Z,paid_basis_to_line=Z,mark_to_line=Z,layers=0))
  for h in d['layers']:
   c=r['caps'][j][h['id']];basis=dec(c['basis']);mark=dec(c['mark']);line=h['last_core_line'] if h['role']=='core' else h['floor'];assert line is not None
   floor_value=dec(h['qty'])*dec(line)/factor(h['sid'],day);paid=max(Z,basis-floor_value);giveback=max(Z,mark-floor_value)
   for target in [stocks[h['sid']],sectors[h['sector']],roles[h['role']]]:
    target['mark']+=mark;target['basis']+=basis;target['paid_basis_to_line']+=paid;target['mark_to_line']+=giveback;target['layers']+=1
   s=stocks[h['sid']];s['unrealized']+=mark-basis;s[h['role'].upper()+'_mark' if h['role']=='core' else 'mobile_mark']+=mark;s['CORE_layers' if h['role']=='core' else 'mobile_layers']+=1
  P.eq(sum((x['mark'] for x in stocks.values()),Z),d['inventory'],'scale native inventory')
  row=dict(window=win,day=day,NAV=nav,ACT_on=d['on'],inventory=dec(d['inventory']),exposure=dec(d['inventory'])/nav,paid_basis_to_known_line=sum((x['paid_basis_to_line'] for x in roles.values()),Z),marked_giveback_to_known_line=sum((x['mark_to_line'] for x in roles.values()),Z),roles=dict(roles),stocks=dict(stocks),sectors=dict(sectors))
  row['paid_basis_to_known_line_pct_NAV']=row['paid_basis_to_known_line']/nav*100;row['marked_giveback_to_known_line_pct_NAV']=row['marked_giveback_to_known_line']/nav*100;daily.append(row);snapshots[day]=row
 rows=[];first_epoch=set();first_campaign=set();prior_actual=defaultdict(list);allbyid={x['layer_in_this_book']:x for x in r['layers']}
 for x in sorted(r['layers'],key=lambda z:(z['opened'],z['layer_in_this_book'])):
  lid=x['layer_in_this_book'];f=ff[lid];P.eq(f['cost'],x['cost'],'feature/reader actual cash');P.eq(f['net'],x['net'],'feature/reader outcome');assert key(f)==x['key']
  day=x['decision_at'][:10];j,d=dmap[day];nav=dec(d['nav']);P.eq(nav,f['decision_NAV'],'exact decision NAV');h=[h for h in d['layers'] if h['sid']==x['sid']];cores=[q for q in h if q['role']=='core' and q['qty']>0];epoch=ep(x['watch_epoch']);samecores=[q for q in cores if epoch is not None and ep(q['epoch'])==epoch]
  kk=(day,x['sid'],x['role'],x['receipt']);i=intents[kk];assert i==f['frozen_intent'];live=snapshots[day]['stocks'].get(x['sid']);sector=snapshots[day]['sectors'].get(f['sector']);events=ind[f['sector']];ei=bisect.bisect_right([q['day'] for q in events],day)-1;state=events[ei] if ei>=0 else None
  actual_core_before=[q for q in r['layers'] if q['sid']==x['sid'] and q['role']=='core' and q['opened']<x['decision_at'] and epoch is not None and ep(q['watch_epoch'])==epoch]
  sameopen_core=[q for q in r['layers'] if q['sid']==x['sid'] and q['role']=='core' and q['opened']==x['opened']]
  core_intent=any(q['sid']==x['sid'] and q['role']=='core' for q in decisions[day]['intents']);ek=(x['sid'],epoch);ck=(x['sid'],f['baseline_campaign_number']);previous=[q for q in prior_actual[ek] if q['opened']<x['decision_at']]
  nominal=dec(f['actual_fill_quantity'])*max(Z,dec(f['actual_execution_price'])-dec(f['initial_raw_floor']));P.eq(nominal,f['actual_initial_nominal_risk'],'filled nominal risk')
  row=dict(window=win,layer=lid,key=x['key'],sid=x['sid'],name=f['name'],sector=f['sector'],industry=f['industry'],role=x['role'],actual_entry_action=x['actual_entry_action'],decision_at=x['decision_at'],opened=x['opened'],closed=x['closed'],watch_epoch=x['watch_epoch'],stock_structure=r['book']['metadata'][str(lid)]['stock_structure'],receipt=x['receipt'],decision_NAV=nav,actual_buycash=dec(x['cost']),actual_initial_nominal_risk=nominal,actual_initial_risk_pct_decisionNAV=dec(f['actual_initial_risk_pct_decisionNAV']),actual_buycash_pct_decisionNAV=dec(f['actual_buycash_pct_decisionNAV']),protection_width_pct=dec(f['width_pct']),decision_plan_gross_pct_NAV=dec(f['decision_budget_pct_NAV']),decision_plan_cap_nominal_risk_pct_NAV=dec(f['decision_cap_nominal_risk_pct_NAV']),decision_plan_core_allin_budget=f['existing_core_allin_risk_budget'],decision_PVR=i.get('PVR_score') if i.get('PVR_ready') else None,decision_PVR_rank=i.get('priority_rank'),industry_market_stage=ext[lid]['industry_original_market_state']['stage_name'],industry_financial_level=None if state is None else state['financial_level'],industry_financial_level_last_event_day=None if state is None else state['day'],industry_financial_level_source='UNKNOWN_NO_LOGGED_COLD_SEED' if state is None else 'latest_native_stage_change_event_at_or_before_decision',actual_pool_at_fill=f['pool_at_fill'],decision_live_CORE_any_epoch=bool(cores),decision_live_CORE_same_epoch=None if epoch is None else bool(samecores),decision_live_CORE_ids=[q['id'] for q in cores],decision_prior_CORE_funded_same_epoch=None if epoch is None else len(actual_core_before),same_CLOSE_CORE_intent=core_intent,decision_CORE_rejection_logs=decision_reject.get((day,x['sid'],d['at']),[]),same_OPEN_actual_CORE_filled_diagnostic_only=bool(sameopen_core),decision_stock_layers=len(h),decision_stock_unrealized=Z if live is None else live['unrealized'],decision_stock_mark_pct_NAV=Z if live is None else live['mark']/nav*100,decision_stock_paid_basis_to_line_pct_NAV=Z if live is None else live['paid_basis_to_line']/nav*100,decision_sector_mark_pct_NAV=Z if sector is None else sector['mark']/nav*100,decision_sector_paid_basis_to_line_pct_NAV=Z if sector is None else sector['paid_basis_to_line']/nav*100,decision_portfolio_paid_basis_to_line_pct_NAV=snapshots[day]['paid_basis_to_known_line_pct_NAV'],funded_mobile_before_decision_same_epoch=None if epoch is None else sum(q['role']=='mobile' for q in previous),prior_authorized_mobile_intents_same_epoch=authorized_before[kk] if x['role']=='mobile' and epoch is not None else None,first_actual_mobile_in_epoch=None if epoch is None else x['role']=='mobile' and ek not in first_epoch,first_actual_mobile_in_campaign=x['role']=='mobile' and ck not in first_campaign,evaluation_fixed_current_tail=x['key'] in fixed_current,outcome_lifecycle_net=dec(x['net']),outcome_strict_realized=dec(x['strict_realized']),outcome_open_unrealized=dec(x['open_unrealized']),outcome_AR=dec(x['AR']))
  row['PVR_bin']=pvrbin(row['decision_PVR']);row['CORE_funding_state']=corestate(row);row['prior_stock_profit_state']='no_live_position' if not h else 'positive' if row['decision_stock_unrealized']>0 else 'negative' if row['decision_stock_unrealized']<0 else 'zero'
  row['stage_CORE_profit_cell']='|'.join([str(row['industry_market_stage']),row['CORE_funding_state'],row['prior_stock_profit_state']]);row['entry_cohort_year']=x['opened'][:4]
  rows.append(row);prior_actual[ek].append(x)
  if x['role']=='mobile':first_epoch.add(ek);first_campaign.add(ck)
 P.eq(sum((x['outcome_lifecycle_net'] for x in rows),Z),dec(r['book']['ending_NAV'])-1000000,'full original layer contribution identity')
 save(win+'_ALL_LAYER_SCALE_CONTEXT.json',rows);save(win+'_DAILY_CAPITAL_RISK_CONTEXT.json',daily)
 g={field:groups(rows,field) for field in ['role','actual_entry_action','entry_cohort_year','PVR_bin','industry_market_stage','industry_financial_level','actual_pool_at_fill']}
 mobile=[x for x in rows if x['role']=='mobile'];first=[x for x in mobile if x['first_actual_mobile_in_epoch']]
 g['mobile_by_CORE_funding_state']=groups(mobile,'CORE_funding_state');g['mobile_by_prior_profit']=groups(mobile,'prior_stock_profit_state');g['mobile_by_authorization_number']=groups(mobile,'prior_authorized_mobile_intents_same_epoch');g['mobile_by_funded_previous_number']=groups(mobile,'funded_mobile_before_decision_same_epoch');g['first_mobile_epoch_by_CORE_state']=groups(first,'CORE_funding_state');g['mobile_stage_CORE_profit_cells']=groups(mobile,'stage_CORE_profit_cell')
 save(win+'_DESCRIPTIVE_GROUPS.json',g)
 snap=dict(window=win,all=summary(rows),mobile=summary(mobile),first_mobile_in_epoch=summary(first),daily_observations=len(daily),portfolio_paid_basis_to_line_pct_NAV=pctile(daily,'paid_basis_to_known_line_pct_NAV'),marked_giveback_to_line_pct_NAV=pctile(daily,'marked_giveback_to_known_line_pct_NAV'),largest_paid_basis_risk_days=sorted(daily,key=lambda x:x['paid_basis_to_known_line_pct_NAV'],reverse=True)[:3],unique_authorized_mobile_receipts=sum(len(v) for v in authcounts.values()),actual_mobile_receipts=len({x['receipt'] for x in mobile}),limits='Nominal entry and current known-line references are not guaranteed maximum risk; CORE line is not independent hard stop. Mark-to-line includes normal trend profit giveback and is not an optimization target. Lifecycle group sums are descriptions, not avoidable-loss causal savings.')
 return rows,snap

def main():
 global OUT
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=HERE/'results_v3');a=p.parse_args();OUT=a.out;assert not OUT.exists();OUT.mkdir(parents=True)
 try:
  P.META_ROWS=read(P.META);P.MANIFEST={x['symbol']:x for x in read(P.W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};P.VALID=read(ROOT/'account_comparison/results_v1/VALIDATION.json');assert P.VALID['status']=='PASS_ALL_FIXED_32_PERIODS'
  allrows=[];summaries={}
  for win in ['2022_2024','strong']:
   rr,ss=process(win);allrows+=rr;summaries[win]=ss;print('SCALE_DONE',win,len(rr),flush=True)
  assert len(allrows)==3436
  save('SUMMARY.json',summaries);fields=[k for k,v in allrows[0].items() if not isinstance(v,(dict,list))]
  with (OUT/'ALL_LAYER_SCALE_CONTEXT.csv').open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(allrows)
  save('VALIDATION.json',dict(status='PASS_DESCRIPTIVE_ORIGINAL3436_NO_NEW_ACCOUNT',layers=3436,original_basis_reader=str(PS),new_accounts=0,new_account_events=0,decision_CLOSE_CORE_primary=True,same_CLOSE_plan_and_future_same_OPEN_fill_separate=True,whole_lifecycle_money_is_not_annual_monthly_money=True,no_linear_shrinkage_savings_claim=True,limits=['CORE reference is not a separate original hard stop; raw OPEN gaps/capacity/fees can exceed nominal line risk.','Marked giveback includes winners normal unrealized gains; do not optimize it as a loss label.','All groups use decision-known states; terminal P&L and fixed tails are evaluation only.','Current industry snapshot/consumed historical/native execution proxy limitations remain.']))
 except BaseException as e:save('FAILURE.json',dict(error=repr(e),new_accounts=0,preserve_partial=True));raise
 finally:
  SRC.update(P.SRC);SRC[str(Path(__file__).resolve())]=sha(__file__);SRC[str(PS)]=sha(PS);save('SOURCE_SHA256.json',SRC);save('DELIVERABLE_SHA256.json',{str(p.resolve()):sha(p) for p in OUT.iterdir() if p.is_file() and p.name!='DELIVERABLE_SHA256.json'})
if __name__=='__main__':main()
