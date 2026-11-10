from pathlib import Path
import sys,json,hashlib,html
import pandas as pd,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1];sys.path.insert(0,str(HERE/'code'))
from gate_common import SEC,IX,OLD,GROUPS

def main():
 out=HERE/'review';out.mkdir(exist_ok=False);s=pd.read_csv(HERE/'analysis/summary.csv');c=pd.read_csv(HERE/'analysis/campaigns.csv');curves=pd.read_csv(HERE/'analysis/curves.csv');c['net_pnl']=c.net_pnl.astype(float);base=s[s.scenario.eq('base')];comparisons=[];cases=[]
 stock=c[c.scenario.eq('base')].groupby(['group','policy','symbol','name']).agg(net_pnl=('net_pnl','sum'),cycles=('net_pnl','size'),tails=('tail_closed','sum')).reset_index();stock.to_csv(out/'stock-contributions.csv',index=False)
 for group in GROUPS:
  for policy in ['E0','I']:
   a=base[base.group.eq(group)&base.policy.eq(policy)].iloc[0];b=base[base.group.eq(group)&base.policy.eq(policy+'G')].iloc[0]
   comparisons.append(dict(group=group,policy=policy,baseline_return=a.net_return,filtered_return=b.net_return,return_difference=b.net_return-a.net_return,baseline_drawdown=a.max_drawdown,filtered_drawdown=b.max_drawdown,baseline_exposure=a.mean_exposure,filtered_exposure=b.mean_exposure,baseline_closed=a.closed,filtered_closed=b.closed,baseline_tail_pnl=a.tail_pnl,filtered_tail_pnl=b.tail_pnl,baseline_ordinary_pnl=a.ordinary_pnl,filtered_ordinary_pnl=b.ordinary_pnl,baseline_open_pnl=a.open_pnl,filtered_open_pnl=b.open_pnl))
   z=stock[stock.group.eq(group)&stock.policy.isin([policy,policy+'G'])].pivot(index=['symbol','name'],columns='policy',values='net_pnl').fillna(0);z['delta']=z[policy+'G']-z[policy];row=z.loc[z.delta.abs().idxmax()];sid,name=row.name;cases.append(dict(group=group,family=policy,symbol=sid,name=name,baseline_pnl=float(row[policy]),filtered_pnl=float(row[policy+'G']),delta=float(row.delta)))
 pd.DataFrame(comparisons).to_csv(out/'comparisons.csv',index=False);pd.DataFrame(cases).to_csv(out/'largest-stock-differences.csv',index=False)
 fig,axes=plt.subplots(2,2,figsize=(14,9))
 for ax,group in zip(axes.flat,GROUPS):
  for policy,color,style in [('E0','#9c8b5b','--'),('E0G','#c58738','-'),('I','#71879d','--'),('IG','#28624f','-')]:
   q=curves[curves.group.eq(group)&curves.policy.eq(policy)&curves.scenario.eq('base')];ax.plot(pd.to_datetime(q.date),q.nav/1e6,label=policy,color=color,ls=style,lw=1.25)
  ax.set_title(group);ax.set_ylabel('NAV / initial 1,000,000');ax.grid(alpha=.18);ax.legend()
 fig.suptitle('Entry-only EMA9 > EMA21 > EMA50, all rising; exits unchanged');fig.tight_layout();fig.savefig(out/'nav.png',dpi=140);plt.close(fig)
 manifest={x['series_id']:x for x in json.loads((OLD/'prepared-v2/manifest.json').read_text())['series']}
 for case in cases:
  sid=case['symbol'];family=case['family'];group=case['group'];f=pd.read_parquet(IX/'signals'/f'{sid}.parquet').loc['2021-01-04':'2026-10-16'];g=pd.read_parquet(HERE/'facts'/f'{sid}.parquet').loc[f.index];fac=pd.read_parquet(OLD/'prepared-v2'/manifest[sid]['files']['signal']['path'],columns=['adjustment_factor']).adjustment_factor
  fig,(ax,v)=plt.subplots(2,1,figsize=(14,7),sharex=True,gridspec_kw={'height_ratios':[4,1]});ax.plot(f.index,f.close,color='#777',lw=.8,label='Causal close')
  for n,color in [(9,'#216ca7'),(21,'#d98729'),(50,'#7d66ad')]:ax.plot(f.index,g['ema'+str(n)],color=color,lw=.7,alpha=.8,label='EMA'+str(n))
  for policy,color in [(family,'#6e829b'),(family+'G','#20634c')]:
   aid=f'{group}_{policy}_base__S1_base';obj=json.loads((HERE/'accounts'/f'{aid}.json').read_text());buys=[];sells=[]
   for x in obj['audit_log']:
    if x['kind']!='fill' or x['receipt']['security_id']!=sid:continue
    d=pd.Timestamp(x['receipt']['at']).tz_localize(None).normalize();target=buys if x['receipt']['side']=='buy' else sells;target.append((d,float(x['price'])*float(fac.loc[d])))
   for data,marker,label in [(buys,'^','buy'),(sells,'x','sell')]:
    if data:ax.scatter([x[0] for x in data],[x[1] for x in data],marker=marker,color=color,s=30,label=policy+' actual '+label)
  v.bar(f.index,f.volume/1e6,color='#8c9aa4',width=1);v.set_ylabel('Vol / 1e6');ax.set_title(f'{group} {family} {sid} | all actual fills, 2021-2026 | PnL delta CNY {case["delta"]:,.0f}');ax.set_ylabel('Causal price units');ax.legend(fontsize=7,ncol=4)
  for a in [ax,v]:a.grid(alpha=.15)
  fig.tight_layout();fig.savefig(out/f'{group}_{family}_difference.png',dpi=125);plt.close(fig)
 def rd(r):return f'{r.net_return:+.2%} / {r.max_drawdown:.2%}'
 body='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>EMA前置过滤 E0/I｜有限资金对照</title><style>body{font:17px/1.75 system-ui,sans-serif;color:#24384a;max-width:1240px;margin:35px auto;padding:0 22px}h1{line-height:1.35}h2{margin-top:36px}a{color:#1f638a}img{width:100%;height:auto;border:1px solid #e2e6eb}table{border-collapse:collapse;width:100%;font-size:15px}td,th{padding:10px;border-bottom:1px solid #dce3e8;text-align:right;white-space:nowrap}td:first-child,th:first-child{text-align:left}.scroll{overflow:auto}.note{background:#f3f5ef;border-left:5px solid #547a63;padding:18px 22px}.muted{font-size:15px;color:#63727e}</style><h1>均线排列作为E0/I入场前置过滤</h1><p class="note"><b>不采用通用硬过滤。</b>唯一条件为EMA9＞21＞50且三线均上行，只限新买、退出不变。I四池累计收益全部下降；E0只有半导体收益与回撤同时改善。四池固定开发历史，不是全市场或样本外。</p><p><a href="../CONCLUSION.md">完整结论</a> · <a href="../PROTOCOL.md">冻结协议</a> · <a href="../analysis/summary.csv">全部结果CSV</a> · <a href="../analysis/accounting.json">独立核账</a> · <a href="../technical/prefix-identity.json">真实前缀</a> · <a href="../DAILY_ADAPTATION_FOR_REVIEW.md">视频日线适配草案（另一支线）</a></p><h2>基础结果：累计收益 / 最大回撤</h2><div class="scroll"><table><tr><th>股票池</th><th>原E0</th><th>E0＋EMA</th><th>原I</th><th>I＋EMA</th></tr>'''
 for group,(label,_) in GROUPS.items():
  body+='<tr><td>'+label+'</td>'+''.join('<td>'+rd(base[base.group.eq(group)&base.policy.eq(p)].iloc[0])+'</td>' for p in ['E0','E0G','I','IG'])+'</tr>'
 body+='</table></div><img alt="完整净值比较" src="nav.png"><h2>全部试错与尾部</h2><p>闭合净回报≥30%仅是尾部分类，非止盈线。所有损益已扣费用；尾部与全部亏损比较，和尾部＋普通净损益＋开放权益的账户口径分开。</p>'
 view=base[['group','policy','closed','win_rate','tail_count','tail_pnl','ordinary_pnl','open_pnl','all_loss','tail_to_all_loss']]
 body+='<div class="scroll">'+view.to_html(index=False,border=0,float_format=lambda x:f'{x:,.4f}')+'</div><p>旧I738周期固定路径筛查拦下374个，其中含72原尾部中的39个；实际资金会换入其他机会，不能把删单后的旧金额当新账户预测。半导体I闭合158→155而非少一半，尾部笔数21→24但尾部金额反降。</p><h2>双成本压力</h2><div class="scroll">'+s[s.scenario.eq('cost2')][['group','policy','net_return','max_drawdown','mean_exposure','closed','tail_pnl','ordinary_pnl','open_pnl']].to_html(index=False,border=0,float_format=lambda x:f'{x:,.4f}')+'</div><h2>实际成交复查：每池每族损益差最大股票</h2><p class="muted">这些股票按结果机械选出，只解释差异，不改规则。每张包含全期所有实际买卖，损益差包含资金数量与占位变化，不是单纯均线时机效应。</p>'
 for z in cases:body+=f'<h3>{GROUPS[z["group"]][0]} · {html.escape(z["name"])} · {z["family"]}族</h3><p>原净贡献{z["baseline_pnl"]/1e4:+.2f}万，过滤后{z["filtered_pnl"]/1e4:+.2f}万。</p><img loading="lazy" src="{z["group"]}_{z["family"]}_difference.png">'
 body+='<h2>经济前12固定窗的门槛图检</h2><p>红叉/绿三角为原I信号是否被挡，非实际成交。原始OHLCV选样与先前视频图检相同，没有按本轮收益换样。</p><img loading="lazy" src="../charts/contact-1.png"><img loading="lazy" src="../charts/contact-2.png"><h2>边界与核验</h2><p>2021-01-04—2026-10-16，每户100万元；原15%初仓、六槽/90%、行业E0/RS-H1、T+1及费用不变。24路径含4旧I控制和20新增经济；33,600日账独立重建差0元，16真实截断11,632日账/决策一致。经济一次，结果后改规则0，不自动放宽门槛或续跑。</p><p>视频日线适配是独立待审设计：已完成日K的高点作次日触发、低点作止损，并明确日内顺序歧义。没有用这轮过滤账户替代视频策略回测。</p></html>'
 (out/'index.html').write_text(body)
 with (out/'receipt.json').open('x') as f:json.dump(dict(passed=True,new_economic_runs=0,new_rules=0,actual_difference_cases=8,posthoc_cases=True,code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),f,indent=2)
 print(pd.DataFrame(cases).to_string(index=False),flush=True)

if __name__=='__main__':main()
