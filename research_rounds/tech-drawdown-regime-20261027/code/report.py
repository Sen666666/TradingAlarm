from pathlib import Path
import json,html
import pandas as pd,numpy as np,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
O=Path(__file__).resolve().parents[1]
LABELS={'CONTROL':'原I-NR1','FAST':'个股快退出','SECTOR':'行业转弱退出','MARKET_NEW':'市场转弱只停新买','MARKET_ALL':'市场转弱统一退出','MARKET_SLOW':'慢市场统一退出','MARKET_PRICE':'纯价格市场对照','JOINT':'市场与个股共同弱化','JOINT_BLOCK':'共同弱化＋停新买','JOINT_SLOW':'共同弱化＋慢市场新买','G1_JOINT':'共同弱化（原G1）','SHADOW10':'影子回撤10%暂停','SHADOW20':'影子回撤20%暂停','SHOCK10':'影子5日跌10%暂停'}
if __name__=='__main__':
 out=O/'report';out.mkdir(exist_ok=False);s=pd.read_csv(O/'results-final/scoreboard.csv');c=pd.read_csv(O/'results-final/curves.csv');p=pd.read_csv(O/'results-final/periods.csv');campaign=pd.read_csv(O/'results-final/campaigns.csv');rows=[]
 for v in LABELS:
  a=s[(s.version==v)&(s.scenario=='base')].iloc[0];h=p[(p.version==v)&(p.account=='I__S0_base')&(p.period=='2026H2')].iloc[0];new=campaign[(campaign.version==v)&(campaign.account=='I__S0_base')&(campaign.entry_at.str[:10]>='2026-07-01')];total=h.end_nav-h.start_nav;rows.append(dict(version=v,h2_pnl=total,new_cycles=len(new),new_losing_cycles=int(new.net_pnl.lt(0).sum()),new_pnl=new.net_pnl.sum(),existing_pnl=total-new.net_pnl.sum()))
 pd.DataFrame(rows).to_csv(O/'results-final/h2-attribution.csv',index=False)
 plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
 for scenario in ['base','cost2','delay1']:
  chosen=['CONTROL','SHADOW10','SHADOW20','SHOCK10'];fig,ax=plt.subplots(3,1,figsize=(14,11),sharex=True)
  for v in chosen:
   a=c[(c.version==v)&(c.scenario==scenario)];ax[0].plot(pd.to_datetime(a.date),a.nav/1e6,label=LABELS[v]);ax[1].plot(pd.to_datetime(a.date),a.market_value/a.nav,label=LABELS[v]);ax[2].plot(pd.to_datetime(a.date),a.drawdown,label=LABELS[v])
  for a in ax:a.grid(alpha=.2);a.axvspan(pd.Timestamp('2026-07-01'),pd.Timestamp('2026-10-26'),color='red',alpha=.06)
  ax[0].legend(ncol=2);ax[0].set_title('账户风险层：2024至2026-10-26完整资金路径 / '+scenario);ax[0].set_ylabel('净值 / 初始100万元');ax[1].set_ylabel('实际持仓市值 / NAV');ax[2].set_ylabel('全程回撤');fig.tight_layout();fig.savefig(out/f'risk-{scenario}.png',dpi=130);plt.close(fig)
 sections=[]
 for sc,title in [('base','基础执行'),('cost2','双成本'),('delay1','额外一次可执行事件延迟')]:
  a=s[s.scenario==sc][['version','net_return','max_drawdown','pre_profit_retention','h2_return','h2_exposure','empty_days']].copy();a.version=a.version.map(LABELS)
  for k in ['net_return','max_drawdown','pre_profit_retention','h2_return','h2_exposure']:a[k]=a[k].map(lambda x:f'{x:.2%}')
  a.columns=['方案','累计收益','全程最大回撤','前期盈利保留','H2收益','H2平均仓位','H2空仓日/78'];sections.append('<section><h2>'+title+'</h2>'+a.to_html(index=False,escape=True,border=0)+f'<img src="risk-{sc}.png"></section>')
 intro='''<section><strong>主要问题不只是指标慢：温度已转弱，但原I仍按较远的E0结构持有，并继续补仓。统一快退出又会损伤大赢家。</strong><p>407科技股、11行业，2024初至2026-10-26；14方案×3情景，共42条独立100万元有限复利路径。各方案是同一资金池的替代模拟。当前存续/行业快照开发研究，非样本外；日线开盘成交代理，无历史分钟数据。</p><p>目前值得保留的取舍是SHADOW20：基础全期收益146.68%，2026H2−19.61%，H2平均仓位10.87%；原I分别139.14%、−39.76%、74.89%。代价是只保留原I截至6月底累计盈利的69.65%，全程最大回撤仍43.92%，未达到20%全程回撤目标。不替换现有基线，不自动实盘。</p><p>持续纸面运行固定原I：影子回撤达到20%关闭交易，回撤回到10%以内恢复；实际账户下一可执行开盘卖出、停止新买。7/13收盘触发、7/14实际清仓，之后未恢复。它是账户风险规则，不是市场趋势算法，也不是实际账户20%硬止损保证。</p><p>前期盈利保留=(方案6月底NAV−100万)/(原I同情景6月底NAV−100万)，不是财富比例。所有失败方案保留；低H2仓位不能掩盖前期错失。</p></section>'''
 reason='''<section><h2>为什么会慢</h2><ol><li>7/2原I持仓90.63%，其中84.66%NAV对应股票已低于暖；7/6剩余79.31%仓位全部低于暖，7/7又补至89.83%。</li><li>源杰6/30收盘距E0支持约44.96%，7/2已冷，7/21实际卖出。支持点不是短线反转线。</li><li>初仓15%不是持续权重上限：原I最高单股49.04%、行业57.35%。</li><li>早退之后又接纳局部反弹。原I闭合尾部贡献282.16万、普通净损耗155.09万；SHADOW20分别196.28万、49.60万。降低普通损耗也牺牲尾部。</li></ol><img src="../diagnostic-v1/account-2026.png"></section>'''
 links='''<section><h2>完整证据</h2><p><a href="../CONCLUSION.md">研究结论</a> · <a href="../RULES.md">第一批规则</a> · <a href="../ROUND2_RULES.md">共同弱化规则</a> · <a href="../ROUND3_RULES.md">影子回撤规则</a> · <a href="../ROUND4_RULES.md">集中损失对照</a> · <a href="../results-final/scoreboard.csv">全部结果CSV</a> · <a href="../results-final/curves.csv">全部逐日净值</a> · <a href="../results-final/h2-attribution.csv">H2损益归因</a> · <a href="../DIAGNOSIS.md">原I逐日诊断</a></p><p>所有历史均已参与开发，未证明跨行情/未来有效。影子必须持续运行，不能看到亏损以后挑选另一条更好的参考净值。全池信号前缀、42执行前缀与3旧控制及独立核账见account-validation-final.json。</p></section>'''
 document='''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>科技账户大跌：算法还是交易策略？</title><style>body{margin:0;background:#f3f5f7;color:#223444;font:15px/1.7 system-ui}main{max-width:1200px;margin:auto;padding:24px}section{background:white;padding:22px;border-radius:12px;margin:16px 0;overflow:auto}h1{font-size:27px}strong{color:#903d29}table{border-collapse:collapse;white-space:nowrap;width:100%;font-variant-numeric:tabular-nums}td,th{text-align:right;padding:7px;border-bottom:1px solid #e4e8ed}td:first-child,th:first-child{text-align:left}img{width:100%;min-width:650px}a{color:#276aa0}</style><main><h1>科技账户大跌：算法还是交易策略？</h1>'''+intro+reason+''.join(sections)+links+'</main>'
 (out/'index.html').write_text(document);print('report built',len(s),'paths')
