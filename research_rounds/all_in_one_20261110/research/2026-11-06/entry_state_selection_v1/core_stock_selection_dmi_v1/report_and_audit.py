"""Post-result descriptive reporting and immutable-input/pick audit, no new arms."""
import json,hashlib
from pathlib import Path
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;R=O.parent
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
def md(df):
 out=['| '+' | '.join(str(k) for k in df.columns)+' |','|'+'---|'*len(df.columns)]
 for row in df.itertuples(index=False,name=None):out.append('| '+' | '.join('UNKNOWN' if pd.isna(v) else str(v) for v in row)+' |')
 return '\n'.join(out)
seal=read(O/'RANK_SEAL.json');assert all(sha(O/n)==h for n,h in seal['hashes'].items())
# Extend provenance back to the pre-existing frozen artifacts, not a new outcome fit.
legacy={}
for dr,mf,names in [(R/'selection_entry_diagnosis_v1','FINAL_OUTPUT_SHA256.json',['ALL_FIRST_ENTRIES.csv']),(R/'selection_entry_diagnosis_v1/mobile_candidate_response_v1','FINAL_OUTPUT_SHA256.json',['FIXED_NATIVE_PRICE_LABELS.parquet']),(R/'dmi_boundary_migration_v1','OUTPUT_SHA256.json',['FEATURES.parquet'])]:
 man=read(dr/mf)
 for n in names:assert sha(dr/n)==man[n],(dr,n);legacy[str(dr/n)]=man[n]
dmi_inputs=read(R/'dmi_boundary_migration_v1/INPUT_HASHES.json')
for p,h in dmi_inputs.items():
 if p.endswith('h1.npz'):assert sha(p)==h;legacy[p]=h
c=pd.read_parquet(O/'FEATURES.parquet');p=pd.read_parquet(O/'SEALED_PICKS.parquet');moves=pd.read_parquet(O/'RANK_MOVES.parquet');q=pd.read_csv(O/'QUEUE_AUDIT.csv');lab=pd.read_parquet(O/'FIXED_NATIVE_LABELS.parquet');rs=pd.read_csv(O/'ROOT_COVERAGE.csv');roots=pd.read_csv(O/'ROOTS.csv');ro=pd.read_csv(O/'ORIGINAL_ROUND_SUMMARY.csv');core=pd.read_csv(O/'ORIGINAL_CORE_ROUNDS.csv');res=pd.read_csv(O/'RESULTS.csv');diff=pd.read_csv(O/'PAIRED_BLOCKS.csv');coverage=pd.read_csv(O/'LABEL_COVERAGE.csv')
mem={k:set(g.row) for k,g in p.groupby('method')};movemap={(m,int(row)):int(rank) for m,row,rank in moves[['method','row','group_rank']].itertuples(index=False,name=None)}
unknowns=0;competition=[];changed=[]
for day,g in c.groupby('day'):
 base=g.sort_values(['original_priority_rank','sid']);top=base.head(min(20,len(g)));quotas=top.groupby(['sector','has_mobile']).size().to_dict()
 for key,z in base.groupby(['sector','has_mobile']):
  k=quotas.get(key,0);rows=list(z.row);known=list(z.loc[z.common_known,'row']);unknowns+=int((~z.common_known).sum())
  competition.append(dict(day=day,sector=key[0],has_mobile=key[1],N=len(z),K=k,known=len(known),competitive=bool(0<k<len(z) and len(known)>1)))
  for method in ['PVR','CLOSE','DMI']:
   ready=sorted(known,key=lambda ix:(-round(float(c.at[ix,method]),12),int(c.at[ix,'original_priority_rank']),str(c.at[ix,'sid']))) if method!='PVR' else known
   it=iter(ready);order=rows if method=='PVR' else [next(it) if bool(c.at[ix,'common_known']) else ix for ix in rows]
   assert all(movemap[(method,ix)]==j+1 for j,ix in enumerate(order));assert set(order[:k])==set(rows)&mem[method]
   for j,ix in enumerate(rows):
    if not bool(c.at[ix,'common_known']):assert order[j]==ix
assert unknowns==506
selected=p.merge(c,on=['row','day']).merge(lab,on=['row','day','sid'])
for n in [5,20,60]:
 good=selected.groupby('day')['complete'+str(n)].all();g=selected[selected.day.isin(good[good].index)];expected=coverage[(coverage.period=='ALL')&(coverage.H==n)].iloc[0];assert g.day.nunique()==expected.common_days and len(g)//3==expected.common_slots
assert all(set(core.loc[core.row.isin(mem[k]),'row'])==set(core.loc[core.row.isin(mem['PVR']),'row']) for k in mem)
# Root-clock audit only. The frozen early-capture origin remains the first legal
# CORE opportunity inside this account-conditioned window, not I birth.
sm={x['symbol']:x for x in read(U/'STOCK_MANIFEST.json')};clocks=[]
for sid,g in roots.groupby('sid'):
 f=pd.read_parquet(sm[sid]['refs']['facts']);on=f.i_target.eq(1);birth=on&~on.groupby(f.segment_id).shift().eq(1);bd=pd.Series(pd.NaT,index=f.index,dtype='datetime64[ns]');bd.loc[birth]=f.index[birth];bd=bd.groupby(f.segment_id).ffill().where(on)
 for r in g.itertuples():
  d=bd.loc[pd.Timestamp(r.day)];clocks.append(dict(sid=sid,epoch=r.epoch,first_legal_CORE_day=r.day,native_first_observed_I_on=None if pd.isna(d) else str(d.date()),left_of_study=bool(pd.notna(d) and d<pd.Timestamp('2022-01-01')),same_day_as_I_on=bool(pd.notna(d) and d==pd.Timestamp(r.day))))
clocks=pd.DataFrame(clocks);clocks.to_csv(O/'ROOT_CLOCK_AUDIT.csv',index=False)
comp=pd.DataFrame(competition);comp.to_csv(O/'COMPARABLE_GROUPS.csv',index=False)
qa=dict(legacy_input_hashes=legacy,independent_full_queue_and_picks_exact=True,all506_unknown_slots_exact=True,same_day_sector_actual_role_quota_exact=True,common_label_days_exact=True,old_actual_CORE_selected_set_all3_identical=True,original_879_firsts=879,all_roles_source_hash_exact=True,root_first_legal_not_birth=True,roots=len(roots),roots_native_I_start_before_window=int(clocks.left_of_study.sum()),roots_first_legal_equals_I_start=int(clocks.same_day_as_I_on.sum()),root_start_unknown=int(clocks.native_first_observed_I_on.isna().sum()),competitive_groups=int(comp.competitive.sum()),groups=len(comp),comparative_new_runs=0)
dump('POST_RESULT_AUDIT.json',qa)
# Descriptive contributions against original all-role net rounds.
x=ro[(ro.period=='ALL')&(ro.view=='terminal_closed')];a=x[x.dimension=='CORE_ALL'].iloc[0];b=x[x.dimension=='ALL_ROLES'].iloc[0]
contrib=dict(original_CORE_first_share=a.firsts/b.firsts,original_loss_count_share=a.losses/b.losses,original_gross_loss_share=a.gross_loser_sum/b.gross_loser_sum,original_gross_profit_share=a.gross_winner_sum/b.gross_winner_sum,core_net=a.net_sum,all_net=b.net_sum,mobile_started_net=b.net_sum-a.net_sum)
dump('ORIGINAL_CORE_CONTRIBUTION.json',contrib)
# Small report tables with all required denominators.
rt=ro[(ro.dimension=='CORE_ALL')&(ro.view=='terminal_closed')][['period','firsts','closed','unclosed','wins','losses','win_rate','net_sum']].copy();rt['win_rate']=(100*rt.win_rate).map(lambda x:f'{x:.2f}%');rt.net_sum=rt.net_sum.map(lambda x:f'{x:,.2f}')
st=ro[(ro.period=='ALL')&ro.dimension.isin(['signal_clock','I_clock'])&(ro.view=='terminal_closed')][['dimension','value','firsts','closed','unclosed','wins','losses','win_rate','net_sum']].copy();st.win_rate=(100*st.win_rate).map(lambda x:f'{x:.2f}%');st.net_sum=st.net_sum.map(lambda x:f'{x:,.2f}')
t=res.pivot(index=['period','H','N','days'],columns='method',values='mean_day').reset_index();t=t[t.H.isin([20,60])];t['DMI-PVR_pp']=(t.DMI-t.PVR)*100
for k in ['PVR','CLOSE','DMI','DMI-PVR_pp']:t[k]=t[k].map(lambda x:f'{x*100:.5f}%' if k!='DMI-PVR_pp' else f'{x:+.5f}')
rr=rs[rs.method=='DMI'][['period','roots','complete','big','caught','lost_vs_PVR','added_vs_PVR']].rename(columns={'caught':'DMI_caught'}).merge(rs[rs.method=='PVR'][['period','caught']],on='period').rename(columns={'caught':'PVR_caught'})
neg=roots[roots.big60&roots.PVR&~roots.DMI]
summary=q.groupby('method').agg(slots=('K','sum'),replaced=('changed','sum'),days_changed=('changed',lambda v:int(v.gt(0).sum()))).reset_index()
report=f'''# CORE 选股覆盖审计与冻结 DMI 融合实测

## 结论

不能把已有 MOBILE 的结论无声推广到 CORE。已独立还原 106,618 个合法 CORE 股票-日；但这次冻结 DMI 融合没有产生值得晋升的选股增量。15,185 个名额只换 58 个，原 Top20 覆盖的 786 个真实 CORE 首仓三臂完全一致。20 日等日均值只改善 0.00213 个百分点，60 日减少 0.02956 个百分点；右尾早期捕获 571→570 / 2,504。保留原公式，不扩大系数、不扫参、不运行新账户。

这是 CORE 条件机会层的研究，不是全市场新账户，也不是已经达到约35%完整净回合胜率。原 CORE 发起的 853 个已闭回合为 210 赢、643 亏，24.62%；26 个未闭不算输。

## 1. 以前做过什么，为什么仍有缺口

- 原 native_rank.py 服务全部 pending 的唯一股票槽，同股 CORE/MOBILE 共用 rank；不是只服务 MOBILE。
- CE 的 EMPTY_FIRST_README.md 已审计原全部空仓股票槽，包含 CORE+MOBILE；无当日 fresh CE 的 CORE-only 原槽固定。已有全部首仓 OHLC 描述、资金互换与旧双时间尺度混合股票池研究。所以“以前完全没研究 CORE”不准确。
- 但最近 DMI、CMF、随机指标、量价等严格同日同行业 TopK 正式检验，大多消费 LEGAL_EMPTY_MOBILE_CANDIDATES：PVR 53,121 + E31 50,645 =103,766 账户-股票-日。不是103,766个独立全市场或CORE机会。
- 旧151个精确预算互换中，实际 CORE 128（58 CORE-only、70双角色），MOBILE 23。这说明资金稀缺处的选股消费亦大量落在 CORE。
- 本轮未发现已完成的同类“新增H/L成熟指标 × 独立CORE资格 × 同日同行业同角色同K”专项，故补这一块，不重命名旧MOBILE结论。

主要历史源：native_rank.py；case-stage-ledger-20261031/v3/joint_v3.py；cp_timing_quality_v1/candidate_test/account_adapter/EMPTY_FIRST_README.md；first_signal_ohlc_mechanism_v1/anatomy/REPORT.md；pvr_dual_memory_v1/READOUT.md。

## 2. 原 planning、资格及资金顺序

CORE 需当日原 i_buy 与原 S0 qualification 为真、原账户空仓、当前CORE epoch未消费。S0含共同资料/买入可用/市值口径/原I上行、股票与行业H1新鲜、行业当日观察与上行、身份/行业已知等；不把 e0_ready+i_buy 几个字段冒充完整资格。本轮直接使用原 core_Q=True 及原 pending，再核四个源字段。

MOBILE 需当日 fresh CP 与 continuing S0 qualification，continuing把buy_allowed替为市场可买，故不额外要求 i_buy；可以空仓首买或持仓加层。CORE 不要求 CP。ACT、待买/待卖、报价/保护线和整数股数/风险cap先由原 planning 处理。CORE用原I线及原0.25% NAV批次风险，次OPEN还需原preview/资金route；合法意图不等于有现金、不等于可成交。

native_rank 先按股票去重、未知PVR保持原数字槽，已知按 round12 PVR 排；同股票两角色一起迁移。opening按(rank,role!=core)先试CORE，成功预留才把股票加入done；CORE失败可继续试MOBILE。排名下降不强制卖持仓。CORE沿原I/ACT退出，MOBILE另有CP保护。本轮均未改变。

## 3. 独立重建CORE域与可比较边界

126,994 原PVR CORE pending中，20,376所在原行业attempt已失效；剩106,618，800日、1,651股。42,908有实际MOBILE意图，63,710为CORE-only。43,127当日有fresh CP，说明fresh CP和MOBILE pending不是同一个布尔字段。原PVR已知106,467。

逐行核原机会 core_Q、空仓、无barrier、CORE角色及非零cap；同日daily无持仓；原rank-policy数值/角色核同；源facts的e0_ready/g_ready/i_target/i_buy核同。全部879真实CORE首仓覆盖，不借用MOBILE名册。

{md(pd.read_csv(O/'DOMAIN_ANNUAL.csv'))}

三臂原CORE队列前 K=min(20,N) 固定各 sector×has_actual_mobile_pending 配额。这比仅同行业更严格，避免CORE-only与有MOBILE备用通道的股票免费互换。各臂7,295 CORE-only票、7,890双角色票。506共同UNKNOWN保留各自原槽。

重要范围：这是原状态条件下CORE队列的Top20比较，不是原完整混合队列的资金排序重放。原资格、行情、固定未来1709股票池与行业归属也不因此变成PIT或全A股历史可交易池。

## 4. 为什么选DMI，以及它增加了什么

PROTOCOL.json的formula字段原样嵌入旧DMI协议，内含旧MOBILE53121/sector-only域文字，仅作继承公式的来源记录；本轮执行域与配额严格按外层CORE/sector×has_mobile协议及封存代码。旧嵌套文字不构成本轮MOBILE外推，封存协议未改。

在任何新CORE结果前复用原已冻结DMI方案，不从CORE结果挑赢家：n=14，up=H−Hprev，down=Lprev−L；+DM仅当up>down且up>0，否则0；−DM对称；同幅外扩和inside bar为0。完整14变化均值初始化后RMA α=1/14。d=(RMA(+DM)−RMA(−DM))/(两者之和)，严格零分母取0，数据无效/缺公共日/来源块改变重置，未充分预热为UNKNOWN。

原PVR只用收盘收益、自身波动标度及金额活动。DMI新增的是H/L包络持续迁移，不是只把PVR换尺度；但它不证明突破有效，也不表示CP信用或已有仓位有利润。这里d的TR分母抵消，ADX只做描述。

E=atanh((PVR−50)/50)/2；E*=E+0.25·d·max(E,0)；score*=50+50tanh(2E*)。0.25是早先冻结的影响预算，不宣称最优。原负E不变；没有ADX门槛、等待转正、过热过滤或新CP状态。

收盘对照把+DM/−DM换成正负收盘变化，同样RMA14、同一融合，即dclose=RSI14/50−1。这样区别“H/L新增信息”和“仅又平滑一次收盘”。来源：https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/average-directional-index-adx 。

106,112共同已知，42908旧MOBILE重叠特征逐值一致；21个真正截断完整前缀精确一致。共同已知之外不删候选。独立重放全排序与UNKNOWN槽均一致。

## 5. 机制实测：几乎没改变买谁

{md(summary)}

CORE合法域的DMI已知点中101,796/106,256为正。全域描述Spearman(PVR,DMI融合)=0.997612，d与dclose为0.884000。该相关是已筛选的跨期样本描述，不是新增预测能力检验。

盈新000620信号2022-01-11的d=0.8050，PVR91.1767→DMI94.2969；盛通002911的2022-07-25为0.8435，90.7889→94.1069。两者都维持各自行业/角色组第1，也仍入选。真实大亏并非都长成DMI转负。与此同时中国医药2022-03-03、海能达2024-10-15等赢家也被保留。不能凭几只失败股改大惩罚或改系数。

原879个CORE首仓中786个在原Top20；三臂仍是完全同一786个，763已闭、194赢/569亏。这只是原已实现回合与名额的关联，不是新策略25.43%胜率，也不意味着排序的资金效果不可能变化。

## 6. 唯一正式同日同资格同K结果

先封存features/picks，再读未来标签。复用旧native口径：次公共OPEN×原因子到第5/20/60公共日收盘，close与原facts核同，所有需要的观察完整；与既有旧标签重叠逐值精确。没有假定日内止损、费用、实际持仓或成交。

每一日三臂全部入选票的该期限路径都完整才纳入。下表是等日价格收益均值，不是净回合收益。正收益及扣40bp的价格正比例另在RESULTS.csv，不叫胜率。

{md(t)}

5日共同748/800天、14,178/15,185票；20日654/800天、12,332/15,185票；60日504/800天、9,427/15,185票。60日丢掉296天，不能把共同支持结论外推全部时期。2026年60日仅12/85天、240/1,678票；2026Q1仅12/56天。各时期缺失见LABEL_COVERAGE.csv。

全期20日DMI−PVR为+0.00213百分点，60会话块描述区间[−0.01069,+0.01241]；删掉最好一天后为−0.00017百分点。60日为−0.02956百分点，描述区间[−0.05045,−0.00699]；DMI−close对照为−0.01313百分点。16个时间块、反复消费的开发历史及不完整支持均不允许宣称未来显著优势或劣势。

## 7. 右尾分母与时钟

根定义是同sid+原账户native epoch的“研究窗口内首次合法CORE机会”，不是全历史I出生。按该次OPEN的60日close-MFE≥30%且期末≥20%定big60；首次机会起+5公共日内选中算早捕获。

{md(rr)}

丢失的唯一原已捕获big60根为002156.SZ，首次合法CORE机会2022-12-15；DMI无新增big60。原571/2504=22.80%，DMI570/2504=22.76%，不是35%净回合胜率。

根时钟审计：{len(roots)}个窗内根中，{int(clocks.left_of_study.sum())}个原I首个已观察开启日早于2022窗口；仅{int(clocks.same_day_as_I_on.sum())}个窗内首合法CORE日等于原I开启日，{int(clocks.native_first_observed_I_on.isna().sum())}个原起点未知。不能将账户机会到达较晚当成指标自身等待，也不把左截断根叫真正首次I信号。

## 8. 原CORE发起完整回合：入场年、时钟与损失贡献

以下都是原120万元连续PVR账户的原完整0→0回合，CORE发起后可能加MOBILE，故不是CORE层单独净额。按entry_day分期，terminal_closed表示截至2026-05-15已闭。未闭不当失败。

{md(rt)}

2022“年内已闭”必须另列：229局，30赢/199亏，13.10%，净−107,504.42元；另外41局当年未闭、后续闭合，不能将最终270局的16.30%混作2022年末胜率。全期所有角色原基准为2693首仓、2626闭局、675赢/1951亏=25.70%，67未闭。

{md(st)}

first_observed_I_on仅是原facts按segment记录到的I从非1变1，非新指标，也不冒充精确全历史出生。CORE在之后原i_buy再次成立时仍可首买，823/879落在此“later_I_buy”，不能把CORE等同I开启当天。fresh CP与否只描述信号时钟，不授权新门。

CORE发起回合占首仓32.64%、已闭亏局32.96%、原总亏损金额25.45%、原总盈利金额32.17%。CORE发起已闭净和+82,333.08元，全部角色−152,342.25元，相减MOBILE发起为−234,675.33元。这不是“把CORE关掉”的反事实。

右尾集中不能隐藏：2023 CORE净+65,747.93元，其中601595.SH原回合+59,920.58元；2026 CORE净+65,336.50元，000711.SZ为+58,562.83元；924入场队列CORE24局只有4赢，合计+14,863.97元，海能达单局+21,374.88元。低胜率与正净额可同时存在，也不能以几只赢家抵消持续失败风险的研究。

## 9. 接下来采用的研究判断

本轮结论仅是：所测连续DMI正证据融合在准确CORE资格域内没有产生有效选股改变，不晋升，不靠事后调参挽救。下一步若另立研究，应仍覆盖全部当前合法唯一股票槽，并先说明新增量价信息如何区别“失败反弹中的H/L上移”和可持续右侧推进，保持CP/CORE各自资格时钟与资金约束。不能回退成只筛MOBILE，也不能仅换指标名称。

没有新账户、参数网格或实盘操作。未证明35%目标可达，也未证明达不到。工程尝试的唯一修正发生在新特征前，原因及旧新脚本哈希见ENGINEERING_FIX_BEFORE_FEATURES.json；正式选股比较只有一次。

## 文件

PROTOCOL.json；DOMAIN_AUDIT.json/DOMAIN_ANNUAL.csv；FEATURES.parquet；SEALED_PICKS.parquet/RANK_SEAL.json；RESULTS.csv/PAIRED_BLOCKS.csv/LABEL_COVERAGE.csv；ROOT_COVERAGE.csv/ROOT_CLOCK_AUDIT.csv；ORIGINAL_CORE_ROUNDS.csv/ORIGINAL_ROUND_SUMMARY.csv；POST_RESULT_AUDIT.json；COMPLETION.json。全部原输入只读，原指标与账户未修改。
'''
(O/'REPORT.md').write_text(report)
assert all(sha(O/n)==h for n,h in seal['hashes'].items())
dump('OUTPUT_SHA256.json',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_SHA256.json'})
print(json.dumps(qa,ensure_ascii=False));print('REPORT',str(O/'REPORT.md'))
