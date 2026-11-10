from pathlib import Path
import json,hashlib,pandas as pd,numpy as np
O=Path(__file__).resolve().parent;W=O/'report_v1_1';E=O.parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
audit=json.loads("{\"verdict\":\"PASS_PREFLIGHT_SUPPORTS_STOP_FOR_FIXED_TARGET\",\"scope\":\"Read-only independent audit of preflight. No ABC economic simulation. Not future ABC integration acceptance.\",\"independent_checks\":{\"original_market_reconstruction\":{\"stocks\":1627,\"window_daily_rows\":495412,\"fields\":[\"S\",\"M3\",\"PVR\",\"I qualification\",\"source comparability\",\"I continuity epoch\"],\"method\":\"Separate vector reconstruction of I epochs and source states\",\"all_exact\":true},\"baseline_state_and_marker\":{\"AB_decisions\":20445,\"persistent_candidates\":2242,\"marker_transitions\":8226,\"method\":\"Latest legal AB ranking loss plus subsequent clearing intervals, independently of marker_step\",\"all_exact\":true,\"covered\":[\"execution UNKNOWN\",\"same-day UNKNOWN cannot rearm\",\"I epoch change\",\"actual entry consumption\"]},\"cost\":{\"close_checks\":639,\"next_OPEN_checks\":613,\"method\":\"Independent reuse of original AST execution helpers\",\"all_exact\":true},\"ranking\":{\"shadow_awards\":[160,238,6],\"PVR_then_sid_remaining_slots_exact\":true,\"known_NOFILL_2024\":2,\"no_replacement\":true},\"clock\":{\"fixed_stocks_full_4595_day_recompute\":7,\"full_recompute_exact\":true,\"new_close_PASS_dates_independently_checked\":613,\"new_date_method\":\"Decimal precision80, independently recomputed strict low-extreme prior63 epsilon-square frozen scale and positive upward crossing\",\"all_613_pass\":true,\"remaining_clock_scope\":\"Other full clock output supported by frozen implementation/input and consistency checks; no claim of independent full1627-clock rerun\"},\"source_hashes\":{\"coverage_sources\":4980,\"baseline_sources\":4898,\"baseline_output_files\":12,\"all_unchanged\":true}},\"target_findings\":{\"fixed_2022\":20,\"hit\":1,\"no_new_relative_UP\":9,\"UP_but_no_legal_persistent_C\":9,\"marker_cleared\":1,\"sole_hit\":\"601399.SH 2022-06-07 close, 2022-06-08 conditional OPEN\",\"Qinchuan\":\"2022-07-14 known false S preserves marker;2022-07-15 S=-1 clears;2022-07-21 cannot revive.\",\"fixed_2024_stocks\":11,\"persistent_candidate_dates_2024\":9,\"those_candidates_with_valid_marker\":0,\"shadow_awards_2024_fixed\":0,\"clarification\":\"Not a claim that these11 stocks never had markers on any calendar day; reversed derived target intervals are not evidence.\"},\"AB_slot_deprivation\":{\"window_order\":[\"2022\",\"2024_924\",\"2026H1_SEMI\"],\"AB_full_close_PASS\":[37,74,11],\"close_PASS_denominators\":[201,392,20]},\"later_AB_risk\":{\"distinct_AB_events\":[197,413,4],\"original_selected_events\":[61,123,0],\"interpretation\":\"Potential footprints only, not observed ABC blockage or performance\"},\"conclusion\":\"Supports stopping this consumer for the fixed aim of recovering the initial startup missed by original AB ranking. Does not disprove future C profitability. No economic run, rule changes, or parameter search.\"}")
assert not (W/'STOP_DECISION.json').exists()
c=pd.read_csv(W/'FIXED_CASE_STATUS.csv',dtype={'window':str});m=pd.read_csv(W/'MARK_TRANSITIONS.csv',dtype={'window':str})
final=c.copy();final['target_interval_applicability']='NOT_REQUESTED'
q=final.group.eq('2022_FIXED_20_EARLY');final.loc[q,'target_interval_applicability']='VALID_STRICT_2022_EARLY_TO_BASELINE_ENTRY_INTERVAL'
tail=final.case_id.str.startswith('2024_TAIL');final.loc[tail,'target_interval_applicability']='NOT_APPLICABLE_USE_COMPLETE_FIXED_2024_WINDOW'
for col in ['target_interval_after','target_interval_before','first_targeted_C_signal','first_targeted_C_open','targeted_C_count','target_interval_persistent_count','target_interval_block_reasons']:
 final.loc[tail,col]=np.nan
final.loc[tail,'target_comparison']='Full2024Sep-Dec window used. Earlier derived reversed or unanchored target intervals are not evidence; original reference dates remain descriptive.'
final.to_csv(W/'FIXED_CASE_STATUS_FINAL.csv',index=False)
full=[]
for r in c[tail].itertuples():
 seeds=m[m.window.eq('2024_924')&m.sid.eq(r.sid)&m.reason.eq('SEED_AB_LOSS')]
 full.append(dict(case_id=r.case_id,sid=r.sid,name=r.name,classification=r.group,fixed_window_start='2024-09-01',fixed_window_end='2024-12-31',window_common_days=r.baseline_days_visible,persistent_candidate_dates=r.broad_persistent_fresh,persistent_candidates_with_valid_unconsumed_marker=r.valid_marker,shadow_C_awards=r.shadow_C_awards,known_OPEN_shadow_C=r.known_open_shadow_C,AB_mark_seed_events_any_window_day=len(seeds),baseline_reference_signal_day=r.baseline_signal_day,baseline_reference_entry_day=r.baseline_later_entry_day,priority_reference_signal_day=r.priority_new_signal_day,target_interval='N/A; complete fixed window is the evidence'))
full=pd.DataFrame(full);assert len(full)==11 and full.persistent_candidate_dates.sum()==9 and full.persistent_candidates_with_valid_unconsumed_marker.sum()==0 and full.shadow_C_awards.sum()==0
full.to_csv(W/'FIXED_2024_FULL_WINDOW_STATUS.csv',index=False)
(W/'INDEPENDENT_AUDIT.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
stop={
'decision':'STOP_AT_PREFLIGHT_NO_ECONOMIC_RUN','scope':'This frozen C consumer as a repair of missed original initial-startup opportunities','parameters_changed':False,'economic_ABC_executed':False,'economic_ABC_prepared':False,'parameter_scan':False,
'reason':'Candidate supply is not scarce, but this definition mostly seeks a later relative turn rather than preserving initial startup evidence.',
'evidence':{'shadow_C_awards':[160,238,6],'conditional_known_OPEN_proxies':[160,236,6],'2024_known_NOFILL':2,'2022_target_hit_cases':1,'2022_target_cases':20,'2022_first_fresh_UP_already_on_missed_AB_day':17,'2024_full_window_fixed_stocks':11,'2024_persistent_candidate_dates':9,'2024_candidates_with_valid_mark':0,'2024_fixed_shadow_C_awards':0},
'falsifiable_limits':['No new-C return or win-rate calculation was performed.','This does not establish that all C candidates are unprofitable.','Baseline shadow states are not the future ABC own-arm states or guaranteed bounds.','Historical orderability and static NON-PIT membership remain unresolved.'],
'followup':'Archived without promotion. No further C economic work or rule change scheduled.',
'audit_verdict':audit['verdict']}
(W/'STOP_DECISION.json').write_text(json.dumps(stop,ensure_ascii=False,indent=2)+'\n')
qa={'status':'PASS_AND_STOPPED','old_AB_state_decisions_exact':20445,'old_AB_original_close_checks_exact':9297,'original_AB_clock_samples_exact':20445,'all_previous_relative_events_exact':True,'new_candidates_PVR_exact':2242,'daily_market_rows':495412,'stocks':1627,'marker_transitions':8226,'original_execution_function_source_unchanged':True,'preflight_repair_only_empty_schema_and_seal_reference':True,'full_clock_outputs_complete':True,'new_economic_run':False,'independent_audit':audit['verdict'],'synthetic_marker_and_spec_tests':28,'ABC_integration_tests':'NOT_RUN_NOT_AUTHORIZED','fixed2024_report_corrected':'Use complete fixed window; invalid target interval fields are N/A in FINAL case table.','historical_orderability':'UNKNOWN'}
(W/'FINAL_QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2)+'\n')
text="""# C入口最终预检：停止，不运行经济臂

独立复核通过。这个C消费者不进入经济回测：候选不稀少，但没有针对性修复原A/B第一次启动被两名额排序挤掉的问题。此结论不等于否定所有C候选将来的盈利能力。

## 冻结公式与消费语义

x_t=log(股票调整收盘价/官方行业调整收盘价)，epsilon_t=x_t-x_(t-1)。
严格极点e冻结：delta_e²=(5/63) × Σ_{j=e-63}^{e-1} epsilon_j²。
原70位Decimal/区间时钟不变，无法确定严格极点或跨阈时UNKNOWN，没有新增经济阈值。

C_t要求：本窗原A/B在真实FLAT且原I/PVR/close检查通过、仅因行业两名额落选所建立的同I未消费资格仍有效；当前真实FLAT；t-1和t为连续共同日且S与M3都known true；当前真正fresh relativeUP；当前不是A/B日；原PVR已知且原close可行。A/B按原PVR先处理，C按PVR降序/sid升序只分剩余槽。

实际入场、I结束、来源/relative/I/S/M3 UNKNOWN清资格；execution UNKNOWN依原引擎锁定。UNKNOWN当日不得重新造可用C标。已知S/M3 false和PVR未知不消费标，PVR未知只阻当日C。C落选或明确NOFILL不能次日重放，但同I未来另一真正freshUP可重新邀请；BUY_PENDING阻邀，实际入场后卖出不复活旧标。

## 全窗口漏斗

顺序均为2022全年 / 2024年9至12月 / 2026上半年半导体：
- 广义persistent fresh：1101 / 1080 / 61。
- 同I曾有合法A/B名额落选：317 / 556 / 24。
- 逐日清标后有效未消费资格且基线FLAT：203 / 414 / 22。
- 原close可行：201 / 392 / 20。
- A/B仍有剩余槽：164 / 318 / 9。
- C按原PVR获影子槽：160 / 238 / 6。
- 下一共同OPEN已知条件代理：160 / 236 / 6；2024另2次明确NOFILL，无替补。

这是沿旧臂状态且从不实际执行C的影子诊断，不是ABC成交数、上界保证或胜率。重复同股影子获槽14 / 18 / 0次，真实首次C成交会改变资格及后续AB持仓。次开代理不能证明历史真实可成交。

## 对原目标的检验

2022全部固定20个提前案例中，只有国机重装命中：6月7日C信号，6月8日条件OPEN，位于原5月27日早AB被错过后、旧臂9月9日入场前。没有套用旧回合收益。
- 9例在目标间隔内没有任何新的relativeUP。
- 9例虽有新UP，但没有符合原I的合法persistent C日期。
- 秦川机床7月21日有persistent UP，但6月27日资格已在7月15日S=-1时清除。7月14日S为已知false仍保标，UNKNOWN才清标，恢复不补造。
- 1例国机重装命中。

17/20案例第一次freshUP已发生在原被挤掉的A/B同日。保持本规则时，另一个freshUP一般须经过下一轮relativeDOWN→UP；等它并非保留第一次启动证据。这是停止当前消费者的机制理由，不是收益判断。

2024固定11股整个9至12月窗口共9个persistent C候选日，这9个候选日全部没有有效未消费标，因此0个C获槽。不是说11股全窗从未造过标：这11股期间实际有4次AB落选造标，后来实际入场消耗。五个延后案例的原派生目标区间反向，不能拿其中的0作证；最终案例表这些字段标N/A，结论只用完整预先固定窗。没有为找命中重选日期。

## 成本、风险和独审

原含费24000初仓预算、含费3000计划保护风险、1200000参考NAV、dated lot/fees、双向5bp不利滑点、至信号收盘最近20个正成交量观察1%容量全部保持。next OPEN按原规则重新算手数。无共享账户或资金规则扩展。

A/B当日占满挡掉closePASS的37/201、74/392、11/20；同日原AB身份冲突为0。新C若真实更早入场，可能阻断同I后续197 / 413 / 4个独立AB事件，其中原已选61 / 123 / 0。这只是风险足迹，不是已发生的阻断或收益归因。

独审独立复核1627股495412日市场状态、20445个AB状态、2242候选、8226标记迁移、639个新close检查、613个next OPEN代理和C余槽排序，全吻合。固定7股全4595日相对时钟另行重算；613个新closePASS C日期的极点前63尺度与正向跨阈另以Decimal80复核。没有声称独立重算全部1627股时钟。28项合成是marker实现和邀请/配额规格测试，不是未来ABC集成验收。

每窗AB股票域对限定C闭合，因为窗口内合法AB落选是必要条件，窗口外资格不继承。1627并集之外82株无必要造标条件，不是漏掉符合定义的C；静态NON-PIT和历史orderability仍未解决。

## 复核入口

最终结论：STOP_DECISION.json、FINAL_QA.json、INDEPENDENT_AUDIT.json。
最终案例：FIXED_CASE_STATUS_FINAL.csv、FIXED_2024_FULL_WINDOW_STATUS.csv、TARGET_2022_CLOCK_REASONS.csv、TARGET_2022_ALL_FRESH_UP_TRACE.csv、FIXED_DAILY.csv。
全量漏斗：FUNNEL.csv、CANDIDATE_PREFLIGHT.csv、AB_SAME_DAY_SLOT_DENOMINATORS.csv、MARK_TRANSITIONS.csv。
风险分母：LATER_AB_CONFLICT_DENOMINATORS.csv和LATER_AB_CONFLICT_RISK.csv。
日级源状态：上级目录DAILY_FEATURES_0..7.parquet。
原失败日志/版本和修订seal均保留。最终FINAL_SEAL.json固定完整产物。

没有运行ABC经济臂，没有新增规则或参数扫描，研究在预检处封存。
"""
(W/'FINAL_READOUT.md').write_text(text)
files=[p for p in O.rglob('*') if p.is_file() and p.name!='FINAL_SEAL.json']
seal={'created_utc':str(pd.Timestamp.now(tz='UTC')),'status':'STOPPED_AFTER_AUDITED_PREFLIGHT','files':{str(p.relative_to(O)):sha(p) for p in files},'final_report':'report_v1_1/FINAL_READOUT.md'}
(W/'FINAL_SEAL.json').write_text(json.dumps(seal,ensure_ascii=False,indent=2)+'\n')
print('FINAL_STOP_SEALED',len(files));print(full[['sid','name','persistent_candidate_dates','persistent_candidates_with_valid_unconsumed_marker','shadow_C_awards','AB_mark_seed_events_any_window_day']].to_string(index=False))
