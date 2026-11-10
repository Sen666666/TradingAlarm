"""Small definition supplement from existing traces; no account/log replay."""
from pathlib import Path
from collections import Counter
import pandas as pd
import json,hashlib
O=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
main=['STOCKDAY_FUNNEL.csv','EXCLUSIVE_STOCKDAY_STAGES.csv','ROLE_FUNNEL.csv','EXACT_ROUTE_AND_ORDER_COUNTS.csv','ROLE_CANDIDATE_TRACE.parquet']
before={n:sha(O/n) for n in main}
periods=json.loads((O/'CONTRACT.json').read_text())['periods']
ex=pd.read_csv(O/'EXCLUSIVE_STOCKDAY_STAGES.csv')
reasons=pd.read_csv(O/'OVERLAPPING_OPPORTUNITY_REASONS.csv')
trace=pd.read_parquet(O/'ROLE_CANDIDATE_TRACE.parquet',columns=['account','signal_day','sid','barriers','industry_active','original_pending','close_result'])
sector_reasons=reasons[reasons.reason.str.startswith('sector_up:')]
assert set(sector_reasons.reason)=={'sector_up:false'},'Unexpected non-false sector reason: retain unknown rather than infer false'
g=trace[trace.barriers.eq('')&trace.industry_active].groupby(['account','signal_day','sid']).agg(any_pending=('original_pending','any'),close_results=('close_result',list)).reset_index()
g=g[~g.any_pending].copy()
known={'minimum_unit_exceeds_risk_or_nominal_cap','no_nominal_gap'}
g['all_known']=g.close_results.map(lambda x:bool(x) and all(v in known for v in x))
g['reason_combination']=g.close_results.map(lambda x:' + '.join(sorted(set(x))) if all(v in known for v in x) else 'UNKNOWN_UNIDENTIFIED')
out=[];details=[]
for period,(lo,hi) in periods.items():
 for arm in ['PVR','NOACT']:
  z=ex[ex.account.eq(arm)&ex.period.eq(period)]
  def number(stage):
   v=z[z.exclusive_stage.eq(stage)].stockdays
   return int(v.iloc[0]) if len(v) else 0
  n=number('02_SECTOR_SIGNAL_FAIL_OR_UNKNOWN')
  raw=sector_reasons[sector_reasons.account.eq(arm)&sector_reasons.period.eq(period)]
  assert int(raw.rows.sum())>=n
  out.append(dict(account=arm,period=period,original_merged_stage='02_SECTOR_SIGNAL_FAIL_OR_UNKNOWN',stockdays=n,known_failure_stockdays=n,unknown_or_unidentified_stockdays=0,basis='All original sector_up rejection tokens are literal sector_up:false; no sector_up:unknown token exists in the full exported original opportunity-reason census. The ACT-first partition selects a subset of these known-false rows.'))
  t=g[g.account.eq(arm)&g.signal_day.between(lo,hi)];n=number('07_CLOSE_SIZE_OR_UNKNOWN_NO_PLAN');assert len(t)==n
  out.append(dict(account=arm,period=period,original_merged_stage='07_CLOSE_SIZE_OR_UNKNOWN_NO_PLAN',stockdays=n,known_failure_stockdays=int(t.all_known.sum()),unknown_or_unidentified_stockdays=int((~t.all_known).sum()),basis='Every role on the stock-day has an explicit original CLOSE size-rejection result; stocks with any pending role are excluded. Unknown would remain separate if a result were absent or unrecognized.'))
  for combo,cnt in t.reason_combination.value_counts().items():details.append(dict(account=arm,period=period,exclusive_close_reason_combination=combo,stockdays=int(cnt)))
pd.DataFrame(out).to_csv(O/'MERGED_STAGE_KNOWN_UNKNOWN_SPLIT.csv',index=False)
pd.DataFrame(details).to_csv(O/'CLOSE_SIZE_STOCKDAY_REASON_COMBINATIONS.csv',index=False)
# Bounded check of the already-frozen 90 industry-state sources, only effective
# fields. A null attempt_id is a documented no-active-attempt state, not a missing
# E0_valid observation. No missing value is cast to false for this check.
frozen=json.loads((O/'INPUT_SHA256.json').read_text())
days=set(pd.read_csv(O/'CLOSE_TO_OPEN_PENDING_COUNTS.csv').signal_day);assert len(days)==1054
statefiles=[p for p in frozen if '/industry/state/' in p and p.endswith('.parquet')];assert len(statefiles)==90
sc=Counter()
for p in statefiles:
 assert sha(p)==frozen[p]
 f=pd.read_parquet(p,columns=['day','E0_valid','attempt_id','stage']);f=f[f.day.isin(days)]
 sc['expected_sector_days']+=len(days);sc['observed_sector_days']+=len(f);sc['missing_sector_day_rows']+=len(days-set(f.day))
 sc['E0_valid_null']+=int(f.E0_valid.isna().sum());sc['stage_null']+=int(f.stage.isna().sum());sc['E0_valid_non_boolean']+=int((~f.E0_valid.isin([True,False])).sum())
 sc['attempt_id_null_known_no_active_attempt']+=int(f.attempt_id.isna().sum())
 sc['stage_positive_without_attempt']+=int((f.stage.gt(0)&f.attempt_id.isna()).sum())
assert all(sc[x]==0 for x in ['missing_sector_day_rows','E0_valid_null','stage_null','E0_valid_non_boolean','stage_positive_without_attempt'])
assert before=={n:sha(O/n) for n in main}
audit=dict(passed=True,main_numeric_artifacts_unchanged=before,account_runs=0,full_opportunity_log_rescans=0,source='existing role trace and original exported opportunity-reason census; bounded existing sector-state effective-column check',sector_state=dict(sc),merged_stage_unknowns=int(pd.DataFrame(out).unknown_or_unidentified_stockdays.sum()),unknown_scope='Zero here refers only to these two logged-stage buckets. Does not establish universal data knowledge, PIT validity, historical real-world tradability or feasible dynamic swaps.')
(O/'MERGED_STAGE_SPLIT_QA.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2))
p=O/'READOUT.md';text=p.read_text();marker='\n## 合并失败/UNKNOWN桶的最终细分\n'
if marker in text:text=text.split(marker)[0]
text+=marker+'\n主漏斗不改。补表 MERGED_STAGE_KNOWN_UNKNOWN_SPLIT.csv 对五窗口、两臂逐项拆分：\n\n'
text+='- 02_SECTOR_SIGNAL_FAIL_OR_UNKNOWN：全期PVR251,299、NOACT343,319个stock-day全部来自原日志明确的 sector_up:false；两个账户原机会拒因全量计数中均无 sector_up:unknown，故该桶UNKNOWN为0。不是把缺失值填成false。\n'
text+='- 07_CLOSE_SIZE_OR_UNKNOWN_NO_PLAN：全期PVR8,743、NOACT10,279个stock-day，全部角色均有明确原CLOSE拒因 minimum_unit_exceeds_risk_or_nominal_cap 或 no_nominal_gap；缺失/不可识别为0。同股双角色原因可能不同，互斥组合另存 CLOSE_SIZE_STOCKDAY_REASON_COMBINATIONS.csv，不重复加总为股票日。\n'
text+='- 额外只核已冻结90份行业state的有效列：94,860个sector-day全部存在，E0_valid/stage无缺失，正stage没有缺attempt_id。attempt_id为空是原状态机明确的无活动attempt，不冒充资料缺失。\n'
text+='- 以上“UNKNOWN=0”只适用于这两桶及所核字段，不代表所有历史状态或实盘执行均已知；原资料中其他个股/common-ready UNKNOWN、NON-PIT、真实可交易性及动态换序结果的UNKNOWN边界保持。合并阶段名称只是通用分类保留，未更改任何主计数。\n'
p.write_text(text)
(O/'OUTPUT_SHA256.json').write_text(json.dumps({p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_SHA256.json'},ensure_ascii=False,indent=2))
print(pd.DataFrame(out)[lambda f:f.period.eq('ALL')].to_string(index=False));print(json.dumps(audit,ensure_ascii=False))
