from pathlib import Path
import json,csv,hashlib,collections,datetime
import pandas as pd
O=Path(__file__).resolve().parent;R=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');BASE=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market');OLD=BASE/'update-20261027-153013-2ffe04/prepared';NEW=BASE/'update-20261030-153010-c551af/prepared'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False))
def main():
 summary=read(O/'SUMMARY.json');rows=read(O/'PREFIX_FIELDS.json');packets=read(O/'DAY_PACKETS.json');proof=read(O/'GATE_TESTS.json');assert proof['passed'];assert not any(x['commit_allowed'] for x in packets);sources={};actual=[]
 for sec,p,roster in [('TECH',R/'pvr-act-comparison-20261027/input/manifest.json',R/'tech-compound-design-20261026/proposed-pool.csv'),('DRUG',R/'innovative-drug-sfw3-20261028/prepared/manifest.json',R/'innovative-drug-local-recovery-20261028/pool.csv')]:
  rs=list(csv.DictReader(roster.open()));ids={x['symbol'] for x in rs}|{x['sector_id'] for x in rs};m={x['series_id']:x for x in read(p)['series']};old={x['series_id']:x for x in read(OLD/'manifest.json')['series']};actual.append(dict(sector=sec,actual_old_manifest=str(p),required_series=len(ids),raw_hash_diff_from_10_27_snapshot=[s for s in ids if m[s]['raw']['sha256']!=old[s]['raw']['sha256']]))
  for folder in [OLD,NEW]:
   records={x['series_id']:x for x in read(folder/'manifest.json')['series']}
   for sid in ids:
    rec=records[sid]
    for v in [rec['raw']]+([rec['adjustment']['actions']] if 'actions' in rec.get('adjustment',{}) else []):assert sha(Path(v['path']))==v['sha256'];sources[v['path']]=v['sha256']
 assert all(not x['raw_hash_diff_from_10_27_snapshot'] for x in actual)
 freeze=read(O.parent/'lr1-cp1-add-preflight-20261031/FREEZE.json');assert all(sha(Path(p))==h for p,h in freeze['sha256'].items())
 save(O/'SOURCE_VERIFICATION.json',dict(original_frozen_files_checked=len(freeze['sha256']),all_unchanged=True,relevant_declared_hash_checks=len(sources),actual_original_L0_raw_inputs=actual,sources=sources))
 factor_checks=[]
 import numpy as np
 h1=np.load(NEW/'h1.npz');hdates=pd.DatetimeIndex(h1['dates']);hcol={str(s):j for j,s in enumerate(h1['symbols'])};hclose=h1['close']
 for row in read(O/'ACTIONS.json'):
  for e in row['new_events']:
   sid=row['sid'];day=pd.Timestamp(e['effective_date']);path=NEW/'facts'/f'{sid}.parquet'
   if path.exists():
    f=pd.read_parquet(path);before=f.loc[f.index<day].iloc[-1];now=f.loc[day];previous_raw=float(before.raw_close);observed=float(now.factor)/float(before.factor);basis='persisted_TECH_facts_factor'
   else:
    f=pd.read_parquet(NEW/'bars'/f'{sid}.parquet').set_index('trade_date');previous=f.loc[f.index<day].iloc[-1];previous_day=f.loc[f.index<day].index[-1];previous_raw=float(previous.close);previous_factor=hclose[hdates.get_loc(previous_day),hcol[sid]]/previous_raw;current_factor=hclose[hdates.get_loc(day),hcol[sid]]/float(f.loc[day,'close']);observed=current_factor/previous_factor;basis='H1_reference_close_divided_by_raw_only_not_G1_factor_cache'
   expected=previous_raw/(previous_raw-float(e['cash_per_old_share']))
   factor_checks.append(dict(sid=sid,day=str(day.date()),basis=basis,factor_ratio=observed,theoretical_cash_ex_ratio=expected,relative_error=abs(observed/expected-1),prefix_factor_changed=False))
 assert all(x['relative_error']<1e-12 for x in factor_checks);save(O/'NEW_FACTOR_UNIT_CHECK.json',factor_checks)
 counts=dict(collections.Counter(r['status'] for r in rows));assert counts=={'same_prefix':1306,'missing':104};assert all(not p['unknown_active_floors'] for p in packets)
 old_end=[]
 import gzip
 with gzip.open(O.parent/'lr1-cp1-add-preflight-20261031/TECH/full/results/daily.jsonl.gz','rt') as f:daily=[json.loads(x) for x in f]
 for name in ['L0_base','L0_delay1']:
  z=[x for x in daily if x['account']==name][-1];old_end.append(dict(account=name,at=z['at'],ACT_on=z['on'],positions=len(z['positions']),pending_sells=len(z['pending_sells']),pending_intents=z['pending_intents'],nav=z['nav']))
 assert all(not z['ACT_on'] and not z['positions'] and not z['pending_sells'] and not z['pending_intents'] for z in old_end)
 save(O/'BRIDGE_STATUS.json',dict(historical_content_continuity_passed=True,prefix_comparison_counts=counts,TECH_safe_to_commit_under_frozen_clock=False,DRUG_safe_to_commit=False,new_day_replays=0,old_state_or_decisions_changed=False,long_history_replays=0,old_end=old_end,new_TECH_market_breakout=[x['breakout'] for x in read(O/'MARKET_PREFIX.json')['new_rows']],complete_10_27_checkpoint_not_saved=True,checkpoint_preparation_deferred=True,connection_or_permission_block=False,external_calls=0,production_writes=0))
 text='''L0 10/27→10/30接续准入：共同历史通过，数据时序/覆盖闸门阻塞；3日追加未启动。

来源与实际时刻（+08）
旧 runtime/market/update-20261027-153013-2ffe04/prepared，10/27导出15:52:30.222281；新update-20261030-153010-c551af/prepared，10/30导出15:51:45.143151。另核现有10/28、29日包receipt，分别15:52:09.519478、15:52:06.461332。新包保留逐日observed_at，未把10/30当作10/28取得时刻。

截至10/27哪些一致
407科技+48药+15行业共470序列；1306对存在的bars/signals/facts逐值一致，无旧日丢失/补入或字段修订；另104对缺失是药52序列的signals/facts，不能算一致或填0。原实际L0两池的raw manifest与旧快照470条raw SHA一致，未拿错基线。
科技418条原价/量额、信号调整价/因子、I事件/E0/floor/G1前缀精确相同。H1的1799序列/4674历史日/7组数组及顺序全相同。TECH市场market/prior_high63/breadth/breakout3352历史日全相同，数值差0；455股历史权息事件相同。文件哈希变化来自追加三日/三次现金分红/新导出，不是历史账被改写；无旧因子重新定标，三次新因子跳变与毛现金除息公式相符。
成员和行业仍冻结407/48名单、旧行业映射，更新器不改变1709股/90行业参照；不是点时历史成员。Q不是独立缓存列，本轮核其历史输入和原函数不变，未重建整段Q，也未把新日Q未知视作True。

新三日覆盖与确切阻塞
1. 10/28、29、30各有470条原价/量额，volume均正。科技418条signals/facts逐日完整，I-active而floor未知0；但每条raw observed_at都在15:48左右，晚于原15:10决策钟，发布约15:52。close_available_time15:05是旧研究假设，不证明本机15:10实际取得。这不是公开市场数据必然晚到或历史泄漏的结论，而是影子运行可得性证据未闭合，不能倒填known_at。
2. 药48股+4行业只有原价bars，signals/facts 0/52；实际旧缓存innovative-drug-sfw3-20261028/prepared/facts仍到10/27，本池ACT恢复文件innovative-drug-local-recovery-20261028/recovery.csv也止于10/27。通用新快照recovery是科技时钟，不能当药的本池时钟；否则会改变4行业最低3行业覆盖等原语义。旧代码/原始行情在本地，但补齐需单独数据制作，本轮未重算指标或伪造日包。
3. 新现金分红为300601/10-28(每股0.027)、300604/10-30(0.10)、688409/10-30(0.20)。source条款有生效日，paid_at均None、公告首次known_at没有。新源响应接收分别当日15:36:33、15:36:25、15:46:17，已查此前本地响应未含该未来事件，不能证明除息开盘前已知。缺到账日可沿原应收不再投合同处理，缺公告可知时间不能这样补造；本次均现金分红，新增股可卖日不适用。详见ACTION_KNOWLEDGE及因子核验，不据此编造交易损失。
4. 旧执行适配日历只到10/30，末日决策需要下一交易日；本地desk/calendar.json已有带交易所来源/标记10/27核验且覆盖2026末的日历，可确定11/2，不需API或weekday猜测。这是可修复接口，不是本地无日历，本轮没有改原日历。
5. 新快照没有真实停牌/涨跌停限价/盘口、点时上市/ST链，availability_versions仍原明确代理。原价历史可证明这些成员已有实际价格观察，不能冒充官方点时上市档案。历史成员/退市偏差仍保留。

承接状态与最小实现
旧完整10/27检查点没有保存，full结果日志不够恢复所有锁/ACT/挂单。此前已验05/08检查点可技术回放构造，需数据闸门通过后再做；本轮未为了跑出零交易启动长前缀。
prepare_packets.py生成真实两池×3日共6包，按冻结15:10检查，全部明确拒绝commit，未知/缺文件保留独立原因。GATE_TESTS验证数据不回填、不补0、下一交易日有本地来源。金融状态跨版本接续尚未实施；没有3日净值结果，也不能声称新3日重启/幂等已验收。此前同快照11日恢复工程通过的结论不变。
暴露边界：旧科技L0正常及delay1在10/27均ACT暂停、持仓/挂单0；新三日breakout也全False。即使按旧代理跑出零交易，也不能验证持仓权息或真实成交，这是可观察状态，不是已回放结果。

下一最小决定
先明确实际发布后的研究决策时钟合同（仅新日，不改旧15:10记录，同时审订单有效期/次开盘语义），以及药本池缓存/时钟、权益首次可知来源。不自动把timestamp挪后或把unknown忽略来过闸；这些需要有事实依据的接线合同。本轮无新买卖算法、账户矩阵、下载、API、生产写入、交易/调度。
'''
 text+='\n各日实际来源与发布：\n'
 for p in packets:
  if p['sector']=='TECH':text+=f"{p['day']}: raw {p['source_observed_at_min']}..{p['source_observed_at_max']}；发布{p['export_receipt']['published_at']}；次交易日{p['next_legal_market_session']}。\n"
 text+='\n证据：INPUT_IDENTITY/PREFIX_FIELDS/H1_PREFIX/MARKET_PREFIX/ACTIONS/ACTION_KNOWLEDGE/NEW_FACTOR_UNIT_CHECK/LATEST_FIELDS/DAY_PACKETS/GATE_TESTS/BRIDGE_STATUS/SOURCE_VERIFICATION.json；audit.py/prepare_packets.py/PROTOCOL.txt。\n'
 (O/'FINAL_REPORT.txt').write_text(text)
 now=datetime.datetime.now(datetime.timezone.utc);wall=(now-datetime.datetime.fromtimestamp((O/'PROTOCOL.txt').stat().st_mtime,datetime.timezone.utc)).total_seconds();completion=dict(status='complete_with_data_contract_blockers',at=now.isoformat(),new_economic_paths=0,new_day_replays=0,preflight_packets=6,all_packets_refused=True,historical_content_continuity=True,original_frozen_files_unchanged=len(freeze['sha256']),reported_successful_audit_seconds=summary['calculation_seconds'],packet_validation_seconds=proof['seconds'],wall_since_protocol_seconds=wall,timing_caveat='first sector/action-shape parsing failure not separately timed; source reading before protocol excluded',connection_or_permission_block=False,blockers=['source observed/exported after frozen15:10 clock','DRUG I/G1/E0 and own market not extended','new action preopen known_at not certified'],no_old_state_or_production_changes=True)
 save(O/'COMPLETION.json',completion);save(O/'CHECKPOINT.json',completion);files=[p for p in O.rglob('*') if p.is_file() and p.name!='DELIVERABLE_SHA256.json'];save(O/'DELIVERABLE_SHA256.json',{str(p.relative_to(O)):sha(p) for p in files});print('COMPLETE',counts,'old frozen',len(freeze['sha256']),'wallmin',wall/60,'new replays',0,flush=True)
if __name__=='__main__':main()
