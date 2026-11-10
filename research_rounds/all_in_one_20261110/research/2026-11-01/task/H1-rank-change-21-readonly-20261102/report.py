from analyze import O,read,save,sha,np,mean
def pct(v):return f'{v:.2f}' if v is not None else 'UNKNOWN'
def main():
 ready=read(O/'READINESS_FIRST.json');paired=read(O/'MATCHED_DATE_PROXY_SUMMARY.json');stats=read(O/'PROXY_GROUP_STATS.json');rows=read(O/'ALL_INDUSTRY_DAYS.json');ann={(r['case'],r['day'],r['sector']):r for r in read(O/'GLOBAL_AND_ORIGINAL_QUEUE_RANK_ANNOTATIONS.json')};conc=read(O/'PROXY_CONCENTRATION.json');actual=read(O/'ORIGINAL_C10_CONTRIBUTION_CONCENTRATION.json');mech=read(O/'RANK_CHANGE_ABSOLUTE_PRICE_AND_TIES.json');loo=read(O/'MATCHED_DATE_LEAVE_ONE_OUT.json')
 lines=[
 'H1位次与固定前21观察位次改善：两原研究月只读检验',
 '裁决：没有跨两月、跨市场fresh/Q与原C申请阶段的一致正向优势；固定21改善还不能把机械早期机会排得更早。按原停止条件收口，不换窗、不混分、不接账户。',
 '',
 '输入与因果：原行业自身价格H1缓存，90行业独立参考域，原0.4/0.2/0.2/0.2分段价格动量、共同观察年龄上限252后的横向位置。未聚合个股H1，未重算信号。两月及此前21观察H1/价格无缺失、nref全90、source segment无变化；首日历史锚2021-12-03/2025-05-30。',
 'A=原H1分数高者优先；B=rank(t−21)−rank(t)大者优先，21为原H1共同有效观察格。得分只读，B同值固定行业ID，不叠加H1二次打分。全90排名、有机会行业内排名和原C比较队列排名分别列出，不能混称同一位次。',
 '全部行业每天一行，共3780行；未获资/无机会/占资但无fresh均保留。M1=原canonical fresh CP1+原retained stock_Q+preliminary有效；M2=M1中实际进入原C10规划trace的需求（含Q=0），它是实际F1/ACT/责任等准入阶段，尚未等于获资。I-only/core/T机会不冒充此C扩张母体；真实旧仓没有fresh也仍列占资。',
 '窗口 | 决策日×90 | M1股票事件/行业日 | M2股票事件/行业日 | 原C正Q行业日 | 实际占资行业日',
 ]
 for z in ready['opportunity']:lines.append(f"{z['case']} | {z['decisions']}×90 | {z['fresh_Q_stock_events']}/{z['fresh_Q_industry_days']} | {z['C_requested_stock_events']}/{z['C_requested_industry_days']} | {z['C_positive_industry_days']} | {z['occupied_industry_days']}")
 lines += [
 '原C计划股票事件：January正Q67/零Q321；July正Q88/零Q3218。零Q全部留在M2，正Q也不冒充下一开盘已成交。',
 '',
 '评价真实缺口：现成行业21/63标签的固定窗口为2022Jun–Dec、2023恢复、旧924、2026局部，不含这两个月；本包3780行业行的未来21/63行业价格标签全UNKNOWN。没有临时从行业缓存挑终点补算。',
 '可复用的只是既有canonical股票21/63价格标签，来自原legacy-Q参考候选，按sid+原授权日+canonical receipt精确join；不是完整新F1域或行业指数未来收益。每个行业日先对其已有标签机会股等权形成代理，再行业日等权；主对照只在A/B偏好组都可评价的相同日期上日等权。候选数不重复行业权重；缺标签不补0、不删分母。',
 '窗口/母体 | 全股票事件→已有标签 | 全行业日→有标签行业日',
 ]
 for z in stats:
  if z['group']=='all' and z['horizon']=='21':lines.append(f"{z['case']}/{z['family']} | {z['stock_events']}→{z['labelled_stock_events']} | {z['industry_days']}→{z['covered_industry_days']}")
 lines += [
 '',
 '分歧集：同一天同母体按A/B分别完整排位，B位次较前为B偏好，A较前为A偏好，相同者另列；无TopK或权重政策。下表为机会股既有价格标签代理均值，非资金/行业指数/成交收益。',
 '窗口/母体/观察 | 双组共同日 | A偏好均值% | B偏好均值% | B−A百分点',
 ]
 for z in paired:lines.append(f"{z['case']}/{z['family']}/{z['horizon']} | {z['common_days']} | {pct(z['A_return'])} | {pct(z['B_return'])} | {pct(z['return_difference'])}")
 lines += [
 'January仅在更宽M1母体B平均更好，进入原C阶段后失去优势；July在两母体两horizon均更弱。不可挑M1 January替代完整结果。M2的21观察日差B较好仅5/12和9/23日；重叠价格窗口/重复股票不是独立试验或策略胜率。',
 '尾部/损耗（M2、同组共同日期，行业日机会股标签先均值）：',
 '窗口/观察 | A/B原MFE>=30%机会占比 | A/B平均MAE%',
 ]
 for z in paired:
  if z['family']=='M2':lines.append(f"{z['case']}/{z['horizon']} | {pct(z['A_tail_share']*100)}/{pct(z['B_tail_share']*100)} | {pct(z['A_MAE'])}/{pct(z['B_MAE'])}")
 lines += [
 'January B在已申请机会中多一点尾部，但平均终值仍较弱且MAE更差；July B尾部也更少，63观察MAE略改善伴随终值下降。尾部未因净均值不佳被删除。',
 '',
 '固定机械早期/赢家对照（下表原C队列同时含合格旧mobile行业，与仅有fresh机会子集不同；B只作同一队列的描述排序，未求资金）：',
 '日期/行业 | 全90 A排名→B排名 | 位次改善 | 本行业过去21绝对价变% | 原C队列A→描述B',
 ]
 points=[('2025Jul','2025-07-01','URFI881268'),('2025Jul','2025-07-08','URFI881268'),('2025Jul','2025-07-21','URFI881268'),('2025Jul','2025-07-22','URFI881268'),('2022Jan','2022-01-12','URFI881140'),('2025Jul','2025-07-11','URFI881271'),('2025Jul','2025-07-01','URFI881129')]
 for c,d,s in points:
  z=next(r for r in rows if r['case']==c and r['day']==d and r['sector']==s);a=ann[c,d,s];lines.append(f"{d}/{z['industry']} | {z['H1_rank90']}→{a['B_rank90']} | {z['rank_improvement21']:+d} | {pct(z['industry_absolute_price_change21_pct'])} | {a['original_C_queue_A_rank']}→{a['description_only_B_on_same_C_queue_rank']}")
 lines += [
 '工程7/1自身价格已涨4.15%，但相对21观察前第11退到31；7/8仅改善4位，未更早置首；7/21/22已急涨后B仍比A靠后。这不支持固定21改善能解决原机械早期资源竞争。7/8三个合法新需求及7/21六个仍全部保留；原正Q为0不是没有市场机会。',
 '正例翰宇：Jan12化药改善24位，本行业自己涨13.12%，原有机会行业内A5→B3，原含旧仓C队列7→4。翰宇该canonical既有21终值+11.86%、MFE49%、MAE−19.14%，63终值+0.36%、MFE57.29%；原C10整月全股净贡献27,329.50。行业均值不能抹掉个股肥尾，也不能把这一个正例推广为排序必优。',
 '赢家负控千方：Jul11 IT自身涨7.09%、改善1位，全90 A2/B46，原C队列2→26。千方既有21/63终值+24.81%/+18.77%，原C10月内净贡献11,735.93；平稳强者位次改善小并不等于已无持续机会。',
 '赢家负控汇绿：Jul1通信设备自己涨14.64%、改善29位，全90 A3/B5，原C队列2→4。汇绿既有21/63终值+35.87%/+66.93%，MFE44.19%/91.48%，原C10月内净贡献9,325.18。股与行业指数不是同一价格序列，未来标签仅评价，未入排序。',
 '',
 '防“别人更跌即启动”：',
 ]
 for z in mech:lines.append(f"{z['case']}/{z['family']}：{z['positive_rank_improvement']}个改善行业日中，{z['rank_improved_but_own_price_nonpositive']}个自身21价变<=0；B偏好组自身不涨{z['B_promoted_own_price_nonpositive']}行；改善数并列{z['improvement_tied_industry_days']}/{z['industry_days']}行。")
 lines += [
 '这些行全保留，不新增绝对收益过滤。July M2约一半行业日改善数并列，B的ID破同值只是固定展示顺序，不能把细小位次差当新市场证据；秩相关另对改善原值作并列均秩。',
 '',
 '贡献集中与脆弱性：原C10 January行业净正贡献中化药占54.59%（21,463.91元），July通信设备占43.65%（18,373.98元）；这是原实际路径贡献，不是B的资金收益。',
 '现成标签代理的B偏好正贡献：January 21观察软件开发占49.77%、63观察医药商业占71.16%；July塑料制品占24.42%/16.16%。正贡献份额是sum(max(行业日代理均值,0))归行业后的描述，非收益率或可配置权重。',
 ]
 for case in ['2022Jan','2025Jul']:
  for h in ['21','63']:
   zz=[z for z in loo if z['case']==case and z['horizon']==h and z['return_difference'] is not None];v=[z['return_difference'] for z in zz];lines.append(f"M2同日比较逐一留掉行业：{case}/{h}，{len(v)}个删一视图，B−A范围{min(v):.2f}..{max(v):.2f}pp，其中正{sum(x>0 for x in v)}。")
 lines += [
 'January方向对个别行业敏感；July删掉任一行业后差仍负，不是只被一个失败案例拉低。此为描述稳定性，不是独立显著性检验。',
 '',
 '边界与收束：行业未来21/63价仍UNKNOWN，不能把旧Q股票代理包装成完整行业持续性验证；未获资机会原样保留，排名变化不等于能获资金，也未改旧仓保留/退出/预算。当前快照1709/90非PIT，历史已研究。按两月不一致停止，不调整21、叠分或追加账户。',
 '复核：PROTOCOL、H1_INPUT_GATE、READINESS_FIRST、RANKS_BEFORE_LABELS（先冻结再读股票标签；原账月末贡献仅后视注记）、ALL_INDUSTRY_DAYS（含占资与未知）、ALL_FRESH_Q_STOCK_EVENTS、MATCHED_DATE_PROXY_*、FIXED_WINNER_AND_FAILURE_CONTROLS、NAMED_STOCK_CONTROLS、ALL_INDUSTRY_LEAVE_ONE_OUT/MATCHED_DATE_LEAVE_ONE_OUT、GLOBAL_AND_ORIGINAL_QUEUE_RANK_ANNOTATIONS、READ_INPUTS。',
 'VERIFICATION以每月首/中/末共6处物理截断缓存数组重核540个行业的排名/改善/绝对价格变化，并用独立groupby核8个同日统计。验证本次读取/统计不依赖未来缓存行，没有重新运行或宣称重审原H1生成器。Jan日志只反序列化已审C10保存态并核完整字段前后不变，无账户初始化/恢复方法/时钟调用。',
 ]
 (O/'REPORT.txt').write_text('\n'.join(lines)+'\n')
 save('CONCLUSION.json',dict(verdict='STOP_NO_STABLE_BENEFIT_FIXED21',industry_future_labels='UNKNOWN_NOT_COMPUTED',existing_stock_labels_only=True,capital_effect_tested=False,signals_or_parameters_changed=False,account_events=0,proxy_summary=paired))
 save('DELIVERY_SHA256.json',{str(p.relative_to(O)):sha(p) for p in sorted(O.rglob('*')) if p.is_file() and p.name!='DELIVERY_SHA256.json' and '__pycache__' not in p.parts})
 print('REPORT',sha(O/'REPORT.txt'),'PACKAGE',sha(O/'DELIVERY_SHA256.json'))
if __name__=='__main__':main()
