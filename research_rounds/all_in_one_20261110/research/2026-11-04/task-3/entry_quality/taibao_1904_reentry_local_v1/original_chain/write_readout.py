"""Format saved original Taibao facts and reuse sealed guard source table."""
from pathlib import Path
import csv,hashlib,json
O=Path(__file__).resolve().parent;Q=O.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(n):return json.loads((O/n).read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
daily=read('ORIGINAL_DAILY_CHAIN.json');entries=read('THREE_ACTUAL_ENTRY_AND_RESERVE_DETAILS.json');dates=read('CP_I_BUY_TRUE_DATE_SETS.json');op=read('SEPT10_OPEN_NECESSARY_STATE_ONLY.json')
bp=Q/'cp_peak_exit_scan_v1/penetration/MOBILE_DAILY_PENETRATION.json';b=json.loads(bp.read_text());guards=[x['summary'] for x in b if x['summary']['sid']=='601601.SH' and '2024-09-02'<=x['summary']['day']<='2024-10-10']
with (O/'DAILY_LAYER_OLD_AND_UPDATED_PROTECTION.csv').open('w') as f:
 keys=['day','layer','qty_current_original','held_previous_CLOSE','C_prev_raw','C_raw','old_floor_adjusted','old_floor_raw','old_floor_source','after_CLOSE_original_floor_adjusted','provenance_kind','floor_origin_day','unique_CP_receipt_id','unique_CP_frozen_scale','scale_frozen_at','current_CP_receipt','current_CP_candidate','current_CP_cache_s','current_CP_cache_z','current_CP_source_day']
 w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows({k:r[k] for k in keys} for r in guards)
for r in guards:
 d=next(d for d in daily if d['day']==r['day']);h=next(h for h in d['actual_layers_after_original_CLOSE_checks'] if h['id']==r['layer']);assert h['floor']==r['after_CLOSE_original_floor_adjusted']
save('GUARD_TABLE_SOURCE_BINDING.json',dict(status='PASS_REUSED_SEALED_ORIGINAL_GUARD_ROWS_AFTER_FLOOR_EXACT',source_path=str(bp.resolve()),source_sha256=sha(bp),rows=len(guards),no_recalculation=True))
lines=['# 太保1904：9/2—10/10原链与后续资格','',
'本件只读原No60模拟账/原daily/缓存与源码，未运行账户、回测或候选fill。9/9 CLOSE A2是外部纸面假设；原策略9/9没有退出请求。后续字段均为原路径记录，不代表提前卖1904后仍会发生的仓位、资金拒绝或成交。','',
'## 9/9已有仓与9/10必要条件','',
'9/9 09:30原层1914已成交400股：raw OPEN30.76，代理价30.775380，买费5.7890807432，源信号9/6。9/9 CLOSE原1904、1914各400，总800股；raw C30.06、I_target=True、i_buy=False、g_grade=−3/g_acute_down=True。原两层同MOBILE floor_a42.713969228041776，原pending exit为空。不能把1914当作9/9还未成交的新计划。','',
'9/10原raw O30.04/H30.18/L29.65/C29.88，V23568055，观测/价格标志有效，H>L、V>0；O×.9995=30.02498只是5bp算术参考。原execution availability是explicit_research_proxy允许买卖，未记录历史ST/真实撮合队列；不是交易所实时许可。','',
'T+1必要状态：原protocol A sellable_lag_sessions=1。1904在9/2实际买，按原session应9/3可卖；1914在9/9买，应9/10可卖。两者至9/10满足该必要日期检查。此为已存fill日期+原calendar/protocol的静态推导，原fill audit没有保存每lot sellable_at快照，不冒充直接原字段。没有构造A2卖单、费用、可卖目标、成交量或新现金。原日线容量还依赖前20正量均值×.01及9/10完整量；本件未调用window/算候选capacity。','',
'源码入口：fast_market.py:63把lag(...,sellable_lag_sessions)送入FillWindow；sector_account.py:729建立InventoryLot(count,window.sellable_at)，:751按sellable_at≤window.at计可卖量，:758仍受提交量/可卖量/容量约束。仅通过日期、H/L/V不等于完成执行证明。','',
'## 三个原实际获资层','',
'|层|原signal→原OPEN|原qty / 价 / 买费|reserve target / 原cap|原pool|','|---|---|---|---|---|']
for e in entries:
 t=e['actual_buy'];r=e['actual_reserve'];j=e['actual_fill_journal'];lines.append(f'|{e["layer"]}|{t["signal_at"][:10]}→{t["at"][:10]}|{t["shares"]} / {t["price"]} / {t["fees_cny"]}|{r["target_shares"]} / {r["frozen_max_shares"]}|{j["pool"]}|')
lines+=['',
'原reserve记录gross预算、fee预留、target/frozen cap、feeschedule、order/source ID；原journal/funding记录实际pool和数量。THREE_ACTUAL_ENTRY_AND_RESERVE_DETAILS.json保逐对象及audit/trade/decision索引。该槽位申请前available、每池试算q、成功时实际binding-constraint向量没保存，明确NOT_RECORDED，不用CLOSE现金替代，也不重建新资金账。','',
'## 9/9之后所有原资格与拒单','',
'9/9—9/13：原mobile_Q=True，但没有新CP，roles=[]、无同股intent。原日志barriers中buy_allowed:false来自event资格；engine.py:44–45把交易可买性AND当日i_buy，J:218另用真实market buyable构造continuing mobile_Q，不能把这条原因直接解释成交易所禁止买。','',
'最早后续原资格日9/18：CP=True、i_buy=False、mobile_Q=True、roles=[mobile]、barriers=[]，生成原cap400/gross预算12414.757602733556430；9/19实际confirmed400，形成1931。原CP新增不要求当日i_buy也为True；保持I_target不等于每天新的买入事件。','',
'|原signal|CP / i_buy|原roles|原cap|次OPEN原结果|','|---|---|---|---:|---|']
for day,nextday in [('2024-09-18','2024-09-19'),('2024-09-23','2024-09-24'),('2024-09-24','2024-09-25'),('2024-09-26','2024-09-27'),('2024-09-27','2024-09-30'),('2024-09-30','2024-10-08'),('2024-10-08','2024-10-09')]:
 d=next(d for d in daily if d['day']==day);o=d['original_opportunities'][0]['original'];nd=next(d for d in daily if d['day']==nextday);ff=[r['original']['result'] for r in nd['original_funding_today']];caps=[x['original']['cap'] for x in d['original_frozen_intents']]
 lines.append(f'|{day}|{d["original_CP_cache"]["receipt"]} / {d["original_facts"]["i_buy"]}|{o["roles"]}|{caps or "无intent"}|{nextday}: {ff or "无该股原funding行"}|')
lines+=['',
'9/23和9/27有i_buy/core_Q，但原已有仓、无CP，因此原roles=[]；不能将其写成被资金门拒绝的CORE单。9/24、9/26、9/30、10/8 CP与i_buy同时真，均原mobile intent，随后原资金拒。多理由是原路由保存的拒因汇总，不识别每个pool搜索全程或唯一binding；去掉1904后资金/行业/池占用会变，原拒不能直接搬到假设后路径。','',
'9/2—10/10 CP=True：'+', '.join(dates['CP_true'])+'。','',
'i_buy=True：'+', '.join(dates['i_buy_true'])+'。','',
'同日CP且i_buy=True：'+', '.join(dates['both_true'])+'。9/18是本窗口唯一CP=True而i_buy=False的日期。原22个交易日I_target始终为True；详细g_grade/fresh/acute、G1 up_reasons、I/i_buy、CP当前s与凭证frozen scale、roles/barriers/intents/funding均逐日保留。','',
'10/9原旧CP保护才为1904/1914/1931请求退出，10/10实际原代理整单卖1200股（rawO36.68、价36.66166），此处仅保原账，未把它替换成A2退出或计算其差额。','',
'文件：ORIGINAL_DAILY_CHAIN.csv/json是22日原表；DAILY_LAYER_OLD_AND_UPDATED_PROTECTION.csv保旧线与更新线及原CP/I provenance，复用已封B全期源而非重播；ORIGINAL_OPPORTUNITIES.json、ORIGINAL_FUNDING.json保原全局行索引；CP_I_BUY_TRUE_DATE_SETS.json保真值日期；SEPT10_OPEN_NECESSARY_STATE_ONLY.json保原bar、规则、T+1必要状态和缺项；SOURCE_MANIFEST.json绑定原文件/源码。所有fill/cash/receipt词汇均为研究模拟账，不是实际broker成交/ACK。']
(O/'READOUT.md').write_text('\n'.join(lines)+'\n')
assert all(d['original_facts']['i_target'] for d in daily)
save('VALIDATION.json',dict(status='PASS_READ_ONLY_ORIGINAL_TAIBAO_CHAIN_SELF_CHECK',days=len(daily),actual_entry_layers=[e['layer'] for e in entries],all_original_I_target_true=True,CP_dates=dates['CP_true'],CP_and_i_buy_dates=dates['both_true'],no_original_Sept09_exit=True,at_reserve_available='NOT_RECORDED_NOT_REBUILT',new_accounts=0,new_models=0,new_backtests=0,candidate_fills=0))
save('DELIVERABLE_SHA256.json',{p.name:sha(p) for p in sorted(O.iterdir()) if p.is_file() and p.name not in ['DELIVERABLE_SHA256.json','SEAL_RECEIPT.json']})
seal=dict(status='SEALED_ORIGINAL_TAIBAO_22_DAY_CHAIN_ONLY',readout_sha256=sha(O/'READOUT.md'),daily_chain_sha256=sha(O/'ORIGINAL_DAILY_CHAIN.json'),Sept10_necessary_state_sha256=sha(O/'SEPT10_OPEN_NECESSARY_STATE_ONLY.json'),source_manifest_sha256=sha(O/'SOURCE_MANIFEST.json'),deliverable_sha256=sha(O/'DELIVERABLE_SHA256.json'),new_accounts=0,new_models=0,new_backtests=0,candidate_fills=0)
save('SEAL_RECEIPT.json',seal);print(json.dumps(seal,ensure_ascii=False))
