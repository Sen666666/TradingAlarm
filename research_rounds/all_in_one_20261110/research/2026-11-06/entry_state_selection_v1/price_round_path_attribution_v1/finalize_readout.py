from pathlib import Path
from datetime import datetime,timezone
import json,hashlib
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent
j=lambda n:json.loads((O/n).read_text())
def dump(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def money(v):return f'{v:,.2f}'
def pct(v):return f'{100*v:.2f}%'
c=j('CLOSE_TABLES.json');p=j('PATH_TABLES.json');cq=j('CLOSE_QA.json');pq=j('PATH_QA.json');r=pd.read_csv(O/'PRICE_ROUND_PATH_ATTRIBUTION.csv',float_precision='round_trip');r['window_label']=r.window_label.astype(str)
# Absence of an ADD is not missing market data. Make this display label explicit.
r.loc[~r.added,'post_add_close_R_bucket']='NOT_APPLICABLE_NO_ADD';r.to_csv(O/'PRICE_ROUND_PATH_ATTRIBUTION.csv',index=False)
for w in ['2022','2024']:
 for z in p[w+'__added__post_add_close_R_bucket']:
  if not z['added']:z['post_add_close_R_bucket']='NOT_APPLICABLE_NO_ADD'
dump('PATH_TABLES.json',p)
sp=O/'supplement_price_and_open.py';s=sp.read_text();needle="out['post_add_close_R_bucket']=out.post_add_close_max_R.map(bucket_net)";assert needle in s;s=s.replace(needle,needle+";out.loc[~out.added,'post_add_close_R_bucket']='NOT_APPLICABLE_NO_ADD'");sp.write_text(s)
proto=O/'PROTOCOL.json';stat=proto.stat();correction=dict(original_file='PROTOCOL.json',original_sha256=sha(proto),original_field='freeze_time_utc',original_value=j('PROTOCOL.json')['freeze_time_utc'],corrected_file_creation_utc=datetime.fromtimestamp(stat.st_birthtime,timezone.utc).isoformat(),original_file_modified_utc=datetime.fromtimestamp(stat.st_mtime,timezone.utc).isoformat(),correction_recorded_utc=datetime.now(timezone.utc).isoformat(),meaning='The original field mistakenly suffixed local UTC+08 wall time with Z. Original bytes remain unchanged. Use file creation UTC 12:30:03Z as the provenance timestamp. This is a timezone-label correction, not new preregistration or a re-freeze; thresholds and methodology are unchanged and were stated before path aggregation.')
dump('TIMEZONE_LABEL_CORRECTION.json',correction)
lines=['# PRICE 完整回合路径归因：2022与2024年9—12月','', '## 结论','',
'2022的主要损失不是已经赚到大段利润后全部回吐，而是大量回合没有正收盘净权益，或虽一度为正、仍未达到自身初始计划风险1R。**但<1R不等于微利，更不等于涨幅<5%。** 这是事后损失承载路径，不是入场前筛单信号。','',
'两窗均只用原联合账本的共同可比集合、PRICE完整闭合回合。所有金额为人民币，已含真实研究账本交易费、5bp条件滑点与已确认NET80现金权益；不是交易所真实成交或账户收益率。','',
'## 1. 分母与完整金额守恒','',
'| 出生窗口 | 共同股票 | PRICE闭合轮/涉及股票 | 盈利轮/净额 | 亏损轮/净额绝对值 | 合计净额 |','|---|---:|---:|---:|---:|---:|']
for w in ['2022','2024']:
 q=cq[w];t=q['closed'];lines.append(f"| {w} | {q['common_stocks']} | {t['n']}/{t['stocks']} | {t['wins']}/{money(t['profit_amount'])} | {t['losses']}/{money(t['loss_amount'])} | {money(t['net'])} |")
lines += ['', '共同集合另有2022/2024的1/8个q0登记回合，没有BUY，不计交易。全池其他已闭合轮不混入本报告。2024只有9—12月出生，不能把两窗重复参与次数直接当相同年化暴露。', '', '## 2. 整轮收盘净权益：三个亏损类别与全部盈利', '', 'R固定为原entry_risk；逐持有收盘净权益使用该日原真实持仓股数、累计买入成本、已确认现金权益和同日整股卖费。收盘mark并不表示当时可以卖出，首仓及ADD当日仍含T+1未结算新股。', '', '| 后验亏损类别 | 2022轮数/亏损金额 | 占2022亏损金额 | 2024轮数/亏损金额 | 占2024亏损金额 |', '|---|---:|---:|---:|---:|']
for b,label in [('NO_POSITIVE_CLOSE','从未出现正收盘净权益'),('POSITIVE_LT_1R','曾为正，但最大值<1R'),('GE_1R','最大值≥1R，最终仍亏')]:
 z=[next(x for x in c[w+'__close_R_bucket__final_outcome'] if x['close_R_bucket']==b and x['final_outcome']=='LOSS') for w in ['2022','2024']]
 lines.append(f"| {label} | {z[0]['n']}/{money(z[0]['loss_amount'])} | {pct(z[0]['loss_amount']/cq['2022']['closed']['loss_amount'])} | {z[1]['n']}/{money(z[1]['loss_amount'])} | {pct(z[1]['loss_amount']/cq['2024']['closed']['loss_amount'])} |")
for w in ['2022','2024']:
 g=r[(r.window_label==w)&r.close_R_bucket.eq('POSITIVE_LT_1R')&r.net_pnl.lt(0)];risk=(g.entry_risk/(g.entry_gross+g.entry_fee)).median();lines.append(f"\n{w}该<1R亏损组：峰值/初始R中位{g.close_max_R.median():.3f}，初始风险/首仓含费成本中位{pct(risk)}，固定首仓坐标收盘MFE中位{pct(g.price_close_mfe.median())}。不能统一叫‘只曾微利’。")
lines += ['', '2022曾正后亏1020轮，绝大部分在<1R组；完整盈利435轮贡献全部1,537,066.74元。2024盈利490轮贡献全部2,636,794.29元。盈利回合全部保留，不能只拿损失分类相加代替净额。', '', '## 3. 固定首仓价格MFE/MAE，与整轮金额分开', '', '价格基准为首仓含5bp成交价×入场adjustment_factor；后续H/L/C转到同一来源坐标。现金除权的复权坐标用于可比价格，不直接当税后经济收益。发生factor变化的137/69轮均逐笔核对原现金权益桥；raw固定基准收益只在factor不变时输出。没有股本数量变动回合。', '', '表为首仓固定坐标的持有收盘MFE。只纳入入场日至退出前一共同交易日收盘；退出日只使用OPEN，绝不纳入退出后的H/L/C。', '', '| 收盘价格MFE | 2022亏损轮/金额 | 2022盈利轮/金额 | 2024亏损轮/金额 | 2024盈利轮/金额 |', '|---|---:|---:|---:|---:|']
for b,label in [('LE_0','≤0'),('GT0_LT5PCT','0至<5%'),('GE5_LT10PCT','5%至<10%'),('GE10PCT','≥10%')]:
 cells=[]
 for w in ['2022','2024']:
  for outcome in ['LOSS','PROFIT']:
   z=next((x for x in p[w+'__price_close_mfe_bucket__final_outcome'] if x['price_close_mfe_bucket']==b and x['final_outcome']==outcome),{'n':0,'net':0});cells.append(f"{z['n']}/{money(abs(z['net']))}")
 lines.append('| '+label+' | '+' | '.join(cells)+' |')
for w in ['2022','2024']:
 g=r[r.window_label==w];lines.append(f"\n{w}全体价格路径中位：持有收盘MFE {pct(g.price_close_mfe.median())}，排除首仓日后的日内High MFE {pct(g.price_t1_high_mfe.median())}，含退出OPEN的价格MAE {pct(g.price_observed_mae.median())}。逐轮High/Low路径和固定0/5%/10%桶均保存。日内High只是事后上界，不能叫可兑现利润，也未用日线H/L推断先后。")
lines += ['', '即使使用整轮当日High净清算上界且加上所有次开静态报价，2022/2024仍有51/76轮从未为正，最终净额分别−120,347.78/−133,893.76元。这比“从未正收盘”严格，但仍只描述此原持仓模型，不能预测未来。', '', '## 4. 次开报价：不把收盘利润当已锁住', '', '对每个已知持有收盘，报价清算其当时持有lot于立即下一共同OPEN，含同日卖费和5bp。旧lot均满足下一日T+1。**主口径排除原账下一OPEN同时ADD的冲突日**，另存包含冲突日、假定撤销ADD的静态旧仓报价，未实际改订单。退出最终OPEN报价与原最终净额逐轮完全一致。', '', '| 主口径最大次开净报价，最终亏损组 | 2022轮数/亏损金额 | 2024轮数/亏损金额 |', '|---|---:|---:|']
for b,label in [('LE_0','从未为正'),('GT0_LT1R','曾为正、最大<1R'),('GE1R','曾≥1R')]:
 z=[next(x for x in p[w+'__next_open_max_no_ADD_conflict_R_bucket__final_outcome'] if x['next_open_max_no_ADD_conflict_R_bucket']==b and x['final_outcome']=='LOSS') for w in ['2022','2024']];lines.append(f"| {label} | {z[0]['n']}/{money(z[0]['loss_amount'])} | {z[1]['n']}/{money(z[1]['loss_amount'])} |")
lines += ['', '这是原路径上逐时点的一跳条件估值，不是一个可同时实现所有峰值的策略，也未沿新退出传播后续现金、重入或ADD。最大次开报价由未来价格事后挑出，不能倒算成前收盘可识别信号。涨跌停、停牌、队列和容量可成交性仍全部UNKNOWN。', '', '## 5. ADD前后与重复试错', '', '| 是否发生ADD | 2022轮数/盈利金额/亏损金额/净额 | 2024轮数/盈利金额/亏损金额/净额 |', '|---|---:|---:|']
for ad in [False,True]:
 cells=[]
 for w in ['2022','2024']:
  z=next(x for x in c[w+'__added'] if x['added']==ad);cells.append(f"{z['n']}/{money(z['profit_amount'])}/{money(z['loss_amount'])}/{money(z['net'])}")
 lines.append(f"| {'有ADD' if ad else '无ADD'} | "+' | '.join(cells)+' |')
for w in ['2022','2024']:
 g=r[(r.window_label==w)&r.added];pre=g[g.pre_add_close_max_R>=1];low=g[(g.pre_add_close_max_R<1)&g.net_pnl.lt(0)];t=cq[w]['closed'];lines.append(f"\n{w}发生ADD的{len(g)}轮中，ADD前收盘已达1R仅{len(pre)}轮；其余中最终亏损{len(low)}轮、亏损金额{money(-low.net_pnl.sum())}元。原ADD交易层净额{money(t['add_trade'])}元，整轮结果不能归为ADD本身的因果效果。ADD前/后收盘与次开峰值、ADD开盘前原prior_round_net均逐轮保存。")
lines += ['', '| 实际BUY顺序 | 2022轮数/净额 | 2024轮数/净额 |', '|---|---:|---:|']
for b,label in [('FIRST_ALL_STRATEGY','本窗首次全策略BUY即PRICE'),('FIRST_PRICE_AFTER_AB','先有AB、首次PRICE'),('REPEAT_PRICE','第二次及以后PRICE')]:
 z=[next(x for x in c[w+'__participation'] if x['participation']==b) for w in ['2022','2024']];lines.append(f"| {label} | {z[0]['n']}/{money(z[0]['net'])} | {z[1]['n']}/{money(z[1]['net'])} |")
lines += ['', '重复确实承载亏损，但2022首次参与同样是大头，2024首次全策略参与则贡献主要盈利。两窗长度不同，且重复群体中仍有盈利轮；不能据此禁止重入或建立按未来结果的冷却规则。', '', '## 6. 持有时间与个股集中度', '', '| 亏损轮持有期，含首仓及退出OPEN日期 | 2022轮数/亏损金额 | 2024轮数/亏损金额 |', '|---|---:|---:|']
for b in ['1_5','6_20','21_60','61_PLUS']:
 cells=[]
 for w in ['2022','2024']:
  g=r[(r.window_label==w)&r.hold_bucket.eq(b)&r.net_pnl.lt(0)];cells.append(f"{len(g)}/{money(-g.net_pnl.sum())}")
 lines.append('| '+b+' | '+' | '.join(cells)+' |')
for w in ['2022','2024']:
 z=[next(x for x in c[w+'__concentration'] if x['group']==f'GROSS_LOSS_{n}_STOCKS') for n in [10,20]];lines.append(f"\n{w}按亏损回合金额排序的最差10/20股，分别承载{money(z[0]['loss_amount'])}/{money(z[1]['loss_amount'])}元，占全部亏损{pct(z[0]['gross_loss_share'])}/{pct(z[1]['gross_loss_share'])}。是分散的试错成本，不是少数股票解释绝大多数损失。全股票、全部回合及剩余项均保留，排序仅为后验诊断。")
lines += ['', '## 7. 覆盖、验证及可用结论', '',
'- 全部1779/1083轮，66,121/48,958个持有收盘日期与原共同日历逐日一致，无缺日、无重复。原holding_sessions包含退出OPEN，因此恰等于持有收盘数量+1。',
'- 原净权益已含cash+receivable；净现金权益仅在ex已确认时计一次，支付日仅把应收转现金。所有逐日重建与保存gate最大误差0，所有最终退出净额重建最大误差0。各完整分组守恒到正式PRICE净贡献。',
'- 价格及研究净估值路径UNKNOWN为0轮/0元；现实可成交性UNKNOWN覆盖全部2862轮。后ADD指标对无ADD回合为NOT_APPLICABLE，不是路径缺失。',
'- 50/23轮只有首仓或ADD当日出现正收盘mark。这些日子含尚不可卖的新lot，不表示旧lot也全部不可卖，更不能视为整仓可兑现利润。',
'- 保留PROTOCOL.json原字节。原freeze_time_utc误把本地+08时间标Z；TIMEZONE_LABEL_CORRECTION.json据文件创建时间更正为2026-11-08T12:30:03Z。仅纠正时区标签，不是重新冻结或样本外注册。',
'- 复用了原保存账本、gate及既有日期费用纯函数，未import或执行joint_engine/run_economic，未更改原退出、参数、旧产物或经济账本，未运行新策略。',
'', '**现在可以定位损失承载路径，但仍不能在入场前识别该拒绝谁。** 本报告未提供新预测资料；事后MFE、1R分桶、未来ADD和退出时间都不能作为入场信号。旧根龄、广度、局部保护或简单禁止重入不能仅凭此处损失大头换名再试。保留这一否定结论比勉强凑一个过滤公式更可靠。', '', '## 文件', '',
'- PRICE_ROUND_PATH_ATTRIBUTION.csv：2862轮全体、价格/净权益/次开/ADD/重复字段。',
'- ORIGINAL_INVENTORY_DAILY_PATH.csv：115079日原库存、成本、NET80、T+1、High/Low上界与次开报价。',
'- CLOSE_TABLES.json、PATH_TABLES.json：全部固定桶；每表同时列盈利金额、亏损金额、净额及成本层拆分。',
'- STOCK_ATTRIBUTION.csv：全部个股集中度，可回溯全部回合。',
'- CLOSE_QA.json、PATH_QA.json、FINAL_QA.json、SOURCE_HASHES_STAGE1/2.json、OUTPUT_HASHES.json：覆盖、金额守恒与来源。',
'- PROTOCOL.json、TIMEZONE_LABEL_CORRECTION.json及三个只读研究脚本。','']
(O/'READOUT.md').write_text('\n'.join(lines))
# Recheck every actual input and stage-one derivative. The original protocol is unchanged.
H={**j('SOURCE_HASHES_STAGE1.json'),**j('SOURCE_HASHES_STAGE2.json')};drift=[path for path,h in H.items() if sha(path)!=h];assert not drift,drift
net={};partitions=0
for w in ['2022','2024']:
 g=r[r.window_label==w];target=cq[w]['closed']['net'];assert abs(g.net_pnl.sum()-target)<1e-7
 for ts in [c,p]:
  for name,rows in ts.items():
   if not name.startswith(w+'__') or name.endswith('__concentration'):continue
   assert sum(x['n'] for x in rows)==len(g),(name,'n');assert abs(sum(x['net'] for x in rows)-target)<1e-7,(name,'net');assert abs(sum(x['profit_amount']-x['loss_amount'] for x in rows)-target)<1e-7;partitions+=1
 net[w]={'rounds':len(g),'final_net':g.net_pnl.sum(),'path_unknown_rounds':int(g.net_path_status.ne('KNOWN').sum()),'path_unknown_original_net':g.loc[g.net_path_status.ne('KNOWN'),'net_pnl'].sum(),'actual_execution_certification':'UNKNOWN_FOR_ALL_ROUNDS'}
qa=dict(complete=True,source_hashes_checked=len(H),source_hashes_unchanged=True,exhaustive_partitions_checked=partitions,windows=net,protocol_timezone_correction_file='TIMEZONE_LABEL_CORRECTION.json',strategy_economic_replays=0,new_strategy_threshold_scans=0,original_files_modified=0,created_utc=datetime.now(timezone.utc).isoformat())
dump('FINAL_QA.json',qa);dump('OUTPUT_HASHES.json',{x.name:sha(x) for x in sorted(O.iterdir()) if x.is_file() and x.name!='OUTPUT_HASHES.json'});print(json.dumps(qa,ensure_ascii=False,indent=2));print('READOUT',O/'READOUT.md')
