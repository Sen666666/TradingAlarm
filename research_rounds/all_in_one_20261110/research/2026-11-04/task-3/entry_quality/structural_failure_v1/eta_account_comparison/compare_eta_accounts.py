"""Finished BASE/ETA paths only. No Account, Runner, replay or score recompute.

Reuse the previously checked financial/basis and period readers. New metadata
gets an explicit in-memory arm label; no actual RUN_METADATA byte is changed.
Legacy EMA/H2 schema fields are temporary read-compatibility, not ETA inputs.
"""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D,getcontext
import argparse,csv,gzip,hashlib,importlib.util,json,math,sys
sys.dont_write_bytecode=True;getcontext().prec=65
HERE=Path(__file__).resolve().parent;S=HERE.parent;E=S.parent;H=E/'dec2022_authorization_v1';ETA=S/'pvr_eta_v1';OLD=E/'trend_exit_controls_v1'
def load(name,p):
 sp=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
M=load('eta_sealed_financial_reader',OLD/'execution_review/account_comparison/compare_accounts.py')
P=load('eta_sealed_period_reader',H/'followup_robustness_v1/performance/analyze_performance.py')
MARK_MODULE=load('eta_native_close_valuation_reference',S/'independent_review/native_mark_sidecar.py')
MARKS=MARK_MODULE.NativeCloseMarks();ORIGINAL_FACT_QUOTE=M.quote;MARK_DIFFERENCES={}
STAGES=[('P01_2022H1','2022-01-01','2022-06-30'),('P02_2022JulNov','2022-07-01','2022-11-30'),('P03_Dec2022','2022-12-01','2022-12-31'),('P04_2023JanApr','2023-01-01','2023-04-30'),('P05_2023MayJul','2023-05-01','2023-07-31'),('P06_2023Aug_2024Jan','2023-08-01','2024-01-31'),('P07_2024FebMay','2024-02-01','2024-05-31'),('P08_2024Jun_Sep23','2024-06-01','2024-09-23'),('P09_2024Sep24_Oct8','2024-09-24','2024-10-08'),('P10_after2024Oct8','2024-10-09','2024-12-31')]
Z=D(0);SRC={};VIRTUAL={};M_READ=M.read;P_READ=P.read
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,gz=False,lines=False):
 p=Path(p);SRC[str(p.resolve())]=sha(p)
 with (gzip.open(p,'rt') if gz else p.open()) as f:return [json.loads(x) for x in f] if lines else json.load(f)
def save(out,n,v):
 with (out/n).open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
def valuation_reference(sid,day):
 # Retain the frozen signal-factor field only for the unused legacy diagnostic;
 # financial CLOSE marks use the exact original native raw/action policy.
 old=ORIGINAL_FACT_QUOTE(sid,day);price,detail=MARKS.at(sid,day)
 if price!=old[0]:MARK_DIFFERENCES[sid+'|'+day]=dict(detail,old_facts_carry=str(old[0]),old_fact_day=old[2],is_tradable_quote=False)
 return price,old[1],detail['raw_observed_day']
M.quote=valuation_reference;P.quote=lambda sid,day:valuation_reference(sid,day)[0]
def runpath(arm,win):return OLD/'runs/BASELINE'/win if arm=='BASELINE' else ETA/'runs'/win
def auditpath(arm,win):return OLD/'independent_review'/f'BASELINE_{win}_ACCOUNT_AUDIT.json' if arm=='BASELINE' else S/'independent_review'/f'PVR_ETA_{win}_ACCOUNT_AUDIT.json'
def is_eta_audit_alias(p):return Path(p).name.startswith('ETA_') and Path(p).name.endswith('_ACCOUNT_AUDIT.json')
def resolve_read(p,original,gz=False,lines=False):
 p=Path(p)
 if is_eta_audit_alias(p):
  win=p.name.removeprefix('ETA_').removesuffix('_ACCOUNT_AUDIT.json');p=auditpath('ETA',win)
 v=original(p,gz=gz,lines=lines)
 if p.name=='RUN_METADATA.json' and p.parent.parent==ETA/'runs':
  assert 'arm' not in v;assert v['policy']=='PVR_ETA_ORIGINAL_E21_MASS_SHARE_SLOT_ONLY_V1';return dict(v,arm='ETA')
 return v
def mread(p,gz=False,lines=False):return resolve_read(p,M_READ,gz,lines)
def pread(p,gz=False,lines=False):
 k=str(Path(p).resolve())
 return VIRTUAL[k] if k in VIRTUAL else resolve_read(p,P_READ,gz,lines)
M.read=mread;P.read=pread;P.runpath=runpath;M.PERIODS={'2022_2024':[],'strong':[]}
class UnusedLegacyDiagnostic:
 def at(self,sid,at,unused):
  return dict(status='UNKNOWN',day=str(at)[:10],causal_close=None,line=None,source_segment=None,source_max_day=None,unknown_reason='Legacy indicator diagnostic intentionally absent in priority-only study')

def analyze(arm,win,calendar):
 M.ROOT=OLD if arm=='BASELINE' else S
 if arm=='ETA':M.INDICATORS[arm]='UNUSED_LEGACY_DIAGNOSTIC'
 r=M.analyze_run(arm,win,runpath(arm,win),UnusedLegacyDiagnostic(),calendar)
 rawmeta=read(runpath(arm,win)/'RUN_METADATA.json');book=read(runpath(arm,win)/'pair/B.json.gz',gz=True);intents={(d['at'][:10],i['sid'],i['role'],i.get('CP1_id')):i for d in book['decisions'] for i in d['intents']};actual_buys={t['layer']:t for t in book['trades'] if t['side']=='buy'}
 for x in r['layers']:
  for k in ['entry_decision_tool','entry_day_CLOSE_tool','buy_OPEN_vs_prior_decision_line_below','entry_day_CLOSE_is_after_buy_and_not_known_at_OPEN']:x.pop(k,None)
  i=intents[x['decision_at'][:10],x['sid'],x['role'],x['receipt']];x.update(priority_score_at_decision=i.get('PVR_score'),priority_ready=i.get('PVR_ready'),priority_rank_at_decision=i.get('priority_rank'),original_H1_rank_at_decision=i.get('original_H1_rank'),priority_score_units='raw_eta[-1,1]_native_PVR_field_alias' if arm=='ETA' else 'original_PVR[0,100]',legacy_actual_trade_pvr_H1_value=actual_buys[x['layer_in_this_book']].get('pvr'),frozen_native_H1_score=i.get('score'),H2_entry_context={'sector':P.META_ROWS[x['sid']]['sector_id']})
  if x['legacy_actual_trade_pvr_H1_value'] is not None and x['frozen_native_H1_score'] is not None:M.eq(x['legacy_actual_trade_pvr_H1_value'],x['frozen_native_H1_score'],'Legacy actual_trade.pvr is H1 score, not priority',tolerance='0.000000001')
  assert set(x['actual_exit_reasons'])<=M.NATIVE_REASONS,'Priority-only study added an exit reason'
  if arm=='ETA' and x['priority_ready']:assert x['priority_score_at_decision'] is not None and math.isfinite(x['priority_score_at_decision']) and -1-1e-12<=x['priority_score_at_decision']<=1+1e-12
 P.ROOT=M.ROOT;P.PREV=HERE/'__memory_financial_views__';VIRTUAL[str((P.PREV/f'{arm}_{win}_LAYERS.json').resolve())]=r['layers'];VIRTUAL[str((P.PREV/f'{arm}_{win}_DAILY_WEALTH_SPLIT.json').resolve())]=r['daily']
 val=dict(r['validation'],partial_basis_state_points={str(k):v for k,v in r['validation']['partial_basis_state_points'].items()});P.VALID={'native_daily_mark_wealth_and_partial_basis':{arm+'|'+win:val}}
 pr=P.load(arm,win)
 for x in r['layers']:x.pop('H2_entry_context',None)
 r['metadata_read_compatibility_only']=dict(actual_metadata_has_arm='arm' in rawmeta,view_arm=arm,actual_RUN_METADATA_unchanged=True,legacy_indicator_diagnostic_not_used=True)
 return r,pr

def slip(book,start,end):
 total=Z
 for t in book['trades']:
  if start<=t['at'][:10]<=end:
   price=D(t['price']);raw=D(t['raw_open']);q=t['shares'];M.eq(price*q,t['gross_cny'],'actual native gross');v=(price-raw)*q if t['side']=='buy' else (raw-price)*q;assert v>=0;total+=v
 return total
def whole_tail(base,r,t):
 sets={'all_original83_94_stocks':{x['original_fixed_member']['sid'] for x in t['rows']},'current_No60_matched45_67_stocks':{x['original_fixed_member']['sid'] for x in t['rows'] if x['baseline_current_exact_match'] is not None}}
 out={}
 for label,ids in sets.items():
  bb=[x for x in base['layers'] if x['sid'] in ids];rr=[x for x in r['layers'] if x['sid'] in ids]
  out[label]=dict(stocks=len(ids),baseline_all_entry_contribution=sum((x['net'] for x in bb),Z),candidate_all_entry_contribution=sum((x['net'] for x in rr),Z),candidate_never_traded_stocks=sorted(ids-{x['sid'] for x in rr}),candidate_entries=len(rr))
 return out
def act_changes(base,r):return M.matching(base,r)
def group_differences(bd,rd,delta):
 out={}
 for field in ['stock','month','sector']:
  bb={x['group']:x for x in bd['group_rows'][field]};rr={x['group']:x for x in rd['group_rows'][field]};rows=[]
  for k in sorted(bb.keys()|rr.keys()):
   b=bb.get(k,{});a=rr.get(k,{});bn=D(b.get('wealth',0));an=D(a.get('wealth',0));row=dict(group=k,BASE_true_period_contribution=bn,ETA_true_period_contribution=an,delta=an-bn)
   if field=='stock':row.update(name=P.META_ROWS[k]['name'],industry=P.META_ROWS[k]['industry'])
   rows.append(row)
  M.eq(sum((x['delta'] for x in rows),Z),delta,'all '+field+' contribution delta')
  out[field]=dict(all_rows=rows,largest_positive=sorted([x for x in rows if x['delta']>0],key=lambda x:x['delta'],reverse=True)[:5],largest_negative=sorted([x for x in rows if x['delta']<0],key=lambda x:x['delta'])[:5])
 return out
def priority_logs(arm,win,layers):
 logs=read(runpath(arm,win)/'pair/rank-policy.jsonl.gz',gz=True,lines=True);days=defaultdict(list)
 for x in logs:days[x['day']].append(x)
 tied=0;one=0;ready=0;unknown=0;lookup={}
 for rows in days.values():
  assert len({x['sid'] for x in rows})==len(rows)
  for x in rows:lookup[x['day'],x['sid']]=x
  known=[x for x in rows if x['PVR_ready']];ready+=len(known);unknown+=len(rows)-len(known);c=Counter(round(float(x['PVR']),12) for x in known);tied+=sum(n for n in c.values() if n>1)
  if arm=='ETA':
   assert all(-1-1e-12<=float(x['PVR'])<=1+1e-12 for x in known);one+=sum(round(float(x['PVR']),12)==1 for x in known)
 for x in layers:
  q=lookup[x['decision_at'][:10],x['sid']];assert bool(x['priority_ready'])==bool(q['PVR_ready'])
  if x['priority_ready']:M.eq(x['priority_score_at_decision'],q['PVR'],'Actual fill frozen-intent priority versus true ranklog',tolerance='0.000000000001')
  else:assert x['priority_score_at_decision'] is None and q['PVR'] is None
  assert x['priority_rank_at_decision']==q['priority_rank'] and x['original_H1_rank_at_decision']==q['original_H1_rank']
 return dict(arm=arm,window=win,eligible_unique_stock_day_queries=len(logs),ready_queries=ready,UNKNOWN_native_H1_slot_queries=unknown,queries_in_same_day_round12_ties=tied,raw_eta_round12_equal1_queries=one if arm=='ETA' else None,actual_filled_layers_true_priority_ranklog_join=len(layers),legacy_trade_pvr_checked_as_H1_only=True,units='raw_eta[-1,1], original field PVR compatibility alias' if arm=='ETA' else 'original PVR[0,100]',limitation='Counts are actual native priority queries, not independent signals or missed profits. Eligible universes and ACT/capital/core histories can change endogenously.')
def representative_chains(base,r,stage_details):
 source=read(S/'chains/COMPLETE_ORIGINAL_CHAINS.json');read(S/'chains/SELECTION_FREEZE.json');assert len(source)==13 and sum(not x['attached_control'] for x in source)==10
 out=[]
 for item in source:
  c=item['campaign'];assert c['window']=='2022_2024';keys=set(c['entry_keys']);bb=[base['bykey'][k] for k in keys];M.eq(sum((x['net'] for x in bb),Z),c['endpoint_net'],'original frozen representative campaign')
  same=[r['bykey'][k] for k in keys if k in r['bykey']];sid=c['sid'];allstock=[x for x in r['layers'] if x['sid']==sid];end=c['closed'] or r['daily'][-1]['at'];overlap=[x for x in allstock if x['opened']<end and (x['closed'] is None or x['closed']>c['opened'])];exact_stage={};stock_stage={}
  for label,detail in stage_details.items():
   exact=[x for x in detail['layer_rows'] if x['key'] in keys];stock=[x for x in detail['group_rows']['stock'] if x['group']==sid]
   exact_stage[label]={k:sum((D(x[k]) for x in exact),Z) for k in ['wealth','real','unreal','AR']};stock_stage[label]={k:sum((D(x[k]) for x in stock),Z) for k in ['wealth','real','unreal','AR']}
  out.append(dict(selection=item['selection'],attached_control=item['attached_control'],original_complete_campaign=c,ETA_exact_original_keys_participating=[x['key'] for x in same],ETA_exact_original_keys_endpoint_contribution=sum((x['net'] for x in same),Z),ETA_all_stock_all_entries_endpoint_contribution=sum((x['net'] for x in allstock),Z),ETA_all_stock_actual_entries=allstock,ETA_holding_overlap_original_campaign_interval=overlap,ETA_same_original_campaign_keys_true_stage_wealth=exact_stage,ETA_all_stock_true_stage_wealth=stock_stage,ETA_roles=dict(Counter(x['role'] for x in allstock)),ETA_entry_actions=dict(Counter(x['actual_entry_action'] for x in allstock)),interpretation='Original campaign full key, candidate own whole-stock entries and true period wealth are separate. Changed keys/roles/ACT/funding are not isolated exit effects; attached controls are not reselected.'))
 return out

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=HERE/'results_v1');a=ap.parse_args()
 for arm in ['BASELINE','ETA']:
  for win in ['2022_2024','strong']:
   path=runpath(arm,win)
   for n in ['DONE.json','TIMING.json','RUN_METADATA.json','pair/B.json.gz','pair/daily.jsonl.gz']:assert (path/n).is_file(),('WAIT',path/n)
   assert read(path/'DONE.json')['completed'] and read(path/'TIMING.json')['completed'];assert read(auditpath(arm,win))['status']=='PASS_COMPLETED_ACCOUNT_WITH_LIMITS'
 assert not a.out.exists();a.out.mkdir(parents=True);matrix=[];stages=[];validation={};tails={};stocktails={};differences={};paths={};ranks={};compat={};original36=[]
 try:
  M.SM={x['symbol']:x for x in read(M.W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};P.MANIFEST=M.SM;P.META_ROWS=read(P.META);P.SECTOR_NAMES={x['sector_id']:x['industry'] for x in P.META_ROWS.values()};semi=read(H/'followup_robustness_v1/performance/SEMICONDUCTOR_COHORT_FREEZE.json');P.SEMIBY={x['sid']:x for x in semi['all_metadata_members'] if x['in_frozen1709']};fixed=read(E/'entry_exit_scale/analysis_summary/FIXED_ORIGINAL_TAILS.json')
  for win in ['2022_2024','strong']:
   calendar=[x['at'] for x in read(runpath('BASELINE',win)/'pair/daily.jsonl.gz',gz=True,lines=True)];base,bp=analyze('BASELINE',win,calendar);base_full=None
   for arm in ['BASELINE','ETA']:
    r,pr=(base,bp) if arm=='BASELINE' else analyze(arm,win,calendar);all_detail={};full_detail=None
    for label,start,end in P.PERIODS[win]:
     m,d=P.period(pr,label,start,end);m['actual_proxy_adverse_slippage']=slip(pr['book'],start,end);matrix.append(m);save(a.out,f'{arm}_{label}_DETAIL.json',d)
     if label in ('full_2022_2024','strong'):full_detail=d
    if arm=='BASELINE':base_full=full_detail
    else:
     delta=r['daily'][-1]['NAV']-base['daily'][-1]['NAV'];differences[win]=group_differences(base_full,full_detail,delta);p=M.matching(base,r);paths[win]=p['summary'];save(a.out,f'ETA_{win}_FULL_ENTRY_AND_ACT_DIFFERENCES.json',p)
    if win=='2022_2024':
     for label,start,end in STAGES:
      m,d=P.period(pr,label,start,end);stages.append(m);all_detail[label]=d;save(a.out,f'{arm}_{label}_STAGE_DETAIL.json',d)
     for k in ['net_wealth_change','strict_realized_change','open_unrealized_change','AR_change','fees','buy_gross','sell_gross','actual_buycash','actual_sell_net']:
      M.eq(sum((x[k] for x in stages if x['arm']==arm),Z),next(x[k] for x in matrix if x['arm']==arm and x['period']=='full_2022_2024'),'ten-stage additive '+k)
     if arm=='ETA':save(a.out,'ETA_PRIMARY_TEN_CAMPAIGNS_PLUS_THREE_CONTROLS.json',representative_chains(base,r,all_detail))
    tf=M.tails_for(win,fixed[win],base,r);assert tf['summary']['baseline_current_matches']=={'2022_2024':45,'strong':67}[win];tails[arm+'|'+win]=tf['summary'];stocktails[arm+'|'+win]=whole_tail(base,r,tf);save(a.out,f'{arm}_{win}_FIXED_ORIGINAL83_94.json',tf)
    validation[arm+'|'+win]=r['validation'];compat[arm+'|'+win]=r['metadata_read_compatibility_only'];ranks[arm+'|'+win]=priority_logs(arm,win,r['layers'])
    save(a.out,f'{arm}_{win}_LAYERS.json',r['layers']);save(a.out,f'{arm}_{win}_DAILY_WEALTH_SPLIT.json',r['daily']);print('ETA_COMPARISON_PATH_DONE',arm,win,flush=True)
  assert len(matrix)==36 and len(stages)==20
  prior=read(H/'followup_robustness_v1/performance/results_v1/FIXED_PERIOD_PERFORMANCE.json');by={(x['window'],x['period']):x for x in prior if x['arm']=='BASELINE'}
  for m in matrix:
   if m['arm']!='BASELINE':continue
   for k in ['NAV_begin','NAV_end','net_wealth_change','strict_realized_change','open_unrealized_change','AR_change','fees','buy_gross','sell_gross','period_rebased_max_DD','mean_previous_CLOSE_exposure']:M.eq(m[k],by[m['window'],m['period']][k],'reused BASE reference '+k)
   original36.append([m['window'],m['period']])
  save(a.out,'FIXED18_PERIODS_TWO_CONFIGURATIONS.json',matrix);save(a.out,'TEN_DISJOINT_STAGES_TWO_CONFIGURATIONS.json',stages);save(a.out,'FIXED_TAIL_SUMMARY.json',tails);save(a.out,'FIXED_TAIL_ALL_ENTRY_STOCK_COVERAGE.json',stocktails);save(a.out,'FULL_STOCK_MONTH_SECTOR_CONTRIBUTION_DIFFERENCES.json',differences);save(a.out,'FULL_PATH_DIFFERENCE_SUMMARY.json',paths);save(a.out,'PRIORITY_QUERY_AND_ALIAS_SUMMARY.json',ranks)
  save(a.out,'FIELD_SEMANTICS.json',dict(actual_trade_pvr='Legacy native meta.score/H1 score only; never eta or true original PVR.',frozen_intent_score='Native H1 carrier score; retained independently of priority.',frozen_intent_PVR_score='Actual priority source: original pressure PVR[0,100] in BASE; raw eta[-1,1] in ETA.',rank_policy_PVR='Actual per-unique-stock priority value; same manifest-dependent units as frozen_intent.PVR_score. Every actual filled layer is joined to its true decision-day ranklog.',no_display_transform_or_old_PVR_secondary_key_added=True,real_RUN_METADATA_and_books_not_modified=True))
  save(a.out,'NATIVE_CLOSE_MARK_DOMAIN.json',dict(source=str(Path(MARK_MODULE.__file__)),source_sha256=MARKS.source_sha256,queries=len(MARKS.queries),stale_action_differences_from_old_facts_carry=list(MARK_DIFFERENCES.values()),definition='Original runtime30 raw eligible observed quotes plus original declared intervening action theoretical_ex_reference. A stale valuation reference is never a new tradable quote. AR remains separately recognized; no double counting.',old_sealed_financial_helpers_unchanged=True,account_books_and_facts_unchanged=True,new_financial_paths=0))
  for name,rr in [('FIXED18_PERIODS_TWO_CONFIGURATIONS.csv',matrix),('TEN_DISJOINT_STAGES_TWO_CONFIGURATIONS.csv',stages)]:
   fields=[k for k,v in rr[0].items() if not isinstance(v,dict)]
   with (a.out/name).open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rr)
  save(a.out,'VALIDATION.json',dict(status='PASS_READ_ONLY_ETA4_PATH36_PERIOD20_STAGE_COMPARISON',new_financial_paths_by_comparator=0,new_account_events=0,actual_parent_new_paths=2,reused_BASE_paths=2,full_paths=4,original_fixed_periods_per_configuration=18,main_period_rows=36,ten_disjoint_stage_rows=20,original83_94_mother_preserved=True,current_No60_baseline_exact_tails=[45,67],primary_frozen_campaigns=10,attached_frozen_controls=3,baseline18_reference_metrics_exact=original36,financial_basis=validation,read_only_metadata_compatibility=compat,limits='BASE and ETA start separate1m per full window, not a2022→2026 uninterrupted book. Main18 overlapping views cannot be added to20-stage supplement; only each weak ten partitions. Priority raweta replaces only scores; PVR alias has different units. All deltas include endogenous funding/CORE/ACT and are not pure exit causal effects. Historical development, snapshot membership and native execution proxies remain.'))
 except BaseException as e:save(a.out,'FAILURE.json',dict(error=repr(e),new_accounts=0,preserve_partial=True));raise
 finally:
  SRC.update(M.SRC);SRC.update(P.SRC)
  SRC.update(MARKS.source_sha256)
  for p in [Path(__file__),Path(M.__file__),Path(P.__file__),ETA/'HYPOTHESIS_FREEZE.json',ETA/'EXECUTION_GATE.json']:SRC[str(p.resolve())]=sha(p)
  save(a.out,'SOURCE_SHA256.json',SRC);save(a.out,'DELIVERABLE_SHA256.json',{str(p.resolve()):sha(p) for p in a.out.iterdir() if p.is_file() and p.name!='DELIVERABLE_SHA256.json'})
 print('ETA_COMPARISON_COMPLETE',len(matrix),'main rows',len(stages),'disjoint stage rows',a.out,flush=True)
if __name__=='__main__':main()
