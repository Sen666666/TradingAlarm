"""Publish reporting supplements without modifying the audited baseline seal."""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
O=Path(__file__).resolve().parent
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,x):(O/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
original=json.loads((O/'OUTPUT_HASHES.json').read_text())
for n,h in original.items():assert sha(O/n)==h,('immutable baseline drift',n)
r=pd.read_parquet(O/'RECEIPT_CONDITIONAL_OVERLAP.parquet');cohort=pd.read_csv(O/'WINNER_FULL_HOLD_FIXED_COHORT.csv');full=pd.read_csv(O/'WINNER_FULL_HOLD_COVERAGE.csv')
for c in ['entry_day','exit_day']:cohort[c]=pd.to_datetime(cohort[c],format='mixed')
with np.load(H,allow_pickle=False) as hh:cal=pd.DatetimeIndex(hh['dates'])
ci={d:i for i,d in enumerate(cal)};rows=[]
for c in cohort.itertuples():
 z=r[r.sid.eq(c.sid)&r.window.eq(c.window)&r.day.ge(c.entry_day)&r.day.lt(c.exit_day)].copy()
 feasible=z[z.conditional_unstarted_target_feasible]
 first=feasible.day.min() if len(feasible) else pd.NaT
 ro=full[full.round_id.eq(c.round_id)].iloc[0]
 rows.append(dict(round_id=c.round_id,window=c.window,sid=c.sid,old_entry_day=c.entry_day,old_exit_day=c.exit_day,existing_size_cache_receipts_in_entry_exit=len(z),existing_size_cache_q_feasible_receipts_in_entry_exit=len(feasible),at_least_one_q_feasible_market_receipt_in_entry_exit=bool(len(feasible)),first_observed_q_feasible_receipt_in_existing_size_cache=first,first_observed_q_feasible_next_common_open=cal[ci[first]+1] if pd.notna(first) else pd.NaT,first_feasible_size_Q=int(feasible.sort_values('day').iloc[0].close_conditional_q) if len(feasible) else None,size_all_full_hold_days_evaluated=False,full_hold_market_receipt_exists=bool(ro.fresh_receipts_entry_to_exit>0),actual_new_participation='NOT_SIMULATED',same_price_or_old_return_retained='NOT_PROVEN'))
f=pd.DataFrame(rows);assert f.at_least_one_q_feasible_market_receipt_in_entry_exit.all();assert (f.first_observed_q_feasible_next_common_open<f.old_exit_day).all()
f.to_csv(O/'WINNER_ENTRY_EXIT_SIZE_EXISTENCE.csv',index=False)
fs=f.groupby('window').agg(old_winners=('round_id','size'),q_feasible_receipt_exists_inside_entry_exit=('at_least_one_q_feasible_market_receipt_in_entry_exit','sum'),first_q_feasible_next_open_precedes_old_exit=('first_observed_q_feasible_next_common_open','size')).reset_index();fs.to_csv(O/'WINNER_ENTRY_EXIT_SIZE_EXISTENCE_SUMMARY.csv',index=False)
save('WINNER_ENTRY_EXIT_SIZE_EXISTENCE_QA.json',dict(passed=True,all_108_have_positive_q_receipt_strictly_inside_old_entry_exit=True,all_108_first_observed_feasible_receipt_next_open_strictly_precedes_old_exit=True,new_size_runs=0,first_date_semantics='First observed feasible date in the already computed fixed-window size cache, not the first possible feasible date in omitted calendar ranges.',source_hashes={str(O/n):sha(O/n) for n in ['RECEIPT_CONDITIONAL_OVERLAP.parquet','WINNER_FULL_HOLD_FIXED_COHORT.csv','WINNER_FULL_HOLD_COVERAGE.csv']}))
readout='''# 独立价格根全1709：旧渠道重合与条件执行预检

## 结论先说

这轮证明了独立stock/day价格许可的真实增量和旧大赢家路径的市场覆盖，没有证明新策略收益或完整参与。

- 2022出生4,057票，其中3,813票满足原24,000元初额/3,000元计划风险/日期整手费用/单边5bp滑点/原前量容量的“尚未创建parent”条件手数。按旧A+B已知空仓对照可行2,738票，其中514票与同日旧市场前置许可均不重合。进一步同时要求旧AB_FAST_SMALL也已知空仓，只剩414票；另41票旧快仍持仓、59票旧快UNKNOWN。两套旧状态都不代表新路径已空仓。
- 2024-09..12出生1,790票，条件手数1,739票，旧A+B已知空仓条件1,403票，同日旧市场前置许可不重合227票。该窗没有执行过同合同AB_FAST_SMALL，不能把缺缓存当快臂不持仓或不准入。
- 2026H1出生2,580票，条件手数2,217票。但同合同修复后的统一持仓未重建，全部旧主状态UNKNOWN，不能报告新增空仓资格为0，也不能宣称有多少真实新增。非半导体A+B原permit覆盖也UNKNOWN。

## 旧大赢家不是被首根失败直接丢掉

固定旧财务覆盖充分且CORE回报>=50%的2022 44轮、2024 64轮，108轮/104只去重股票，全部在严格旧entry≤收盘<exit区间有新的fresh receipt，而且已有固定窗size缓存足以证明108/108至少一票q>0，首个观察到的可行票对应次开均早于旧exit。它不是最后一个收盘的无意义机会。

另对这108轮补全了所有缺导出年份的完整共同日历市场路径，未重跑经济：旧signal时无价格根的29/17轮随后各有新根；当时已有根的15/47轮，其首次价格失败都对应旧退出的同一个次开，提前退出0，路径UNKNOWN0。此前只看固定导出窗时的12/26个PRICE_FAILED，同样都是正常同次开退出，不能当提前丢赢家。

这些都是市场许可和退出时钟覆盖，非同价入场、非旧收益保留、非新策略收益。完整市场表没有重算全持有期手数；first_observed_q_feasible只指已有size缓存中首个观察日期，不声称是遗漏日期中的最早可行票。亏损样本仍只使用固定窗可见区间，缺段保留窗口截断，不扩大重算。

## 增量不是全部“成熟历史更早启动”

按出生时E0成熟度分层：

- 2022：E0未ready 55票；ready但target=0有92票；E0=1而I=0有255票；E0/I均1有3,655票。514张条件独立票中36张属于E0未ready，不能把初始化更短当成熟历史提速。
- 2024：上述四类为6、60、86、1,638票；227张条件独立票中5张属于E0未ready。
- 2026：上述四类为31、54、192、2,303票；仅做市场事实和条件手数，不作空仓增量结论。

G完整分布见BIRTH_E0_MATURITY_SUMMARY.csv，不把I关闭机械归因为某单一原因。

## 2026切源边界与未成交后新证据

2026-05-18附近tushare→ths切源使1,041个有效价格根严格隔离为UNKNOWN，不是卖出、价格失败或真实持仓解锁。5/18后新出生526根，其中516根量信用UNKNOWN，须与切源前单列。模型未续接旧根，也未把旧I当退出。

若出生尝试未成交：2022/2024/2026分别3,408/1,646/2,096根在窗内后来有新frontier；649/144/484根没有后续票。没有新frontier就不自动重申。出生nextopen全日一字的11/13/8例后来都有新票，但一字仅是日线事实，不证明当时NOFILL，也不证明以后成交。真实ACK仍未知，只有晚于解锁known_at的新票才可能续同parent固定Q-F，不能按新S重新领24,000元。

## 合同与来源边界

- 新价格根/收据不AND回旧event_Q、I、G、PVR或行业门。原行业sector_known/observed_today/rs_ready/up仅分列对照；完整新行业准入和资源分配未在本轮逐项固定，new_full_trade_eligibility明确UNSPECIFIED。
- 原快精确臂为AB_FAST_SMALL。旧event_Q/continuing_Q只是原事实；未计消费的FAST_CORE/MOBILE_CP前置许可、2022真实角色检查/selected以及旧持仓各自分列。2024/26完整快臂准入UNKNOWN。
- 原A+B只保留A_SECTOR_BIRTH和B_STOCK_BIRTH_DURING_SECTOR，raw、I/PVR合格、旧selected分列。2026修复46例是固定半导体permit恢复，旧选股占位未重建，不能拼成统一持仓。
- 容量保持旧式：截至信号日收盘含当日的最近20个正raw_volume均量×1%，在次开冻结，故对次开严格属前量。收盘可行检查不读未来open；次开检查单独输出，不用当日后续HLC/volume/amount flags。
- 对signal→open因子变化没有套用修复引擎的特殊pending权益桥，标FACTOR_BRIDGE_NOT_EVALUATED_UNKNOWN，不是NOFILL。原修复引擎某些已验证权益事件可桥接，故本预检不是其完整执行等价实现。
- 条件q仅是从未创建parent的上界。逐receipt数量不能相加，同根不能重复24,000元；无新账户、订单、成交、真实ACK或新收益。UNKNOWN不当false、卖出或flat。
- 1709固定现时池并非PIT成员；22无本地观察单列，不当负例。上游复权/原生事实因果性未由这轮重新证明。

## 验证与文件

旧Q扩展2024/2026共334,964行，抽取2022两日3,418 stock-days所有原列exact。旧A+B 19,795条decision、旧快52,453条decision的状态重构均exact。完整固定赢家扩展与原固定窗27,490 stock-days逐列exact。全部旧输入hash未变。

主表：DAILY_OVERLAP.parquet；BIRTH_CONDITIONAL_OVERLAP.parquet；RECEIPT_CONDITIONAL_OVERLAP.parquet；UNSTARTED_TARGET_SIZE_CHECKS.parquet；2026半导体子表。

先读：OVERLAP_SUMMARY.csv、DUAL_OLD_REFERENCE_FLAT_SUMMARY.csv、WINNER_FULL_HOLD_SUMMARY.csv、WINNER_ENTRY_EXIT_SIZE_EXISTENCE_SUMMARY.csv、BIRTH_E0_MATURITY_SUMMARY.csv、IF_BIRTH_UNFILLED_SUMMARY.csv。

旧亏损/赢家同行业同日slots仅潜在竞争。没有新排名，所以不能断言真挤出，也没把事后收益标签加入任何门槛。原44/64赢家中1/10例存在独立市场票与原两slot同日潜在竞争，仅是排队风险线索。

基线OUTPUT_HASHES.json保持不变。附表、本文与完整赢家补全另由SUPPLEMENT_OUTPUT_HASHES.json封存；独立审计结果单独交付。
'''
(O/'READOUT.md').write_text(readout)
for n,h in original.items():assert sha(O/n)==h
supp={p.name:sha(p) for p in sorted(O.iterdir()) if p.is_file() and p.name not in original and p.name not in ['OUTPUT_HASHES.json','SUPPLEMENT_OUTPUT_HASHES.json','MERGE_RUN.log']}
save('SUPPLEMENT_OUTPUT_HASHES.json',dict(immutable_baseline_seal_sha256=sha(O/'OUTPUT_HASHES.json'),supplement_files=supp))
print(fs.to_string(index=False));print('supplement files',len(supp))
