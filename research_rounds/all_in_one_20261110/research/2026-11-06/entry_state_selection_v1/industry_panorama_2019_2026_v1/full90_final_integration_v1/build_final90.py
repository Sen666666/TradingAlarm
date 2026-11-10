import pathlib,json,hashlib,pandas as pd,numpy as np
O=pathlib.Path(__file__).parent;P=O.parent
U=pathlib.Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
S={};sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def rc(p):S[str(p)]=sha(p);return pd.read_csv(p)
def rj(p):S[str(p)]=sha(p);return json.loads(p.read_text())
old=rc(P/'MANUAL_RECORDS.csv');kept=rc(P/'manual_followup_integration_v1/NEW_61_MANUAL_RECORDS.csv');kept['review_batch']='此前61行业';prior=[];led=[]
for name in ['health_finance','energy','tech']:
 f=P/f'prior29_{name}_review_v1';m=rc(f/'MANUAL_CYCLES.csv');m['review_batch']='原29行业最后补审';m['origin']='prior29_'+name
 if 'note' not in m:m['note']=m.boundary_rationale
 if 'sessions_after_start' not in m:m['sessions_after_start']=m.sessions
 if 'outside_pool' not in m:m['outside_pool']=m.current_all_members-m.research_pool_members
 if 'auxiliary_ids' not in m:m['auxiliary_ids']=m.aux_ids.str.replace(' ',';')
 if 'nested_in' not in m:m['nested_in']=''
 prior.append(m)
 g=rc(f/'AUXILIARY_REVIEW_LEDGER.csv');g=g.rename(columns={'canonical_id':'manual_cycle_id','disposition':'review_decision','reason':'review_reason','aux_id':'auxiliary_id'})
 if 'review_reason' not in g:g['review_reason']=g['manual_reason'] if 'manual_reason' in g else ''
 if 'review_decision' not in g:g['review_decision']='人工归属'
 led.append(g[['auxiliary_id','manual_cycle_id','review_decision','review_reason']]);rc(f/'OLD_MANUAL_RECONCILIATION.csv');rj(f/'QA.json')
prior=pd.concat(prior,ignore_index=True);priorsecs=set(prior.sector);assert len(priorsecs)==29 and priorsecs==set(old.sector)
a=rc(P/'AUXILIARY_20PCT_WAVES.csv');c=rc(P/'COVERAGE_90.csv')
ldold=rc(P/'manual_followup_integration_v1/REVIEWED_425_AUXILIARY_DISPOSITIONS.csv');ledger=pd.concat([ldold,*led],ignore_index=True)
assert len(ledger)==669 and ledger.auxiliary_id.nunique()==669 and set(ledger.auxiliary_id)==set(a.record_id)
allm=pd.concat([kept,prior],ignore_index=True);assert allm.record_id.is_unique and allm.sector.nunique()==90
for sec,g in allm.groupby('sector'):
 q=g.sort_values('start');assert q.end.shift().fillna('0000').lt(q.start).all(),(sec,q[['start','end']])
def grade(v):return '重点候选' if '重点' in v else ('证据不足或等级待讨论' if '不足' in v or '待' in v else '普通或可错过')
allm['unified_grade']=allm.priority.map(grade)
# Strict, conservative novelty identity: positive time intersection only, within same industry.
for i,r in allm.iterrows():
 if r.sector not in priorsecs:
  allm.loc[i,'novelty']='此前61行业已交付，不重复计新增';continue
 hit=old[(old.sector==r.sector)&(old.start<r.end)&(old.end>r.start)];hitf=hit[hit.priority.str.contains('重点')]
 allm.loc[i,'old_manual_overlap']=';'.join(hit.record_id);allm.loc[i,'old_priority_overlap']=';'.join(hitf.record_id)
 if r.unified_grade!='重点候选':x='非重点'
 elif not len(hit):x='原人工表完全遗漏的新增重点'
 elif not len(hitf):x='原非重点延伸或等级上调'
 else:x='原重点保留 延伸或合并'
 allm.loc[i,'novelty']=x
# Normalize post-peak description for ALL canonical rows using the next canonical start inclusive.
prices={}
for z in rj(U/'INDUSTRY_MANIFEST.json'):
 p,h=next((p,h) for p,h in z['source_sha256'].items() if p.endswith('/signal.parquet') and '/a-share-selection-e0-' in p);assert sha(p)==h;S[p]=h
 d=pd.read_parquet(p,columns=['close','observed_bar','price_eligible','source_invalid','synthetic_event_bar']);ok=d.observed_bar.astype(bool)&d.price_eligible.astype(bool)&~d.source_invalid.astype(bool)&~d.synthetic_event_bar.astype(bool)&d.close.gt(0)&np.isfinite(d.close);prices[z['series']]=d.close[ok].loc[:'2026-10-22']
for i,r in allm.iterrows():
 future=allm[(allm.sector==r.sector)&(allm.start>r.end)].start.tolist();cut=min(future) if future else '2026-10-22';p=prices[r.sector];q=p.loc[r.end:cut]
 allm.loc[i,'post_scope']='截至下轮人工周期起点'+cut+'（含）' if future else '截至2026-10-22'
 allm.loc[i,'post_low_day']=str(q.idxmin().date());allm.loc[i,'post_drop_pct']=(q.min()/p.loc[r.end]-1)*100;allm.loc[i,'post_newhigh']=bool(q.max()>p.loc[r.end])
 allm.loc[i,'start_is_interval_minimum']=bool(p.loc[r.start:r.end].min()==p.loc[r.start]);allm.loc[i,'end_is_interval_maximum']=bool(p.loc[r.start:r.end].max()==p.loc[r.end])
assert allm.end_is_interval_maximum.astype(bool).all()
recon=[]
for r in old.itertuples():
 h=allm[(allm.sector==r.sector)&(allm.start<r.end)&(allm.end>r.start)];assert len(h)
 rr=r._asdict();rr.update(canonical_ids=';'.join(h.record_id),canonical_grades=';'.join(h.unified_grade),mapping_count=len(h),relation='拆分包络或跨两个周期；旧数值仍保留' if len(h)>1 else ('原边界保留' if h.start.iloc[0]==r.start and h.end.iloc[0]==r.end else '内部阶段或背景起点延伸；不另计独立主周期'));recon.append(rr)
recon=pd.DataFrame(recon);assert len(recon)==102
counts=allm.unified_grade.value_counts().to_dict();pp=allm[allm.sector.isin(priorsecs)];pc=pp.unified_grade.value_counts().to_dict();nov=pp[pp.unified_grade=='重点候选'].novelty.value_counts().to_dict();newf=pp[pp.novelty=='原人工表完全遗漏的新增重点']
allm.to_csv(O/'FINAL_CANONICAL_CYCLES_90.csv',index=False);pp.to_csv(O/'FINAL_PRIOR29_CYCLES.csv',index=False);ledger.to_csv(O/'ALL_669_AUXILIARY_DISPOSITIONS.csv',index=False);recon.to_csv(O/'ORIGINAL_102_RECONCILIATION.csv',index=False);newf.to_csv(O/'TRULY_NEW_PRIOR29_PRIORITY.csv',index=False)
coverage=c.copy();coverage['canonical_records']=coverage.sector.map(allm.groupby('sector').size()).astype(int);coverage['reviewed_auxiliary_records']=coverage.auxiliary_records;coverage['coverage_statement']='现有全部辅助候选与连续日线已人工审视；未声称20%以下所有小波动穷尽';coverage.to_csv(O/'FINAL_COVERAGE_90.csv',index=False)
num=lambda v:'未知' if pd.isna(v) else f'{float(v):+.2f}%'
ni=lambda v:str(int(v)) if pd.notna(v) else '未知'
def br(r):return f'上涨{ni(r.positive_members)}/可算{ni(r.known_members)}/研究池{ni(r.research_pool_members)}/现时行业{ni(r.current_all_members)}；UNKNOWN{ni(r.unknown_members)}，池外{ni(r.outside_pool)}，全路径有效{ni(r.full_path_members)}'
lines=['2019至2026年A股行业独立行情全景复盘','全90行业逐项人工复盘版','行情资料截至2026年10月22日\n',
'一 完成范围与这次新增\n',f'90个行业的连续日线与全部669个既有辅助候选均已逐项人工审视，并归入{len(allm)}个同业不重叠的主周期：重点候选{counts["重点候选"]}、普通或可错过{counts["普通或可错过"]}、证据不足或等级待讨论{counts["证据不足或等级待讨论"]}。起势、推进、回撤和峰值按行业各自路径处理，没有在自然年末统一截断。',
f'此前补齐的61行业319周期保持原数值与判断。本次再补原29行业244辅助段，形成{len(pp)}个人工主周期。其中重点{pc.get("重点候选",0)}：{nov.get("原人工表完全遗漏的新增重点",0)}条与旧人工表没有任何正时间重叠，才称完全遗漏的新增重点；{nov.get("原非重点延伸或等级上调",0)}条是旧非重点延伸或上调；{nov.get("原重点保留 延伸或合并",0)}条为旧重点保留、延伸或合并，不能冒充新发现。',
'旧102条阶段记录没有丢失：原时段、原涨幅、原回撤、原广度和原等级完整保留在末尾对账，并注明归入哪一主周期。旧重点中的局部片段被合并，可能减少记录数；这不是删除行情或抹去阶段收益。主周期与内部阶段不能重复累计次数、也不能相加收益。',
'完成的是对现有候选集及连续路径的逐行业人工复盘，不是声称所有大小行情已经穷尽。辅助候选原用固定20%收盘转折产生；人工主周期可以合并多个候选，也可按事实修正边界，20%不构成肥尾标准。没有触及该辅助阈值的小波动，不能据此断言不存在。',
'本报告判断行业群体机会，不要求买中某只事后暴涨的妖股。所有峰谷和等级是后视讨论材料，不是入场信号、可实现利润或首仓35%胜率的验证。\n',
'二 原人工表真正遗漏的新增重点\n','以下仅列本轮原29行业中与旧人工记录完全无正时间交集的重点；主线延伸和等级上调另列，不混充新发现。']
for r in newf.sort_values(['sector','start']).itertuples():lines.extend([f'{r.record_id} {r.name} {r.start}→{r.end}：行业{num(r.industry_return_pct)}，中途最大回撤{num(r.mdd_pct)}；{br(r)}，成员中位{num(r.member_median_pct)}，前三正收益占{num(r.top3_positive_share_pct)}。',str(r.note)])
lines+=['\n旧非重点延伸或等级上调：']
for r in pp[pp.novelty=='原非重点延伸或等级上调'].sort_values(['sector','start']).itertuples():lines.append(f'{r.record_id} {r.name} {r.start}→{r.end}：行业{num(r.industry_return_pct)}，回撤{num(r.mdd_pct)}，成员{ni(r.positive_members)}/{ni(r.known_members)}/{ni(r.research_pool_members)}/{ni(r.current_all_members)}、中位{num(r.member_median_pct)}；原记录{r.old_manual_overlap}，不是完全新增。')
lines += ['\n明确不升级或需保留风险的例子：','零售2024至2026虽然行业主周期约117%，但12个样本中位约50%、前三正收益贡献约78%，且只覆盖现时12/71，仍保留待讨论，不因时间延长就自动升级。保险2021段源指数上涨约23%而现时5成员全跌，仍待历史成分/权重与源口径解释。轨交与美容护理某些指数大涨段因样本仅2至4只也不宣称已证实板块广度。','白酒2019至2021、证券2018至2020、医疗器械2018至2022等旧分段合并后只计一个主周期；中途深回撤和较长停顿仍列出。长周期不是全程持有建议，也不能用整段低到高涨幅替代实际策略收益。','924仍是史诗级全面反转：原9月23日至10月8日窗口90行业全部上涨，行业中位35.48%，半导体104/104可算成员上涨。起始小仓试错并不意味着确认后整轮只能始终小仓；但本报告不假设涨停、跳空或无开盘记录时可以成交。\n',
'三 口径与限制\n','1. 分母依次为上涨n/端点可算K/研究池P/现时行业F。P来自2026现时1709只约100亿元以上市值存续股票，F为2026年10月行业映射，均非历史时点成员PIT。退市、后上市、行业迁移和事后市值选择偏差没有消除。广度只支持已覆盖固定池，不能直接外推全部历史行业。',
'2. 所有成员使用同一主周期的精确起止日，不替每股挑低高点。端点缺价保留UNKNOWN，不填价、不当作下跌、不凭缺行判断停牌。端点齐全与中途全路径齐全分别披露。',
'3. 行业为既有同花顺行业收盘，个股为既有theoretical_ex_price调整链的close，不是raw_close，也不是官方PIT公司行动、含息总回报或费后账户利润的认证。行业指数不直接等于可交易组合。',
'4. 涨幅=终点收盘/起点收盘−1；最大中途回撤用区间内此前最高收盘到随后最低收盘。主周期峰后最低统一观察到下一人工周期起点（含），无下一周期则到2026年10月22日。观察截止和峰值都不是永久结束认证。个别背景起点不是区间绝对最低，正文显式注明。',
'5. 前三正收益集中度为前三股max(涨幅,0)之和/全部成员max(涨幅,0)之和，按期初等额，不是历史指数权重贡献。小K时该比率天然较高，要同时看中位、分位和分母。',
'6. 重点是尚待与你对齐的后视机会等级，不是统一阈值或实时选股门。普通波段不等于禁止参与，证据不足不等于没有机会。即使同业周期不重叠，跨行业同日行情和同一股票跨期仍相关，不能将记录数当独立统计样本。','7. 本轮没有分钟研究、实盘交易、账户重跑或信号参数调整。原账胜率、加仓和资金约束问题未由本报告替代。\n',
f'四 全部{len(allm)}个人工主周期速查\n']
for grade_ in ['重点候选','普通或可错过','证据不足或等级待讨论']:
 lines.append('\n'+grade_+' '+str(counts[grade_])+'条')
 for r in allm[allm.unified_grade==grade_].sort_values(['sector','start']).itertuples():lines.append(f'{r.record_id} {r.name} {r.start}→{r.end}：行业{num(r.industry_return_pct)}，回撤{num(r.mdd_pct)}；成员{ni(r.positive_members)}/{ni(r.known_members)}/{ni(r.research_pool_members)}/{ni(r.current_all_members)}，中位{num(r.member_median_pct)}。')
lines+=['\n五 90行业逐项主周期与全部辅助段归属\n'];dl=ledger.set_index('auxiliary_id');mi=allm.set_index('record_id')
for r in coverage.sort_values('sector').itertuples():
 mm=allm[allm.sector==r.sector].sort_values('start');aa=a[a.sector==r.sector].sort_values('start');lines += [f'\n【{r.name} {r.sector}】',f'行业日线{r.period_valid}/{r.period_expected}有效；固定研究池{r.research_pool_members}/现时行业{r.current_all_members}；主周期{len(mm)}，辅助候选{len(aa)}，本次全部有人工归属。']
 for v in mm.itertuples():
  lines += [f'  人工主周期 [{v.record_id}] {v.start}→{v.end}｜{v.unified_grade}',f'    行业{num(v.industry_return_pct)}；途中最大回撤{num(v.mdd_pct)}（{v.mdd_peak}→{v.mdd_trough}）；{ni(v.sessions_after_start)}个后续交易收盘。','    '+br(v)+'。',f'    成员25/50/75分位 {num(v.member_p25_pct)}/{num(v.member_median_pct)}/{num(v.member_p75_pct)}；≥30% {ni(v.above30_members)}/{ni(v.known_members)}，≥50% {ni(v.above50_members)}/{ni(v.known_members)}；前三正收益占{num(v.top3_positive_share_pct)}，剔前三均值{num(v.mean_without_top3_pct)}。',f'    {v.post_scope}，最低{v.post_low_day}较峰{num(v.post_drop_pct)}；不据此认证永久结束。',f'    判断：{v.note}']
  if not v.start_is_interval_minimum:lines.append('    注意：本起点为人工背景起点，不是区间绝对最低收盘，不能把本行称作绝对谷峰收益。')
  if v.sector in priorsecs and v.unified_grade!='重点候选' and pd.notna(v.old_priority_overlap) and v.old_priority_overlap:lines.append('    注意：内部旧阶段'+v.old_priority_overlap+'仍保留原阶段指标与原重点判断；当前长周期证据不足不等于否定该短阶段的机会。')
  if v.sector in priorsecs:lines.append(f'    与旧表关系：{v.novelty}；旧记录{v.old_manual_overlap if pd.notna(v.old_manual_overlap) and v.old_manual_overlap else "无正时间交集"}。')
 lines.append('  全部辅助段去向（内部子段不另计主周期）：')
 for v in aa.itertuples():
  z=dl.loc[v.record_id];dst=mi.loc[z.manual_cycle_id];conf='峰后20%回撤尚未确认' if pd.isna(v.down_confirm) else '下行确认'+v.down_confirm
  lines += [f'    {v.record_id} {v.start}→{v.end}，行业{num(v.industry_return_pct)}，段内回撤{num(v.mdd_pct)}；上行确认{v.up_confirm}，{conf}。',f'      → {z.manual_cycle_id} {dst.unified_grade}；{z.review_decision}。成员{ni(v.positive_members)}/{ni(v.known_members)}/{ni(v.research_pool_members)}/{ni(v.current_all_members)}，中位{num(v.member_median_pct)}。']
# Preserve original quantitative stages in full user-facing reconciliation, not silent deletion.
lines += ['\n六 原102条阶段记录逐项保留与对账\n','下面是旧阶段原数值，不按新版主周期起止回写，故同业数字可能与上文不同。这102条是追溯层，不加到新版主周期总数中。原局部重点若成为长周期内部阶段，仍保留其价量证据，并未丢失研究成果。']
for r in recon.sort_values(['sector','start','end']).itertuples():lines += [f'{r.record_id} {r.name} {r.start}→{r.end}｜原等级{r.priority}；原行业{num(r.industry_return_pct)}、原回撤{num(r.mdd_pct)}；原成员{ni(r.positive_members)}/{ni(r.known_members)}/{ni(r.research_pool_members)}/{ni(r.current_all_members)}，原中位{num(r.member_median_pct)}。',f'  现归入{r.canonical_ids}；{r.relation}。']
# Retain detailed 50 late-cycle stage windows and gold asset separation.
v0=(P/'manual_followup_integration_v1/DELIVERED_VERSION_0.txt').read_text();detail=v0.split('五 五条跨2024至2026主段的完整推进与回撤顺序')[1].split('七 仍未完成的部分与可得出的结论')[0]
detail=detail.replace('六 黄金现货单列 不计入90个A股行业','八 黄金现货单列 不计入90个A股行业')
lines += ['\n七 五条2024至2026原主段的内部推进与回撤顺序'+detail,'\n九 仍有边界\n','全部90行业和669候选已在当前资料口径内人工复盘，但周期划分不唯一，也不是全市场全部小行情的穷尽性认证。日线、现时成员、调整链与历史成交可得性仍有前述限制。','重点候选讨论的是应争取的群体机会，不是必须买中的个股清单。对CPO、低空、华为链、短剧等主题，现有行业大类不等于历史主题成员；不能用两三个暴涨个股填补主题广度证据。','此前61行业的319周期、4516成员记录，以及本次原29行业的201周期、5767成员记录，均已由另一实现直接读取对应原日线核对；全90行业520条统一峰后字段、669唯一归属和102原记录保留也通过核对。合计涉及1709只股票，但成员记录不是独立股票数。核对不认证人工等级、历史全行业代表性、未来收益或因果关系。公开行业入口 https://q.10jqka.com.cn/thshy/ ；924政策背景 https://finance.people.com.cn/n1/2024/0925/c1004-40328065.html 。']
text='\n'.join(lines)+'\n';assert text.count('【')==90 and text.count('  人工主周期 [')==len(allm) and text.count('      → ')==669
assert '/Users/' not in text
(O/'2019至2026年A股行业独立行情全景复盘.txt').write_text(text)
q=dict(industry_count=90,canonical_count=len(allm),grade_counts=counts,prior29_canonical_count=len(pp),prior29_grade_counts=pc,prior29_priority_novelty=nov,all_auxiliary_count=669,each_auxiliary_once=True,original_records_preserved=102,within_industry_nonoverlap=True,all_period_end_is_highest=True,background_not_absolute_low_records=allm.loc[~allm.start_is_interval_minimum.astype(bool),'record_id'].tolist(),no_account_run=True)
assert all(sha(p)==h for p,h in S.items());(O/'SOURCE_HASHES.json').write_text(json.dumps(S,ensure_ascii=False,indent=2)+'\n');(O/'QA.json').write_text(json.dumps(q,ensure_ascii=False,indent=2)+'\n');print(json.dumps(q,ensure_ascii=False));print('bytes',len(text.encode()))
