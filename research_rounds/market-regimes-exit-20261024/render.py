from pathlib import Path
import json,html
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
R=Path(__file__).resolve().parent;O=R/'results/v0';C=R/'charts';C.mkdir(exist_ok=True)
font_manager.fontManager.addfont('/System/Library/Fonts/Supplemental/Arial Unicode.ttf');plt.rcParams.update({'font.family':'Arial Unicode MS','axes.unicode_minus':False,'font.size':10,'figure.facecolor':'#faf9f6','axes.facecolor':'#faf9f6','savefig.facecolor':'#faf9f6'})
s=pd.read_csv(O/'summary.csv');cases=json.loads((R/'cases.json').read_text());facts=pd.read_csv(R/'prepared/case-prices.csv');pol=['E0','E2','E3','ED'];labels={'E0':'原结构退出','E2':'＋2倍波幅退出','E3':'＋3倍波幅退出','ED':'＋向下量价事件','HOLD':'买入持有'};colors={'E0':'#176b78','E2':'#d57235','E3':'#8b66a5','ED':'#bd4453','HOLD':'#969184'}
base=s.loc[s.scenario.eq('base')&s['mode'].isin(['P','H'])];order=[c['id'] for c in cases];namemap={c['id']:c['name']+' '+c['start'][:4] for c in cases};rows=[]
def pct(v):return '—' if pd.isna(v) else f'{100*v:+.2f}%'
def unsigned(v):return '—' if pd.isna(v) else f'{100*v:.2f}%'
def table(df):return '<div class="scroll">'+df.to_html(index=False,border=0,escape=True)+'</div>'
def acc(cid,mode,p,sc='base'):return O/'accounts'/f'{cid}__{mode}__{p}__{sc}'
def ledger(cid,p,mode='P',sc='base'):return pd.read_parquet(acc(cid,mode,p,sc)/'ledger.parquet')
def summary_table(z,extra=[]):
 v=z[extra+['policy','net_return','max_drawdown','trades','win_rate','natural_win_rate','exposure_fraction']].copy();v.policy=v.policy.map(labels)
 for col in ['net_return']:v[col]=v[col].map(pct)
 for col in ['max_drawdown','win_rate','natural_win_rate','exposure_fraction']:v[col]=v[col].map(unsigned)
 return table(v.rename(columns={'policy':'算法/退出','net_return':'累计净收益','max_drawdown':'最大回撤','trades':'交易笔数','win_rate':'胜率(含期末)','natural_win_rate':'自然退出胜率','exposure_fraction':'参与观察比例','scenario':'情景','mode':'实验'}))
def clean(axes):
 for ax in np.array(axes).flat:ax.grid(alpha=.15);ax.spines[['right','top']].set_visible(False)
# Matrices include all selected cases and the passive comparator.
ret=base.pivot(index='case',columns='policy',values='net_return').loc[order,pol+['HOLD']];dd=base.pivot(index='case',columns='policy',values='max_drawdown').loc[order,pol+['HOLD']]
fig,axes=plt.subplots(1,2,figsize=(16,9),layout='constrained')
for ax,mat,title,cmap,vmin,vmax in [(axes[0],ret,'累计净收益 %','RdBu',-.5,.5),(axes[1],dd,'日收盘最大回撤 %','YlOrRd',0,.65)]:
 ax.imshow(mat.to_numpy(),aspect='auto',cmap=cmap,vmin=vmin,vmax=vmax);ax.set_yticks(range(len(order)),[namemap[k] for k in order]);ax.set_xticks(range(5),['E0原结构','E2波幅2','E3波幅3','ED反向事件','买入持有'],rotation=20);ax.set_title(title)
 for i in range(len(order)):
  for j in range(5):ax.text(j,i,f'{mat.iloc[i,j]*100:.2f}',ha='center',va='center',color='white' if abs(mat.iloc[i,j])>(.32 if j<5 and title.startswith('累计') else .4) else '#25323b',fontsize=10)
fig.suptitle('同一开仓机制，不同退出规则；案例在策略收益前固定，不能按事后市场类型自动切换',fontsize=14);fig.savefig(C/'matrix.png',dpi=140);plt.close(fig)
for c in cases:
 cid=c['id'];d=pd.read_parquet(R/'inputs'/f'{c["symbol"]}.parquet').loc[c['start']:c['end']];fig,axes=plt.subplots(3,1,figsize=(14,10),sharex=True,layout='constrained',gridspec_kw={'height_ratios':[1.5,2,1.2]})
 axes[0].plot(d.index,d.close,c='#9b8450',lw=1.3);axes[0].set_yscale('log');axes[0].set_ylabel('因果权息价格 / 对数轴')
 for p in pol+['HOLD']:
  mode='H' if p=='HOLD' else 'P';l=ledger(cid,p,mode);style='--' if p=='HOLD' else '-';axes[1].plot(l.index,l.nav,c=colors[p],ls=style,label=labels[p],lw=1.5);axes[2].plot(l.index,100*l.drawdown,c=colors[p],ls=style,lw=1.1)
 axes[1].set_ylabel('扣费净值，初始1');axes[2].set_ylabel('峰值回撤 %');axes[1].legend(ncol=3,fontsize=9);fig.suptitle(c['name']+' '+c['start']+'—'+c['end']+' '+c['type']+'\n同初始条件，允许按原规则重入；不是自动识别市场环境或真实整手账户');clean(axes);fig.savefig(C/f'{cid}.png',dpi=120);plt.close(fig)
# all-case visual review contact sheets, both success and failures.
for k in range(0,len(cases),2):
 fig,axes=plt.subplots(1,2,figsize=(18,7),layout='constrained')
 for ax,c in zip(axes,cases[k:k+2]):ax.imshow(plt.imread(C/f'{c["id"]}.png'));ax.axis('off')
 fig.savefig(C/f'review-{k//2+1}.png',dpi=110);plt.close(fig)
# YTD actual transactions and matched-control paths.
cid='semi_ytd26';d=pd.read_parquet(R/'inputs/USHJ512480.parquet').loc['2026-01-01':];fig,axes=plt.subplots(4,1,figsize=(15,13),sharex=True,layout='constrained')
for ax,p in zip(axes,pol):
 f=pd.read_csv(acc(cid,'P',p)/'fills.csv');st=pd.read_parquet(R/'prepared'/cid/f'{p}.parquet');ax.plot(d.index,d.close,c='#a48f58',lw=1);ax.plot(st.index,st.exit_line.where(st.target.astype(bool)),c=colors[p],lw=.8,alpha=.7)
 for side,marker,color in [('buy','^','#208563'),('sell','v','#c15345')]:
  z=f.loc[f.side==side];ax.scatter(pd.to_datetime(z.date),z.price,marker=marker,c=color,s=38,zorder=4,label='实际买' if side=='buy' else '实际卖')
 ax.set_yscale('log');ax.set_title(labels[p],loc='left');ax.legend(ncol=2,fontsize=8);ax.grid(alpha=.15)
fig.suptitle('2026半导体：上半年推进、下半年走弱，实际买卖和当时保护线');fig.savefig(C/'ytd-transactions.png',dpi=120);plt.close(fig)
fig,axes=plt.subplots(2,2,figsize=(16,9),sharex=True,layout='constrained')
for j,mode in enumerate(['P','M']):
 for p in pol:
  l=ledger(cid,p,'P' if p=='E0' else mode);axes[0,j].plot(l.index,l.nav,c=colors[p],label=labels[p]);axes[1,j].plot(l.index,100*l.drawdown,c=colors[p])
 axes[0,j].set_title('P：按原规则自主重入' if mode=='P' else 'M：锁定E0同6次买入，原周期内不重入');axes[0,j].legend(fontsize=9);axes[1,j].set_ylabel('回撤 %')
clean(axes);fig.suptitle('仅卖早可以改善；反复买回可能消耗改善。M是机制诊断，不是已批准的新策略');fig.savefig(C/'ytd-matched.png',dpi=130);plt.close(fig)
# Tables and saved readable results.
for c in cases:
 r={'环境':c['type'],'标的/期间':namemap[c['id']]}
 for p in pol+['HOLD']:r[labels[p]]=pct(ret.loc[c['id'],p])
 rows.append(r)
main=pd.DataFrame(rows);main.to_csv(O/'readable-returns.csv',index=False)
periods=[]
for mode in ['P','M','H']:
 for p in (pol if mode=='P' else pol[1:] if mode=='M' else ['HOLD']):
  l=ledger(cid,p,mode);cut=l.loc[:'2026-06-30','nav'].iloc[-1];periods.append({'实验':mode,'算法':labels[p],'上半年连续净值收益':cut-1,'7月起至10月23日收益':l.nav.iloc[-1]/cut-1,'全期':l.nav.iloc[-1]-1})
period=pd.DataFrame(periods);period.to_csv(O/'ytd-subperiods.csv',index=False)
for col in ['上半年连续净值收益','7月起至10月23日收益','全期']:period[col]=period[col].map(pct)
casehtml=''
for c in cases:
 cid2=c['id'];z=s.loc[s.case.eq(cid2)&s.scenario.eq('base')];factsrow=facts.loc[facts.id.eq(cid2)].iloc[0]
 casehtml+=f'<details id="{cid2}"><summary>{html.escape(c["type"])} · {namemap[cid2]}：净值、回撤、全部交易与压力结果</summary><p>实际观察{factsrow["first"]}—{factsrow["last"]}，{int(factsrow.observations)}观察，{int(factsrow.warmup)}条前史。收盘到收盘净变动{pct(factsrow.price_return)}，收盘最高/最低振幅{unsigned(factsrow["range"])}，年化日波动{unsigned(factsrow.annualized_vol)}。这些价格描述与首开盘到末收盘扣费的被动收益口径不同。</p>{summary_table(z,["mode"])}<img loading="lazy" src="charts/{cid2}.png"><details><summary>三执行情景全部主账户</summary>{summary_table(s.loc[s.case.eq(cid2)&s["mode"].eq("P")],["scenario"])}</details>'
 for p in pol:
  t=pd.read_csv(acc(cid2,'P',p)/'trades.csv')[['entry_date','exit_date','net_return','exit_reason','terminal']];t.net_return=t.net_return.map(pct);casehtml+=f'<details><summary>{labels[p]}全部交易</summary>{table(t)}</details>'
 casehtml+='</details>'
ytd=s.loc[s.case.eq('semi_ytd26')&s.scenario.eq('base')&s['mode'].isin(['P','H'])];ym=s.loc[s.case.eq('semi_ytd26')&s.scenario.eq('base')&(s['mode'].eq('M')|(s['mode'].eq('P')&s.policy.eq('E0')))];kf=facts[['id','type','name','first','last','observations','price_return','range','annualized_vol','efficiency']].copy()
for col in ['price_return','range','annualized_vol']:kf[col]=kf[col].map(unsigned)
kf.efficiency=kf.efficiency.round(3)
body=f'''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>熊市、震荡与2026半导体：退出规则对照</title><style>
body{{margin:0;background:#faf9f6;color:#27353a;font:16px/1.8 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}}main{{max-width:1400px;margin:36px auto;padding:0 24px}}h1{{font-size:34px;line-height:1.4}}h2{{margin-top:38px;font-size:24px}}.lead{{font-size:21px;max-width:1150px}}.note{{background:#eee8da;padding:18px 22px;border-left:4px solid #a98a45}}.cards{{display:flex;gap:14px;flex-wrap:wrap}}.card{{flex:1;min-width:220px;padding:18px;background:white;border:1px solid #ded8c8}}.big{{font-size:30px;color:#176b78}}img{{width:100%;height:auto}}table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{padding:9px 11px;text-align:left;border-bottom:1px solid #ddd6c7;white-space:nowrap}}th{{background:#eee8da}}.scroll{{overflow-x:auto}}details{{margin:16px 0;padding:12px;border:1px solid #ddd6c7}}summary{{cursor:pointer;font-weight:600}}a{{color:#176b78}}.small{{font-size:14px;color:#606b70}}
</style><main><h1>退出姿态的优势，确实随行情变化</h1><p class="lead">更敏感退出在两段熊市和若干震荡案例中改善，但不是普遍优势。2026半导体的完整上行＋下行路径里，原结构退出仍获得更高收益；同时，同批买入诊断暴露了重新入场对敏感退出的拖累。</p><p>9个固定历史案例＋今年半导体 · 四原规则不改 · 240账户一次运行 · 参数修订0 · 80精确前缀 · 原始量价和全部信号在账户前审阅</p>
<div class="cards"><div class="card">熊市半导体2022<div class="big">−23.21% → −17.34%</div>E0 → E2；向下事件退出为−14.49%<br>敏感退出减损，仍未避免熊市亏损</div><div class="card">偏弱震荡也有反例<div class="big">−0.44% → −9.32%</div>沪深300ETF2021，E0 → E2<br>不能按“震荡”标签就选择敏感退出</div><div class="card">今年半导体完整区间<div class="big">24.97% / 32.29%</div>原算法累计收益 / 最大回撤<br>E2为7.87% / 37.40%</div></div>
<p class="note">本轮按上一轮512480作为半导体板块代理，补齐的是2026完整时间段，不是全部半导体成分股的选股组合。10月24日是周六，实际至10月23日收盘。用户随后已明确确认：512480代表板块完整时间段；强/弱震荡按价格重心偏强/偏弱解释。另列高/低振幅对照。案例类型是事后描述，不输入策略；不能事后知道市场类型再挑每行最好算法。所有历史是开发材料。</p>
<h2>1. 各环境累计净收益：全部案例保留</h2>{table(main)}<p>所有收益都扣费和滑点、按实际价格代理成交；每窗初始资金1，无杠杆。不同年份和资产的案例不能相互连乘为真实组合，也不能按这一人为构造的案例数量断言总体胜率。E2在10窗中7窗收益高于E0，只是本案例集合的事实；此前大牛市和13分仓结果仍保留。</p><img src="charts/matrix.png"><p class="small">左图收益、右图日收盘最大回撤。收益不是年化。蓝色为正收益、红色为负收益；回撤越深颜色越红。原算法/敏感算法与被动的差额不是经过统计显著性验证的alpha。</p>
<h2>2. 为什么这些区间称为熊市或震荡</h2><p>熊市采用半导体2022和京东2023，保留其中反弹。偏强震荡采用半导体2021和中电2023，前者大幅来回、后者低波动慢涨；偏弱震荡采用沪深300ETF2021和恒生科技2023。再保留半导体2023、恒隆2022的高振幅中性/先跌后升，以及黄金ETF2021的低振幅偏弱作为幅度对照。全用完整日历年，没有按策略盈亏挑起止点或删除不合意案例。</p><details><summary>全部价格形态、波动、方向效率与实际日期</summary>{table(kf)}<p>振幅=最高收盘/最低收盘−1；日波动年化=log收盘收益标准差×√252；方向效率=绝对期末log位移/逐日绝对log变化之和。均为区间描述，不能证明存在唯一真实市场标签。</p></details>
<h2>3. 熊市和震荡：结论需要比“早卖更安全”具体</h2><p><b>熊市：</b>半导体2022，E0−23.21%，E2−17.34%，ED−14.49%；京东2023，E0−34.04%，E2−29.46%，ED−28.06%。四组都比各自被动少亏，但仍有25%—49%左右最大回撤，不能称已经解决熊市风险。重复参与熊市反弹没有被出口单独消除。</p><p><b>偏强震荡：</b>半导体2021，E2为28.63%，高于E0的21.60%；中电2023，E2为19.98%，高于E0的15.71%，回撤也更低。短周期获利退出在这些路径确有价值，不能把上一轮牛市中的“截断长趋势”代价直接推广到所有震荡。</p><p><b>偏弱震荡出现相反结果：</b>恒生科技2023的E2从E0−20.02%改善到0.59%；沪深300ETF2021却从−0.44%变成−9.32%。同属偏弱震荡，反复进出的位置与后续收复完全不同，标签不足以决定退出规则。</p><p><b>幅度对照：</b>半导体2023中E2为7.69%、E0−0.15%；但恒隆2022中E0为26.92%、E2只有16.44%。黄金2021所有政策亏损，E3−7.96%比E0−11.40%少亏，仍不如被动−6.70%。不能根据“高波动/低波动”直接产生万能切换规则。</p>
<h2>4. 今年完整半导体：2026年初至10月23日</h2>{summary_table(ytd)}<p>实际首个观察2026年1月5日，193条；起始按前一观察E0结构统一承接，无期前利润。各组实际持仓均在期末前退出，策略胜率没有期末行政结算污染；被动仍按期末结算。这里是2026新起点的同初始条件比较，不是上一轮2025起连续资金账户截取的百分比收益。</p><img src="charts/semi_ytd26.png"><p>连续净值拆分：E0上半年＋84.58%，7月起−32.29%，全期＋24.97%；E2分别＋72.31%、−37.40%、＋7.87%。敏感方案并未避免本次下半年走弱。前一轮2025至2026年6月末E0的162.01%属于另一个起点和终点，不能当作今年上半年收益。</p><img src="charts/ytd-transactions.png">
<h2>5. 卖早有用，为何敏感账户反而更差？</h2>{summary_table(ym,["mode"])}<p><b>锁定E0同6次真实买入、原周期内不重入（M），E2收益54.82%、回撤21.52%，ED收益66.18%、回撤21.67%，都优于E0。</b>开放原规则自主重入（P）后，E2只剩7.87%、回撤37.40%。因此今年这个案例的关键矛盾更明确：敏感卖出本身有帮助，但新增入场及其复利后果严重拖累了账户。三执行情景也需保留：额外延迟一观察时，E2收益升至30.51%，接近E0的32.06%，回撤31.74%略低于E0的32.68%；原收益排序仍在，但优势幅度及回撤排序对执行时点敏感，不能只报基础情景。</p><p>具体例子：6月16日同次买入，E0到7月14日获利14.66%，E2在7月6日获利21.35%；但E2于7月10日买回，到7月14日亏13.76%。8月6日同次买入，E0到10月9日亏9.96%，E2在8月25日仅亏1.40%；随后E2于9月21日买回，到9月29日又亏7.50%。原算法也有7月22日至30日亏11.99%的失败，全部保留。进一步逐笔核对：E2的P与M共同六笔收益和卖出日完全相同；P新增四笔买回全部亏损，分别为−8.12%、−4.93%、−13.76%、−7.50%。这四笔的复利系数约0.697，直接将M终值1.5482压到P的1.0787，差异并非新旧六笔卖点不同。<a href="results/v0/ytd-reentry-decomposition.json">拆解核验</a>与<a href="results/v0/ytd-E2-extra-reentries.csv">新增四笔</a>均保留。</p><img src="charts/ytd-matched.png"><p class="note">M使用原算法的买入序列作为共同实验条件，是机制拆解。它没有通过本轮规则设计准入成为新的自主策略，不能拿54.82%或66.18%当作已完成的可替换交易方案。当前支持的是“退出与重入需要联合评价”这一具体命题，不能据此继续叠加历史日期例外或事后市场标签过滤。</p><details><summary>今年上、下半年所有连续账户分段结果</summary>{table(period)}</details><details><summary>今年三执行情景主账户</summary>{summary_table(s.loc[s.case.eq('semi_ytd26')&s['mode'].eq('P')],["scenario"])}</details>
<h2>6. 所有案例的图、逐笔交易与费用/延迟对照</h2>{casehtml}
<h2>7. 本轮结论</h2><p>对上一轮判断作出限定：<b>当前结构退出保留大趋势的能力有证据，但不是全环境占优；敏感退出在熊市和一些震荡环境确有减损价值，也存在显著反例。</b>今年完整半导体的P主账户依然支持保留E0，但它的32.29%回撤高于研究20%目标，不能称风险已经合格。两段熊市更不支持“趋势算法会自动空仓避熊”的想象。</p><p>本轮最有价值的新证据是：今年半导体的同批买入组明显受益于提前退出，自主重入组却变差。后续若另获研究任务，应针对重入的量价证据与累计试错提出一个有限、可证伪的问题，而不是宣布牛市用E0、熊市震荡用E2——市场类型本身还没有在当时被可靠识别。本轮不改旧模型、不启动追加搜索、不重置全池研究停止计数。</p>
<h2>8. 数据补尾与验证</h2><p>只补512480最后五个交易日，向既有授权同花顺节点做日线/权益2次只读查询。745条重叠OHLC完全一致；线端量为旧原始量100倍，归一后最大相对误差8.37e-8；权益仅2021/2026两次2倍拆分，旧期末后无新事件。保留旧因果价格factor4和量factor0.25追加，不覆盖旧输入。原始响应和查询证据均保存，无微信操作、无实盘。</p><p>10窗E0逐日恒等、80精确前缀通过。独立重放240账户的所有成交，核对现金、数量、费用、滑点、成交时序、复利和最大回撤；90匹配入场账户另查真实买入一致且退出不晚于E0。详见审计收据。</p><p><a href="PROTOCOL.md">事前协议</a> · <a href="cases.json">冻结案例</a> · <a href="freeze.json">代码与数据哈希</a> · <a href="inputs.json">数据覆盖与补尾口径</a> · <a href="results/v0/summary.csv">240账户CSV</a> · <a href="results/v0/readable-returns.csv">收益对照CSV</a> · <a href="results/v0/audit.json">独立核账</a> · <a href="prepared/prefix-checks.csv">80前缀</a> · <a href="results/v0/matched-legs.csv">同批逐笔配对</a> · <a href="http://127.0.0.1:8776/">前轮完整牛市参照</a></p><p class="small">均为已看过历史开发研究，不是全A/H市场、全部半导体成分股、样本外或真实整手账户；单标的/同市场案例相关，不以笔数声称统计显著。日收盘回撤不含盘中最坏值；HK原币收益未含人民币汇率。</p></main></html>'''
(R/'index.html').write_text(body);print('Rendered10case reports +13 comparison figures; no new accounts')
