import json,hashlib,re
from pathlib import Path
from datetime import datetime,timezone
import pandas as pd
ROOT=Path('/Users/bytedance/Documents/Codex/2026-11-09/sector51_924_entry_review_v1')
O=ROOT/'joint_equity_evidence_v1/002064_suspension_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
sources=json.loads((O/'OFFICIAL_SOURCES.json').read_text())
for x in sources:
 aid=x['row']['announcementId'];p=Path(x['path']);assert sha(p)==x['sha256']
 t=p.with_suffix('.pdf.txt');body=re.sub(r'\s+','',t.read_text());assert '证券代码：002064' in body
 if aid=='1221543754':
  assert '自2024年10月29日开市时起开始停牌' in body
  assert '本次交易预计不构成重大资产重组' in body
  x.update(notice_number='2024-042',publication_date='2024-10-29',signature_date='2024-10-28',excerpt='自 2024 年 10 月 29 日开市时起开始\n停牌。')
 else:
  assert aid=='1221604670' and '公司股票将于2024年11月4日开市起复牌' in body
  x.update(notice_number='2024-043',publication_date='2024-11-02',signature_date='2024-11-01',excerpt='公司股票将于 2024 年11 月4 日开市起复牌。')
 x['text_path']=str(t);x['text_sha256']=sha(t)
manifest=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
entry=next(x for x in json.loads(manifest.read_text()) if x['symbol']=='002064.SZ')
sp=Path(next(x for x in entry['source_sha256'] if x.endswith('/signal.parquet')));assert sha(sp)==entry['source_sha256'][str(sp)]
d=pd.read_parquet(sp);old=d.loc[:'2024-10-28'].iloc[-1];new=d.loc['2024-10-29':].iloc[0]
assert str(old.name.date())=='2024-10-28' and str(new.name.date())=='2024-11-04'
assert str(old.raw_close)=='8.11' and str(old.adjustment_factor)=='2.277636261313823'
assert all(old[k]==new[k] for k in ['source_kind','source_path','segment_id','adjustment_factor'])
requested=['2024-10-29','2024-10-30','2024-10-31']
assert all(pd.Timestamp(x) not in d.index for x in requested)
ap=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v1/actions/002064.SZ.json')
actions=[x for x in json.loads(ap.read_text())['events'] if '2024-10-29'<=x['effective_date']<='2024-11-03'];assert not actions
hp=ROOT/'joint51_candidate_v10_suspension_accounting/full_20241031_once/HOLDINGS.json';hold=[x for x in json.loads(hp.read_text()) if x['sid']=='002064.SZ'];last=[x for x in hold if x['day']=='2024-10-28'];assert sum(x['qty'] for x in last)==100 and last[0]['raw_mark']=='8.11'
diag=ROOT/'joint51_candidate_v10_suspension_accounting/BLOCKED_DAY_ALL_ISSUES.json'
snapshot=O/'LOCAL_SOURCE_AND_EXPOSURE.json';dump(snapshot,{'sid':'002064.SZ','manifest_entry':entry,'signal_path':str(sp),'signal_sha256':sha(sp),'adjacent_rows':json.loads(d.loc['2024-10-23':'2024-11-04'].reset_index().to_json(orient='records',date_format='iso',double_precision=15)),'held_rows':hold,'holdings_path':str(hp),'holdings_sha256':sha(hp),'missing_requested_dates':requested,'no_local_equity_action_in_gap':True,'diagnostic':json.loads(diag.read_text()),'same_lineage_and_factor_adjacent_observations':True})
ev={str(p):sha(p) for p in [sp,ap,manifest,hp,diag,snapshot,O/'OFFICIAL_SOURCES.json',O/'CNINFO_ANNOUNCEMENT_QUERY.json',Path(__file__)]}
for s in sources:ev[s['path']]=s['sha256'];ev[s['text_path']]=s['text_sha256']
fact={'schema':'reviewed_official_suspension_fact_v1','sid':'002064.SZ','name_at_event':'华峰化学','fact_type':'OFFICIAL_TRADING_SUSPENSION','scope':'Actual v10 blocker only; facts and proposed boundary, no automatic extension of 300277 exception.','reviewed_at_utc':datetime.now(timezone.utc).isoformat(),'suspension_start':'2024-10-29','suspension_start_phase':'OPEN','requested_window':['2024-10-29','2024-10-31'],'verified_nontradable_dates':requested,'retrospectively_confirmed_resume_date':'2024-11-04','resume_phase':'OPEN','retrospective_last_suspended_session':'2024-11-01','reason':'拟发行股份及支付现金购买浙江华峰热塑性聚氨酯有限公司及浙江华峰合成树脂有限公司各100%股权，构成关联交易。官方初始公告预计不构成重大资产重组、不构成重组上市；仍属筹划，不能当成已完成股本或现金事件。','official_sources':sources,'source_observations':{'previous_observed_date':'2024-10-28','previous_raw_close':'8.11','previous_adjustment_factor':'2.277636261313823','next_observed_date':'2024-11-04','missing_requested_dates':requested,'adjacent_same_lineage_and_factor':True,'no_local_equity_event_in_gap':True,'note':'后一观测只用于事后诊断；不生成缺失日factor或OHLC，SOURCE_CHANGE诊断在缺行时不证明真实切源。'},'exposure':{'last_complete_day':'2024-10-28','registered_held_qty':100,'buy_day':'2024-10-23','last_observed_market_value':'811.00','currency':'CNY'},'point_in_time_limits':['初始公告落款10月28日，巨潮展示披露10月29日，当前HTTP Last-Modified为10月28日12:14:53 GMT，支持事前发布线索但不是原时点归档。不得把日期字段冒称精确盘中可得时间。','复牌公告落款11月1日、披露11月2日；11月4日复牌及之后行情只用于事后核验，不能提前用于10月29日至31日决策。','这不是生产级PIT认证。'], 'proposed_accounting_boundary_not_implemented':{'requires_new_version_and_explicit_contract':True,'old_v10_remains_blocked':True,'no_automatic_extension_of_300277_exception':True,'tradable_on_suspension_dates':False,'no_OHLC_or_factor_rows_to_insert':True,'optional_valuation_only_mark':{'price':'8.11','source_day':'2024-10-28','qty':100,'illustrative_market_value':'811.00','stale':True,'observed_bar':False,'not_official_fair_value':True,'not_liquidation_value':True},'requirements':['持仓和未成交意图不能因缺价被删除；不得以沿用估值生成价格触发、买卖成交或销售现金。','即使允许独立停牌估值，也必须同一新版本明确验证旧前缀、披露标记日期/金额和不可成交边界。','不能用公告提议的资产购买直接更改股数、现金、调整因子。复牌后的成交仍须依当时真实行情及交易限制另行验证。']},'evidence_hashes':ev,'performed_actions':{'engine_changed':False,'source_price_changed':False,'account_executed':False,'other_stocks_scanned':False}}
fp=O/'SUSPENSION_FACT_002064_V1.json';dump(fp,fact)
for p,h in ev.items():assert sha(p)==h,(p,h)
seal={str(p):sha(p) for p in O.iterdir() if p.is_file() and p.name!='EVIDENCE_SEAL.json'};dump(O/'EVIDENCE_SEAL.json',{'files':seal,'fact_sha256':sha(fp)})
print(json.dumps({'fact_path':str(fp),'fact_sha256':sha(fp),'evidence_hash_count':len(ev),'status':'PASS'},ensure_ascii=False,indent=2))
