import pathlib,json,hashlib,pandas as pd,numpy as np
R=pathlib.Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');O=pathlib.Path(__file__).parent
M=pd.read_csv(O/'MANUAL_RECORDS.csv');A=pd.read_csv(O/'AUXILIARY_20PCT_WAVES.csv');C=pd.read_csv(O/'COVERAGE_90.csv');qa=json.loads((O/'QA.json').read_text())
oldp=R/'market_regime_2019_2022_v1/sector_campaigns_v2/USER_REVIEW_CAMPAIGNS.csv';old=pd.read_csv(oldp);ep=pd.read_csv(R/'market_regime_2023_2024_review_v1/INDEPENDENT_EPISODES.csv');lateph=pd.read_csv(R/'major_trends_2025_2026_review_v1/industry_specific_cycles/SIX_INDEPENDENT_PHASES.csv');latebr=pd.read_csv(R/'major_trends_2025_2026_review_v1/industry_specific_cycles/member_participation/WINDOW_PARTICIPATION.csv')
labels={'重点':'重点肥尾候选','次级':'普通或次级波段','待讨论':'等级待讨论'};changes=[]
for i,r in M.iterrows():
 if r.origin=='2019_2022_manual':
  z=old[(old.sector==r.sector)&(old.start==r.start)&(old.end==r.end)];assert len(z)==1;q=z.iloc[0]
  new=labels[q.priority]
  if r.priority!=new:changes.append(dict(record_id=r.record_id,old=r.priority,new=new,reason='latest delivered editorial priority'))
  M.loc[i,'priority']=new;M.loc[i,'post_low_day']=q.post63_low;M.loc[i,'post_drop_pct']=q.post63_drop*100;M.loc[i,'post_scope']='峰后63个已有交易日';M.loc[i,'post_newhigh']=bool(q.post63_newhigh)
 elif r.origin=='2023_2024_manual':
  q=ep[(ep.sid==r.sector)&(ep.low_day==r.start)&(ep.peak_day==r.end)].iloc[0];M.loc[i,'post_low_day']=q.after_peak_low_day;M.loc[i,'post_drop_pct']=q.after_peak_drawdown_pct;M.loc[i,'post_scope']='截至'+q.observation_end;M.loc[i,'post_newhigh']=False
 else:
  M.loc[i,'post_low_day']=r.peak_following_low;M.loc[i,'post_drop_pct']=r.peak_to_observed_low_pct;M.loc[i,'post_scope']='截至2026-10-22';M.loc[i,'post_newhigh']=False
M.to_csv(O/'MANUAL_RECORDS.csv',index=False)
# Future reproduction must use the same final editorial source, not an earlier intermediate table.
p=O/'build_panorama_data.py';s=p.read_text();s=s.replace("sector_campaigns_v2/USER_REVIEW_WITH_PARTICIPATION.csv","sector_campaigns_v2/USER_REVIEW_CAMPAIGNS.csv");p.write_text(s)
sources=json.loads((O/'SOURCE_HASHES.json').read_text());sources[str(oldp)]=hashlib.sha256(oldp.read_bytes()).hexdigest();(O/'SOURCE_HASHES.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2)+'\n')
counts=M.priority.value_counts().to_dict();assert counts=={'重点肥尾候选':54,'普通或次级波段':41,'等级待讨论':7}
qa['priority_counts']=counts;qa['editorial_priority_corrections']=changes;qa['source_count']=len(sources);(O/'QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2)+'\n')
def num(v,dec=2):return '未知' if pd.isna(v) else f'{v:+.{dec}f}%'
def n(v):return int(v)
def breadth(r):return f"上涨{n(r.positive_members)}/可算{n(r.known_members)}/研究池{n(r.research_pool_members)}/现时行业{n(r.current_all_members)}；端点UNKNOWN {n(r.unknown_members)}，池外{n(r.outside_pool)}"
def dist(r):return f"成员25/50/75分位 {num(r.member_p25_pct)}/{num(r.member_median_pct)}/{num(r.member_p75_pct)}；前三正收益贡献{r.top3_positive_share_pct:.2f}%；剔除前三后均值{num(r.mean_without_top3_pct)}"
lines=['2019至2026年A股行业独立行情全景复盘','行业主线 跨年衔接 成员广度与未决部分','行情资料截至2026年10月22日\n',
'一 先说明实际完成了什么\n',
'这份报告按行业组织，不按自然年把同一行情切断，也不把少数妖股的暴涨当作整个行业的肥尾。判断对象是行业自己的推进与回撤，以及同一时段成员是否共同上涨；不要求策略必须买中任何一只事后最强股。',
'全景覆盖现行同花顺90个行业，2019年起至2026年10月22日共1891个共同交易日，170190个行业收盘格全部有效。此前重点区段人工复盘合并为102条行业记录，涉及29个行业：54条重点肥尾候选、41条普通或次级波段、7条等级待讨论。三条重复跨年记录已合并。这里含长周期与嵌套子段，不能把102或54当作互相独立的行情样本，更不能相加收益。',
'对全部90行业，另补了669条按统一20%收盘转折识别的辅助波段，并统一计算成员分布。本报告逐条列出，不只给少数主线摘要。另61个行业已经有价格与成员统计，但尚未逐项人工确定长周期与目标等级，清楚标为待核，不假装已经完成90行业全部主观审查。',
'所有价格空间都是历史描述，不是买在低点、卖在高点的可实现收益，更不是新策略回测。任何行情或成员广度都不能直接推出首仓35%胜率。\n',
'二 对主要行情的统一判断\n',
'2019至2020科技：半导体、消费电子、元件和软件各有自己的起势与峰值，不能只用2019或2020年度收益代替。半导体2019年1月3日至2020年2月25日行业上涨163.49%，中途最大收盘回撤20.85%，已知成员28/29上涨；消费电子同期行业上涨127.95%，17/17上涨。它们是行业级机会，不以抓中某只芯片股为条件。',
'消费医药与新能源跨年主线：白酒2020年3月23日至2021年1月5日上涨280.75%，但医疗服务的主线从2019年延续至2021年6月28日。光伏、风电、电池与能源金属又有不同的调整和重新推进时点。2021年电池段32/32已知成员上涨，中位+140.54%，前三正收益占17.75%；这比单举一只新能源大牛股更能支持行业共同走强。能源金属2020至2021段虽价格空间约505%，中途回撤约35%，且只有6个端点可算成员，必须同时看到困难与样本限制。',
'2022并非所有行业都应停做：煤炭从2021年11月到2022年6月有独立推进；春夏汽车整车6月28日先到阶段峰值，风电7月20日、半导体8月11日、光伏8月18日、电池8月23日随后见峰。医药和软件秋季又有不同起点。不能把“2022是弱市”变成全年封禁全部行业。',
'2022秋至2023的AI第一轮：通信、传媒、软件三个跨年段已去重合并，游戏另列。通信已知38只中32只上涨、中位+69.63%；传媒29/29上涨、中位+72.71%；软件29/30上涨、中位+65.30%；游戏12/12上涨、中位+150.38%。这些仅是现时静态研究池内的广度，不是完整历史全行业成员认证。',
'2023年末至2024年中CPO强股：撤回把它当作通信行业普遍肥尾的外推。同一2023年11月1日至2024年7月10日，通信41只可算股仅16只上涨，中位−11.92%，前三正收益占71.70%，去掉前三后均值−11.37%。强股价格路径真实，但CPO细分主题历史成员未齐，不能据两三股推定主题整体广度，也不能把它们设为必须买中的目标。',
'2024春资源与银行长趋势：贵金属14/14已知成员上涨，中位+55.33%；工业金属34/34上涨，中位+50.66%。银行2023年12月至2024年12月39/39上涨、中位+43.71%，前三占12.15%。这些存在不同强度和速度的群体趋势，不能一律只追求单股数倍涨幅。银行2024年底仍近高位，年末不是自然结束。',
'924是史诗级全面反转：9月23日至10月8日90行业全部上涨，行业涨幅中位35.48%。已知半导体成员104/104上涨，中位+64.24%，前三正收益占3.89%；软件33/33上涨，证券46/46上涨。初始小仓是试错方式，不代表整个行情应只小仓。确认后应具备扩大参与的能力，但本报告不把事后峰谷当作当时可执行触发，也不保证涨停或跳空时能够成交。',
'2024至2026的跨年主段：半导体二次底部2024年9月23日至2026年6月30日上涨360.87%；元件9月18日至2026年6月25日上涨359.57%；电子化学品9月13日至2026年7月1日上涨467.09%；通信9月18日至2026年5月13日上涨256.08%；贵金属9月12日至2026年1月29日上涨358.82%。这些不是从2025年元旦突然出生，也不在2024年11月局部高点或年底统一结束。五行业同段成员中位分别+321.27%、+420.27%、+459.32%、+377.09%、+249.39%，但峰后又有显著广泛回撤，不能把上涨永久外推。',
'华为链、短剧、低空：本报告不再用赛力斯、光弘、中文在线、万丰或宗申的个股极值给整个主题定级。万丰同区间48只可算汽车零部件股中位仅+1.26%，≥50%只有1只。行业大类又不等于这些主题的概念成员，因此保留“主题广度待证”，不编造完整主题行情。\n',
'三 统一口径\n',
'1. 重点肥尾候选、普通或次级、等级待讨论是历史目标判断，尚待与你对齐，不是数学阈值、实时买入规则或保证盈利。普通波段不等于永远不能做，重点也不等于整段收益必须吃满。',
'2. 分母固定写为上涨n / 端点可算K / 研究池P / 现时全行业F。P来自原1709只2026年现时约100亿元以上市值的存续股票；F来自2026年10月22日现时行业归属。二者均不是历史时点成员PIT。旧材料某些N实际指P，本报告已纠正，不混成全行业F。未来上市、退市、行业迁移和事后市值选择偏差未消除。',
'3. 成员收益以同一行业段精确起止日期的有效调整后收盘计算，不给每股单独挑最低最高。端点缺失列UNKNOWN，不补价、不按不涨处理，也不凭缺行认定停牌。端点可算不代表中途每日有价，另列全路径有效人数。当前研究池外股票不混入同合同复权统计。',
'4. 行业用原始指数收盘；个股用既有theoretical_ex_price调整链。均非含股息再投资总回报、非费后账户利润。日线也不认证盘中成交、涨跌停排队和历史可交易性。行业指数本身不是可直接买入的组合。',
'5. 最大中途回撤按该段此前最高收盘到随后最低收盘计算。峰后回撤沿用各原记录明确的观察范围；观察截止不是永久结束。对2024至2026主段，2024年11月和2025年4月等局部峰谷作为内部分段保留。',
'6. 前三集中度＝前三股max(涨幅,0)之和/所有成员max(涨幅,0)之和，按期初等额。它不是指数历史权重贡献。K小时占比天然偏高，必须与分布及K一起读。删除前三后的均值仅作集中度描述，不是新交易策略。',
'7. 人工长周期与机械波段是不同层级。辅助层固定20%收盘阈值，先连续处理历史再展示2019以来相交区间：从运行低点上涨20%才确认上行；从运行高点下跌20%才确认峰值。回填的峰谷日期是后见值，真正确认日单列；末段尚未确认也单列。20%不是经过优化的策略参数，更不是肥尾标准；长主线中的20%以上回撤可能切成几段，不能因此否定长主线。没有触发阈值的小行情不在辅助列表中，不等于没有机会。',
'8. 本轮核对90行业完整日线、1709股票源及既有结果。89条已有人工记录的成员分母与上涨数完全重现，中位数最大误差约5.7e−14。共16606条成员窗口；这只是来源和算术核对，不冒称外部独审、历史PIT或实盘验证。没有新账户运行，没有改M3、I、CP、PVR。\n',
'四 90行业逐项复盘\n',
'以下每个行业先给已有人工判断的全部记录，再列所有机械辅助波段。机械段一律“人工定级待核”，不能把它们自动加到54条重点中。对没有人工段的61行业，也给实际价格和成员统计，明确缺的是逐项长周期判断，而非假装没有日线。可用行业名称或URFI代码搜索。\n']
# Sector-specific narrative joins, avoiding calendar-year resets.
joinnotes={
'URFI881121':'跨期衔接：2019至2022有四次不同推进。2024-09-23至2024-11-11是2024-09-23至2026-06-30长段的内部阶段，不算另一条独立总收益。',
'URFI881129':'跨期衔接：2022秋至2023年6月只记一段；个股CPO跨年强势没有替代行业共同表现。2024年2月形成新的背景底部，9月二次底部后继续至2026年5月。',
'URFI881169':'跨期衔接：2022至2023、2024春段与2024秋后跨2026推进应分层看；2024年4月至9月的回撤不能抹掉。该行业含白银股票，不等同黄金现货。',
'URFI881270':'跨期衔接：2020至2021段因成员分化已降为待讨论。2024年7月已有先行上涨，9月二次底部后延续到2026年6月，不按2025元旦重置。',
'URFI881172':'跨期衔接：2024年11月局部峰后调整至2025年4月，再延续到2026年7月；不能把年末设为终点。',
'URFI881155':'银行2022秋至2023修复与2023年末以后的新段分别列出。2024年底不是周期已结束的证据；2025至2026的完整人工边界仍待核。',
'URFI881158':'零售有指数与有限成员支持，但现时71只中只有12只进入同合同研究池；不能称全行业广度已验证。'}
for _,c in C.sort_values('sector').iterrows():
 sid=c.sector;ms=M[M.sector==sid].sort_values(['start','end']);aa=A[A.sector==sid].sort_values(['start','end']);lines.append(f"\n【{c['name']}  {sid}】")
 lines.append(f"覆盖：研究池{n(c.research_pool_members)}/现时行业{n(c.current_all_members)}；行业日线{n(c.period_valid)}/{n(c.period_expected)}有效。人工记录{len(ms)}条，机械辅助{len(aa)}条。")
 lines.append('证据状态：'+c.review_status+'。')
 if sid in joinnotes:lines.append(joinnotes[sid])
 if not len(ms):lines.append('人工长周期、重点或普通等级：待核。以下候选并非“无行情”的判断，也不自动标成肥尾。')
 for i,r in enumerate(ms.itertuples(),1):
  lines.append(f"  人工记录{i} [{r.record_id}] {r.start} → {r.end}｜{r.priority}")
  lines.append(f"    行业{num(r.industry_return_pct)}；中途最大回撤{num(r.mdd_pct)}（{r.mdd_peak}→{r.mdd_trough}）；{n(r.sessions_after_start)}个后续交易收盘。")
  lines.append('    '+breadth(r)+f"；全路径有效{n(r.full_path_members)}。")
  lines.append('    '+dist(r)+'。')
  lines.append(f"    {r.post_scope}，低点{r.post_low_day}较阶段峰值{num(r.post_drop_pct)}；不是永久结束认证。")
  if bool(r.post_newhigh):lines.append('    峰后原观察窗还有更高收盘，因此这里只称阶段峰值。')
  if pd.notna(r.nested_in) and r.nested_in:lines.append('    本段位于同业更长人工记录内部，收益与记录数不可重复累计。')
  lines.append('    依据与判断：'+r.note+'。')
 lines.append('  全部20%辅助波段（人工定级待核，阈值确认与后见峰谷分开）：')
 for i,r in enumerate(aa.itertuples(),1):
  confirm='尚未确认20%峰后回撤，峰值暂定' if pd.isna(r.down_confirm) else '下行确认 '+r.down_confirm
  lines.append(f"    {i}. [{r.record_id}] {r.start}→{r.end}；行业{num(r.industry_return_pct)}，中途回撤{num(r.mdd_pct)}；上行确认 {r.up_confirm}，{confirm}。")
  lines.append('       '+breadth(r)+f"；成员中位{num(r.member_median_pct)}，≥30% {n(r.above30_members)}/{n(r.known_members)}，前三占{r.top3_positive_share_pct:.2f}%。")
lines+=['\n五 五条跨2024至2026主段的完整推进与回撤顺序\n','下面的50个行业子段用于看见中途失效、恢复与峰后回落，不新增为独立肥尾次数。所有边界仍是后视人工选择，不是自动交易信号。']
for sid,g in lateph[lateph.sid.str.startswith('URFI')].groupby('sid',sort=False):
 lines.append('\n'+g.iloc[0]['name'])
 for r in g.itertuples():
  z=latebr[(latebr.sector==sid)&(latebr.start==r.start)&(latebr.end==r.end)&latebr.window.str.startswith('阶段')];assert len(z)==1;q=z.iloc[0]
  lines.append(f"  {r.start}→{r.end} {r.description}：行业{num(r.return_pct)}，段内最大回撤{-abs(r.internal_max_drawdown_pct):.2f}%；成员上涨{n(q.positive_n)}/可算{n(q.known_endpoint_n)}/研究池{n(q.pool_n)}/现时{n(q.current_master_n)}，UNKNOWN {n(q.unknown_endpoint_n)}；成员中位{num(q.median_pct)}。")
lines+=['\n六 黄金现货单列 不计入90个A股行业\n','Au99.99现货从2022年7月21日二次底部到2026年1月29日主峰上涨236.34%；更早背景低点在2021年3月。2022年7月至2024年10月的推进、之后数次回撤和恢复不能按年度截断。2026年1月峰后到7月主要回撤约30.11%，随后反弹未收复前峰。现货与A股贵金属股票不是同一资产，也不在原1709股票账户中，不能要求股票策略直接获取现货收益。现货来源为已保存上海黄金交易所原始响应，成员广度概念不适用。',
'\n七 仍未完成的部分与可得出的结论\n',
'已经完成的是90行业逐日价格覆盖、同一固定规则的连续辅助波段、1709静态研究池内同窗成员分布，以及29行业重点区段的人工记录整合。尚未完成的是其余61行业全部长周期的人工定级，以及任何行业2019至2026所有细小机会的穷尽性认证。102条人工记录不是全部真实机会总数，669条辅助段也不是“真实行情”的唯一划分。',
'尚无人工定级行业：'+ '、'.join(C[C.manual_records.eq(0)].sort_values('sector')['name'])+'。',
'所有行业仍共同欠缺完整历史PIT成员与权重、退市退出者完整覆盖、全体股票统一可审计公司行动与可得时间、历史实际可成交性。因此报告可以用于对齐“哪些行业行情值得系统争取、哪些普通波段允许漏掉”，不能用来声称这些机会当时均可被识别或实现。',
'正确的目标是能参与有广度、持续推进或反复恢复的行业行情，而不是倒过来要求买中特定妖股。924及有成员支持的跨年大行情应保留扩大参与的能力；没有后续推进的普通反弹可以讨论容忍错过。如何做到以及付出多少试错成本，仍需另用真实可执行时点的日线策略验证。',
'\n数据依据\n','本报告统一使用既有同花顺行业历史日线和1709股准备数据，行业资料截至2026年10月22日，现时行业成员映射为2026年10月22日快照。先前2019至2022行业独立周期复盘、2023至2024行业广度修订版、2025至2026五行业跨年周期及成员参与度为重点记录来源。三份资料的年度背景表未用于强行切断行业。',
'公开入口：同花顺行业页面 https://q.10jqka.com.cn/thshy/ ；924政策背景 https://finance.people.com.cn/n1/2024/0925/c1004-40328065.html 。公开报道仅核背景，所有涨幅与分布按已保存日线计算。',
'本报告没有引用任何个股暴涨作为行业必捕证据，没有新实盘交易或账户回测。']
text='\n'.join(lines)+'\n'
index=['四之前 全部102条人工记录速查索引','以下索引与逐行业正文是同一批记录，不额外增加行情次数，也不相加收益。分母依次为上涨/可算/研究池/现时全行业。']
for label in ['重点肥尾候选','普通或次级波段','等级待讨论']:
 index.append('\n'+label+' 共'+str(sum(M.priority==label))+'条')
 for r in M[M.priority==label].sort_values(['sector','start','end']).itertuples():
  index.append(f'{r.record_id} {r.name} {r.start}→{r.end}：行业{num(r.industry_return_pct)}，中途回撤{num(r.mdd_pct)}；成员{n(r.positive_members)}/{n(r.known_members)}/{n(r.research_pool_members)}/{n(r.current_all_members)}，中位{num(r.member_median_pct)}。')
text=text.replace('四 90行业逐项复盘\n','\n'.join(index)+'\n\n四 90行业逐项复盘\n',1)
dest=O/'2019至2026年A股行业独立行情全景复盘.txt';dest.write_text(text)
assert text.count('【')==90 and text.count('  人工记录')==102 and text.count('上行确认 ')==669
assert '梦' not in text and '/Users/' not in text
assert all(hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()==h for p,h in sources.items())
seal={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_SEAL.json'};(O/'OUTPUT_SEAL.json').write_text(json.dumps(seal,ensure_ascii=False,indent=2)+'\n')
print('REPORT',str(dest),'BYTES',dest.stat().st_size,'CHARS',len(text));print('PRIORITIES',counts,'SECTORS',text.count('【'),'MANUAL',text.count('  人工记录'),'AUX',text.count('上行确认 '),'SOURCE',len(sources));print('CORRECTIONS',changes)
