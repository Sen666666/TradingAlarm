from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;W=O/'report_v1_1';E=O.parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert not (W/'SUPPLEMENTAL_REVIEW.json').exists()
files=[O/'preflight.py',O/'preflight_v1_1.py',O/'FREEZE.json',O/'FREEZE_PREFLIGHT_REPAIR.json',O/'policy_checks.py',O/'SUPPLEMENTAL_SYNTHETIC_QA.json',W/'POSTPROCESS_SEAL.json',W/'CANDIDATE_PREFLIGHT.csv',W/'FIXED_DAILY.csv',W/'FIXED_CASE_STATUS.csv',W/'LATER_AB_CONFLICT_RISK.csv',Path(__file__)]
(W/'SUPPLEMENTAL_REVIEW_SEAL.json').write_text(json.dumps({str(p):sha(p) for p in files},indent=2)+'\n')
c=pd.read_csv(W/'CANDIDATE_PREFLIGHT.csv',parse_dates=['day'],dtype={'window':str})
fd=pd.read_csv(W/'FIXED_DAILY.csv',parse_dates=['day'],dtype={'window':str})
case=pd.read_csv(W/'FIXED_CASE_STATUS.csv',dtype={'window':str});mark=pd.read_csv(W/'MARK_TRANSITIONS.csv',parse_dates=['day'],dtype={'window':str})
full=pd.concat([pd.read_parquet(O/f'DAILY_FEATURES_{i}.parquet') for i in range(8)],ignore_index=True)
ec=pd.DatetimeIndex(sorted(pd.read_parquet(E.parent/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet').day.unique()));nm=dict(zip(ec[:-1],ec[1:]))
fd['next_common_day']=fd.day.map(nm)
ab=pd.read_csv(E/'relative_priority_v1/baseline/DECISIONS.csv',parse_dates=['day'],dtype={'window':str});abkeys=set(map(tuple,ab[['window','sid','day']].to_numpy()))
rows=[];traces=[]
for r in case[case.group.eq('2022_FIXED_20_EARLY')].itertuples():
 g=fd[fd.window.eq('2022')&fd.sid.eq(r.sid)&fd.day.gt(pd.Timestamp(r.missed_early_AB_day))&fd.next_common_day.lt(pd.Timestamp(r.baseline_later_entry_day))].copy()
 ups=g[g.relative_known&g.relative_event.eq(1)].copy()
 for ix,z in ups.iterrows():
  isab=('2022',r.sid,z.day) in abkeys
  if isab:reason='FRESH_UP_ON_ORIGINAL_AB_DATE_NOT_C'
  elif not z.persistent:reason='S_OR_M_NOT_BOTH_CONSECUTIVE_TRUE'
  elif not z.I_qualified or pd.isna(z.I_continuity_epoch):reason='I_INVALID_OR_EPOCH_UNKNOWN'
  elif not z.marker_active:
   prev=mark[mark.window.eq('2022')&mark.sid.eq(r.sid)&mark.day.le(z.day)].sort_values('day')
   reason='NO_VALID_MARKER_'+(prev.iloc[-1].reason if len(prev) else 'NO_SEED')
  elif z.baseline_state!='FLAT':reason='BASELINE_'+z.baseline_state
  else:
   cc=c[c.window.eq('2022')&c.sid.eq(r.sid)&c.day.eq(z.day)]
   reason=cc.iloc[0].first_block_or_proxy if len(cc) else 'NOT_IN_FROZEN_PERSISTENT_SCOPE'
  traces.append(dict(case_id=r.case_id,sid=r.sid,name=r.name,day=z.day,reason=reason,**{k:z[k] for k in ['baseline_state','marker_active','marker_day','sectorS','M3_known','M3','I_qualified','I_continuity_epoch','relative_known','relative_event','persistent','qualification_unknown']}))
 if not len(ups):classification='NO_NEW_RELATIVE_UP_BEFORE_BASELINE_ENTRY'
 elif r.targeted_C_count>0:classification='TARGETED_C_EXISTS'
 elif not r.target_interval_persistent_count>0:classification='FRESH_UP_EXISTS_BUT_NO_LEGAL_PERSISTENT_C_DATE'
 else:classification='PERSISTENT_DATE_EXISTS_BUT_MARKER_OR_QUEUE_BLOCKED'
 rows.append(dict(case_id=r.case_id,sid=r.sid,name=r.name,missed_early_AB_day=r.missed_early_AB_day,baseline_later_entry_day=r.baseline_later_entry_day,full_common_days=len(g),new_relative_UPs=len(ups),persistent_new_relative_UPs=int(ups.persistent.sum()),legal_persistent_receipts=r.target_interval_persistent_count,targeted_C_count=r.targeted_C_count,classification=classification))
pd.DataFrame(rows).to_csv(W/'TARGET_2022_CLOCK_REASONS.csv',index=False);pd.DataFrame(traces).to_csv(W/'TARGET_2022_ALL_FRESH_UP_TRACE.csv',index=False)
risk=pd.read_csv(W/'LATER_AB_CONFLICT_RISK.csv',dtype={'window':str})
riskstats=[]
for w,g in risk.groupby('window'):
 riskstats.append(dict(window=w,C_future_AB_pairs=len(g),distinct_future_AB=g.original_AB_event_id.nunique(),distinct_C_stocks=g.sid.nunique(),selected_AB_pairs=int(g.original_AB_selected.sum()),distinct_selected_AB=g[g.original_AB_selected].original_AB_event_id.nunique()))
pd.DataFrame(riskstats).to_csv(W/'LATER_AB_CONFLICT_DENOMINATORS.csv',index=False)
old=pd.read_csv(E/'relative_m3_cache_v1/coverage_upper_bound_v1/ALL_RECEIPTS.csv',parse_dates=['day'],dtype={'window':str})
old=old[old.arm.eq('SAME_DAY')&old.old_birth_type.eq('NONE')]
z=c.merge(old[['window','sid','day','PVR_score','PVR_known']],on=['window','sid','day'],suffixes=('_new','_old'),validate='one_to_one')
np.testing.assert_allclose(z.PVR_score_new,z.PVR_score_old,rtol=1e-14,atol=1e-12,equal_nan=True);assert z.PVR_known_new.eq(z.PVR_known_old).all()
repair=(O/'preflight.py').read_text().replace("frozen=read(O/'FREEZE.json')['hashes']","frozen=read(O/'FREEZE_PREFLIGHT_REPAIR.json')['hashes']").replace("ore=groups_or.get(sid,pd.DataFrame())","ore=groups_or.get(sid,pd.DataFrame(columns=['day','relative_event','window']))")
assert repair==(O/'preflight_v1_1.py').read_text()
summary={'PVR_all_2242_exact':True,'repair_exactly_empty_schema_and_seal_reference_only':True,'targeted20_clock_classification':pd.DataFrame(rows).classification.value_counts().to_dict(),'later_AB_risk_denominators':riskstats,'synthetic_checks':28,'synthetic_scope':'Actual marker helper and specification-level invitation/queue tests, not ABC economic integration','new_economic_run':False}
(W/'SUPPLEMENTAL_REVIEW.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
text='''# 时钟、成本与作用域审查\n\nC规则和数值时钟未改动。x_t=log(股票调整收盘/官方行业调整收盘)，epsilon_t=x_t-x_(t-1)；严格极点e冻结delta_e²=(5/63) sum(epsilon_(e-63)..epsilon_(e-1))²，极点自身新回报不进入其冻结尺度。使用原70位Decimal/区间数值保护；无法确定极点顺序或阈值跨越时UNKNOWN，不引入经济epsilon。区间只覆盖最终binary64表示舍入，不消除供应商上游或复权修订。\n\n4595共同日完整相对时钟预热，1088日原M预移位，1085执行共同日。1627股票、495412窗内市场日，旧20445个AB状态和所有检查到的原close字段精确；2242 broad receipts的PVR原分与known逐条精确。连续Iepoch从完整facts/source重建，所有旧AB日epoch、relative事件/known精确，不把稀疏旧表当连续全日状态。\n\n成本直接AST提取原finite/true/false/lineage/flags/getmeta/fee/size/checkclose/load/DayFrame函数。初仓含费预算24000，计划floor风险含双边费用<=3000，NAV参考1200000；dated lot与dated fees、双向5bp不利滑点不变。容量=至signal close原始正成交量最近20观察均值的1%，不是20个完整日或当天实盘可执行流动性。next common OPEN按同预算/风险/容量重新算量，不能把close手数当固定单。OPEN<=保护价/0手为明确NOFILL；来源/factor/dated-rule不明为UNKNOWN。不能声称历史涨跌停/停牌/排队或真实成交可知。\n\n当日AB原PVR先分2槽，C只分剩余，再观察next OPEN代理；两次2024 NOFILL未替补。影子C获槽160/238/6，已知OPEN代理160/236/6，不是ABC实际交易数。重复同股影子获槽14/18/0次可能在真实C第一次成交后消失；首次成交也会改未来AB资格和持仓。\n\n潜在后续AB冲突必须区分C-AB配对与独立AB事件：详见LATER_AB_CONFLICT_DENOMINATORS.csv。它只显示如果C更早入场可能阻断的同I后续AB，不宣称已经阻断，不能作为收益归因。\n\n每窗起始标记为空，必须该窗原AB合法且纯排名落选才能造标。因此每窗AB股票域对限定C是闭合的；并集外82株无法形成必要条件。仍是静态NON-PIT研究，非新全池、非共享账户、非完整策略。\n\n固定2022目标20例仅国机重装有合格C，6月7日发邀、6月8日条件OPEN代理；不能继承旧回合收益。秦川机床7月21日虽有persistent新UP，但6月27日资格已于7月15日UNKNOWN清掉。其余18例没有目标间隔内符合原I的persistent收据；原始fresh时钟原因详见TARGET_2022_CLOCK_REASONS.csv，避免把“无C日期”误说成“完全没有任何新UP”。2024既定11例均无已知OPEN影子C，明细完整保留。\n\n修订记录：原预检第6片因无事件股票空DataFrame缺列失败，保留原代码/FREEZE/日志，仅追加preflight_v1_1并补6，另7片复用。修复逐字符验证只改空表schema及对应seal引用。首版汇总因示例字典重复window键失败，其部分文件保留；最终report_v1_1修复展示，并将目标时间窗日期映射扩展至全部候选以免漏原因分母。冻结规则、名单、C资格、PVR配额与nextOPEN不变。\n\n经济ABC尚未授权、未运行。28项补充检查是marker实现及邀请/配额规格检查，不冒充未来ABC集成验收。独审最终意见另行提供。\n'''
(W/'CLOCK_COST_SCOPE_REVIEW.md').write_text(text)
(W/'SUPPLEMENTAL_OUTPUT_HASHES.json').write_text(json.dumps({p.name:sha(p) for p in W.iterdir() if p.is_file() and p.name!='SUPPLEMENTAL_OUTPUT_HASHES.json'},indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
