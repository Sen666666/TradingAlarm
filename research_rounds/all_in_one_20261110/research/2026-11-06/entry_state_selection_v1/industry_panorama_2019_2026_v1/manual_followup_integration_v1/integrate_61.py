import pathlib,json,hashlib,pandas as pd,numpy as np,re
O=pathlib.Path(__file__).parent;P=O.parent;R=P.parent
U=pathlib.Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
S={};sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def readc(p):S[str(p)]=sha(p);return pd.read_csv(p)
def readj(p):S[str(p)]=sha(p);return json.loads(p.read_text())
base=(O/'DELIVERED_VERSION_0.txt').read_text();S[str(O/'DELIVERED_VERSION_0.txt')]=sha(O/'DELIVERED_VERSION_0.txt')
old=readc(P/'MANUAL_RECORDS.csv');a=readc(P/'AUXILIARY_20PCT_WAVES.csv');c=readc(P/'COVERAGE_90.csv')
new=[];ledgers=[]
for label,folder in [('industrial','manual_followup_industrial_v1'),('consumers','manual_followup_consumers_v1'),('resources','manual_followup_resources_v1')]:
 f=P/folder;m=readc(f/('MANUAL_INDEPENDENT_CYCLES.csv' if label=='resources' else 'MANUAL_CYCLES.csv'));m['origin']='new61_'+label
 if 'note' not in m:m['note']=m.boundary_rationale
 if 'sessions_after_start' not in m:m['sessions_after_start']=m.sessions
 if 'outside_pool' not in m:m['outside_pool']=m.current_all_members-m.research_pool_members
 if 'auxiliary_ids' not in m:m['auxiliary_ids']=m.aux_ids.str.replace(' ',';')
 if label=='industrial':g=readc(f/'ALL_AUXILIARY_DISPOSITIONS.csv').rename(columns={'aux_id':'auxiliary_id','manual_record_id':'manual_cycle_id','rationale':'review_reason','role':'review_decision'})
 else:g=readc(f/'AUXILIARY_REVIEW_LEDGER.csv').rename(columns={'record_id':'auxiliary_id','review_disposition':'review_decision'})
 new.append(m);ledgers.append(g[['auxiliary_id','manual_cycle_id','review_reason','review_decision']]);readj(f/'QA.json')
new=pd.concat(new,ignore_index=True);new.loc[new.record_id.eq('RS0664'),'note']='2020-02-03作为背景起点；段内2020-04-28还低3.493%，本行不是绝对最低到最高收益。原辅助起点保留供观察，不把它视为当时可知低点。行业广度仅2个有效成员，证据不足。';ledger=pd.concat(ledgers,ignore_index=True);newsecs=set(new.sector);assert len(newsecs)==61 and newsecs==set(c[c.manual_records==0].sector)
assert len(ledger)==425 and ledger.auxiliary_id.nunique()==425 and set(ledger.auxiliary_id)==set(a[a.sector.isin(newsecs)].record_id)
assert new.record_id.is_unique
# New61 post-peak description is bounded by the next human cycle's start, inclusive.
prices={}
for m in readj(U/'INDUSTRY_MANIFEST.json'):
 if m['series'] not in newsecs:continue
 p,h=next((p,h) for p,h in m['source_sha256'].items() if p.endswith('/signal.parquet') and '/a-share-selection-e0-' in p);assert sha(p)==h;S[p]=h
 d=pd.read_parquet(p,columns=['close','observed_bar','price_eligible','source_invalid','synthetic_event_bar']);ok=d.observed_bar.astype(bool)&d.price_eligible.astype(bool)&~d.source_invalid.astype(bool)&~d.synthetic_event_bar.astype(bool)&d.close.gt(0)&np.isfinite(d.close);prices[m['series']]=d.close[ok].loc[:'2026-10-22']
for i,r in new.iterrows():
 starts=new[(new.sector==r.sector)&(new.start>r.end)].start.tolist();cut=min(starts) if starts else '2026-10-22';q=prices[r.sector].loc[r.end:cut]
 new.loc[i,'post_scope']='截至下轮人工周期起点'+cut+'（含）' if starts else '截至2026-10-22'
 new.loc[i,'post_low_day']=str(q.idxmin().date());new.loc[i,'post_drop_pct']=(q.min()/q.iloc[0]-1)*100;new.loc[i,'post_newhigh']=bool(q.max()>q.iloc[0]);new.loc[i,'nested_in']=''
allm=pd.concat([old,new],ignore_index=True)
def grade(v):return '重点候选' if '重点' in v else ('证据不足或等级待讨论' if '不足' in v or '待' in v else '普通或可错过')
allm['unified_grade']=allm.priority.map(grade);counts=allm.unified_grade.value_counts().to_dict();nc=new.priority.map(grade).value_counts().to_dict()
assert allm.sector.nunique()==90 and allm.record_id.is_unique
allm.to_csv(O/'ALL_MANUAL_RECORDS_V1.csv',index=False);new.to_csv(O/'NEW_61_MANUAL_RECORDS.csv',index=False);ledger.to_csv(O/'REVIEWED_425_AUXILIARY_DISPOSITIONS.csv',index=False)
cc=c.copy();cc['new_manual_records']=cc.sector.map(new.groupby('sector').size()).fillna(0).astype(int);cc['total_manual_records']=cc.sector.map(allm.groupby('sector').size()).astype(int);cc['review_coverage']=np.where(cc.new_manual_records.gt(0),'本轮全体既有机械候选已逐项人工审视；不是全部可交易机会穷尽','既有重点区段人工复盘；本轮不重复复核全部244辅助段');cc.to_csv(O/'COVERAGE_90_V1.csv',index=False)
num=lambda v:'未知' if pd.isna(v) else f'{float(v):+.2f}%'
ni=lambda v:str(int(v)) if pd.notna(v) else '未知'
def br(r):return f"上涨{ni(r.positive_members)}/可算{ni(r.known_members)}/研究池{ni(r.research_pool_members)}/现时行业{ni(r.current_all_members)}；池内UNKNOWN {ni(r.unknown_members)}，池外{ni(r.outside_pool)}，全路径有效{ni(r.full_path_members)}"
# Preserve core conclusions and all previous non-cycle material, update coverage explicitly.
prefix=base.split('四之前 全部102条人工记录速查索引')[0]
oldp='对全部90行业，另补了669条按统一20%收盘转折识别的辅助波段，并统一计算成员分布。本报告逐条列出，不只给少数主线摘要。另61个行业已经有价格与成员统计，但尚未逐项人工确定长周期与目标等级，清楚标为待核，不假装已经完成90行业全部主观审查。'
newp=f'本次已补审此前没有人工记录的61个行业：425个既有辅助候选逐条归属，共形成{len(new)}个人工周期，其中重点候选{nc.get("重点候选",0)}、普通或可错过{nc.get("普通或可错过",0)}、证据不足{nc.get("证据不足或等级待讨论",0)}。每个行业均列出具体起止、涨幅、回撤、成员分母与判断理由，合并周期重新从日线计算，没有相乘拼接子段收益。合计90行业现有{len(allm)}条人工记录：重点候选{counts.get("重点候选",0)}、普通或可错过{counts.get("普通或可错过",0)}、证据不足或等级待讨论{counts.get("证据不足或等级待讨论",0)}。这仍不是互相独立的统计样本。'
assert oldp in prefix;prefix=prefix.replace(oldp,newp)
prefix=prefix.replace('8. 本轮核对90行业完整日线','8. 上版已核对90行业完整日线')
prefix=prefix.replace('行业主线 跨年衔接 成员广度与未决部分','行业主线 跨年衔接 成员广度与未决部分\n更新版：补齐原61个行业的人工周期审视')
prefix=prefix.replace('全景覆盖现行同花顺90个行业，2019年起至2026年10月22日共1891个共同交易日，170190个行业收盘格全部有效。此前重点区段人工复盘合并为102条行业记录，涉及29个行业：54条重点肥尾候选、41条普通或次级波段、7条等级待讨论。三条重复跨年记录已合并。这里含长周期与嵌套子段，不能把102或54当作互相独立的行情样本，更不能相加收益。','全景覆盖现行同花顺90个行业，2019年起至2026年10月22日共1891个共同交易日，170190个行业收盘格全部有效。上版保留的29个行业共有102条重点区段人工记录，已去掉三条精确重复跨年记录；其中仍有长周期与嵌套子段，不能累计记录数为独立行情样本，也不能相加收益。')
prefix += '\n覆盖边界：本次61行业的425个辅助候选已全部有人工去向；先前29行业的244个辅助段仍只配有既有重点记录，未在本轮逐条重新审阅。90行业都有人工记录，不等于2019至2026所有大小机会已穷尽。20%以下未触发候选的路径也不能据此判作没有机会。\n'
# First practical additions, then full index.
add=['\n新增复核中值得对齐的重点和降级\n',
'电网设备、通用设备、自动化设备、其他电源设备及资源化工里有此前摘要没有覆盖的多年群体行情。例：电网2024年2月至2026年3月行业+214.14%，29/29可算成员上涨，中位+164.12%，但现时全行业140只中研究池仅29只。自动化2024年9月至2026年6月行业+215.59%，中途回撤25.93%，28/28成员上涨、中位+266.35%；通用设备2024年8月至2026年5月+189.30%，40/40上涨、中位+326.17%。这些支持在固定池内列重点候选，不自动证明行业所有小市值股票共同上涨。',
'资源与消费也新增了群体证据：农化2020年2月至2022年7月行业+185.79%，20/20上涨、中位+264.42%；电力2020年2月至2022年8月+108.87%，48/51上涨、中位+63.90%。白色家电从2018年10月至2026年5月的长母周期+342.16%，中途最大回撤30.34%，9/9可算成员上涨、中位+334.35%；但研究池只覆盖现时10/43且全路径有效5只，因此不能当作完整行业认证，更不能视为八年无须退出的持有建议。',
'对指数大涨也有明确降级。轨交2024至2026行业约+121.82%，但只有4/30现时成员可算，中位约+24.35%，前三占91.19%，仍列证据不足。美容护理2018至2021指数约+208.27%，只有2只历史端点可用，同样不能当作已证行业广度。纺织制造2024至2026指数约+104.65%，3个样本仅1个上涨、中位−4.13%，不以指数幅度掩盖成员分歧。',
'保险2021段还有更强的冲突：行业源指数上涨约23%，现时5个成员却全部下跌。该段列证据不足，需要历史成分、权重及源口径解释，不能自行编造原因。2024夏至2026初的另一保险周期则5/5上涨，中位+98.26%，两段不能互相替代。',
'长周期可以含大幅回撤和长期停顿。新合并周期不是假设全程持有；例如自动化2025中途回撤约26%，通信服务的2024夏主升后，2025多为整理，直到2026年5月才略创新高。初始试错、后续扩大参与、失效退出与再次参与应分别研究，不能把整段低到高收益当系统已实现。\n']
idx=[f'全部{len(allm)}条人工记录速查索引','本索引和逐行业正文是同一组记录；候选是后视目标判断，不是预测结论。分母为上涨/可算/研究池/现时全行业。']
for grade_ in ['重点候选','普通或可错过','证据不足或等级待讨论']:
 idx.append('\n'+grade_+' 共'+str(counts.get(grade_,0))+'条')
 for r in allm[allm.unified_grade==grade_].sort_values(['sector','start','end']).itertuples():idx.append(f'{r.record_id} {r.name} {r.start}→{r.end}：行业{num(r.industry_return_pct)}，中途回撤{num(r.mdd_pct)}；成员{ni(r.positive_members)}/{ni(r.known_members)}/{ni(r.research_pool_members)}/{ni(r.current_all_members)}，中位{num(r.member_median_pct)}。')
body=['\n四 90行业逐项复盘\n','每行业先列人工周期，再保留机械子段及归属。对本轮61行业，机械段已人工归并或降级；原29行业的辅助段没有在本轮全部重新定级。人工长周期与其子段不得重复计算。']
ld=ledger.set_index('auxiliary_id');mids=allm.set_index('record_id')
for _,ccr in cc.sort_values('sector').iterrows():
 sid=ccr.sector;mm=allm[allm.sector==sid].sort_values(['start','end']);aa=a[a.sector==sid].sort_values(['start','end']);isnew=sid in newsecs
 body.extend([f'\n【{ccr["name"]}  {sid}】',f'行业日线{ni(ccr.period_valid)}/{ni(ccr.period_expected)}有效；研究池{ni(ccr.research_pool_members)}/现时全行业{ni(ccr.current_all_members)}。人工周期记录{len(mm)}，辅助候选{len(aa)}。','覆盖状态：'+ccr.review_coverage+'。'])
 for i,r in enumerate(mm.itertuples(),1):
  body.append(f'  人工记录{i} [{r.record_id}] {r.start}→{r.end}｜{r.unified_grade}')
  body.append(f'    行业{num(r.industry_return_pct)}；中途最大回撤{num(r.mdd_pct)}（{r.mdd_peak}→{r.mdd_trough}）；{ni(r.sessions_after_start)}个后续交易收盘。')
  body.append('    '+br(r)+'。')
  body.append(f'    成员25/50/75分位 {num(r.member_p25_pct)}/{num(r.member_median_pct)}/{num(r.member_p75_pct)}；≥30% {ni(r.above30_members)}/{ni(r.known_members)}，≥50% {ni(r.above50_members)}/{ni(r.known_members)}；前三正收益占{num(r.top3_positive_share_pct)}，剔除前三后均值{num(r.mean_without_top3_pct)}。')
  body.append(f'    {r.post_scope}，最低{r.post_low_day}较阶段峰{num(r.post_drop_pct)}；观察截止不是永久结束。')
  if pd.notna(r.post_newhigh) and bool(r.post_newhigh):body.append('    该峰后观察区间存在更高收盘，所以这里只称阶段峰。')
  if pd.notna(r.nested_in) and r.nested_in:body.append('    本段嵌套于该行业更长原记录，不能重复累计。')
  body.append('    判断依据：'+str(r.note))
 body.append('  机械子段与人工归属：' if isnew else '  机械辅助段（本轮未全部逐项重新定级）：')
 for r in aa.itertuples():
  conf='截至观察日尚未确认20%峰后回撤' if pd.isna(r.down_confirm) else '20%下行确认'+r.down_confirm
  body.append(f'    [{r.record_id}] {r.start}→{r.end} 行业{num(r.industry_return_pct)}，段内回撤{num(r.mdd_pct)}；上行确认{r.up_confirm}，{conf}。')
  if isnew:
   z=ld.loc[r.record_id];dest=mids.loc[z.manual_cycle_id];body.append(f'      人工归属{z.manual_cycle_id}（{dest.start}→{dest.end}，{dest.unified_grade}）；{z.review_decision}。')
  body.append(f'      成员{ni(r.positive_members)}/{ni(r.known_members)}/{ni(r.research_pool_members)}/{ni(r.current_all_members)}，UNKNOWN{ni(r.unknown_members)}，中位{num(r.member_median_pct)}，前三正收益占{num(r.top3_positive_share_pct)}。')
late=base.split('五 五条跨2024至2026主段的完整推进与回撤顺序')[1].split('七 仍未完成的部分与可得出的结论')[0]
ending=['\n七 已完成与仍未解决\n',f'本次新增61行业、{len(new)}个人工周期，全部425个既有辅助候选各有去向。连同原29行业102个重点记录，现90行业均有人工判断，共{len(allm)}条记录。没有把任意20%波段自动称肥尾，也没有拿个股极端涨幅代替行业成员分布。',
'“补齐61个行业”不等于“所有历史周期均已穷尽”。原29行业的244个辅助段未在这轮全部重新审阅；其既有重点段继续保留。所有行业未触及辅助阈值的较小波动，也未声称完全排查。长期包络与内部子段并非独立样本。',
'所有行业共同欠缺真实历史PIT成员、完整退市退出者、历史指数权重和可验证的实际成交队列。研究池为现时1709只大市值存续股，不能把其上涨比例直接解释成当年全行业上涨比例。端点UNKNOWN和全路径缺口逐段列出。',
'本报告是可讨论的后视机会地图。重点候选可用于讨论策略应该争取哪类群体机会，普通波段可以容忍错过，证据不足不等于机会不存在。它不能直接证明首仓35%胜率、成交可实现性或任何新策略收益。初始小仓试错不意味着确认后的大行情只能始终小仓。\n',
'数据与核对\n','行业使用既有同花顺行业日线，个股使用既有theoretical_ex_price调整链的close；不是未复权raw_close，也不是官方PIT公司行动或含息总回报认证。原报告来源和89条旧记录复现结论保留。本轮319个人工周期和4516条成员记录已由另一实现直接读取原日线核对，涨幅、回撤、分布、缺失和425候选唯一归属均无实质差异；人工分组和重点等级本身并不因此获得预测或因果认证。少数人工起点是背景起点而非区间绝对最低，相关条目已注明。',
'公开背景入口：同花顺行业 https://q.10jqka.com.cn/thshy/ ；924政策背景 https://finance.people.com.cn/n1/2024/0925/c1004-40328065.html 。价格与分布均来自已保存同口径日线，不是报道中个股案例的外推。',
'没有实盘交易、新账户回测、分钟研究或原策略改动。']
text=prefix+'\n'.join(add+idx+body)+'\n五 五条跨2024至2026主段的完整推进与回撤顺序'+late+'\n'.join(ending)+'\n'
assert text.count('【')==90 and text.count('  人工记录')==len(allm)
assert '另61个行业已经有价格与成员统计，但尚未' not in text and '/Users/' not in text
(O/'2019至2026年A股行业独立行情全景复盘.txt').write_text(text)
assert all(sha(p)==h for p,h in S.items())
qa=dict(new_industries=61,new_records=len(new),new_priority_counts=nc,all_industries=90,all_records=len(allm),all_priority_counts=counts,new_auxiliary_dispositions=len(ledger),original29_auxiliary_not_reaudited=244,all_sector_blocks=90,no_economic_run=True,sources_unchanged=True)
(O/'SOURCE_HASHES.json').write_text(json.dumps(S,ensure_ascii=False,indent=2)+'\n');(O/'QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2)+'\n');print(json.dumps(qa,ensure_ascii=False));print('bytes',len(text.encode()))
