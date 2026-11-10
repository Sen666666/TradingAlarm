"""Seal immutable market artifacts separately from independent reviewer outputs."""
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,default=str,allow_nan=False)+'\n')
def main():
 qa=json.loads((O/'QA.json').read_text());assert qa['errors']==[]
 d=pd.read_parquet(O/'DAILY_STATES.parquet');b=pd.read_parquet(O/'BIRTHS.parquet');u=d[d.root_unknown].copy()
 u['unknown_cause']=np.where(u.valid,'VALID_PRICE_BUT_SOURCE_IDENTITY_CHANGED','INVALID_OR_MISSING_PRICE_COORDINATE')
 u.groupby(['window','day','unknown_cause'],dropna=False).size().rename('root_unknown_events').reset_index().to_csv(O/'UNKNOWN_BOUNDARY_COUNTS.csv',index=False)
 b['source_period']=np.where(b.day<pd.Timestamp('2026-05-18'),'BEFORE_2026_05_18','ON_OR_AFTER_2026_05_18')
 b.groupby(['window','source_period','source_kind','phase'],dropna=False).size().rename('births').reset_index().to_csv(O/'BIRTH_PHASE_SOURCE_BOUNDARY.csv',index=False)
 rr=pd.read_csv(O/'ROOT_VOLUME_ROLE.csv')
 rr.groupby(['window','cohort','birth_phase','terminal_status','probe_outcome_at_window_end'],dropna=False).size().rename('roots').reset_index().to_csv(O/'ROOT_PHASE_ENDPOINT_COUNTS.csv',index=False)
 directories=[O/'startup_attempt_1_metadata_error',O/'startup_attempt_2_empty_facts',O/'startup_attempt_3_empty_fact_assertion']
 history=[]
 for i,a in enumerate(directories,1):
  old=json.loads((a/'INPUT_HASHES.json').read_text());mapping=[]
  for p,h in old.items():
   original=Path(p)
   if str(O) not in p:continue
   candidates=[a/original.name]+[v/original.name for v in directories]+[original]
   candidates=[v for v in candidates if v.is_file() and sha(v)==h]
   assert candidates,(i,p,h)
   mapping.append(dict(original_active_path=p,sha256=h,verified_archive_or_unchanged_path=str(candidates[0])))
  history.append(dict(attempt=i,archive=str(a),original_input_hash_file_sha256=sha(a/'INPUT_HASHES.json'),source_version_mapping=mapping,original_failure_log_sha256=sha(a/'ERRORS.json')))
 # Current consumed data/code unchanged from successful resumed pass.
 current=json.loads((O/'INPUT_HASHES.json').read_text());assert all(sha(p)==h for p,h in current.items())
 checkpoints=json.loads((O/'RECOVERY_VALIDATION.json').read_text());assert checkpoints['completed_stocks']==177
 for n,z in checkpoints['files'].items():assert sha(O/'startup_attempt_2_empty_facts'/n)==z['sha256']
 save('ENGINEERING_RECOVERY_CHAIN.json',dict(market_formula_unchanged=True,current_core_sha256=sha(O.parent/'independent_channel_probe_preflight_v1/core.py'),current_fast_core_sha256=sha(O/'fast_core.py'),current_input_hash_file_sha256=sha(O/'INPUT_HASHES.json'),attempts=history,final_attempt=4,attempt1=dict(market_paths_computed=1,market_output_rows=0,reason='Metadata column sector renamed from sector_id before output; no mechanism change.'),attempt2=dict(complete_stocks=177,complete_stock_day_rows=77526,receipts=5867,first_failing_sid='001232.SZ',reason='No-history canonical facts have object dtype; np.isclose rejected them.'),attempt3=dict(new_market_paths_computed=0,new_market_output_rows=0,reused_stocks=177,reason='Empty facts final allclose assertion also required dtype normalization.'),attempt4=dict(reused_completed_market_paths=177,new_market_paths=1532,successful_universe_stocks=1709),checkpoint_manifest_sha256=sha(O/'RECOVERY_VALIDATION.json'),source_dtype_change='Only canonical facts close/factor/raw_close coerced numeric float before alignment. No fillna=0; NaN remains unknown. Five full paths and all46 synthetic exact after change, independent8 paths/48 prefixes reported by reviewer.',output_semantics='Only first-window-day carry state is exported; prior-window root birthdate retained. No unsaved pre-window state reconstructed from later windows.',counts_exclude_verification_replays=True))
 summary=pd.read_csv(O/'WINDOW_SUMMARY.csv');volume=pd.read_csv(O/'VOLUME_ROLE_SUMMARY.csv');new=volume[volume.cohort.eq('NEW_WINDOW_BIRTH')]
 lines=['# Full 1709 causal market-state preflight','', '固定唯一算法，未运行账户、经济收益、股数、订单或成交。仅对固定输入计算市场根、fresh收据及覆盖；旧指标只作并列事实，未用PVR准入。', '', '## Coverage']
 for r in summary.itertuples():lines.append(f'- {r.window}: 1709股；已知价格覆盖{r.covered_stocks}股；出生{r.births}，fresh收据{r.receipts}，失效{r.failures}，根UNKNOWN {r.root_unknown}；窗口首日承接活根{r.carried_roots_at_start}。')
 lines += ['', '各窗22股明确为 NO_LOCAL_HISTORY_BY_END，不是未出信号的负例。全部748,542股日包括缺历史行；三窗总收据55,201，不是成交。完整同源历史先暖启动，窗口只裁输出。承接根及首日失效/UNKNOWN另见WINDOW_CARRY与ROOT_VOLUME_ROLE，不将窗口外出生当作不可参与。', '', '## Volume role, censored at each fixed window end']
 for r in new.itertuples():lines.append(f'- {r.window}: 出生已确认 {r.birth_already_confirmed}/{r.roots} ({100*r.birth_already_confirmed_fraction:.1f}%)；已知PROBE {r.birth_probe}，其中随后确认{r.new_probe_confirmed_later}，中位等待{r.confirmation_wait_median:g}个共同交易日；未确认且活跃/价格失效/价格UNKNOWN分别{r.new_probe_still_unconfirmed_active}/{r.new_probe_unconfirmed_price_failed}/{r.new_probe_unconfirmed_price_unknown}；出生金额UNKNOWN {r.birth_amount_unknown}。')
 lines += ['', '这些结果说明2022/2024大部分根在20High突破出生时已量态确认；量态不是价格首探闸门。是否产生账户层增量必须由独立同日/原持仓/手数必要条件预检回答，不能从这些比例推断优越或收益。', '', '## Source boundary is material', '2026H1的1,064次根UNKNOWN中，1,041发生于2026-05-18的 tushare_raw → ths_raw 身份切换，当前OHLC/factor坐标仍有效；其余23次是价格缺失/无效。严格跨源隔离是冻结合同，不是价格失效、更不是卖出。2026H1出生金额UNKNOWN 536中，516发生在该切源之后；新来源段的a前21金额基准不足，不补借旧源金额。原规则不因本次结果放宽。', '', 'NEXT_OPEN_SUMMARY只列紧邻共同OPEN的原价观察、源/factor匹配和日线一字事实。2026H1有195张6月30日收据的下一共同OPEN超出冻结输入边界。没有跳至之后可成交日、没有把一字当fill。', '', '## Verification and limits', '优化为机械迭代/读取替换，五股各4,595全warm行与冻结core全字段exact；46原synthetic全部通过，30真实输入截断前缀通过。独立审另做8股/48前缀。输入hash运行后全匹配，core原文未改。最终独审报告由独立worker另出。', '', '记录四次工程启动：第一次元数据字段错误，算首股但未写市场行；第二次保留177完整股后遇空facts dtype；第三次仅复用177股，空facts最终断言仍需dtype归一，未新增市场路径；第四次复用177股并算剩余1,532股。所有失败源码/hash/日志和checkpoint均保留，详见ENGINEERING_RECOVERY_CHAIN及RECOVERY_VALIDATION。未做参数搜索或第二套机制。', '', '边界：这是既看过历史窗口上的固定机制全域预检，不是样本外。当前股票池/行业成员非PIT；上游复权公告时钟、原E0/I/CP构建、停牌/涨跌停可达性及真实成交ACK未重审。只证明冻结上游输入条件下的本层因果与覆盖。', '']
 (O/'READOUT.md').write_text('\n'.join(lines))
 exclude=lambda p:p.name.startswith('independent_') or p.name.startswith('INDEPENDENT_') or p.name=='FINAL_MARKET_SEAL.json'
 files={p.name:sha(p) for p in sorted(O.iterdir()) if p.is_file() and not exclude(p)}
 save('FINAL_MARKET_SEAL.json',dict(status='SEALED_MARKET_OUTPUTS_INDEPENDENT_REVIEW_SEPARATE',files=files,excluded='Independent reviewer scripts/reports (independent_*, INDEPENDENT_*), FINAL_MARKET_SEAL self, and all subdirectories including overlap. Their own seals are separate. Original generation OUTPUT_HASHES retained as historical snapshot, possibly including then-present reviewer script.',archive_source_chain_sha256=sha(O/'ENGINEERING_RECOVERY_CHAIN.json'),market_parquets_unchanged_since_completed_run=True,all_current_input_hashes_reverified=True))
 print(json.dumps(dict(sealed_files=len(files),core=sha(O.parent/'independent_channel_probe_preflight_v1/core.py'),daily=sha(O/'DAILY_STATES.parquet'),receipts=sha(O/'RECEIPTS.parquet'),seal=sha(O/'FINAL_MARKET_SEAL.json'))))
if __name__=='__main__':main()
