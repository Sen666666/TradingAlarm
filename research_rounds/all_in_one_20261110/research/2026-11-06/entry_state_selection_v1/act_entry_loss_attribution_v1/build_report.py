from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,datetime
O=Path(__file__).resolve().parent;F=json.loads((O/'FREEZE.json').read_text())
r=pd.read_csv(O/'ALL_ROUND_ATTRIBUTION.csv');t=pd.read_csv(O/'COHORT_TOTALS.csv');s=pd.read_csv(O/'PRICE_SPACE_PARTITION.csv');p=pd.read_csv(O/'PROGRESS20_PARTITION.csv');a=pd.read_csv(O/'PROGRESS20_BY_ADD.csv');sg=pd.read_csv(O/'INITIAL_TO_ROUND_SIGN.csv');gd=pd.read_csv(O/'TERMINAL_PRICE_GIVEBACK.csv');dist=pd.read_csv(O/'PREENTRY_DISTRIBUTIONS.csv');ov=pd.read_csv(O/'PREENTRY_OVERLAP.csv');co=pd.read_csv(O/'PREENTRY_GROUP_OUTCOMES.csv')
for f in [r,t,s,p,a,sg,gd,dist,ov,co]:f['entry_year']=f.entry_year.astype(str)
def n(x):return f'{x:,.0f}'
def m(x):return f'{x:,.2f}'
def pct(x):return f'{x*100:.2f}%'
def table(headers,rows):
 return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,row))+' |' for row in rows])
slow=[];details=[];give=[]
for arm in ['PVR','NOACT']:
 for year in ['ALL','2022','2024']:
  z=r[r.account.eq(arm)&(True if year=='ALL' else r.entry_year.eq(year))]
  stall=z[z.round_progress20.eq('STALLED20')]
  for threshold in [0.,.3,.5]:
   q=stall[stall.round_status.eq('CLOSED')&(stall.round_return.gt(0) if threshold==0 else stall.round_return.ge(threshold))]
   slow.append(dict(account=arm,entry_year=year,threshold=threshold,stalled_total=len(stall),closed_winners_n=len(q),round_net=q.round_pnl.sum(),initial_net=q.initial_pnl.sum(),capital_days=q.round_capital_days.sum(),first5_confirmed_after20=int((q.round_first5_session.gt(20)&q.round_first5_time_known.eq(True)).sum()),first5_never_observed=int(q.round_first5_session.isna().sum()),first5_min=q.round_first5_session.min(),first5_max=q.round_first5_session.max()))
  details.append(dict(account=arm,entry_year=year,n=len(stall),closed=int(stall.round_status.eq('CLOSED').sum()),open=int(stall.round_status.eq('OPEN').sum()),initial_capital_days=stall.initial_capital_days.sum(),round_capital_days=stall.round_capital_days.sum(),initial_from20=stall.round_stalled20_initial_capital_days_from20.sum(),round_from20=stall.round_capital_days_from20.sum(),no_ADD_by20=int(stall.round_stalled20_no_add_by20.eq(True).sum()),no_ADD_ever=int(stall.has_followup_add.eq(False).sum()),initial_pool_probe=int(stall.initial_pool.eq('probe').sum()),initial_pool_confirmed=int(stall.initial_pool.eq('confirmed').sum())))
  zz=z.merge(gd,on=['account','round_id','sid','entry_year'],validate='one_to_one')
  for pref in ['initial','round']:
   q=zz[zz[pref+'_space_then_loss'].eq(True)]
   give.append(dict(account=arm,entry_year=year,level=pref,n=len(q),pnl=q[pref+'_pnl'].sum(),terminal_below_peak=int(q[pref+'_terminal_below_observed_peak'].eq(True).sum()),median_observed_peak=q[pref+'_observed_close_max'].median(),median_terminal=q[pref+'_terminal_price_return'].median(),median_peak_to_terminal_drawdown=q[pref+'_observed_peak_to_terminal_drawdown'].median(),full_price_unknown=int(q[pref+'_path_status'].eq('UNKNOWN').sum())))
slow=pd.DataFrame(slow);detail=pd.DataFrame(details);give=pd.DataFrame(give)
slow.to_csv(O/'STALLED20_LATE_WINNERS.csv',index=False);r[r.round_progress20.eq('STALLED20')&r.round_status.eq('CLOSED')&r.round_return.ge(.3)].to_csv(O/'STALLED20_BIG_WINNER_MEMBERS.csv',index=False);detail.to_csv(O/'STALLED20_CAPITAL_DETAIL.csv',index=False);give.to_csv(O/'PRICE_ADVANCE_THEN_LOSS.csv',index=False)
L=['# ACT 首仓亏损与未推进占资归因','',
'## 主结论','',
'1. **初层毛亏主要来自买入后没有足够收盘价格推进。** PVR初层毛亏149.89万元中，45.35%来自从未有正收盘价格回报，33.17%来自最高正回报不足5%；NOACT初层毛亏177.34万元中，对应46.07%与32.07%。两类合计78.52%与78.14%。这是实际持有窗口描述，不是股票此后永远没有行情。',
'2. **长时间不推进确实占资，但不是总亏损的最大来源。** 固定“持有至少20个共同收盘、前20日没有+5%收盘价格推进”组，PVR354轮、NOACT441轮，分别占整轮资本日19.14%与19.14%，只承载闭合整轮毛亏9.40%与9.65%。相反，不到20收盘就退出且未推进者，中位持有6日，承载整轮毛亏55.36%与54.10%。',
'3. **达到5%后仍亏，以及后续层改变最终符号，是另一条损失路径。** 首层曾达到5%却最终亏的PVR564层、NOACT682层，占初层毛亏21.35%与21.77%；整轮对应686轮与808轮，占整轮毛亏36.32%与37.56%。初层为正、整轮转负126/131轮，反向只有3/4轮。但后续层全部合计仍净增收益，不能据此推导取消ADD。',
'4. **20日不是退出建议，入场前常见特征也没有形成可靠分界。** 未推进组后来仍有PVR5轮、NOACT3轮实现≥30%的完整净回报，其中1/2轮≥50%。固定20日退出的价格、后续订单、预算腾挪和错失赢家代价没有模拟。停滞亏损与大赢家的入场前涨幅、量比、保护距离存在分布差异，也有大量重叠，不把事后标签或分位数改成准入门。',
'','## 范围与分母','',
'只读取原ACT-only连续账户完整成交、公司行动、日末持仓与已完成分析，无账户重跑。账户初始120万元，2022年初空仓连续到2026-05-15；PVR2626闭合+67未闭，NOACT3064闭合+67未闭。以下2022/2024均按**实际首买年份**分组，整笔回合净额可能包含以后年度，不是该年NAV收益，也不是结构birth年。',
'初层是每个严格0→0回合的首个实际BUY，可能kind=add；“后续ADD”只计算此后实际add层。初层回报分母仅其首次BUY含费成本，整轮分母全部BUY含费、含ADD。初层和整轮终止状态分别核验，本样本恰好两臂都没有“初层已闭而整轮仍未闭”的组合，没有把这种状态按规则删去。',
'价格只看实际持有期间收盘：买入OPEN当日CLOSE开始，卖出OPEN前最后CLOSE结束；未闭到期末。使用原冻结raw close乘首买后的原账拆股比例，除以首层含滑点成交价。它不含现金股息/费用，**+5%是收盘价格推进，不是可净清算盈利空间**。入场日收盘还受T+1约束；收盘峰值不是可实现退出。',
'资本日=各共同交易日日末剩余含买入费成本之和，单位元×交易日；初层与整轮分别算。清仓OPEN当日日末0不计入，未闭包括末日。下表以百万资本日展示。资本日不是额外注资、资金机会成本或可以保证释放的现金。','',
'## 全样本总表','']
sel=t[t.entry_year.isin(['ALL','2022','2024'])]
L.append(table(['账户','首买年','层级','总数/闭合/未闭','闭合胜/负','闭合净额元','未闭mark净额元','资本日百万','持有收盘中位/p90'],[[x.account,x.entry_year,x.level,f'{x.n}/{x.closed}/{x.open}',f'{x.closed_wins}/{x.closed_losses}',m(x.closed_net),m(x.open_mark_net),m(x.capital_days/1e6),f'{x.median_held_closes:g}/{x.p90_held_closes:g}'] for x in sel.itertuples()]))
L+=['','全部买入年份2022至2026均保留在COHORT_TOTALS.csv。未闭mark不当最终胜负。所有层及整轮的初层与后续层净额可对账到原NAV增量。','',
'## 价格推进与亏损所在','',
'“无正收盘”要求完整新鲜价格路径且最高回报≤0；“不足5%”要求完整路径且0<最高回报<5%；“观察到≥5%”只需任一有效收盘证据，即使其他日期缺价也足以证明曾推进；“无法判断”是未观察到5%且路径不完整。各桶包括赢家、输家、未闭，下面不是只挑亏损样本。']
names={'CLOSE_NO_UPSIDE':'无正收盘','CLOSE_UP_LT5':'正但不足5%','OBSERVED_GE5':'观察到≥5%','UNKNOWN':'无法判断'}
for year in ['ALL','2022','2024']:
 L+=['',f'### 首买年 {year}','']
 z=s[s.entry_year.eq(year)]
 L.append(table(['账户','层级','价格桶','总数/未闭','闭合负数','闭合毛亏元','占本层总毛亏','闭合净额元','资本日占比'],[[x.account,x.level,names[x.category],f'{x.n}/{x.open}',x.closed_losses,m(x.closed_gross_loss),pct(x.fraction_of_all_closed_gross_loss),m(x.closed_net),pct(x.fraction_of_all_capital_days)] for x in z.itertuples()]))
L+=['','首层曾≥5%但最终亏的PVR564层、NOACT682层，最后实际卖出价格均低于曾观察峰值。其峰值价格回报中位数8.77%/9.10%，最后实际卖出价格回报中位数−4.52%/−5.01%，从观察峰值到最后成交的价格跌幅中位数13.47%/14.07%。这是价格回吐，终点净额仍按全部实际分批卖出、费用和已记账股息计算。完整及不完整路径分别保留，详情PRICE_ADVANCE_THEN_LOSS.csv。','',
'## 固定20日未推进群','',
'前20个持有收盘任一天达到+5%即归“20日内推进”；至少20收盘且前20完整未达到才归“20日未推进”；提前结束和未闭不足20分别列；有缺价且不能确证的单列UNKNOWN。没有按收益调整20日或5%阈值。']
names2={'EXIT_BEFORE20':'未推进且20日前退出','OPEN_CENSORED_BEFORE20':'未闭且不足20日','PROMOTED_BY_20':'20日内推进','STALLED20':'20日未推进','UNKNOWN':'UNKNOWN'}
for year in ['ALL','2022','2024']:
 z=p[p.entry_year.eq(year)&p.level.eq('round')]
 L+=['',f'### 整轮首买年 {year}','',table(['账户','类别','总数/未闭','闭合胜/负','闭合毛亏元','毛亏占比','闭合净额元','未闭mark元','资本日占比'],[[x.account,names2[x.category],f'{x.n}/{x.open}',f'{x.closed_wins}/{x.closed_losses}',m(x.closed_gross_loss),pct(x.fraction_of_all_closed_gross_loss),m(x.closed_net),m(x.open_mark_net),pct(x.fraction_of_all_capital_days)] for x in z.itertuples()])]
L+=['','### 未推进组的资本日与后续ADD','',table(['账户','首买年','轮数','首层资本日百万','整轮资本日百万','第20收盘起首层/整轮百万','前20无ADD数','全程无ADD数','首层原probe/confirmed'],[[x.account,x.entry_year,x.n,m(x.initial_capital_days/1e6),m(x.round_capital_days/1e6),f'{m(x.initial_from20/1e6)}/{m(x.round_from20/1e6)}',x.no_ADD_by20,x.no_ADD_ever,f'{x.initial_pool_probe}/{x.initial_pool_confirmed}'] for x in detail.itertuples()]),
'','这里的“未推进组”不是原生probe池的同义词，表中特别列原首次pool。第20收盘起资本日包含第20天，仍是已经发生的日末成本积分。PVR全程无后续ADD303轮，闭合净额−97,058.06元；有ADD51轮，−13,618.16元。NOACT分别374轮−125,483.90元与67轮−22,754.19元。两组都有赢家；不能把未来ADD标签当入场过滤项。',
'','### 慢赢家不能删去','',
table(['账户','首买年','未推进总数','后来净盈利数/净额','后来≥30%数/净额','后来≥50%数/净额','≥30%首次5%确证晚于20日'],[[arm,year,int(slow[(slow.account==arm)&(slow.entry_year==year)].iloc[0].stalled_total)]+[f'{int(slow[(slow.account==arm)&(slow.entry_year==year)&(slow.threshold==th)].iloc[0].closed_winners_n)}/{m(slow[(slow.account==arm)&(slow.entry_year==year)&(slow.threshold==th)].iloc[0].round_net)}' for th in [0.,.3,.5]]+[int(slow[(slow.account==arm)&(slow.entry_year==year)&(slow.threshold==.3)].iloc[0].first5_confirmed_after20)] for arm in ['PVR','NOACT'] for year in ['ALL','2022','2024']]),
'','门槛回报分母仍为完整回合全部BUY含费，非将未来某次涨幅叫赢家。全期PVR5个≥30%慢赢家净额5,899.95元，NOACT3个9,279.04元，8轮首次5%均确证在第20日之后。完整成员见STALLED20_BIG_WINNER_MEMBERS.csv。这只说明不能默认20日全退出没有代价，不能把已有净额机械当成新退出规则的机会成本。',
'','## 初层到完整回合的符号转换','',
'下表只取双方均已闭合，未闭的双状态矩阵完整保存在INITIAL_TO_ROUND_SIGN.csv。首层闭合时点与完整回合时点仍各自保留。']
for year in ['ALL','2022','2024']:
 z=sg[sg.entry_year.eq(year)&sg.round_status.eq('CLOSED')]
 L+=['',f'### 首买年 {year}','',table(['账户','初层→整轮','数','初层净额元','后续层净额元','整轮净额元'],[[x.account,x.initial_sign+'→'+x.round_sign,x.n,m(x.initial_net),m(x.later_layer_net),m(x.round_net)] for x in z.itertuples()])]
L+=['','PVR闭合初层合计−269,594.96元，加入后续层后整轮−152,342.25元，后续层合计+117,252.71元。NOACT初层−77,061.91元，整轮+7,147.63元，后续层合计+84,209.53元。正转负的数量和损失不能抹掉其余赢家的后续层收益。未闭原样保留：PVR首层17负50正、整轮18负49正；NOACT首层18负49正、整轮21负46正，只称期末mark状态。','',
'## 入场前可见旧信息与后来大赢家','',
'这是主结果完成后按追加要求单独冻结的补充，见SUPPLEMENT_FREEZE.json，不称预注册。观察点严格为原首买trade.signal_at收盘t，所有signal_at均早于实际买入OPEN。1/5/21共同日log涨幅、成交额/前21日中位数、log(同坐标调整收盘/原始信号保护线)是已有描述量；保护线来自不可变首次BUY trade.floor，不用可能被抬升的期末LAYER.floor。每个窗口要求全新鲜有效且source_kind/source_path/segment一致，否则该特征UNKNOWN。',
'比较组是“20日未推进且最终整轮亏损”与“最终完整回合净回报≥30%”。这两个组用未来结果定义，只能做描述。全部其他闭合与67个未闭也留在PREENTRY_FEATURES_ALL.csv，未参与这两组分布不是被删掉。',
'',table(['账户','首买年','分组','数','首层负/正','首层回报中位','首次5%中位日','原初层STALLED20数','有ADD数','持有中位日'],[[x.account,x.entry_year,x.group,x.n,f'{x.initial_losses}/{x.initial_positive}',pct(x.initial_median_return),m(x.first5_median),x.initial_STALLED20,x.with_ADD,m(x.median_hold)] for x in co.itertuples()]),
'','首次5%时间中位仅在观察到5%的组内计算；未达到不填0。所有≥30%完整赢家的初层最终均为正，但它们并非全都很快推进，慢赢家已另列。',
'','### 全期分布中位数和四分位','',
'log变量下表以100×log显示，不是简单百分比收益；量比保持倍数。括号为p25至p75，覆盖为有值/总数。']
fn={'log_return_1':'1日log涨幅','log_return_5':'5日log涨幅','log_return_21':'21日log涨幅','amount_ratio_prev21':'成交额量比','log_distance_signal_floor':'到信号floor的log距离'}
rows=[]
for arm in ['PVR','NOACT']:
 for feature in fn:
  z=dist[dist.account.eq(arm)&dist.entry_year.eq('ALL')&dist.feature.eq(feature)];cells=[arm,fn[feature]]
  for group in ['STALLED20_FINAL_LOSS','BIG_WINNER30']:
   x=z[z.group.eq(group)].iloc[0];scale=1 if feature=='amount_ratio_prev21' else 100;cells+=[f'{m(x.p50*scale)} [{m(x.p25*scale)}, {m(x.p75*scale)}]',f'{int(x.known)}/{int(x.n)}']
  q=ov[ov.account.eq(arm)&ov.entry_year.eq('ALL')&ov.feature.eq(feature)].iloc[0];cells+=[pct(q.stalled_loss_within_winner_p10_p90),pct(q.winner_within_stalled_loss_p10_p90)];rows.append(cells)
L.append(table(['账户','特征','停滞亏中位[IQR]','覆盖','大赢家中位[IQR]','覆盖','停滞亏落赢家10–90%内','赢家落停滞亏10–90%内'],rows))
L+=['','全期赢家入场前涨幅中位数较高，但两组仍大范围重叠。NOACT停滞亏样本约63.8%至82.4%落在赢家各特征10–90分位区间，PVR约68.8%至88.4%。2022/2024同口径完整分位数与重叠在PREENTRY_DISTRIBUTIONS.csv及PREENTRY_OVERLAP.csv；PVR2022大赢家仅7轮，年度差异不能读成稳定规律。没有扫阈值、训练、排名或测试新准入。',
'','## 覆盖和可核验性','',
'- 两臂各33轮持有窗口至少一日没有有效新鲜收盘，因此完整MFE/MAE为UNKNOWN；其中PVR29/NOACT30轮仍有某个有效收盘达到5%，可归“观察到5%”，不是抹去缺价。只剩PVR4/NOACT3轮价格空间桶无法判断。20日进展UNKNOWN为PVR5/NOACT4轮。缺失值没有作为0。',
'- 原账估值允许沿用最近有效原价，仅用来核对原日末库存。两臂最大库存重建误差均2.33e−10元；全部日末layer股数逐日相同，部分卖出成本与期末剩余成本误差0。资本日与原平均剩余成本×1054完全守恒。',
'- 原源1534文件哈希在计算前后不变，48项原run封存和22项原analysis封存通过。无新账户执行、无年度重置、无期末强平、无新模型或交易门。分析阈值冻结后未调整。',
'- 原已记账股息纳入初层及整轮净额；外部真实兑付、历史条款PIT、真实历史可成交性仍对全样本UNKNOWN，不能当0或可兑现现金。固定未来1709池/行业映射/开盘代理假设继承，不能声称OOS或实盘优势。',
'','## 机制病例','',
'病例按冻结的最早日期选择，不挑盈利最大或损失最大。每臂2022/2024各取首层无上行亏、首层达5%仍亏、20日停滞整轮亏的最早记录，加最早未闭例；病例只解释机制，不用于估计比例。MECHANISM_CASES.csv及MECHANISM_CASE_PATHS.csv保留完整字段与日路径。',
'','## 文件索引','',
'- REPORT.md：本报告。DEFINITIONS.md、FREEZE.json：主定义和冻结来源。',
'- ALL_ROUND_ATTRIBUTION.csv：全部5824个回合，初层/整轮各自状态、净额、分母、MFE/MAE、首次5%、ADD、资本日及UNKNOWN。',
'- DAILY_HELD_PATH.csv：127146个实际持有日的原股份、剩余成本和价格观察。CALENDAR_YEAR_CAPITAL_DAYS.csv按实际占资日期归年，不同于首买年回合归因。',
'- COHORT_TOTALS.csv、PRICE_SPACE_PARTITION.csv、PROGRESS20_PARTITION.csv、PROGRESS20_BY_ADD.csv、HOLDING_DURATION_PARTITION.csv：完整固定分组，含所有年度及未闭。',
'- INITIAL_TO_ROUND_SIGN.csv：初层到完整回合双状态符号矩阵。',
'- STALLED20_CAPITAL_DETAIL.csv、STALLED20_LATE_WINNERS.csv、STALLED20_BIG_WINNER_MEMBERS.csv：停滞占资与慢赢家。',
'- PREENTRY_FEATURES_ALL.csv、PREENTRY_DISTRIBUTIONS.csv、PREENTRY_OVERLAP.csv、PREENTRY_GROUP_OUTCOMES.csv：新增入场前描述量，全年份全样本及固定组分布。',
'- TERMINAL_PRICE_GIVEBACK.csv、PRICE_ADVANCE_THEN_LOSS.csv：峰值到最后实际成交/未闭末收盘的价格变化，非模拟净清算收益。',
'- CHECKS.json、SUPPLEMENT_CHECKS.json、FINAL_MANIFEST.json：对账、源不变与输出哈希。',
'','**可以定位已发生的亏损与资金占用，却尚未得到入场前可可靠拒绝的名单。不能从这份归因直接推出20日止损、禁止ADD或加强某个旧指标。**','']
(O/'REPORT.md').write_text('\n'.join(L))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
for path,h in F['source_hashes'].items():assert sha(path)==h,('source changed',path)
manifest=dict(status='PASS_COMPLETED_RESEARCH',account_runs=0,source_files_unchanged=len(F['source_hashes']),created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),files={x.name:sha(x) for x in O.iterdir() if x.is_file() and x.name!='FINAL_MANIFEST.json'})
(O/'FINAL_MANIFEST.json').write_text(json.dumps(manifest,indent=2))
print('REPORT_READY',len(L),len(manifest['files']));print(slow.to_string(index=False));print(detail.to_string(index=False))
