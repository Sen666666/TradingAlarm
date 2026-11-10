import json, hashlib, re, math
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal
import pandas as pd

ROOT=Path('/Users/bytedance/Documents/Codex/2026-11-09/sector51_924_entry_review_v1')
CODE=Path(__file__).parent.name.split('_')[0]
O=Path(__file__).parent
SID=CODE+('.SH' if CODE=='603268' else '.SZ')
CFG={
 '603268':{
  'name':'松发股份','resume':'2024-10-17','last_suspended':'2024-10-16',
  'suspended_sessions':['2024-09-30','2024-10-08','2024-10-09','2024-10-10','2024-10-11','2024-10-14','2024-10-15','2024-10-16'],
  'reason':'筹划出售部分或全部资产及负债，并以资产置换、发行股份购买资产等方式购买恒力重工若干股权或其下属子公司若干股权，同时拟募集配套资金；初始公告的标的范围和交易方案尚未最终确定。',
  'notices':{
    '1221330013':{'notice_number':'2024临-046','signature_date':'2024-10-01','role':'INITIAL_FORMAL_NOTICE_RETROSPECTIVE_FOR_0930','fragments':['已于2024年9月30日（星期一）开市起停牌','将于2024年10月8日（星期二）开市起继续停牌','2024年10月1日']},
    '1221366248':{'notice_number':'2024临-048','signature_date':'2024-10-12','role':'CONTINUED_SUSPENSION','fragments':['公司股票将继续停牌','2024年10月12日']},
    '1221408477':{'notice_number':'2024临-052','signature_date':'2024-10-17','role':'RESUMPTION','fragments':['公司股票将于2024年10月17日（星期四）开市起复牌','2024年10月17日']}
  },
  'pit':[
   '初始正式公告2024临-046的披露日和落款均为2024-10-01，其正文追认股票已于9月30日开市停牌；表格所列10月8日为继续停牌安排，不能误当成首次停牌日。',
   '本次2026年取证HTTP Last-Modified为2024-09-30 08:46:46 GMT（北京时间16:46:46），仅是现时服务器元数据。它及10月1日日期均不能证明9月30日开盘前正式公告已可知。',
   '有限范围检索未取得9月30日开盘前的上交所正式停牌提示或历史时点归档。不能把未取得证据表述为当时不存在提示；严格盘前PIT可知性仍未认证。',
   '10月12日延续公告和10月17日复牌公告用于事后验证停牌区间，9月30日决策不得预知复牌日、价格或重组后续进展。'
  ],
  'pit_certification':'HISTORICAL_SUSPENSION_CONFIRMED_PREOPEN_KNOWABILITY_UNPROVEN',
 },
 '300489':{
  'name':'光智科技','resume':'2024-10-14','last_suspended':'2024-10-11',
  'suspended_sessions':['2024-09-30','2024-10-08','2024-10-09','2024-10-10','2024-10-11'],
  'reason':'筹划以发行A股股份等方式购买先导电子科技股份有限公司控制权，并募集配套资金，预计构成重大资产重组及关联交易；初始公告说明交易方案及最终收购比例尚未确定。',
  'notices':{
    '1221314103':{'notice_number':'2024-075','signature_date':'2024-09-30','role':'INITIAL_SUSPENSION','fragments':['自2024年9月30日开市时起开始停牌','2024年9月30日']},
    '1221368168':{'notice_number':'2024-081','signature_date':'2024-10-14','role':'RESUMPTION','fragments':['将于2024年10月14日（星期一）开市起复牌','2024年10月14日']}
  },
  'pit':[
   '初始正式公告2024-075的披露日和落款均为2024-09-30。巨潮announcementTime为日期字段，不作为准确到小时的首次发布时间。',
   '本次2026年取证HTTP Last-Modified为2024-09-29 07:30:43 GMT（北京时间15:30:43），提供前一日文件已存在的补充线索，但不是独立历史抓取归档，不据此宣称严格逐时点PIT认证。',
   '初始公告披露预计不超过10个交易日，并规定未能在期限内披露方案则最晚10月21日复牌及终止筹划的条件安排。此条件期限不等于已确定的实际复牌日；实际10月14日复牌只能由后续公告事后确认。',
   '10月14日复牌公告仅用于事后验证区间；9月30日决策不得预知10月14日复牌日、价格或后续方案。'
  ],
  'pit_certification':'HISTORICAL_SUSPENSION_CONFIRMED_DATE_LEVEL_NOTICE_INTRADAY_ARCHIVE_UNCERTIFIED',
 }
}[CODE]
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v): Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def compact(t): return re.sub(r'\s+','',t)
def scalar(x):
 if hasattr(x,'item'): x=x.item()
 if x is pd.NA or (isinstance(x,float) and math.isnan(x)): return None
 return x

def records(df):
 return [dict(date=i.strftime('%Y-%m-%d'),**{k:scalar(v) for k,v in row.items()}) for i,row in df.iterrows()]

sources=json.loads((O/'OFFICIAL_SOURCES.json').read_text())
assert len(sources)==len(CFG['notices'])
for s in sources:
 assert sha(s['path'])==s['sha256']
 text_path=Path(s['path']+'.txt'); t=compact(text_path.read_text())
 n=CFG['notices'][s['announcement_id']]
 for f in n['fragments']: assert compact(f) in t,(SID,s['announcement_id'],f)
 s.update(n)
 s['text_path']=str(text_path); s['text_sha256']=sha(text_path)
 s['excerpts_whitespace_normalized_only']=True
sources.sort(key=lambda s:(s['publication_date'],s['announcement_id']))

manifest=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
entry=next(x for x in json.loads(manifest.read_text()) if x['symbol']==SID)
sp=Path(next(x for x in entry['source_sha256'] if x.endswith('/signal.parquet')))
assert sha(sp)==entry['source_sha256'][str(sp)]
d=pd.read_parquet(sp); before=d.loc[:'2024-09-29'].tail(1); after=d.loc['2024-09-30':].head(1)
assert before.index[0].strftime('%Y-%m-%d')=='2024-09-27'
assert after.index[0].strftime('%Y-%m-%d')==CFG['resume']
assert all(pd.Timestamp(x) not in d.index for x in CFG['suspended_sessions'])
assert d.loc['2024-09-30':pd.Timestamp(CFG['resume'])-pd.Timedelta(days=1)].empty
same_lineage=all(before.iloc[0][c]==after.iloc[0][c] for c in ['source_kind','source_path','segment_id'])
same_factor=bool(before.iloc[0]['adjustment_factor']==after.iloc[0]['adjustment_factor'])
assert same_lineage and same_factor
act=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v1/actions')/(SID+'.json')
actions=json.loads(act.read_text()); gap_actions=[x for x in actions['events'] if '2024-09-30'<=x['effective_date']<CFG['resume']]; assert gap_actions==[]
union_path=ROOT/'allocation_ablation_v1/report_fact2/ACTUAL_BLOCKER_REQUEST_UNION.json'
union=next(x for x in json.loads(union_path.read_text()) if x['sid']==SID and x['day']=='2024-09-30')
assert union['actions']==[]
assert union['previous_factor']==str(before.iloc[0]['adjustment_factor'])
m_path=ROOT/'mainline_candidate_v1/MISSING_FACT_TARGETS.json'
m_rows=[x for x in json.loads(m_path.read_text()) if x['sid']==SID]
if CODE=='603268':
 assert len(m_rows)==1 and m_rows[0]['held_qty']==0 and m_rows[0]['pending'] and m_rows[0]['retained_status']=='RETAINED'
 assert m_rows[0]['source_path']==str(sp) and m_rows[0]['source_sha256']==sha(sp) and m_rows[0]['action_sha256']==sha(act)
 assert union['arm_exposures']==[{'arm':'D','held_qty':0,'pending_seed':True,'retained_ticket':True}]
else:
 assert union['arm_exposures']==[{'arm':'B','held_qty':100,'pending_seed':False,'retained_ticket':False},{'arm':'D','held_qty':0,'pending_seed':True,'retained_ticket':True}]

snapshot={'sid':SID,'manifest_entry':entry,'signal_path':str(sp),'signal_sha256':sha(sp),'signal_hash_matches_frozen_manifest':True,'adjacent_source_rows':records(pd.concat([d.loc[:'2024-09-29'].tail(5),d.loc[CFG['resume']:].head(3)])),'immediate_previous_observation':records(before)[0],'immediate_next_observation':records(after)[0],'missing_requested_dates':['2024-09-30'],'all_confirmed_suspended_sessions_absent':CFG['suspended_sessions'],'same_lineage_across_gap':bool(same_lineage),'same_adjustment_factor_across_gap':same_factor,'local_actions_in_gap':gap_actions,'actions_path':str(act),'actions_sha256':sha(act),'allocation_union_source':str(union_path),'allocation_union_entry':union,'mainline_source':str(m_path),'mainline_matching_entries':m_rows,'note':'邻行和复牌后行情只用于事后核对，不生成任何停牌日OHLC或factor，不构成可成交性认证。'}
dump(O/'LOCAL_SOURCE_AND_EXPOSURE.json',snapshot)
inputs=[manifest,sp,act,union_path,m_path]
evidence={str(p):sha(p) for p in inputs}
for p in O.iterdir():
 if p.is_file() and p.name not in ['EVIDENCE_SEAL.json',f'SUSPENSION_FACT_{CODE}_V1.json','VERIFY_RESULT.json']: evidence[str(p)]=sha(p)
raw_close=str(before.iloc[0]['raw_close'])
fact={'schema':'reviewed_official_suspension_fact_v1','sid':SID,'name_at_event':CFG['name'],'fact_type':'OFFICIAL_TRADING_SUSPENSION','scope':'Historical evidence only. No authority to alter frozen engine, fill market rows, delete retained tickets, or run accounts.','reviewed_at_utc':datetime.now(timezone.utc).isoformat(),'suspension_start':'2024-09-30','suspension_start_phase':'OPEN','requested_window':['2024-09-30','2024-09-30'],'verified_nontradable_dates':['2024-09-30'],'retrospectively_confirmed_suspended_sessions':CFG['suspended_sessions'],'retrospectively_confirmed_resume_date':CFG['resume'],'resume_phase':'OPEN','retrospective_last_suspended_session':CFG['last_suspended'],'reason':CFG['reason'],'transaction_is_proposal_not_effective_share_conversion':True,'official_sources':sources,'point_in_time_certification':CFG['pit_certification'],'point_in_time_limits':CFG['pit']+['这是一套明确披露限制的历史研究补证，不宣称生产级逐时点PIT认证。'],'source_observations':{'previous_observed_date':'2024-09-27','previous_raw_close':raw_close,'previous_adjustment_factor':str(before.iloc[0]['adjustment_factor']),'next_observed_date':CFG['resume'],'missing_requested_dates':['2024-09-30'],'lineage_equal_on_adjacent_observations':bool(same_lineage),'factor_equal_on_adjacent_observations':same_factor,'local_actions_in_gap':gap_actions,'note':'缺整行在此已由真实停牌解释；相邻因子和源相同不能转成停牌日行情。不得将缺行诊断误判为真实factor改变或换源。'},'exposure':{'allocation_arm_exposures':union['arm_exposures'],'mainline_exposures':m_rows,'zero_quantity_ticket_still_in_scope':True,'exposure_source':'Frozen blocker union and mainline missing-fact list, not a new account run.','held_B_last_observed_raw_mark_if_applicable':raw_close if CODE=='300489' else None,'held_B_illustrative_value_100_shares_if_applicable':format(Decimal(raw_close)*100,'.2f') if CODE=='300489' else None,'currency':'CNY'},'non_execution_boundary':{'old_frozen_contract_remains_blocked':True,'requires_explicit_new_contract_for_account_handling':True,'suspension_is_not_effective_equity_conversion':True,'no_OHLC_or_factor_rows_to_insert':True,'no_order_fill_or_cash_release_from_suspension':True,'do_not_delete_zero_quantity_retained_SEED_ticket':True,'held_quantities_not_changed_by_this_fact':True,'resume_does_not_certify_fillability':True},'evidence_hashes':evidence,'performed_actions':{'official_pdf_downloads':len(sources),'engine_changed':False,'source_price_changed':False,'source_factor_changed':False,'ticket_deleted':False,'account_executed':False,'other_stocks_scanned':False},'query_scope_note':'CNINFO original pageSize=100 requests returned 30 records and page 2 repeated page 1; the independent 2024-09-20 through 2024-10-13 narrow query returned all 6 or 2 records and supplied initial notices. No completeness claim is based on the repeated page.'}
fact_path=O/f'SUSPENSION_FACT_{CODE}_V1.json'; dump(fact_path,fact)
for p,h in evidence.items(): assert sha(p)==h,(p,h)
verification={'status':'PASS','fact_path':str(fact_path),'fact_sha256':sha(fact_path),'verified_evidence_files':len(evidence),'suspension_start':'2024-09-30','resume_date':CFG['resume'],'source_unchanged':True,'official_pdf_fragment_assertions_pass':True,'all_suspended_sessions_absent_from_frozen_signal':True,'zero_quantity_ticket_kept_in_scope':True,'account_executed':False,'pit_certification':CFG['pit_certification']}
dump(O/'VERIFY_RESULT.json',verification)
seal={str(p):sha(p) for p in O.iterdir() if p.is_file() and p.name!='EVIDENCE_SEAL.json'}
dump(O/'EVIDENCE_SEAL.json',{'sealed_at_utc':datetime.now(timezone.utc).isoformat(),'files':seal,'fact_sha256':sha(fact_path)})
for p,h in seal.items(): assert sha(p)==h,(p,h)
print(json.dumps(dict(verification,seal_sha256=sha(O/'EVIDENCE_SEAL.json')),ensure_ascii=False,indent=2))
