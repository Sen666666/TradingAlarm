from pathlib import Path
import json,html
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
R=Path(__file__).resolve().parent;O=R/'results/v0';C=R/'charts';C.mkdir(exist_ok=True)
for f in ['/System/Library/Fonts/Supplemental/Arial Unicode.ttf','/System/Library/Fonts/PingFang.ttc']:
 if Path(f).exists():font_manager.fontManager.addfont(f);plt.rcParams['font.family']=font_manager.FontProperties(fname=f).get_name();break
plt.rcParams.update({'font.size':10,'axes.unicode_minus':False,'figure.facecolor':'#faf9f6','axes.facecolor':'#faf9f6','savefig.facecolor':'#faf9f6'})
s=pd.read_csv(O/'summary.csv');a=pd.read_csv(O/'aggregates.csv');met=json.loads((R/'inputs.json').read_text())['series'];pol=['E0','E2','E3','ED'];labels={'E0':'现行结构退出','E2':'结构＋2倍波幅','E3':'结构＋3倍波幅','ED':'结构＋向下量价事件','HOLD':'区间买入持有'};colors={'E0':'#176b78','E2':'#d57235','E3':'#8b66a5','ED':'#bd4453','HOLD':'#8f8c7e'}
def pct(x):return '—' if pd.isna(x) else f'{x*100:.2f}%'
def table(x):return '<div class="scroll">'+x.to_html(index=False,border=0,escape=True)+'</div>'
def view(z,extra=[]):
 cs=extra+['policy','net_return','max_drawdown','trades','win_rate','natural_win_rate'];v=z[cs].copy();v.policy=v.policy.map(labels)
 for k in ['net_return','max_drawdown','win_rate','natural_win_rate']:v[k]=v[k].map(pct)
 v=v.rename(columns={'policy':'退出规则','net_return':'累计净收益','max_drawdown':'最大回撤','trades':'交易笔数','win_rate':'胜率(含期末)','natural_win_rate':'自然退出胜率','window':'窗口','scenario':'情景','name':'资产','mode':'实验'})
 return table(v)
def acc(sym,p,mode='P',window='primary'):
 return O/'accounts'/'__'.join([sym,window,'base',mode,p])
def clean(axes):
 for ax in np.array(axes).flat:ax.grid(alpha=.16);ax.spines[['top','right']].set_visible(False)
# fixed-sleeve paths, not average drawdown.
fig,axs=plt.subplots(2,2,figsize=(16,10),layout='constrained')
for j,w in enumerate(['primary','history2024']):
 for p in pol+['HOLD']:
  mode='H' if p=='HOLD' else 'P';d=pd.read_csv(O/f'aggregate-{w}-base-all13-{mode}-{p}.csv',index_col=0,parse_dates=True)
  axs[0,j].plot(d.index,d.nav,c=colors[p],label=labels[p],ls='--' if p=='HOLD' else '-');axs[1,j].plot(d.index,100*d.drawdown,c=colors[p])
 axs[0,j].set_title(('2025-01-02—2026-10-13' if j==0 else '2024-01-02—2024-12-31')+' · 13固定分仓');axs[0,j].legend(fontsize=9);axs[0,j].set_ylabel('净值，初始1');axs[1,j].set_ylabel('最大峰值以来回撤 %')
clean(axs);fig.suptitle('相同开仓逻辑，允许按原规则重入；共同成本、下一开盘成交\n各资产初始等额，此后不调仓、不转移资金；无汇率变化，非人民币真实账户');fig.savefig(C/'aggregate.png',dpi=145);plt.close(fig)
# full single asset charts all13: not selected by result.
for m in met:
 sym=m['symbol'];d=pd.read_parquet(R/'inputs'/f'{sym}.parquet').loc['2025-01-02':'2026-10-13'];fig,axs=plt.subplots(4,1,figsize=(15,13),sharex=True,layout='constrained',gridspec_kw={'height_ratios':[2.3,1,1.5,1]})
 axs[0].plot(d.index,d.close,c='#a18d54',lw=1.4,label='收盘价');axs[0].set_yscale('log');axs[0].set_ylabel('价格(对数轴)')
 for p,marker in [('E0','o'),('E2','x')]:
  ss=pd.read_parquet(O/'states'/f'{sym}-primary-{p}.parquet');axs[0].plot(ss.index,ss.exit_line.where(ss.target.astype(bool)),c=colors[p],alpha=.7,lw=.8,label=labels[p]+'保护线')
  ff=pd.read_csv(acc(sym,p)/'fills.csv');sell=ff.loc[ff.side=='sell'];axs[0].scatter(pd.to_datetime(sell.date),sell.price,c=colors[p],s=35,marker=marker,label=labels[p]+'实际卖出',zorder=4)
  dd=pd.read_parquet(acc(sym,p)/'ledger.parquet');axs[1].step(dd.index,dd.quantity.gt(0).astype(int)+(0 if p=='E2' else 1.3),where='post',c=colors[p],label=p)
 axs[0].legend(ncol=2,fontsize=8);axs[1].set_yticks([.5,1.8],['E2持仓','E0持仓']);axs[1].set_ylim(-.1,2.5)
 for p in pol+['HOLD']:
  dd=pd.read_parquet(acc(sym,p,'H' if p=='HOLD' else 'P')/'ledger.parquet');axs[2].plot(dd.index,dd.nav,c=colors[p],ls='--' if p=='HOLD' else '-',label=labels[p]);axs[3].plot(dd.index,dd.drawdown*100,c=colors[p])
 axs[2].legend(ncol=3,fontsize=9);axs[2].set_ylabel('扣费净值');axs[3].set_ylabel('回撤 %');clean(axs);fig.suptitle(f'{m["name"]} {sym} · 原开仓逻辑＋各退出规则\nP自主重入；标记为真实模型成交日期，期初承接和期末结算均计成本');fig.savefig(C/f'{sym}.png',dpi=130);plt.close(fig)
# across-assets bars
z=s.loc[(s.window=='primary')&(s.scenario=='base')&(s['mode']=='P')];fig,axs=plt.subplots(1,2,figsize=(16,9),layout='constrained');names=[m['name'] for m in met];pos=np.arange(13)
for k,p in enumerate(pol):
 v=z.loc[z.policy==p].set_index('name').loc[names];axs[0].barh(pos+(k-1.5)*.18,100*v.net_return,height=.18,color=colors[p],label=labels[p]);axs[1].barh(pos+(k-1.5)*.18,100*v.max_drawdown,height=.18,color=colors[p])
for ax in axs:ax.set_yticks(pos,names);ax.invert_yaxis();ax.axvline(0,c='#888',lw=.6)
axs[0].set_xlabel('累计净收益 %');axs[1].set_xlabel('日收盘最大回撤 %');axs[0].legend(loc='lower left',fontsize=9);clean(axs);fig.suptitle('13个样本全部保留：黄金改善不能代表普遍改善');fig.savefig(C/'asset-comparison.png',dpi=145);plt.close(fig)
# matched legs summary, no capital weighting of leg changes
m=pd.read_csv(O/'matched-legs.csv');pairs=[]
for p in pol[1:]:
 v=m.loc[(m.scenario=='base')&(m.policy==p)];pairs.append({'退出规则':labels[p],'同批开仓':len(v),'收益提高':int(v.delta.gt(1e-10).sum()),'收益降低':int(v.delta.lt(-1e-10).sum()),'相同':int(v.delta.abs().le(1e-10).sum()),'提前卖出':int(v.sensitive_exit.lt(v.base_exit).sum())})
pd.DataFrame(pairs).to_csv(O/'matched-readable.csv',index=False)
main=a.loc[(a.window=='primary')&(a.scenario=='base')&(a.group=='all13')&(a['mode']=='P')];hist=a.loc[(a.window=='history2024')&(a.scenario=='base')&(a.group=='all13')&(a['mode']=='P')]
gold=s.loc[(s.symbol=='AU0')&(s.window=='primary')&(s.scenario=='base')&s['mode'].isin(['P','H'])];hold=a.loc[(a.scenario=='base')&(a.group=='all13')&(a['mode']=='H')]
matched=a.loc[(a.window=='primary')&(a.scenario=='base')&(a.group=='all13')&(a['mode']=='M')];stress=a.loc[(a.group=='all13')&(a['mode']=='P')]
assetdetails=''
for mm in met:
 sym=mm['symbol'];zz=s.loc[(s.symbol==sym)&(s.scenario=='base')&s['mode'].isin(['P','H'])];assetdetails+=f'<details id="{sym}"><summary>{html.escape(mm["name"])} · {sym}：两窗口全部结果、价格和成交图</summary>{view(zz,["window","mode"])}<img loading="lazy" src="charts/{sym}.png"><p>源价格口径：{html.escape(mm["price_basis"])}</p>'
 for p in pol:
  t=pd.read_csv(acc(sym,p)/'trades.csv')[['entry_date','exit_date','net_return','exit_reason','terminal']];t.net_return=t.net_return.map(pct)
  assetdetails+=f'<details><summary>{labels[p]} · 所有主窗口交易</summary>{table(t)}</details>'
 assetdetails+='</details>'
body=f'''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>退出姿态对照：先保留结构退出</title><style>
body{{margin:0;background:#faf9f6;color:#27353a;font:16px/1.8 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}}main{{max-width:1380px;margin:36px auto;padding:0 24px}}h1{{font-size:34px;line-height:1.4}}h2{{margin-top:40px;font-size:24px}}.lead{{font-size:21px;max-width:1100px}}.note{{background:#eee8da;padding:18px 24px;border-left:4px solid #a98a45}}.cards{{display:flex;flex-wrap:wrap;gap:14px}}.card{{flex:1;min-width:230px;padding:18px;background:white;border:1px solid #ded8c8}}.big{{font-size:30px;color:#176b78}}img{{width:100%;height:auto}}table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{padding:9px 11px;text-align:left;border-bottom:1px solid #ddd6c7;white-space:nowrap}}th{{background:#eee8da}}.scroll{{overflow-x:auto}}details{{margin:18px 0;padding:12px;border:1px solid #ddd6c7}}summary{{cursor:pointer;font-weight:600}}a{{color:#176b78}}code{{background:#eee8da;padding:3px}}.small{{font-size:14px;color:#606b70}}
</style><main><h1>退出更敏感，是否更好？</h1><p class="lead">本轮结论：保留现行结构退出作为默认。2倍波幅退出提高了主窗口胜率、改善了沪金主连，却降低跨资产累计收益；2024年的胜率和回撤也未稳定改善。3倍方案是收益与回撤的取舍，尚不足以统一替换。</p><p>先设计并冻结 → 一次运行507账户 → 156个精确前缀复算 → 独立重放成交核账。原算法未改；无需微信、Key或新增行情。</p>
<div class="cards"><div class="card">现行结构退出<div class="big">11.27% / 12.07%</div>13分仓累计收益 / 最大回撤<br>胜率37.30%，126笔</div><div class="card">加2倍波幅退出<div class="big">3.64% / 8.67%</div>同口径收益 / 最大回撤<br>胜率39.13%，207笔</div><div class="card">沪金主连的局部优势<div class="big">39.50% → 43.77%</div>2倍方案回撤31.76% → 14.21%<br>黄金ETF收益却31.57% → 19.76%</div></div>
<p class="note">“保留默认”只表示这次收紧退出没有提供足够替换证据，不表示现行算法已经合格。主窗口京东、腾讯、美团仍亏损，部分单资产回撤超过40%；13分仓收益也低于同池买入持有15.08%。这是有限开发样本的机制诊断，不能代替当前A/H板块→个股全池策略检验。</p>
<h2>1. 先固定比较什么</h2><p>固定此前13个可投资价格代理，主窗口2025-01-02—2026-10-13，历史窗口2024全年；足够前史仅作信号预热，不计收益。A股3只个股的2024前预热仅77条，必须保留这一边界。</p><p><b>E0</b>收盘触及结构保护点退出；<b>E2/E3</b>另加2/3倍此前14观察相对真实波幅的单向跟踪线；<b>ED</b>另加原量价检测器确认的向下事件。入场保留原上行量价确认与高量下跌跨日收复。这里比较的是借自拟合候选的退出机制，不能称恢复了趋势动物原公式。</p><p><b>P自主循环</b>允许退出后按同一原开仓机制重入；<b>M同批开仓</b>强制锁定E0的实际买入日和买入价，每个E0周期最多一次，只改变卖出，最迟随E0卖出。两层共同回答“卖早的效果”和“反复重入的代价”。</p><p>收盘得信号，下一观察开盘执行；另测成本翻倍与再延迟一观察。卖单锁存；跳空低于已知结构保护点取消买入；不用当天未来最低价取消开盘成交。期初若已有结构统一首日承接，期末预定收盘结算，均扣费。</p>
<h2>2. 主结果：原开仓机制＋自主重入</h2><p>13条初始等额、资金各自独立，不每日再平衡；用逐日净值汇总后计算回撤。胜率按所有扣费后闭合交易计，不是资产上涨比例。黄金与黄金ETF、多个科技样本相关，不能把笔数当独立统计样本。</p>{view(main)}<p class="small">最大回撤为日收盘净值口径，不含盘中最坏值。胜率分别列包含与排除期末行政结算；本金均1，无杠杆。13分仓不计汇率，非真实人民币组合。</p><img src="charts/aggregate.png">
<h2>3. 2024与执行压力：优势没有稳定延续</h2>{view(hist)}<p>主窗口去掉沪金主连后，E0收益8.92%、回撤9.71%；E2收益0.30%、回撤10.66%，收益和回撤同时变差。主窗口E2仅4/13资产收益高于E0，E3为5/13；2024分别5/13与4/13。成本翻倍后主窗口E0为9.30%，E2仅0.65%。额外延迟会改变个别排序，2024延迟情景E3略胜E0，不能称现行方案每个情景都占优。</p><details><summary>两窗口 × 三情景：所有13分仓结果</summary>{view(stress,['window','scenario'])}</details><details><summary>排除沪金主连的12分仓：全部情景</summary>{view(a.loc[(a.group=='exAU0_12')&(a['mode']=='P')],['window','scenario'])}</details>
<h2>4. 隔离同次买入：多数小改善，抵不过少数大损伤</h2>{view(matched)}{table(pd.DataFrame(pairs))}<p>同批126次买入中，E2有54笔收益提高、30笔降低、42笔基本相同；累计收益仍由11.27%降到6.67%。这正说明不能数“卖早有利的次数”就决定策略。半导体2025-04-10同次买入，E0持有到11-13获39.40%，E2在05-16卖出仅0.79%；江苏银行2025-02-28同次买入，29.36%被截为0.45%。此表是126笔配对诊断，不是显著性检验。</p><p>允许自主重入后E2收益进一步降到3.64%，表明卖早后重新参与并不自动修复收益。主窗口闭合交易中净收益≥30%的笔数由6降到3；切碎交易也会改变分类，因此同时给同批周期比较，不能只依靠30%标签。E0尾部损益贡献21.52个百分点、普通交易−10.25；E2分别7.84、−4.20。改善普通交易的同时损伤了大赢家。</p>
<h2>5. 黄金确实改善，但原因不是“卖早就够了”</h2>{view(gold,['mode'])}<p>仅锁定原来那5次黄金买入、加2倍退出而不重入，收益为−3.90%；允许按原信号重入，才达到43.77%。第一段2025-01-02买入，E0到10-23获48.72%，E2在03-03只获7.73%；后面新增入场补回了一部分行情并规避部分回落。这是完整路径的结果。2024黄金E0收益19.71%，E2仅9.66%；同类黄金ETF主窗口E2也落后，不能把一个AU0窗口的成功推广。</p><img src="charts/AU0.png">
<h2>6. 单资产全部公开：没有删除失败</h2><img src="charts/asset-comparison.png">{assetdetails}
<h2>7. 本轮决策与证据边界</h2><p><b>默认保留E0；不统一改成2倍波幅或向下事件即退出。</b>若只追求主窗口更平滑的分仓净值，3倍有收益7.33%、回撤8.21%的取舍，但2024基础情景回撤反而略高，不支持作为全局替换。当前问题也不止卖出：下跌后反弹的重新入场、资产选择与仓位，会决定敏感退出省下的损失是否被下一次试错消耗。此次未改它们，也不继续加过滤器或寻参。</p><p>全部历史已看过，结果只属开发检验。13条不是全市场；当前存续/此前选样有偏差，黄金相关样本重复、科技相关性高；股票/ETF使用既有因果权息研究价格，A股个股不是真实分红现金账户。AU0主连不含经核验逐合约换月、整数手或保证金；成本是假设。不能从本轮有限样本推断未来胜率，更不能据此自动实盘。</p>
<h2>8. 审计与复核</h2><p id="audit">独立核账见audit.json；完整账户保留逐日现金、数量、净值、成交、订单与逐笔损益。原始图检页raw-1..4在冻结前看过；raw-review.json文件名文字误写review-1..4，审计记录了更正，冻结PNG本身完整。</p><p><a href="PROTOCOL.md">事前协议</a> · <a href="freeze.json">冻结与哈希</a> · <a href="results/v0/audit.json">独立审计</a> · <a href="results/v0/summary.csv">507账户总表CSV</a> · <a href="results/v0/aggregates.csv">全部汇总CSV</a> · <a href="results/v0/matched-legs.csv">同批1131组腿对照CSV</a> · <a href="results/v0/prefix-checks.csv">156前缀检查</a> · <a href="inputs.json">数据与预热口径</a></p><p class="small">研究到此收口；未替换旧算法，结果后参数修订0次，外部行情请求0次，微信操作0次。</p></main></html>'''
(R/'index.html').write_text(body)
print('Rendered13asset charts + aggregate + comparison; complete report')
