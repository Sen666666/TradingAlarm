from study_common import *
import collections,html
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.family']=['Arial Unicode MS','DejaVu Sans']
NAMES={'I':'原I','AMT15':'原跨日换仓','SD':'修复同早盘换仓','SD25':'修复换仓/配对买25bps','IBD':'I仅买延迟','ISD':'I仅卖延迟','IL2':'I两日意图'}
def pct(x):return f'{float(x)*100:.2f}%'
def table(cols,rs):return '| '+' | '.join(cols)+' |\n| '+' | '.join(['---']*len(cols))+' |\n'+''.join('| '+' | '.join(map(str,r))+' |\n' for r in rs)
def main():
 ss=pd.read_csv(HERE/'analysis/summary.csv');cs=pd.read_csv(HERE/'analysis/campaigns.csv');stocks=pd.read_csv(HERE/'analysis/stocks.csv');rots=pd.read_csv(HERE/'analysis/rotations.csv');oldss=pd.read_csv(BASE/'analysis/summary.csv');oldcv=pd.read_csv(BASE/'analysis/curves.csv');cv=pd.read_csv(HERE/'analysis/curves.csv');dd=read(HERE/'old-I-deep-summary.json');ex=read(HERE/'old-I-expiry-summary.json');meta=read(OLD/'inputs-v2/metadata.json')
 funnel=[];stats={}
 for aid in ['SD__S0_base','SD__S0_cost2','SD__S0_delay1','SD25__S0_base']:
  z=rots[rots.account.eq(aid)];actual=z.actual_new_buy_fills.gt(0);funnel.append(dict(account=aid,started=len(z),sold=int(z.sold_at.notna().sum()),actually_bought=int(actual.sum()),partial_bought_then_failed=int((actual&z.status.ne('bought')).sum()),sold_without_buy=int((z.sold_at.notna()&~actual).sum()),unfinished=int(z.status.eq('open').sum()),statuses={str(k):int(v) for k,v in z.status.value_counts().items()}))
 pd.DataFrame(funnel).to_csv(HERE/'analysis/rotation-funnel-v2.csv',index=False)
 for aid in ['SD__S0_base','IL2__S0_base','IL2__S0_delay1','IBD__S0_delay1','ISD__S0_delay1']:
  z=stocks[stocks.account.eq(aid)];stats[aid]=dict(source_profit=float(z.loc[z.symbol.eq('688498.SH'),'net_profit'].sum()),tengjing_profit=float(z.loc[z.symbol.eq('688195.SH'),'net_profit'].sum()),top5=z.nlargest(5,'net_profit')[['symbol','name','net_profit']].to_dict('records'))
 # Exact actual stock profit differences, not a hypothetical reclaimed winner.
 a=stocks[stocks.account.eq('IL2__S0_delay1')].set_index('symbol');b=stocks[stocks.account.eq('I__S0_delay1')].set_index('symbol');x=a[['name','net_profit']].rename(columns={'net_profit':'latch'}).join(b[['net_profit']].rename(columns={'net_profit':'old_delay'}),how='outer');x.name=x.name.fillna(b.name);x[['latch','old_delay']]=x[['latch','old_delay']].fillna(0);x['difference']=x.latch-x.old_delay;x.sort_values('difference',ascending=False).to_csv(HERE/'analysis/IL2-delay-stock-differences.csv')
 # Trace whether original big winners actually got into the bounded-intent group.
 selected=[]
 for row in rows(HERE/'accounts/daily.jsonl.gz'):
  if row['account']=='IL2__S0_delay1' and row['at'][:10] in ['2025-07-02','2025-10-24']:
   selected.append(dict(at=row['at'],positions={meta[s]['name']:q for s,q in row['positions'].items()},pending=[meta[s]['name'] for s in row['pending_buys']],nav=row['nav']))
 write(HERE/'analysis/post-results-v2.json',dict(recorded_at=now(),rotation_funnel=funnel,actual_stock_stats=stats,latch_snapshots=selected))
 groups=[(['I__S0_base','AMT15__S0_base','SD__S0_base','IL2__S0_base'],'基础：同100万元'),(['I__S0_delay1','AMT15__S0_delay1','SD__S0_delay1','IL2__S0_delay1'],'双腿延迟压力')]
 fig,axs=plt.subplots(2,2,figsize=(15,10))
 for j,(ids,title) in enumerate(groups):
  for aid in ids:
   f=cv[cv.account.eq(aid)]
   if f.empty:f=oldcv[oldcv.account.eq(aid)]
   label=NAMES[aid.split('__')[0]];d=pd.to_datetime(f.date);axs[0,j].plot(d,f.nav/1e4,label=label,lw=1.25);axs[1,j].plot(d,-100*f.drawdown,label=label,lw=1.25)
  axs[0,j].set_title(title);axs[0,j].set_ylabel('净值/万元');axs[1,j].set_ylabel('距历史峰值/%')
  for ax in axs[:,j]:ax.legend(fontsize=8);ax.grid(alpha=.2);ax.tick_params(axis='x',rotation=15,labelsize=8)
 fig.tight_layout();fig.savefig(HERE/'comparison.png',dpi=130);plt.close(fig)
 rows1=[]
 for r in ss.itertuples():rows1.append([NAMES[r.policy],r.scenario,pct(r.net_return),f'{r.final_nav/1e4:.2f}',pct(r.max_drawdown),pct(r.mean_exposure),f'{r.fees/1e4:.2f}',r.closed])
 text='# EXE-001修复与I延迟：全部结果\n\n2024-01-02—2026-10-26；407科技股/11行业；独立100万元，原比例复利；9新增机制路径＋3完整恒等控制。日线估算早盘卖后买，不是分钟成交复现。\n\n'+table(['方案','情景','净收益','期末万元','最大回撤','平均仓位','显式费用万元','闭合周期'],rows1)
 text+='\n## 换仓实际漏斗\n\n'+table(['路径','发起','完整卖出','实际换入','卖后零买入','未完成'],[[r['account'],r['started'],r['sold'],r['actually_bought'],r['sold_without_buy'],r['unfinished']] for r in funnel])
 text+='\n修复后新路径重新选择全部机会，并非把原189对平移。235次基础换仓都完成；延迟组未买仍须报告。原跨日42次卖后未买不能机械视为修复后追回42次。\n\n## 净利润来源（万元，成本已含）\n\n'+table(['路径','尾部闭合','普通闭合','开放/权益未结','全部闭合亏损','尾部/全部亏损'],[[r.account,f'{r.tail_profit/1e4:.2f}',f'{r.ordinary_profit/1e4:.2f}',f'{r.open_profit/1e4:.2f}',f'{r.all_closed_losses/1e4:.2f}',f'{r.tail_over_all_losses:.2f}'] for r in ss.itertuples()])
 text+='\n## 原I订单与回撤诊断\n\n'+table(['项','原I基础','原I双腿延迟'],[['预约订单',104,379],['有实际买入订单',102,73],['零买入订单',2,306],['尾部净利润万元','282.16','123.62'],['普通闭合净损益万元','−155.09','−105.78'],['开放/权益净损益万元','+12.07','−14.46']])
 text+=f'\n306次零买入中304次已到期、2次期末待买；已到期中{ex["structure_still_active"]}次I结构仍有效，{ex["warm_active_but_no_fresh_event"]}次仍暖但没有新事件。不能将这些订单都解释为行情判断错误。\n'
 text+='\n原I102次有买入的起源事件，在延迟账户同日：64次结束时被股票/行业容量占用，34次相同起源预约但零成交，2次已持有，2次相同起源成交。分类是决策后资源诊断，不是逐项可加回利润。36个共同股票/决策日起源订单仅2个双方成交，且两次执行时刻相同（等待信用）；不构成同批交易机械晚一天的价格效应样本。\n'
 text+='\n2025-07-02源杰原事件在延迟账户仍合格，但六持股、三行业各两股满；没有源杰买单。原I源杰贡献112.66万元、腾景33.78万元，存在其它抵消；不得将其直接加回。旧逐日快照、所有起源匹配和亏损对照均保留。\n'
 text+='\n最大回撤：原I2026-06-25峰值405.64万至10-26的239.14万，少166.50万；延迟I06-30峰值250.11万至103.37万，少146.73万。百分比回撤更大并不表示同区间金额损失更大。持仓不同，亏损净贡献见old-I-drawdown-contributions.csv。\n'
 (HERE/'RESULTS.md').write_text(text)
 # Compact HTML keeps no build/runtime dependency and links all source reports.
 t='<html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>换仓修复与I延迟归因</title><style>body{font:16px/1.7 -apple-system,sans-serif;max-width:1200px;margin:32px auto;padding:0 24px;color:#233544}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:7px;border-bottom:1px solid #dce3e7;text-align:right}td:first-child,th:first-child{text-align:left}img{width:100%}a{color:#176b7b}pre{white-space:pre-wrap}</style><h1>换仓修复与I延迟归因</h1><p>2024年初—2026-10-26｜407科技股｜每方案一个100万元账户｜日线执行近似</p><p><a href="CONCLUSION.md">完整分析</a> · <a href="RESULTS.md">全部数字</a> · <a href="PROTOCOL.md">冻结规则</a> · <a href="analysis/rotation-funnel-v2.csv">实际换仓</a> · <a href="analysis/summary.csv">结果CSV</a></p><img src="comparison.png"><h2>全部路径</h2>'+ss[['account','net_return','max_drawdown','mean_exposure','fees']].assign(net_return=lambda z:z.net_return.map(pct),max_drawdown=lambda z:z.max_drawdown.map(pct),mean_exposure=lambda z:z.mean_exposure.map(pct),fees=lambda z:z.fees.map(lambda v:f'{v/1e4:.2f}万元')).to_html(index=False,border=0)+'<h2>原始量价与实际参与</h2><img src="overlay-v2.png"><p>原始图先看，成交/事件后叠；已见开发历史，不是未见样本。</p></html>'
 (HERE/'index.html').write_text(t)
 print(ss[['account','net_return','max_drawdown']].to_string(index=False));print(funnel);print(stats)
if __name__=='__main__':main()
