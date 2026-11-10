import json, hashlib, re
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal
import pandas as pd

ROOT=Path('/Users/bytedance/Documents/Codex/2026-11-09/sector51_924_entry_review_v1')
O=ROOT/'joint_equity_evidence_v1/300277_suspension_v1'
SID='300277.SZ'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v): Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def compact(t): return re.sub(r'\s+','',t)
source_index=json.loads((O/'OFFICIAL_SOURCES.json').read_text())
fragments={
'2024-071':['证券代码：300277','股票自2024年10月28日（星期一）开市起停牌','预计停牌时间不超过10个交易日','2024年10月25日'],
'2024-072':['公司股票将继续停牌','2024年11月1日'],
'2024-076':['将于2024年11月11日（星期一）开市起复牌','2024年11月9日']
}
for s in source_index:
 p=Path(s['path']); assert sha(p)==s['sha256']
 t=p.with_suffix('.pdf.txt'); text=compact(t.read_text())
 for frag in fragments[s['notice_number']]: assert compact(frag) in text,(s['notice_number'],frag)
 s['text_path']=str(t);s['text_sha256']=sha(t)
 s['signature_date']={'2024-071':'2024-10-25','2024-072':'2024-11-01','2024-076':'2024-11-09'}[s['notice_number']]
 # Short original excerpts, one per notice.
 s['excerpt']={
 '2024-071':'股票自2024 年 10 月 28日（星期一）开市起停牌',
 '2024-072':'根据深圳证券交易所相关规定，公司股票将继续停牌。',
 '2024-076':'年 11 月 11 日（星期一）开市起复牌。'
 }[s['notice_number']]
 s['excerpt_whitespace_normalized_only']=False
manifest=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
entry=next(x for x in json.loads(manifest.read_text()) if x['symbol']==SID)
sp=next(Path(x) for x in entry['source_sha256'] if x.endswith('/signal.parquet'))
assert sha(sp)==entry['source_sha256'][str(sp)]
d=pd.read_parquet(sp)
before=d.loc[:'2024-10-27'].tail(1)
after=d.loc['2024-10-28':].head(1)
assert before.index[0].strftime('%Y-%m-%d')=='2024-10-25'
assert after.index[0].strftime('%Y-%m-%d')=='2024-11-11'
expected_dates=['2024-10-28','2024-10-29','2024-10-30','2024-10-31']
assert all(pd.Timestamp(x) not in d.index for x in expected_dates)
cols=['source_kind','source_path','segment_id']
same_lineage=all(before.iloc[0][c]==after.iloc[0][c] for c in cols)
assert same_lineage
assert before.iloc[0]['adjustment_factor']==after.iloc[0]['adjustment_factor']
signal_subset=json.loads(d.loc['2024-10-21':'2024-11-11'].reset_index().to_json(orient='records',date_format='iso',double_precision=15))
snapshot_path=O/'LOCAL_SOURCE_AND_EXPOSURE.json'
act=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v1/actions/300277.SZ.json')
events_in_gap=[e for e in json.loads(act.read_text())['events'] if '2024-10-28'<=e['effective_date']<='2024-11-10']
assert events_in_gap==[]
input_paths=[manifest,sp,act]
holdings={}
for name,folder in [('baseline',ROOT/'joint51_candidate_v9_facts/full_20241031_once'),('oneprice_stress',ROOT/'oneprice_execution_stress_v1/facts_v9/full_20241031_once')]:
 hp=folder/'HOLDINGS.json'; bp=folder/'BLOCKERS.json'
 rows=[r for r in json.loads(hp.read_text()) if r['sid']==SID]
 assert rows[-1]['day']=='2024-10-25' and rows[-1]['qty']==100
 assert rows[-1]['raw_mark']=='12.02' and rows[-1]['market_value']=='1202.00'
 holdings[name]={'path':str(hp),'sha256':sha(hp),'rows':rows,'blockers_path':str(bp),'blockers':json.loads(bp.read_text())}
 input_paths += [hp,bp]
diag=ROOT/'joint51_candidate_v9_facts/BLOCKED_DAY_ALL_ISSUES.json'
input_paths.append(diag)
dump(snapshot_path,{'sid':SID,'manifest_entry':entry,'signal_path':str(sp),'signal_sha256':sha(sp),'adjacent_source_rows':signal_subset,'missing_requested_dates':expected_dates,'next_observation_date':'2024-11-11','same_lineage_across_gap':bool(same_lineage),'same_adjustment_factor_across_gap':True,'local_actions_in_gap':events_in_gap,'holdings':holdings,'baseline_diagnostic':json.loads(diag.read_text())})
evidence={str(p):sha(p) for p in input_paths}
for p in [O/'OFFICIAL_SOURCES.json',O/'CNINFO_ANNOUNCEMENT_QUERY.json',snapshot_path,Path(__file__)]:
 evidence[str(p)]=sha(p)
for s in source_index:
 evidence[s['path']]=s['sha256']; evidence[s['text_path']]=s['text_sha256']
fact={
 'schema':'reviewed_official_suspension_fact_v1',
 'sid':SID,'name_at_event':'海联讯','fact_type':'OFFICIAL_TRADING_SUSPENSION',
 'scope':'Facts and proposed research-account boundary only. Not an old-engine equity-event adapter.',
 'reviewed_at_utc':datetime.now(timezone.utc).isoformat(),
 'suspension_start':'2024-10-28','suspension_start_phase':'OPEN',
 'requested_window':['2024-10-28','2024-10-31'],'verified_nontradable_dates':expected_dates,
 'retrospectively_confirmed_resume_date':'2024-11-11','resume_phase':'OPEN',
 'retrospective_last_suspended_session':'2024-11-08',
 'reason':'筹划海联讯向杭汽轮全体股东发行A股，通过换股方式吸收合并杭汽轮，构成拟重大资产重组及关联交易；初始公告说明仍在筹划，方案及实施不确定。',
 'transaction_is_proposal_not_effective_share_conversion':True,
 'official_sources':source_index,
 'source_observations':{'previous_observed_date':'2024-10-25','previous_raw_close':'12.02','previous_adjustment_factor':str(before.iloc[0]['adjustment_factor']),'next_observed_date':'2024-11-11','missing_requested_dates':expected_dates,'lineage_equal_on_adjacent_observations':bool(same_lineage),'factor_equal_on_adjacent_observations':True,'local_actions_in_gap':events_in_gap,'note':'相邻两条源记录一致仅作事后核对，不能生成停牌日OHLC或把11月11日数据提前用于10月。SOURCE_CHANGE/FACTOR_UNCHECKABLE在该缺行上不证明真实源切换。'},
 'exposure':{'baseline_last_complete_day':'2024-10-25','stress_last_complete_day':'2024-10-25','qty_each_branch':100,'last_observed_market_value_each_branch':'1202.00','currency':'CNY','buy_day':'2024-10-23'},
 'point_in_time_limits':[
 '初始停牌公告落款2024-10-25，巨潮展示公告日2024-10-28；本次2026年取证的HTTP Last-Modified为2024-10-27 07:32:29 GMT，可作为发布前日的补充线索，但不是独立历史抓取归档，也不把日期字段解释为确切可得时刻。',
 '11月2日延续公告和11月11日复牌公告仅用于事后验证完整区间；10月28日至31日决策不得预知11月11日复牌日期或价格。',
 '这是一套明确披露的历史研究事实补证，不宣称生产级逐时点PIT认证。'
 ],
 'proposed_accounting_boundary_not_implemented':{
 'requires_new_version_and_explicit_contract':True,'old_frozen_v9_remains_blocked':True,
 'no_tradable_open_on_suspended_dates':True,'no_OHLC_rows_to_insert':True,
 'position_quantity_retained_without_effective_equity_event':True,'no_sale_cash_or_turnover_or_fee_or_fill_from_suspension':True,
 'optional_research_mark':{'method':'LAST_OBSERVED_RAW_CLOSE_CARRY_FOR_VALUATION_ONLY','raw_mark':'12.02','mark_source_day':'2024-10-25','qty':100,'illustrative_market_value':'1202.00','observed_bar':False,'tradable':False,'stale':True,'not_official_fair_value':True,'not_liquidation_value':True},
 'signal_and_order_boundary':[
 '成交条件与估值分离。停牌时不执行买卖、不以沿用价格触发价格型止损/CP突破/加仓或假造新bar；订单等待/有效期和锁定退出需在新合同中明确。',
 '可独立计算的板块退出条件如需保留只能记录退出意图，不能释放卖出现金；如何顺延和复牌后处理由新合同明示。',
 '不能把拟合并当成已完成换股、现金分红或因子调整，也不能仅因缺行删股。',
 '恢复后也必须以当时可用真实报价、公司行动桥和成交限制另行判断；复牌公告不保证任何方向可成交。'
 ],
 'reporting_required':['独立版本名和参数/规则差异','截至10月25日旧前缀精确重放','每日停牌持仓与沿用标记金额','账面权益与可立即成交/变现能力分离','不把已估值到10月31日描述为已逐股真实可成交到10月31日']
 },
 'evidence_hashes':evidence,
 'performed_actions':{'official_pdf_downloads':3,'engine_changed':False,'source_price_changed':False,'account_executed':False,'other_stocks_scanned':False}
}
fact_path=O/'SUSPENSION_FACT_300277_V1.json'; dump(fact_path,fact)
seal_paths=list(O.glob('*'))
seal={str(p):sha(p) for p in seal_paths if p.is_file() and p.name!='EVIDENCE_SEAL.json'}
dump(O/'EVIDENCE_SEAL.json',{'sealed_at_utc':datetime.now(timezone.utc).isoformat(),'files':seal,'fact_sha256':sha(fact_path)})
# End-to-end verify generated fact evidence, including frozen input files.
for p,h in fact['evidence_hashes'].items(): assert sha(p)==h,(p,h)
for p,h in seal.items(): assert sha(p)==h,(p,h)
print(json.dumps({'fact_path':str(fact_path),'fact_sha256':sha(fact_path),'seal_sha256':sha(O/'EVIDENCE_SEAL.json'),'verified_evidence_files':len(evidence),'status':'PASS','missing_requested_dates':expected_dates,'last_raw_close':'12.02','each_branch_qty':100,'source_unchanged':True},ensure_ascii=False,indent=2))
