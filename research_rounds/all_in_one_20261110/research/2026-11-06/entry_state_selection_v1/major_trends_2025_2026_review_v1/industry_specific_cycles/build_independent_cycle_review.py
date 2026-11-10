from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');O=R/'major_trends_2025_2026_review_v1/industry_specific_cycles'
d=pd.read_csv(O/'FULL_CONTEXT_2019_2026_DAILY.csv',index_col=0);d.index=pd.to_datetime(d.index)
# Anchors selected by visual reading of each independent daily series, not calendar partitions.
spec={
'URFI881121':{'name':'半导体','base':'2024-02-05','secondary':'2024-09-23','prior_high':'2024-03-20','peak':'2026-06-30','anchors':['2024-02-05','2024-03-20','2024-09-23','2025-02-26','2025-04-07','2025-10-09','2025-11-21','2026-01-28','2026-03-23','2026-06-30','2026-10-22'],'labels':['筑底后的首轮修复','回落形成第二底部','跨年再启动及推进','主浪中的深回撤','恢复并再创推进高点','回撤且未破4月低点','再推进','第二次主要回撤','主升加速至本轮最高','高位深回撤 末端仍为观察截断']},
'URFI881270':{'name':'元件','base':'2024-02-05','secondary':'2024-09-18','prior_high':'2024-07-16','peak':'2026-06-25','anchors':['2024-02-05','2024-07-16','2024-09-18','2025-03-18','2025-04-08','2025-10-29','2025-11-21','2026-02-26','2026-03-23','2026-06-25','2026-07-30','2026-09-23','2026-10-22'],'labels':['先行修复与上涨','中期回撤形成第二底部','跨年推进','主浪中的深回撤','恢复后的持续主升','阶段回撤','再推进','再次回撤','主升加速并见本轮最高','峰后急跌','恢复但未超过6月最高','再次回撤 观察未结束']},
'URFI881172':{'name':'电子化学品','base':'2024-02-05','secondary':'2024-09-13','prior_high':'2024-03-20','peak':'2026-07-01','anchors':['2024-02-05','2024-03-20','2024-09-13','2024-11-11','2025-04-07','2026-02-26','2026-03-23','2026-07-01','2026-10-22'],'labels':['首轮修复','回落形成第二底部','再启动','较长整理回撤','跨2025至2026的持续推进','短期回撤','加速至本轮最高','峰后持续回撤 末端未决']},
'URFI881129':{'name':'通信设备','base':'2024-02-05','secondary':'2024-09-18','prior_high':'2024-03-20','peak':'2026-05-13','anchors':['2024-02-05','2024-03-20','2024-09-18','2025-02-26','2025-04-08','2026-03-11','2026-03-23','2026-05-13','2026-07-30','2026-09-21','2026-10-22'],'labels':['新底部后的修复 不是延续2023旧高','回落形成第二底部','跨年再推进','主浪中的回撤','跨2025至2026的持续推进','较急回撤','再推进至本轮最高','峰后主要调整','反弹尚未超过5月高点','再次回落 观察未结束']},
'URFI881169':{'name':'A股贵金属股票 含白银','base':'2024-02-05','secondary':'2024-09-12','prior_high':'2024-04-12','peak':'2026-01-29','anchors':['2024-02-05','2024-04-12','2024-09-12','2025-04-22','2025-05-15','2025-10-13','2025-11-24','2026-01-29','2026-07-17','2026-08-24','2026-10-22'],'labels':['新底部后的第一主升','较深回撤形成第二底部','跨年推进','回撤','再推进','回撤','加速至本轮最高','峰后主调整','较大反弹但未收复1月高点','反弹失败后回落 末端未决']},
'sge-Au9999':{'name':'黄金现货 Au99.99','base':'2022-07-21','secondary':'2022-07-21','prior_high':'2022-03-09','peak':'2026-01-29','anchors':['2022-07-21','2024-10-30','2024-11-14','2025-04-22','2025-05-15','2025-10-17','2025-10-28','2026-01-29','2026-07-01','2026-08-24','2026-10-22'],'labels':['跨多年主升 中间小波动不另立年周期','短期回撤','恢复后加速','回撤','再推进','回撤','加速至主升最高','本轮主要调整','反弹未重返1月高点','再次回落 末端未决']}}
rows=[];summ=[]
for sid,z in spec.items():
 s=d[sid].dropna()
 hi=s.loc[z['prior_high']];after=s.loc[z['secondary']:];cross=after[after>hi].index[0]
 summ.append({'sid':sid,'name':z['name'],'background_base':z['base'],'secondary_base':z['secondary'],'previous_recovery_high':z['prior_high'],'first_close_reclaim_date':str(cross.date()),'main_peak':z['peak'],'base_to_peak_pct':100*(s.loc[z['peak']]/s.loc[z['base']]-1),'secondary_to_peak_pct':100*(s.loc[z['peak']]/s.loc[z['secondary']]-1),'base_to_peak_days':int((pd.Timestamp(z['peak'])-pd.Timestamp(z['base'])).days),'base_to_peak_observed_sessions':len(s.loc[z['base']:z['peak']])-1,'observation_end':'2026-10-22','end_is_cycle_end':False,'status':'主升峰后调整 未来周期结束/恢复尚未由本观察完整识别'})
 for i,(a,b,label) in enumerate(zip(z['anchors'][:-1],z['anchors'][1:],z['labels']),1):
  t=s.loc[a:b];v=t.values;ratio=v[None,:]/v[:,None]-1;vals=ratio[np.triu_indices(len(v),k=1)]
  rows.append({'sid':sid,'name':z['name'],'phase':i,'description':label,'start':a,'end':b,'start_close':float(t.iloc[0]),'end_close':float(t.iloc[-1]),'return_pct':100*(t.iloc[-1]/t.iloc[0]-1),'calendar_days':int((pd.Timestamp(b)-pd.Timestamp(a)).days),'observed_sessions_after_start':len(t)-1,'internal_max_drawdown_pct':-min(0,float(vals.min()))*100,'last_segment_observation_censored':b=='2026-10-22','retrospective':True})
summary=pd.DataFrame(summ);ph=pd.DataFrame(rows)
summary.to_csv(O/'SIX_INDEPENDENT_CYCLES.csv',index=False);ph.to_csv(O/'SIX_INDEPENDENT_PHASES.csv',index=False)
json.dump({'type':'retrospective_human_chart_review','coverage':'five A-share industries plus one spot gold series, NOT all90 industries','selection':'core semiconductor/electronics and gold themes from assigned2025–2026 request','full_context':'2019–2026-10-22 native valid daily prices; gold original SGE raw response','annual_tables_role':'background only, not cycle identification','phase_anchors':spec,'calendar_boundaries':'not used as turning-point rules','breakout_date':'first close after selected secondary low exceeding the earlier recovery high; descriptive observable test, chosen anchors already inspected and not OOS trading signal','end':'main peak is retrospectively known;2026-10-22 only observation cutoff, no automatic cycle terminal declaration','account_economics':'prior quarterly accounting unchanged; not relabeled as per-cycle economics'},open(O/'CYCLE_REVIEW_PROTOCOL.json','w'),ensure_ascii=False,indent=2)
lines=['按板块独立周期补充复核','覆盖五个A股行业与黄金现货，不是全90行业人工周期已完成','',
'核对结论：此前年度、半年和统一市场阶段表不能代替逐板块周期。此处不按1月1日换轮，不把同日市场拐点强套给所有行业，也不把观察截止日当行情结束。原年度数据仍可作背景，但其用途应降级。',
'以下日期先按各自完整日线图选定结构，再核算价格、持续时间和中途回撤。它们是事后人工复盘，不是盲样本算法。底部最低点不等于当时可以下单；主升峰值在事后才知道。',
'每条分为背景底部、二次底部、收盘重返此前修复高点、主升峰值及随后调整。重返前高只是可逐日观察的价格事件；本次选哪些高低点已经看过后续，不宣称这是已验证实时规则。',
'2026/10/22仅为共同资料截止。各自峰值及回撤日期完全独立；截至此日仍在调整或反弹中，更大周期是否最终终结不强行判定。',
'']
for _,r in summary.iterrows():
 lines+=[r['name']+' '+r.sid,
 f"背景底部{r.background_base}；二次底部{r.secondary_base}；第一次收盘重新超过{r.previous_recovery_high}修复高点在{r.first_close_reclaim_date}。主升最高在{r.main_peak}。背景底部至最高{r.base_to_peak_pct:+.2f}%，二次底部至最高{r.secondary_to_peak_pct:+.2f}%，经历{r.base_to_peak_days}自然日、{r.base_to_peak_observed_sessions}个后续有效交易收盘。",
 '逐段顺序：']
 for _,p in ph[ph.sid==r.sid].iterrows():
  lines.append(f"  {int(p.phase)}. {p.start}至{p.end}，{p.description}；收盘变化{p.return_pct:+.2f}%，{int(p.calendar_days)}自然日/{int(p.observed_sessions_after_start)}个后续交易收盘；段内最大回撤{p.internal_max_drawdown_pct:.2f}%。")
 lines.append('')
lines+=['需要修正的解释',
'1. 半导体2025/4/7只是2024筑底后行情中的一次主要回撤低点，不应一律重新定义为完整行情起点。2024/9/23二次低点之后，主升持续到2026/6/30，中间仍有2025年4月、11月及2026年3月的回撤。',
'2. 元件在2024年2月至7月已经先行推进；它的二次底部9/18、2025高点10/29、2026最高6/25均与半导体不同。7/30之后又恢复到9/23局部高点，不能把6/25之后整段简单说成单向下跌。',
'3. 电子化学品二次低点2024/9/13，第一次推进高点2024/11/11，随后整理到2025/4/7，再跨年至2026/7/1最高。2025年底不是行情终点。',
'4. 通信设备2023年那轮高点后曾跌破旧起势区域，应与2024年2月新底部之后的行情分开。新一轮主升高点在2026/5/13，早于元件、半导体和电子化学品。',
'5. A股贵金属2024/2/5至4/12已出现第一段强涨，然后回撤到9/12，再跨年至2026/1/29。其阶段与黄金现货并不相同，且行业包含白银股票。',
'6. 黄金Au99.99的2025加速是更长周期的延续。本次主升起势背景取2022/7/21的二次底部369.57，早前2021/3/5还有更大级别底部355.70；2023/1/16收盘重新超过2022/3/9高点415.11，此后跨年走到2026/1/29的1243.02。并非从2025年元旦突然出生。',
'主观验收：核心肥尾应看整个跨年主升及反复恢复，不要求精确买最低卖最高。中间失效后允许小仓重入，但不能用后来的大行情替每一次早期失败交易辩护。峰后回撤与未收复前高的反弹可选择错过，不必为覆盖每一段局部上涨而无限扩大试错。',
'覆盖缺口：本补充已人工核六条主线，不把其余85行业的年度极值表伪装成独立周期审查。若需全90行业完整人工周期表，应逐个扩展这一过程，并保留未决/被观察窗口截断的周期。',
'经济边界：此前原PVR2025至2026/5/15的逐季度净贡献仍为会计时间切片，不能直接改名为这里的完整周期收益。原账5/15以后的持仓与交易未生成，不能推断6、7月是否继续遗漏。现货黄金不在1709股票账户中。',
'数据边界：固定现有行业映射NON-PIT；只用日线收盘。图表用对数纵轴以展示跨年比例变化。黄金从已保存的官方SGE原始响应提取完整历史，无新增外部行情请求。']
(O/'逐板块跨年周期补充复核.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(summary.to_string(index=False));print('phases',len(ph))
