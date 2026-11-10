from common_abcd import *
import pandas as pd,html
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
font_manager.fontManager.addfont('/System/Library/Fonts/Supplemental/Arial Unicode.ttf');plt.rcParams.update({'font.family':'Arial Unicode MS','axes.unicode_minus':False,'font.size':11})
NAMES={'A':'A 原IX＋原选股/配置','B':'B 双通道选股','C':'C 主动轮换','D':'D 双通道＋轮换'};COLORS={'A':'#6b7280','B':'#007f83','C':'#dd7c21','D':'#6d4bc3'}

def table(f):return f.to_html(index=False,border=0,escape=True,classes='data')
def p(x):return f'{x:.2%}'
def main():
 out=HERE/'report';out.mkdir(exist_ok=False);f=pd.read_csv(HERE/'analysis/summary.csv');c=pd.read_csv(HERE/'analysis/curves.csv');c['dt']=pd.to_datetime(c.date);a=pd.read_csv(HERE/'analysis/annual.csv');w=pd.read_csv(HERE/'diagnostics/annual-winner-reasons.csv');n=pd.read_csv(HERE/'diagnostics/named-winner-reasons.csv');rot=pd.read_csv(HERE/'diagnostics/rotation-handoffs.csv');d=pd.read_csv(HERE/'analysis/daily-stock-contributions.csv')
 for stress in ['base','cost2','delay1']:
  fig,axes=plt.subplots(2,1,figsize=(14,7.8),sharex=True,gridspec_kw={'height_ratios':[2,1]})
  for mode in 'ABCD':
   g=c[c.scheme.eq(mode)&c.scenario.eq(stress)];axes[0].plot(g.dt,g.nav/10000,color=COLORS[mode],label=NAMES[mode],lw=1.5);axes[1].plot(g.dt,-g.drawdown*100,color=COLORS[mode],lw=1.3)
  axes[0].axhline(100,color='#b3bac2',ls='--',lw=.8);axes[0].set_ylabel('净资产（万元）');axes[0].legend(ncol=2);axes[0].set_title(f'同池、同区间、各100万元｜{stress}｜2015—2026-10-22')
  axes[1].set_ylabel('距历史高点回撤（%）');axes[1].invert_yaxis()
  for ax in axes:ax.grid(alpha=.15);ax.spines[['top','right']].set_visible(False)
  fig.text(.06,.02,'当前存续/市值/行业开发口径；含费用和滑点；期末持仓按市值计价，未强制平仓。',fontsize=10,color='#596475');fig.tight_layout(rect=[0,.04,1,1]);fig.savefig(out/f'nav-{stress}.png',dpi=150);plt.close(fig)
 # Comparable realized daily contribution, not overlapping whole-campaign PnL.
 named=['688256.SH','300308.SZ','300502.SZ'];dc=d[d.symbol.isin(named)&d.date.ge('2023-01-01')&d.account.str.endswith('_base')].groupby(['account','symbol']).net_contribution.sum();rr=[]
 for mode in 'ABCD':
  for sid in named:
   q=n[n.scheme.eq(mode)&n.symbol.eq(sid)];rr.append(dict(组别=mode,股票=q.name.iloc[0],持有收盘日=int(q.held_closes.sum()),实际贡献万元=round(float(dc.get((mode+'__S0_base',sid),0))/10000,3),当年窗口参与数=int(q.participated.sum())))
 pd.DataFrame(rr).to_csv(HERE/'diagnostics/named-winner-actual-contribution.csv',index=False)
 annual=a[a.scenario.eq('base')].pivot(index='year',columns='scheme',values='net_return').reset_index()
 for mode in 'ABCD':annual[mode]=annual[mode].map(p)
 base=f[f.scenario.eq('base')].copy();summary=pd.DataFrame({'组别':base.scheme,'总收益':base.net_return.map(p),'最大回撤':base.max_drawdown.map(p),'期末万元':base.final_nav.map(lambda x:f'{x/10000:.2f}'),'平均仓位':base.mean_exposure.map(p),'闭合胜率':base.win_rate.map(p),'闭合周期数':base.closed_campaigns,'费用万元':base.fees_cny.map(lambda x:f'{x/10000:.2f}'),'主动替换次数':base.rotation_requests})
 attribution=pd.DataFrame({'组别':base.scheme,'普通闭合净损益万元':base.ordinary_closed_pnl.map(lambda x:f'{x/10000:.2f}'),'≥30%尾部闭合净损益万元':base.tail_closed_profit.map(lambda x:f'{x/10000:.2f}'),'未闭合损益万元':base.open_campaign_pnl.map(lambda x:f'{x/10000:.2f}'),'其他账户费用万元':base.noncampaign_expenses.map(lambda x:f'{x/10000:.3f}')})
 counts=w.groupby('scheme').agg(年度大赢家窗口参与=('participated','sum'),总窗口=('participated','size')).reset_index();reasons=w[~w.participated].groupby(['scheme','main_reason']).size().reset_index(name='未参与窗口')
 stress=f[['scheme','scenario','net_return','max_drawdown','fees_cny']].copy();stress['net_return']=stress.net_return.map(p);stress['max_drawdown']=stress.max_drawdown.map(p);stress['fees_cny']=stress.fees_cny.map(lambda x:f'{x/10000:.2f}万')
 body=['<h1>双通道选股 × 主动轮换</h1>','<p class="lead">四组独立100万元，S0：最多3行业各2股。原IX自身退出/E0保护/初仓15%/新投入90%保持一致。A是旧账技术控制，B/C/D为9个新经济账户。</p>', '<div class="note">'+html.escape((HERE/'CONCLUSION.md').read_text().split('\n\n')[1] if (HERE/'CONCLUSION.md').exists() else '收益结果与机制归因见下方；不自动晋升或继续调参。')+'</div>', '<h2>完整连续资金结果</h2>',table(summary),'<p>当前1709股合格池＋2市值未知记录，90行业；原IX当日新买事件与原行业E0保持。当前名册/市值/行业开发偏差保留，全部历史已见。胜率不等于收益优势；≥30%只作闭合尾部标签，不是止盈线。</p>', '<label>执行情景 <select id="stress"><option value="base">基础</option><option value="cost2">可变成本与滑点加倍</option><option value="delay1">多一次可执行事件延迟</option></select></label><img id="nav" src="nav-base.png" alt="四组净值和回撤">', '<h2>收益来自哪里</h2>',table(attribution), '<h2>成本与延迟</h2>',table(stress), '<h2>逐年连续收益</h2>',table(annual),'<p>每年继承上一年资金和持仓，不充值、不重置100万元。原固定半导体场景的切片位于下载表，只作同钟参照，不称全A市场牛熊分类。</p>', '<h2>三只已知赢家：真实持仓与贡献（2023至期末）</h2>',table(pd.DataFrame(rr)), '<p>实际贡献来自逐日现金/股数/分红独立归因，跨年不重复累加。价格翻倍数是事后事实，不能直接当账户可获收益。</p>', '<h2>全部固定年度大赢家窗口</h2>',table(counts),table(reasons), '<h2>实际行业和股票</h2>']
 for mode in 'ABCD':
  sectors=pd.read_csv(HERE/'analysis/actual-industries.csv');stocks=pd.read_csv(HERE/'analysis/actual-stocks.csv');ss=sectors[sectors.account.eq(mode+'__S0_base')].sort_values('net_pnl',ascending=False);st=stocks[stocks.account.eq(mode+'__S0_base')].sort_values('net_pnl',ascending=False)
  meta=read(OLD/'inputs-v2/metadata.json');st['name']=st.symbol.map(lambda s:meta[s]['name']);st['industry']=st.symbol.map(lambda s:meta[s]['industry'])
  ss=pd.concat([ss.head(8),ss.tail(5)]).drop_duplicates();st=pd.concat([st.head(10),st.tail(5)]).drop_duplicates()
  for q in [ss,st]:q['net_pnl']=q.net_pnl.map(lambda x:f'{x/10000:.3f}万')
  body+=['<details><summary>'+NAMES[mode]+'：贡献最高及最低行业/股票</summary>',table(ss.drop(columns=['account','scheme'])),table(st.drop(columns=['account','scheme'])),'</details>']
 body+=['<h2>主动替换的真实交接与代价</h2>','<p>行业优先；同一挑战者连续3个不同收盘领先被替换者至少2名，触发当日仍需新买事件且最小数量可放入15%NAV。原持仓自身有退出则先处理。卖出未成交仍占位，卖后下一收盘重新竞争，最早再下一开盘买，不承诺原挑战者最终买到。</p>']
 if len(rot):
  rs=rot.groupby('scheme').agg(被卖股票项=('outgoing','size'),实际出现卖出=('first_sale','count'),首批包含原目标=('first_later_buy_matches_original_challenger','sum'),提出替换后21日平均价格变化=('outgoing_posthoc_21','mean'),提出替换后63日平均价格变化=('outgoing_posthoc_63','mean')).reset_index()
  for k in ['提出替换后21日平均价格变化','提出替换后63日平均价格变化']:rs[k]=rs[k].map(p)
  body+=[table(rs),'<details><summary>逐笔示例（完整CSV可下载）</summary>',table(rot.head(24)),'</details>','<p>“首批包含原目标”只检查出清后首个买入开盘批次是否包含原挑战行业/股票，不表示固定替换配对或该批买入全由这次卖出引起。21/63日从提出替换日收盘起算，属于事后价格机会成本，不加入组合收益，也不单凭后涨认定换错；接近期末可能无后续数据。</p>']
 body+=['<p><a href="../case-review/">查看按时间选取的首次行业/个股替换：量价与实际持仓图</a></p>','<h2>固定规则、核账和下载</h2>','<p>B/D：短期R5上行与21/63同日相对排序，长期R63/R126上行与原RS-H1；行业另要求绝对上行和过半可比成员上涨。行业长短交替、个股短长交替。新股可走短通道，不强制253日；无合格候选可以持现金。这是排序/配置实验，原量价趋势模型未重写。</p>', '<p>A逐日/全部金融日志必须精确复现旧IX-S0；12组独立现金、股数、费用、权益、T+1及每日归因核验；两个物理截断日期检查账户与完整决策/换仓状态。所有代码和输入身份留存；没有结果后阈值搜索或经济重跑。</p>','<div class="downloads">']
 for file,label in [('PROTOCOL.md','完整事前规则'),('CONCLUSION.md','结论'),('analysis/summary.csv','全部12组结果'),('analysis/campaigns.csv','全部持仓周期'),('analysis/actual-industries.csv','实际行业'),('analysis/actual-stocks.csv','实际股票'),('diagnostics/annual-winner-reasons.csv','960个年度赢家窗口'),('diagnostics/named-winner-reasons.csv','三股分年原因'),('diagnostics/rotation-handoffs.csv','逐笔主动替换'),('diagnostics/fixed-scenario-slices.csv','固定场景连续净值切片'),('analysis/accounting-audit.json','独立核账'),('case-review/index.html','首次替换量价与实际持仓'),('freeze.json','经济前冻结')]:body.append(f'<a href="../{file}">{label}</a>')
 body+=['</div>','<script>document.getElementById("stress").onchange=e=>document.getElementById("nav").src="nav-"+e.target.value+".png"</script>']
 css='body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;max-width:1200px;margin:40px auto;color:#1f2937;padding:0 24px;line-height:1.65}h1{font-size:34px;margin-bottom:12px}h2{margin-top:44px}p{color:#526071}.lead{font-size:17px}.note{background:#e9f2f5;border-left:4px solid #007f83;padding:20px}img{width:100%;margin:20px 0}.data{border-collapse:collapse;width:100%;font-size:13px;margin:16px 0}.data th,.data td{border-bottom:1px solid #dce2e7;padding:9px;text-align:right}.data th{background:#f3f6f8}.data td:first-child,.data th:first-child{text-align:left}details{overflow:auto;border-top:1px solid #ddd;padding:15px 0}summary{cursor:pointer;font-weight:600}.downloads{display:flex;gap:18px;flex-wrap:wrap;margin-bottom:60px}select{padding:8px;font-size:15px}'
 out.joinpath('index.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>A/B/C/D选股与换仓对照</title><style>'+css+'</style>'+''.join(body)+'</html>')
 write(HERE/'report-build.json',dict(recorded_at=now(),charts=3,base_accounts=4,all_scenarios=12,all_annual_winner_windows=960));print(dict(report_ready=True),flush=True)
if __name__=='__main__':main()
