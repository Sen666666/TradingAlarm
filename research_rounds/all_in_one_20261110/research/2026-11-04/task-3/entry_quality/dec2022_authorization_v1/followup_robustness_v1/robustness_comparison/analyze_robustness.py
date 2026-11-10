"""Read completed robustness outputs; no Runner/Account or economic replay.

The sealed accounting reader and follow-up period arithmetic run unchanged.
Two explicit read views provide new metadata labels and already-derived in-memory
layer/daily/partial sidecars. No source output or financial checkpoint is changed.
"""
from pathlib import Path
from decimal import Decimal as D, getcontext
import argparse,copy,csv,gzip,hashlib,importlib.util,json,statistics,sys

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;F=HERE.parent;ROOT=F.parent;ENTRY=ROOT.parent
OLD=ENTRY/'trend_exit_controls_v1';W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
def module(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
M=module('sealed_financial_reader_robustness',OLD/'execution_review/account_comparison/compare_accounts.py')
P=module('sealed_period_reader_robustness',F/'performance/analyze_performance.py')
V=module('explicit_variant_reader_robustness',F/'variant_provider.py')
getcontext().prec=65
Z=D(0);SRC={};VIRTUAL={};ORIGINAL_M_READ=M.read;ORIGINAL_P_READ=P.read

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,gz=False,lines=False):
 p=Path(p);SRC[str(p.resolve())]=sha(p)
 with (gzip.open(p,'rt') if gz else p.open()) as f:return [json.loads(x) for x in f] if lines else json.load(f)
def save(out,name,x):
 with (out/name).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
def runpath(label,win):
 base=OLD if label=='BASELINE' else ROOT if label=='JOINT' else F
 return base/'runs'/label/win
def auditpath(label,win):
 base=OLD if label=='BASELINE' else ROOT if label=='JOINT' else F
 return base/'independent_review'/f'{label}_{win}_ACCOUNT_AUDIT.json'
def meta_read_view(p,gz=False,lines=False):
 value=ORIGINAL_M_READ(p,gz=gz,lines=lines)
 if Path(p).name=='RUN_METADATA.json' and 'label' in value:
  assert 'arm' not in value or value['arm']==value['label']
  return dict(value,arm=value['label'])
 return value
def period_read_view(p,gz=False,lines=False):
 key=str(Path(p).resolve())
 if key in VIRTUAL:return VIRTUAL[key]
 return ORIGINAL_P_READ(p,gz=gz,lines=lines)
M.read=meta_read_view;M.PERIODS={'2022_2024':[],'strong':[]}
P.read=period_read_view;P.runpath=runpath

class LegacyEMAReadView:
 def __init__(self,provider):self.provider=provider
 def at(self,sid,at,unused):
  q=self.provider.at(sid,at)
  return dict(status='READY' if q['ready_P'] else 'UNKNOWN',day=q['day'],causal_close=q['close'],line=q['EMA20'],source_segment=q['source_segment'],source_max_day=q['source_max_day'],unknown_reason=q['unknown_reason'])

def analyze(label,win,provider,calendar):
 rp=runpath(label,win);M.ROOT=OLD if label=='BASELINE' else ROOT if label=='JOINT' else F
 if label not in ('BASELINE','JOINT'):
  meta=read(rp/'RUN_METADATA.json');assert meta['context_provider_parameter_sha256']==provider.manifest_sha256
 if label!='BASELINE':M.INDICATORS[label]='EMA20'
 r=M.analyze_run(label,win,rp,LegacyEMAReadView(provider),calendar)
 for x in r['layers']:
  for k in ['entry_decision_tool','entry_day_CLOSE_tool','buy_OPEN_vs_prior_decision_line_below','entry_day_CLOSE_is_after_buy_and_not_known_at_OPEN']:x.pop(k,None)
  q=provider.at(x['sid'],x['decision_at']);x['H2_entry_context']=q
  # The unchanged policy suppresses only mobile; CORE may be weak by design.
  if label not in ('BASELINE','BASE_COST150') and x['role']=='mobile':
   assert not(q['ready_R'] and q['ready_P'] and q['RS20']<=0 and q['close']<q['EMA20']),'Actual known-weak mobile bypassed frozen guard'
 # Feed the already-audited financial reader outputs to unchanged period code.
 # These are in-memory read inputs, never on-disk synthetic account files.
 P.ROOT=M.ROOT;P.PREV=HERE/'__in_memory_financial_views__'
 VIRTUAL[str((P.PREV/f'{label}_{win}_LAYERS.json').resolve())]=r['layers']
 VIRTUAL[str((P.PREV/f'{label}_{win}_DAILY_WEALTH_SPLIT.json').resolve())]=r['daily']
 # The unchanged period loader normally receives a JSON sidecar (string keys).
 # Preserve that schema in memory, including every nontrivial partial state.
 validation=dict(r['validation'],partial_basis_state_points={str(k):v for k,v in r['validation']['partial_basis_state_points'].items()})
 P.VALID={'native_daily_mark_wealth_and_partial_basis':{label+'|'+win:validation}}
 pr=P.load(label,win)
 assert len(pr['raw'])==len(calendar)
 return r,pr

def whole_stock_tail_coverage(base,r,tf):
 fixed={x['original_fixed_member']['sid'] for x in tf['rows']}
 current={x['original_fixed_member']['sid'] for x in tf['rows'] if x['baseline_current_exact_match'] is not None}
 rows=[]
 for name,ids in [('all_original_fixed_stocks',fixed),('current_baseline_matched_fixed_stocks',current)]:
  bb=[x for x in base['layers'] if x['sid'] in ids];rr=[x for x in r['layers'] if x['sid'] in ids]
  rows.append(dict(cohort=name,stocks=len(ids),baseline_all_entry_contribution=sum((x['net'] for x in bb),Z),candidate_all_entry_contribution=sum((x['net'] for x in rr),Z),candidate_minus_baseline=sum((x['net'] for x in rr),Z)-sum((x['net'] for x in bb),Z),candidate_never_traded_stocks=sorted(ids-{x['sid'] for x in rr}),all_original_members_retained=True))
 return rows

def unknown_activity(label,win):
 p=runpath(label,win)/'pair/mobile-authorization-policy.jsonl.gz'
 if label in ('BASELINE','BASE_COST150'):
  if p.exists():assert not read(p,gz=True,lines=True),'BASE must have no overlay hooks'
  return dict(label=label,window=win,overlay_checks=0,base_has_no_overlay=True)
 logs=read(p,gz=True,lines=True);result={}
 for phase in ['new_mobile_role_before_pending','held_mobile_after_native_hard_exits']:
  rr=[x for x in logs if x['phase']==phase];uu=[x for x in rr if x['decision']['predicate_state']=='UNKNOWN']
  for x in uu:
   assert not x['decision']['denies_mobile']
   if phase=='new_mobile_role_before_pending':assert x['allowed']
   else:assert not x['added_mobile_exit_layer_ids']
  result[phase]=dict(checks=len(rr),mode_UNKNOWN=len(uu),ready_R_false=sum(not x['context']['ready_R'] for x in rr),ready_P_false=sum(not x['context']['ready_P'] for x in rr),known_weak=sum(x['decision']['predicate_state']=='TRUE' for x in rr),unknown_adds_no_action=True)
 return dict(label=label,window=win,overlay_checks=len(logs),by_phase=result,meaning='Policy query counts, not independent opportunities or guaranteed funding. Parameter shifts alter both known-state timing and the UNKNOWN/warmup population.')

def actual_proxy_slippage(book,start,end):
 values={'buy':Z,'sell':Z}
 for t in book['trades']:
  if not start<=t['at'][:10]<=end:continue
  gross=D(t['gross_cny']);raw=D(t['raw_open'])*D(t['shares']);M.eq(gross,D(t['price'])*D(t['shares']),'Actual CNY gross/price proxy')
  slip=gross-raw if t['side']=='buy' else raw-gross;assert slip>=0
  values[t['side']]+=slip
 return dict(buy_adverse_slippage=values['buy'],sell_adverse_slippage=values['sell'],total_adverse_slippage=values['buy']+values['sell'],meaning='Actual filled quantity x adverse price difference to its recorded raw OPEN; descriptive native proxy cost, not a no-cost rerun or achievable avoided loss.')

def perturbation_path_differences(reference,r,reference_detail,detail):
 bridge=M.matching(reference,r);groups={}
 for grouping in ['stock','month']:
  bb={x['group']:x for x in reference_detail['group_rows'][grouping]};cc={x['group']:x for x in detail['group_rows'][grouping]};rows=[]
  for group in sorted(bb.keys()|cc.keys()):
   b=bb.get(group,{});c=cc.get(group,{});bn=D(b.get('wealth',0));cn=D(c.get('wealth',0));row=dict(group=group,original_JOINT_contribution=bn,perturbation_contribution=cn,delta=cn-bn)
   if grouping=='stock':row.update(name=P.META_ROWS[group]['name'],industry=P.META_ROWS[group]['industry'])
   rows.append(row)
  M.eq(sum((x['delta'] for x in rows),Z),bridge['summary']['account_net_delta'],'Perturbation full '+grouping+' identity')
  groups[grouping]=dict(all_rows=rows,largest_positive_deltas=sorted([x for x in rows if x['delta']>0],key=lambda x:x['delta'],reverse=True)[:3],largest_negative_deltas=sorted([x for x in rows if x['delta']<0],key=lambda x:x['delta'])[:3])
 def transitions(daily):
  previous=True;out=[]
  for d in daily:
   if d['ACT_on']!=previous:out.append(dict(at=d['at'],ACT_on=d['ACT_on'],NAV=d['NAV'],exposure=d['exposure']));previous=d['ACT_on']
  return out
 return dict(summary=bridge['summary'],all_stock_and_month_differences=groups,ACT_changed_closes=bridge['ACT_changes'],original_JOINT_ACT_transitions=transitions(reference['daily']),perturbation_ACT_transitions=transitions(r['daily']),limitation='All stocks/all entries and all calendar months are retained. Deltas and ACT changes are descriptive identities of full endogenous paths, not isolated exit savings, future signals, or conditions to rescue a failed perturbation.')

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=HERE/'results_v1');p.add_argument('--available',action='store_true');a=p.parse_args()
 freeze=read(F/'ROBUSTNESS_FREEZE.json');specs={s['label']:s for s in freeze['parameter_variants']+freeze['cost_variants']}
 pairs=[(label,win) for label in specs for win in freeze['windows']];waiting=[];ready=[]
 for label,win in pairs:
  rp=runpath(label,win);ap=auditpath(label,win)
  if not all((rp/n).is_file() for n in ['DONE.json','TIMING.json','RUN_METADATA.json','pair/B.json.gz','pair/daily.jsonl.gz']) or not ap.is_file():waiting.append(label+'|'+win);continue
  if not read(rp/'DONE.json')['completed'] or not read(rp/'TIMING.json')['completed']:waiting.append(label+'|'+win);continue
  assert read(ap)['status']=='PASS_COMPLETED_ACCOUNT_WITH_LIMITS'
  ready.append((label,win))
 if not a.available:assert not waiting,('Wait for complete accounts AND independent receipts',waiting)
 assert ready,'No completed and independently audited robustness path yet'
 assert not a.out.exists(),'Preserve earlier results; choose a new output directory'
 a.out.mkdir(parents=True)
 providers={};matrix=[];valid={};tails={};whole={};unknowns={};costpaths={};perturbations={};completed=[];original_refs=[]
 try:
  M.SM={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
  P.MANIFEST=M.SM;P.META_ROWS=read(P.META);P.SECTOR_NAMES={x['sector_id']:x['industry'] for x in P.META_ROWS.values()}
  sf=read(F/'performance/SEMICONDUCTOR_COHORT_FREEZE.json');P.SEMIBY={r['sid']:r for r in sf['all_metadata_members'] if r['in_frozen1709']};assert len(P.SEMIBY)==126
  fixed=read(ENTRY/'entry_exit_scale/analysis_summary/FIXED_ORIGINAL_TAILS.json')
  # All parameter views share the identical immutable arrays. Only query spans
  # and their exact canonical parameter hash differ; do not reload GB per view.
  shared=V.VariantProvider(20,20);providers[20,20]=shared
  def provider_for(relative,ema):
   key=(relative,ema)
   if key not in providers:
    assert key in ((10,20),(40,20),(20,10),(20,40))
    q=copy.copy(shared);q.relative,q.ema=key
    q.manifest_sha256=hashlib.sha256((q.data_manifest_sha256+'|RS'+str(relative)+'|EMA'+str(ema)).encode()).hexdigest();providers[key]=q
   return providers[key]
  for win in freeze['windows']:
   calendar=[x['at'] for x in read(runpath('BASELINE',win)/'pair/daily.jsonl.gz',gz=True,lines=True)]
   base,bp=analyze('BASELINE',win,provider_for(20,20),calendar)
   reference_runs={'BASELINE':base};reference_details={}
   for label in ['BASELINE','JOINT']+[x for x in specs if (x,win) in ready]:
    if label=='BASELINE':r,pr=base,bp
    else:
     s=specs.get(label,dict(R=20,EMA=20));r,pr=analyze(label,win,provider_for(s['R'],s['EMA']),calendar)
    if label=='JOINT':reference_runs[label]=r
    for period,start,end in P.PERIODS[win]:
     m,detail=P.period(pr,period,start,end);slip=actual_proxy_slippage(pr['book'],start,end);m.update(actual_buy_adverse_slippage=slip['buy_adverse_slippage'],actual_sell_adverse_slippage=slip['sell_adverse_slippage'],actual_total_adverse_slippage=slip['total_adverse_slippage'],actual_fee_plus_proxy_slippage=D(m['fees'])+slip['total_adverse_slippage']);matrix.append(m);save(a.out,f'{label}_{period}_DETAIL.json',detail)
     if period in ('full_2022_2024','strong'):
      if label in ('BASELINE','JOINT'):reference_details[label]=detail
      if label in {x['label'] for x in freeze['parameter_variants']}:perturbations[label+'|'+win]=perturbation_path_differences(reference_runs['JOINT'],r,reference_details['JOINT'],detail)
    if label in ('BASE_COST150','JOINT_COST150'):
     reference=reference_runs['BASELINE' if label=='BASE_COST150' else 'JOINT'];bridge=M.matching(reference,r)
     ids={x['sid'] for x in reference['layers']}|{x['sid'] for x in r['layers']};stocks=[]
     for sid in sorted(ids):
      bb=[x for x in reference['layers'] if x['sid']==sid];cc=[x for x in r['layers'] if x['sid']==sid];bn=sum((x['net'] for x in bb),Z);cn=sum((x['net'] for x in cc),Z)
      stocks.append(dict(sid=sid,name=P.META_ROWS[sid]['name'],industry=P.META_ROWS[sid]['industry'],normal_entry_count=len(bb),cost150_entry_count=len(cc),normal_all_entry_contribution=bn,cost150_all_entry_contribution=cn,delta=cn-bn))
     M.eq(sum((x['delta'] for x in stocks),Z),bridge['summary']['account_net_delta'],'Cost stock contribution identity')
     costpaths[label+'|'+win]=dict(summary=bridge['summary'],stock_rows=stocks,limitation='Endpoint accounting identity across actual cost paths, not a fee-only causal mediation. Higher assumed costs can change units, competition and ACT, yielding higher realized NAV in one sample; not a claim costs are beneficial.')
     save(a.out,f'{label}_{win}_VERSUS_SAME_POLICY_NORMAL_COST_FULL_KEYS.json',bridge)
    tf=M.tails_for(win,fixed[win],base,r);assert tf['summary']['baseline_current_matches']=={'2022_2024':45,'strong':67}[win]
    tails[label+'|'+win]=tf['summary'];whole[label+'|'+win]=whole_stock_tail_coverage(base,r,tf)
    unknowns[label+'|'+win]=unknown_activity(label,win)
    save(a.out,f'{label}_{win}_FIXED_ORIGINAL_TAILS.json',tf);save(a.out,f'{label}_{win}_LAYERS.json',r['layers']);save(a.out,f'{label}_{win}_DAILY_WEALTH_SPLIT.json',r['daily'])
    valid[label+'|'+win]=r['validation'];completed.append(label+'|'+win)
    print('ROBUST_READ_COMPLETE',label,win,flush=True)
  # Calibrate all reused reference rows against the independently checked72.
  old=read(F/'performance/results_v1/FIXED_PERIOD_PERFORMANCE.json');omap={(x['arm'],x['window'],x['period']):x for x in old}
  for m in matrix:
   if m['arm'] not in ('BASELINE','JOINT'):continue
   x=omap[m['arm'],m['window'],m['period']]
   for k in ['NAV_begin','NAV_end','net_wealth_change','period_rebased_max_DD','fees','buy_gross','sell_gross','mean_previous_CLOSE_exposure']:
    M.eq(m[k],x[k],'Original checked72 reference '+k)
   original_refs.append([m['arm'],m['window'],m['period']])
  by={(x['arm'],x['window'],x['period']):x for x in matrix};sensitivity=[];cost=[]
  for win,full in [('2022_2024','full_2022_2024'),('strong','strong')]:
   b=by['BASELINE',win,full];j=by['JOINT',win,full];deltas=[]
   for spec in freeze['parameter_variants']:
    key=(spec['label'],win,full)
    if key not in by:continue
    r=by[key];delta=D(r['NAV_end'])-D(b['NAV_end']);deltas.append(delta)
    sensitivity.append(dict(label=spec['label'],window=win,spec=spec,NAV_end=r['NAV_end'],minus_original_BASE=delta,minus_original_JOINT=D(r['NAV_end'])-D(j['NAV_end']),advantage_over_BASE_positive=delta>0,period_DD=r['period_rebased_max_DD'],fees=r['fees'],oneway_turnover=r['conventional_oneway_turnover_over_mean_CLOSE_NAV']))
   if deltas:sensitivity.append(dict(label='DESCRIPTIVE_FOUR_PERTURBATIONS',window=win,completed=len(deltas),original_JOINT_minus_BASE=D(j['NAV_end'])-D(b['NAV_end']),minimum_advantage=min(deltas),median_advantage=statistics.median(deltas),maximum_advantage=max(deltas),positive_advantage_count=sum(x>0 for x in deltas),not_parameter_selection=True))
   if all((label,win,full) in by for label in ['BASE_COST150','JOINT_COST150']):
    cb=by['BASE_COST150',win,full];cj=by['JOINT_COST150',win,full]
    cost.append(dict(window=win,normal_BASE_NAV=b['NAV_end'],normal_JOINT_NAV=j['NAV_end'],normal_JOINT_advantage=D(j['NAV_end'])-D(b['NAV_end']),cost150_BASE_NAV=cb['NAV_end'],cost150_JOINT_NAV=cj['NAV_end'],cost150_JOINT_advantage=D(cj['NAV_end'])-D(cb['NAV_end']),advantage_change_including_endogenous_path=(D(cj['NAV_end'])-D(cb['NAV_end']))-(D(j['NAV_end'])-D(b['NAV_end'])),normal_BASE_fees=b['fees'],normal_JOINT_fees=j['fees'],stress_BASE_actual_fees=cb['fees'],stress_JOINT_actual_fees=cj['fees'],normal_BASE_slippage=b['actual_total_adverse_slippage'],normal_JOINT_slippage=j['actual_total_adverse_slippage'],stress_BASE_slippage=cb['actual_total_adverse_slippage'],stress_JOINT_slippage=cj['actual_total_adverse_slippage'],normal_BASE_gross=b['buy_plus_sell_gross'],normal_JOINT_gross=j['buy_plus_sell_gross'],stress_BASE_gross=cb['buy_plus_sell_gross'],stress_JOINT_gross=cj['buy_plus_sell_gross'],normal_BASE_fills=b['buy_fills']+b['sell_fills'],normal_JOINT_fills=j['buy_fills']+j['sell_fills'],stress_BASE_fills=cb['buy_fills']+cb['sell_fills'],stress_JOINT_fills=cj['buy_fills']+cj['sell_fills'],limitation='Full actual native stress paths. Difference in advantage includes changed sizing, fills, cash, ACT and opportunities; not a fee-only static attribution.'))
  save(a.out,'FIXED_PERIOD_PERFORMANCE.json',matrix);save(a.out,'PARAMETER_SENSITIVITY.json',sensitivity);save(a.out,'PERTURBATION_PATH_DIFFERENCES.json',perturbations);save(a.out,'COST_SENSITIVITY.json',cost);save(a.out,'COST_ENDOGENOUS_PATH_BRIDGES.json',costpaths);save(a.out,'FIXED_TAIL_SUMMARY.json',tails);save(a.out,'FIXED_TAIL_ALL_ENTRY_STOCK_CONTRIBUTION.json',whole);save(a.out,'ACTUAL_UNKNOWN_ACTIVITY.json',unknowns)
  fields=[k for k,v in matrix[0].items() if not isinstance(v,dict)]
  with (a.out/'FIXED_PERIOD_PERFORMANCE.csv').open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(matrix)
  save(a.out,'VALIDATION.json',dict(status='PASS_AVAILABLE_ONLY' if waiting else 'PASS_ALL_FROZEN_ROBUSTNESS_PATHS',completed=completed,waiting=waiting,expected_new_paths=12,completed_new_paths=len(ready),fixed_period_rows=len(matrix),references_calibrated_exact=original_refs,financial_reader_validation=valid,new_accounts=0,new_account_events=0,limits='History consumed development. Snapshot membership and native execution/corporate-action proxies retained. Same-entry differences are not pure exit causal effects. No best parameter selection.'))
 except BaseException as e:save(a.out,'FAILURE.json',dict(error=repr(e),new_accounts=0,preserve_partial=True));raise
 finally:
  SRC.update(M.SRC);SRC.update(P.SRC)
  for pth in [Path(__file__),Path(M.__file__),Path(P.__file__),Path(V.__file__),F/'contexts/MANIFEST.json']:SRC[str(pth.resolve())]=sha(pth)
  save(a.out,'SOURCE_SHA256.json',SRC);save(a.out,'DELIVERABLE_SHA256.json',{str(p.resolve()):sha(p) for p in a.out.iterdir() if p.is_file() and p.name!='DELIVERABLE_SHA256.json'})
 print('ROBUSTNESS_COMPARISON_COMPLETE',len(ready),'new completed paths',len(matrix),'rows',a.out,flush=True)
if __name__=='__main__':main()
