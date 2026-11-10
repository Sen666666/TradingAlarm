"""Source/trace inventory only. No import of selector, runner or account."""
from pathlib import Path
from decimal import Decimal as D
import json,gzip,hashlib
O=Path(__file__).resolve().parent;R=O.parent;READS={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 p=Path(p);READS[str(p.resolve())]=sha(p)
 return json.loads(gzip.open(p,'rt').read() if p.suffix=='.gz' else p.read_text())
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def main():
 # Preserve all twenty-one numeric plans; correct report text in a new place.
 originals={
  'SIX_PACKAGE':R/'replacement-six-package-projection-v1-20261103/REPORT.txt',
  'AUG15_PACKAGE':R/'replacement-aug15-package-projection-v1-20261103/REPORT.txt'}
 prefix=('独审勘误：21计划数值核验通过，数字不撤。通用资格存在BASE_DEFICIT例外：'
  '原实现允许无任何合格接收边的BAD donor先补旧缺口，再由其他合格donor给新股。'
  '因此不能把本实现推广为无例外硬门；当前21计划未发现实际采用此类BAD D。'
  '停止推广/不再修这条硬门，不接账户。原文件/hash保持，以下为单独修订报告。\n\n')
 for label,p in originals.items():
  READS[str(p.resolve())]=sha(p);text=p.read_text().replace('道通2144','优刻得2144').replace('四会2500','能科科技2500').replace('埃斯顿','通宇通讯')
  (O/('CORRECTED_'+label+'_REPORT.txt')).write_text(prefix+text)
 errata=dict(financial_events=0,optimization_calls=0,original_reports_sha256={k:sha(v) for k,v in originals.items()},
  BASE_DEFICIT=dict(base=-50,BAD_supply=50,GOOD_supply=1,receiver_A_need=1,BAD_has_eligible_edge=False,GOOD_has_eligible_edge=True,
   old_implementation_can_accept=True,violates_absolute_donor_eligibility=True,actual_exception_D_found_in_21=False,
   source='parent independent 21-plan audit; matching.py flow() permits every positive donor to BASE_DEFICIT',
   disposition='Do not promote or further repair this hard-gate implementation.'),
  names=[dict(code='688158.SH',qty=2144,correct='优刻得',wrong='道通'),dict(code='603859.SH',qty=2500,correct='能科科技',wrong='四会'),dict(code='002792.SZ',old_Q=1300,new_Q=1100,correct='通宇通讯',wrong='埃斯顿')])
 save(O/'REPORT_ERRATA.json',errata)
 specs=[('2022-01-12',R/'replacement-six-package-projection-v1-20261103/INPUT-2022-C10-2022-01-12.json'),
  ('2025-07-08',R/'g-s-C-three-batch-causal-preview-20261102/INPUT-C10-2025-07-08.json'),
  ('2025-07-22',R/'replacement-six-package-projection-v1-20261103/INPUT-C10-2025-07-22.json'),
  ('2025-08-13',R/'replacement-six-package-projection-v1-20261103/INPUT-C10-2025-08-13.json'),
  ('2025-08-15',R/'replacement-aug15-package-projection-v1-20261103/INPUT.json')]
 summaries=[]
 for day,p in specs:
  x=read(p);v=x['trusted'];cert=x.get('certificate',x.get('saved_certificate'));res=x.get('original_result',x.get('saved_result'))
  # Original records only; counts describe trace tags, not local feasibility.
  tagged=[]
  for z in res['trace']:
   if z.get('q',0)<z.get('raw_max',0) and any('account_risk6' in k for k in z.get('blockers_or_necessary_bounds',{})):
    tagged.append(dict(sid=z['sid'],raw_max=z['raw_max'],q=z['q'],priority=z['priority'],original_diagnostics=z.get('blockers_or_necessary_bounds',{}),
      classification='necessary/or encountered constraint, not proven sole blocker or newly funded quantity'))
  summaries.append(dict(day=day,source=str(p.resolve()),certificate=cert['certificate_id'],complete_C_candidate_count=len(v['demands']),
   original_positive_Q_count=sum(q>0 for q in cert['Q'].values()),account6_tagged_clipped_count=len(tagged),
   account6_tagged_original_candidates=tagged,
   original_Q=cert['Q'],raw_demands_source_available=True,original_positive_Q_domain_insufficient=True,
   core_T_fallback_not_inside_C_demand_domain=True,no_new_projection=True))
 cp=R/'g-s-C-August-continuation-v1-20261102/runs/C10/2025-08-05-CLOSE.json.gz';state=read(cp);last=state['results'][-1]
 ch=next(z for z in last['projection']['trace'] if z['sid']=='603516.SH')
 summaries.append(dict(day='2025-08-05',source=str(cp.resolve()),complete_C_candidate_count=len(last['projection']['trace']),
   original_positive_Q_count=sum(q>0 for q in last['certificate']['Q'].values()),pending_intent_count=len(state['pending']),
   Chunzhong_original_trace=ch,interpretation='First August mature-S fresh/Q day in saved audit; Aug1 was T. Necessary bound is not a full legal counterfactual.',no_new_projection=True))
 save(O/'FROZEN_CANDIDATE_READINESS.json',dict(cases=summaries,financial_events=0,new_solver_calls=0,new_price_labels=0))
 rows=read(R/'replacement-quality-six-batches-v2-20261102/ALL_ROWS.json')
 keep=[z for z in rows if z['side']=='Q' and (z['signal_close'][:10] in ['2022-01-12','2025-07-22','2025-08-13'])]
 # Outcomes are observational annotations only, never inputs to an experiment.
 save(O/'OBSERVED_LAYER_ANNOTATIONS.json',[dict(day=z['signal_close'][:10],sid=z['sid'],name=z['signal']['name'],original_Q=z['approved_qty'],original_actual_qty=z['actual_qty'],
   original_actual_layer_outcomes=z['actual_account_outcomes'],no_scaled_or_counterfactual_PNL=True) for z in keep])
 source_paths=[
  R/'pvr-slot1-native-readiness-20261101/native_rank.py',R/'account-risk-ablation-20261031/adapter.py',
  R/'account-risk-ablation-20261031/model_without_account_check.py',R/'account-risk-ablation-20261031/route_without_account_check.py',
  R/'case-stage-ledger-20261031/budget_v3/model.py',R/'case-stage-ledger-20261031/v3/joint_v3.py',
  R/'g-s-C-native-synthetic-v1-20261102/native_c.py',R/'g-s-C-native-synthetic-v3-20261102/native_c.py',
  R/'g-s-historical-native-prefix-20261101/native_capital.py',R/'g-broad-s-concentrated-native-r3-20261101/policy.py',
  R/'g-s-joint-funding-projection-jf2-20261102/projector.py',R/'g-s-B-joint-target-v2-20261102/selector.py',
  R/'replacement-six-package-projection-v1-20261103/matching.py',
  Path('/tmp/August-C10-limited-readonly-20261102/FINAL_READOUT.json'),
  Path('/Users/bytedance/Documents/Codex/2026-11-01/task/PVR-vs-C-July-readonly-20261102/REPORT.txt')]
 for p in source_paths:READS[str(p.resolve())]=sha(p)
 save(O/'SOURCE_READS.json',dict(sources_sha256=READS,all_unchanged=all(sha(p)==h for p,h in READS.items()),
   financial_events=0,new_optimization_calls=0,new_indicators=0,new_labels=0))
 print('READONLY_READY',[(r['day'],r['complete_C_candidate_count'],r['original_positive_Q_count']) for r in summaries])
if __name__=='__main__':main()
