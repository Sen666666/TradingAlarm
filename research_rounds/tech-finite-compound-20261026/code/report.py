"""Post-result comparisons and figures. Does not change or rerun decisions."""
from common import *
from decimal import Decimal as D
import collections,csv,html
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

NAMES={'E0':'E0原趋势','I':'I趋势持有','IX':'IX敏感退出','RB1':'RB1风险定仓','H50':'H50固定半仓','BH':'BH起点持有','AMT15':'成交额1.5倍换仓'}
ORDER=list(NAMES)
def table(headers,rs):return '| '+' | '.join(headers)+' |\n| '+' | '.join(['---']*len(headers))+' |\n'+''.join('| '+' | '.join(map(str,r))+' |\n' for r in rs)
def pct(v):return f'{float(v):.2%}'
def money(v):return f'{float(v)/1e4:.2f}'

def background(curves):
 dates=pd.DatetimeIndex(sorted(curves.date.unique()));paths=sorted((PREP/'facts').glob('*.parquet'));records={r['series_id']:r for r in read(CORE/'manifest.json')['series']};arrays=[]
 for p in paths:
  if records[p.stem]['kind']!='stock':continue
  f=pd.read_parquet(p);prior=f.loc[:'2023-12-29','close'];series=f.close.reindex(f.index.union(dates)).sort_index().ffill().reindex(dates)
  if len(prior):base=float(prior.iloc[-1]);a=series/base
  else:
   first=f.index[0];base=float(f.close.iloc[0]);a=series/base;a.loc[a.index<first]=1
  arrays.append(a.fillna(1).to_numpy(float))
 assert len(arrays)==407;z=np.mean(arrays,axis=0);df=pd.DataFrame(dict(date=dates,normalized_price=z));df.to_csv(HERE/'analysis/pool-price-background.csv',index=False)
 return df

def risk_review(camps):
 rs=[]
 for scenario in ['base','cost2','delay1']:
  aid='RB1__S0_'+scenario;obj=read(HERE/'accounts-v2'/f'{aid}.json');intents={r['order_id']:r for r in obj['audit_log'] if r['kind']=='entry_contract'};entries={}
  for r in obj['audit_log']:
   if r['kind']=='fill' and r['receipt']['side']=='buy':f=r['receipt'];entries.setdefault((f['security_id'],f['at']),intents[r['order_id']])
  cc=camps[camps.account.eq(aid)&camps.closed.astype(bool)];losses=[]
  for c in cc.itertuples():
   if c.net_pnl>=0:continue
   z=entries[(c.symbol,c.entry_at)];losses.append(dict(account=aid,symbol=c.symbol,name=c.name,entry_at=c.entry_at,exit_at=c.exit_at,net_loss=-c.net_pnl,entry_risk_budget=float(z['risk_budget']),loss_R=-c.net_pnl/float(z['risk_budget'])))
  for l in losses:rs.append(l)
 pd.DataFrame(rs).to_csv(HERE/'analysis/risk-realized-losses.csv',index=False);return rs

def swap_review(rot,stocks,camps):
 facts={};meta=read(OLD/'inputs-v2/metadata.json');reasons=[];summary=[]
 for r in rot.itertuples():
  if r.status not in ['candidate_invalid_after_sale','candidate_invalid_while_waiting']:continue
  day=str(r.sold_at)[:10] if r.status=='candidate_invalid_after_sale' else None
  if day is None:
   log=read(HERE/'accounts-v2'/f'{r.account}.json')['audit_log'];end=next(x for x in log if x['kind']=='rotation_finished' and x['rotation']['id']==r.id);day=end['at'][:10]
  if r.candidate not in facts:facts[r.candidate]=pd.read_parquet(PREP/'facts'/f'{r.candidate}.parquet')
  f=facts[r.candidate];q=f.loc[:day].iloc[-1]
  why='I结构已失效' if not q.i_target else '强度未准备' if not q.g_ready else '温度退至暖以下' if q.g_grade<2 else '行业/交易/排名继续资格失效'
  reasons.append(dict(account=r.account,scenario=r.scenario,id=r.id,candidate=r.candidate,name=meta[r.candidate]['name'],day=day,reason=why,actual_new_buy_fills=r.actual_new_buy_fills))
 pd.DataFrame(reasons).to_csv(HERE/'analysis/rotation-invalid-reasons.csv',index=False)
 for scenario in ['base','cost2','delay1']:
  z=rot[rot.scenario.eq(scenario)];cycles=camps[camps.account.eq('AMT15__S0_'+scenario)];actual=z.actual_new_buy_fills.gt(0);profit=0.
  for r in z.loc[actual].itertuples():
   cc=cycles[cycles.symbol.eq(r.candidate)&cycles.entry_at.eq(r.first_new_buy_at)];assert len(cc)==1;profit+=float(cc.net_pnl.iloc[0])
  summary.append(dict(scenario=scenario,started=len(z),sold=int(z.sold_at.notna().sum()),actually_bought=int(actual.sum()),partly_bought_then_invalid=int((actual&z.status.ne('bought')).sum()),sold_without_buy=int((z.sold_at.notna()&~actual).sum()),unfinished=int(z.status.eq('open').sum()),new_position_cycle_profit=profit))
 pd.DataFrame(summary).to_csv(HERE/'analysis/rotation-funnel.csv',index=False)
 return summary,reasons

def winner_gap_case(camps):
 cs=camps[camps.account.eq('I__S0_base')&camps.symbol.eq('688498.SH')];c=cs.sort_values('net_pnl',ascending=False).iloc[0];obj=read(HERE/'accounts-v2/I__S0_base.json');fill=next(r for r in obj['audit_log'] if r['kind']=='fill' and r['receipt']['side']=='buy' and r['receipt']['security_id']==c.symbol and r['receipt']['at']==c.entry_at);intent=next(r for r in obj['audit_log'] if r['kind']=='entry_contract' and r['order_id']==fill['order_id']);day=intent['decision_at'][:10]
  # At that same observed close, inspect actual AMT portfolio and locked pair.
 ds=next(r for r in rows(HERE/'accounts-v2/daily.jsonl.gz') if r['account']=='AMT15__S0_base' and r['at'][:10]==day);de=next(r for r in rows(HERE/'accounts-v2/decisions.jsonl.gz') if r['account']=='AMT15__S0_base' and r['at'][:10]==day);meta=read(OLD/'inputs-v2/metadata.json');case=dict(stock='688498.SH',I_entry=c.entry_at,I_exit=c.exit_at,I_cycle_profit=float(c.net_pnl),signal_day=day,AMT_originally_eligible=c.symbol in de['eligible'],AMT_positions=[dict(symbol=s,name=meta[s]['name'],industry=meta[s]['industry'],shares=n) for s,n in ds['positions'].items()],AMT_pending_buys=ds['pending_buys'],AMT_swap=de['swap'],AMT_ever_bought=False)
 amt=read(HERE/'accounts-v2/AMT15__S0_base.json');case['AMT_ever_bought']=any(f['security_id']==c.symbol and f['side']=='buy' for f in amt['fills']);write(HERE/'analysis/source-winner-gap.json',case);return case

def main():
 out=HERE/'analysis';s=pd.read_csv(out/'summary.csv');curves=pd.read_csv(out/'curves.csv');annual=pd.read_csv(out/'annual.csv');stocks=pd.read_csv(out/'stocks.csv');camps=pd.read_csv(out/'campaigns.csv');rot=pd.read_csv(out/'rotations.csv');base=s[s.scenario.eq('base')].set_index('policy').loc[ORDER].reset_index();risk=risk_review(camps);funnel,reasons=swap_review(rot,stocks,camps);case=winner_gap_case(camps);bg=background(curves)
 plt.rcParams['font.family']=['Arial Unicode MS','DejaVu Sans'];colors=dict(zip(ORDER,plt.cm.tab10.colors[:7]));fig,axes=plt.subplots(3,1,figsize=(14,11),sharex=True)
 for mode in ORDER:
  q=curves[curves.policy.eq(mode)&curves.scenario.eq('base')];dt=pd.to_datetime(q.date);axes[0].plot(dt,q.nav/1e6,label=NAMES[mode],color=colors[mode]);axes[1].plot(dt,q.drawdown*100,label=NAMES[mode],color=colors[mode]);axes[2].plot(dt,q.market_value/q.nav*100,label=NAMES[mode],color=colors[mode],alpha=.8,lw=.8)
 axes[0].plot(bg.date,bg.normalized_price,color='#555',ls='--',lw=1,label='407池复权价格背景（非账户）');axes[0].set_ylabel('净值倍数（初始100万）');axes[1].set_ylabel('最大峰值回撤路径（%）');axes[1].invert_yaxis();axes[2].set_ylabel('股票市值/NAV（%）')
 for ax in axes:ax.grid(alpha=.2);ax.legend(ncol=4,fontsize=8)
 fig.suptitle('科技股有限复利账户｜2024—2026-10-26｜基础情景');fig.tight_layout();fig.savefig(HERE/'comparison.png',dpi=140);plt.close(fig)
 fig,ax=plt.subplots(figsize=(10,7))
 for r in base.itertuples():ax.scatter(r.max_drawdown*100,r.net_return*100,s=80+200*r.mean_exposure,color=colors[r.policy]);ax.annotate(NAMES[r.policy],(r.max_drawdown*100,r.net_return*100),xytext=(6,6),textcoords='offset points')
 ax.set_xlabel('最大回撤（%，越低越好）');ax.set_ylabel('累计净收益（%）');ax.grid(alpha=.2);ax.set_title('相同100万元本金的收益与风险');fig.tight_layout();fig.savefig(HERE/'return-risk.png',dpi=140);plt.close(fig)
 text='# 科技有限复利与成交额换仓：完整结果\n\n2024首交易日—2026-10-26，各账户100万元，407股/11行业，三行业各最多两股、总六股。2023-12-29只作初始预约，不继承旧持仓。本轮21个有效路径，原始数据已补尾；当前存续、市值/行业快照开发偏差及日线成交代理保留，非样本外。\n\n'
 text+=table(['方案','期末万元','累计收益','年化','最大回撤','平均仓位','费用万元','闭合笔数','闭合胜率'],[[NAMES[r.policy],money(r.final_nav),pct(r.net_return),pct(r.cagr),pct(r.max_drawdown),pct(r.mean_exposure),money(r.fees),r.closed,'—' if pd.isna(r.win_rate) else pct(r.win_rate)] for r in base.itertuples()])
 text+='\n复利由每次新买随当时NAV伸缩实现；持仓自然增长，不每日等权。收益分母始终是初始100万元，非峰值持仓或事后反推资金。全部费用/滑点已计入，期末不强平。BH无闭合交易，全部利润为开放持仓/权益，不能把胜率记成100%。\n\n## 全部执行情景\n\n'
 text+=table(['方案','情景','累计收益','最大回撤','平均仓位','费用万元'],[[NAMES[r.policy],r.scenario,pct(r.net_return),pct(r.max_drawdown),pct(r.mean_exposure),money(r.fees)] for r in s.itertuples()])
 text+='\n双成本只对原指定可变费率/滑点加倍；延迟为多一次可执行事件，并含日有效、重竞和等待信用，交易集合会变化。换仓两条腿有独立短期承接合同，因此延迟组优势不能单独归给成交额指标。\n\n## 年度收益\n\n2026截至10月26日；各年起点为上一年底真实NAV，收益不能相加。\n\n'
 year=annual[annual.scenario.eq('base')].pivot(index='policy',columns='year',values='net_return')
 text+=table(['方案','2024','2025','2026至今'],[[NAMES[p],*[pct(year.loc[p,y]) for y in [2024,2025,2026]]] for p in ORDER])
 text+='\n## 全部试错与大赢家\n\n单位万元。尾部为已闭合扣费回报≥30%的周期，30%不是止盈。\n\n'
 text+=table(['方案','尾部净利润','普通闭合净损益','未闭合净损益','全部闭合亏损','尾部/全部亏损'],[[NAMES[r.policy],money(r.tail_profit),money(r.ordinary_profit),money(r.open_profit),money(r.all_closed_losses),'—' if pd.isna(r.tail_over_all_losses) else f'{r.tail_over_all_losses:.2f}'] for r in base.itertuples()])
 text+='\n总净利润＝尾部＋普通＋未闭合；所有亏损是负交易金额之和，区别于普通净损耗。原I、RB1尾部可单独覆盖全部闭合亏损；换仓组尾部仍大，但不足单独覆盖所有负交易，普通盈利与未结也必须一并计入。费用已含，不再重复扣。\n\n## 换仓真实漏斗\n\n'
 text+=table(['情景','发起','完整卖出','发生实际换入','其中部分换入后失效','卖出未买','期末未完成','换入周期实际净贡献万元'],[[r['scenario'],r['started'],r['sold'],r['actually_bought'],r['partly_bought_then_invalid'],r['sold_without_buy'],r['unfinished'],money(r['new_position_cycle_profit'])] for r in funnel])
 text+='\n换入周期贡献包含这些实际持仓的后续退出/再换与期末估值，不是相对原I的增量收益。期末未完成不冒充失败或已成交。部分换入后失效也有真实股份，不能从实际换入数删除。\n\n卖出后/等待中失效原因（次数，可区分是否已有部分成交）：\n\n'
 counts=collections.Counter((r['scenario'],r['reason'],int(r['actual_new_buy_fills'])>0) for r in reasons)
 text+=table(['情景','首先失效条件','已有实际部分买入','次数'],[[a,b,'是' if c else '否',n] for (a,b,c),n in sorted(counts.items())])
 text+='\n卖后仍须暖以上，是本轮先卖后买承接约定之一，失效不等于原始成交额比较有误。若未来研究承接合同，应另作单一对照，不在本轮结果后放宽。\n\n## 风险预算与实际损失\n\n1%为首仓名义失效预算，不能保证整笔只亏1%、更不能保证整户回撤20%以内。\n\n'
 text+=table(['情景','闭合亏损周期','损失>1R周期','最大损失R','亏损周期损失R中位数'],[[sc,len(rr),sum(r['loss_R']>1+1e-8 for r in rr),f'{max((r["loss_R"] for r in rr),default=0):.2f}',f'{np.median([r["loss_R"] for r in rr]):.2f}'] for sc in ['base','cost2','delay1'] for rr in [[r for r in risk if r['account'].endswith(sc)]]])
 text+='\n实际成交时的名义预算已经独立逐笔核验；后续收盘确认退出、开盘跳空、T+1、相关股票连续试错会带来超额和累计回撤。\n\n## 固定本轮I贡献最大的十股\n\n单位万元，事后名单只作归因，不参与选股。缺席记0，不把未来涨幅补成收益。\n\n'
 st=stocks[stocks.scenario.eq('base')].pivot_table(index=['symbol','name'],columns='policy',values='net_profit',aggfunc='sum',fill_value=0);top=st.nlargest(10,'I')
 text+=table(['代码','名称','I','RB1','H50','换仓组'],[[idx[0],idx[1],*[money(r.get(p,0)) for p in ['I','RB1','H50','AMT15']]] for idx,r in top.iterrows()])
 text+=f'\n源杰科技实际缺口证据：原I最赚钱周期{case["I_entry"][:10]}起，贡献{money(case["I_cycle_profit"])}万元；换仓组全期从未实际买入该股，不能描述为“买到后被换走”。同一信号日{case["signal_day"]}的实际占位与锁定意图见analysis/source-winner-gap.json。全期股票贡献还受金额、后续选择和资金路径影响，不是单一换仓动作的纯因果效果。\n\n'
 text+='## 参照与核验\n\nBH起点名单由2023末已知排名固定：'+ '、'.join(x['name'] for x in read(HERE/'benchmark.json')['stocks'])+'。它是可成交六股参照，不代表整个科技行业。\n\n'
 text+=f'407池复权价格背景期末为初始{bg.normalized_price.iloc[-1]:.4f}倍；它使用因果复权价格，非税费/支付日完整总回报。源起点晚于2023末的股票在有源价格前对应份额保持1；首次源价格作其参考原点。它不是100万元可以按整手复制的407股账户，也不能用于声称严格同风险超额。\n\n'
 text+='21有效路径14280日账独立核账净值最大差0元；原价/股份/权益/费用/T+1、首仓与名义风险、成交额和配对身份核验通过。2024年末七base真实执行前缀与首轮截至2026-10-22的21路径完整修复前缀精确一致。首轮费用表末端覆盖不足失败保留，同参经济重跑一次；只延覆盖日期，不改费率或策略参数。详见EXECUTION_BOUNDARY_REPAIR.md与TECHNICAL_FAILURES.md。\n'
 (HERE/'RESULTS.md').write_text(text)
 write(HERE/'post-result-summary.json',dict(base=base.to_dict('records'),rotation_funnel=funnel,rotation_invalid_reason_counts=[dict(scenario=a,reason=b,had_partial_buy=c,count=n) for (a,b,c),n in sorted(counts.items())],pool_price_background_final=float(bg.normalized_price.iloc[-1])))
 page='<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>科技有限复利与成交额换仓</title><style>body{font:16px/1.75 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;max-width:1250px;margin:30px auto;padding:0 20px;color:#203047;background:#f7f9fc}table{border-collapse:collapse;background:white;width:100%;font-size:14px}th,td{padding:9px;border-bottom:1px solid #ddd;text-align:right}th:first-child,td:first-child{text-align:left}img{max-width:100%;height:auto}.scroll{overflow:auto}a{color:#2264a7}.note{background:#fff5dc;padding:15px;border-radius:8px}</style><h1>科技股有限复利与成交额换仓</h1><p>2024—2026-10-26 · 407股 · 每户100万元 · 21条有效路径</p><p class="note">I基础收益139.14%/回撤41.05%；风险定仓62.20%/34.01%优于固定半仓37.89%/39.26%。成交额换仓109.47%/50.19%，基础更差、延迟情景改善，尚不稳定。所有基础组回撤均超过20%。</p><p><a href="CONCLUSION.md">研究结论</a> · <a href="RESULTS.md">完整结果与归因</a> · <a href="PROTOCOL.md">规则</a> · <a href="analysis/summary.csv">21情景CSV</a> · <a href="analysis/rotations.csv">逐对换仓</a></p><img src="comparison.png" alt="净值回撤暴露"><h2>基础情景</h2><div class="scroll">'+base[['policy','final_nav','net_return','max_drawdown','mean_exposure','fees']].to_html(index=False,float_format=lambda v:f'{v:.4f}')+'</div><h2>全部三情景</h2><div class="scroll">'+s[['policy','scenario','net_return','max_drawdown','mean_exposure','fees']].to_html(index=False,float_format=lambda v:f'{v:.4f}')+'</div><img src="return-risk.png" alt="收益与回撤"><p>表内小数收益/回撤/暴露乘100为百分比；金额为元。当前存续/分类/市值快照历史开发研究，非样本外；日线成交为声明代理。首次费用边界失败已保留，同参修复重跑一次，全部独立核账及前缀通过，无实盘。</p></html>'
 (HERE/'index.html').write_text(page);print('post-result report complete',flush=True)
if __name__=='__main__':main()
