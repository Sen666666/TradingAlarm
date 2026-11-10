from budget_common import *
import html
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

def main():
 a=HERE/'analysis-v2';out=HERE/'report';out.mkdir(exist_ok=False);f=pd.read_csv(a/'curves.csv');s=pd.read_csv(a/'summary.csv').set_index('account');stocks=pd.read_csv(a/'stocks.csv');pairs=pd.read_csv(a/'entry-pairs.csv');scope=read(HERE/'scope.json')['chosen'];font=FontProperties(fname='/System/Library/Fonts/Supplemental/Arial Unicode.ttf');plt.rcParams.update({'font.family':font.get_name(),'axes.unicode_minus':False,'font.size':10})
 fig,axs=plt.subplots(2,2,figsize=(15.5,9.6));colors={'SHARED':'#5279bd','ISOLATED':'#c66532'};labels={'SHARED':'共享现金','ISOLATED':'行业预算隔离'}
 for mode in colors:
  g=f[f.account==mode];ds=pd.to_datetime(g.date)
  axs[0,0].plot(ds,g.nav/1e4,label=labels[mode],color=colors[mode],lw=1.5)
  axs[0,1].plot(ds,100*g.drawdown,label=labels[mode],color=colors[mode],lw=1.1)
  axs[1,0].plot(ds,g.exposure.rolling(21,min_periods=1).mean()*100,label=labels[mode],color=colors[mode],lw=1.2)
 axs[0,0].axhline(100,color='#aaa',ls='--',lw=.8);axs[0,0].set(title='账户净值（万元）：机会相同，只有资金归属不同',ylabel='万元')
 axs[0,1].set(title='最大回撤几乎相同：25.01% / 24.90%',ylabel='距此前净值峰值（%）')
 axs[1,0].set(title='实际股票仓位（21日均值），全期平均27.15% / 26.60%',ylabel='整户NAV占比（%）',ylim=(0,90))
 names={x['symbol']:x['name'] for x in scope};x=np.arange(6)
 for j,mode in enumerate(colors):
  g=stocks[stocks.account==mode].set_index('symbol').reindex([r['symbol'] for r in scope]);axs[1,1].bar(x+(j-.5)*.36,g.pnl/1e4,width=.36,color=colors[mode],label=labels[mode])
 axs[1,1].set_xticks(x,[r['name'] for r in scope]);axs[1,1].axhline(0,color='#777',lw=.8);axs[1,1].set(title='股票累计净贡献：收益改善主要来自斯达半导少亏',ylabel='万元（含费用、分红权益）')
 for ax in axs.flat:ax.grid(alpha=.17);ax.legend(fontsize=9)
 fig.suptitle('BUDGET-O1｜固定六股、原IX、100万元｜2021-01-04—2026-10-16',fontsize=16);fig.text(.5,.012,'当前存续池/市值/行业快照的开发检验；非样本外。两组均按整户NAV的15%初仓，不调算法、不按结果换名单。',ha='center',fontsize=10);fig.tight_layout(rect=(0,.04,1,.96));fig.savefig(out/'comparison.png',dpi=160);plt.close(fig)
 rows=[]
 for mode in colors:
  r=s.loc[mode];rows.append({'方案':labels[mode],'总收益':f'{r.net_return:.2%}','最大回撤':f'{r.max_drawdown:.2%}','平均股票仓位':f'{r.exposure:.2%}','已结束交易':int(r.closed),'胜率':f'{r.win_rate:.2%}','交易费用':f'{r.fees/1e4:.2f}万元'})
 table=pd.DataFrame(rows).to_html(index=False,border=0);st=stocks[stocks.account.isin(colors)].pivot(index=['industry','symbol','name'],columns='account',values='pnl').reset_index();st['差额']=st.ISOLATED-st.SHARED
 for k in ['SHARED','ISOLATED','差额']:st[k]=st[k].map(lambda x:f'{x/1e4:+.2f}万')
 st=st.rename(columns={'industry':'行业','symbol':'代码','name':'股票','SHARED':'共享净贡献','ISOLATED':'隔离净贡献'}).to_html(index=False,border=0)
 top=pairs.assign(name=pairs.symbol.map(names)).sort_values('pnl_difference',ascending=False).head(8)[['name','shared_entry','shared_gross','isolated_gross','shared_pnl','isolated_pnl','pnl_difference']];top.shared_entry=top.shared_entry.str[:10]
 for k in ['shared_gross','isolated_gross','shared_pnl','isolated_pnl','pnl_difference']:top[k]=top[k].map(lambda x:f'{x/1e4:+.2f}万')
 top.columns=['股票','共同入场日','共享买入金额','隔离买入金额','共享净贡献','隔离净贡献','隔离改善'];top=top.to_html(index=False,border=0)
 old=pd.read_csv(a/'old-standalone-six-reference.csv');old=old[old.policy=='IX'][['symbol','net_return','max_drawdown']];old['name']=old.symbol.map(names);old.net_return=old.net_return.map(lambda x:f'{x:+.2%}');old.max_drawdown=old.max_drawdown.map(lambda x:f'{x:.2%}');old.columns=['代码','旧单股IX收益','旧单股IX回撤','股票'];old=old[['股票','代码','旧单股IX收益','旧单股IX回撤']].to_html(index=False,border=0)
 scope_table=pd.DataFrame(scope)[['industry','symbol','name','score']].rename(columns={'industry':'行业','symbol':'代码','name':'股票','score':'2020-12-31 RS-H1'}).to_html(index=False,border=0,float_format=lambda x:f'{x:.2f}')
 body=f'''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BUDGET-O1 现金归属隔离</title><style>body{{font:16px/1.7 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;color:#253246;max-width:1170px;margin:auto;padding:36px 22px;background:#f7f9fc}}h1{{font-size:30px;line-height:1.3}}h2{{margin-top:38px;font-size:22px}}.card{{background:white;padding:20px 26px;border:1px solid #dfe5ed;border-radius:12px;margin:22px 0}}.lead{{font-size:20px}}.muted{{color:#657184;font-size:14px}}table{{border-collapse:collapse;width:100%;font-size:14px;background:white}}th,td{{border-bottom:1px solid #e2e7ed;padding:9px;text-align:right}}th:first-child,td:first-child{{text-align:left}}img{{max-width:100%;height:auto}}a{{color:#245eaf}}details{{margin:20px 0}}summary{{cursor:pointer}}.scroll{{overflow-x:auto}}</style><h1>现金预算隔离有小幅改善，解释不了全市场的大落差</h1><p class="muted">BUDGET-O1 · 固定机会序列的机制定位 · 2021-01-04—2026-10-16 · 仅A股 · 每组100万元</p><div class="card lead">共享现金收益 <b>+2.03%</b>，隔离预算 <b>+4.47%</b>，差 <b>2.44个百分点</b>；最大回撤均约25%。不能据此晋升预算隔离为解决方案。</div><div class="scroll">{table}</div><p>两组316次实际入场时间全部相同，88次买入金额不同。隔离组有34次可明确归因于所属现金不足的预算约束；它减少了部分交易金额，没有产生更好的择时。共享跟踪类关闭约束后，与原金融引擎逐日及完整金融日志100%一致。</p><img src="comparison.png" alt="两账户净值、回撤、仓位及个股贡献"><h2>差额到底来自哪里</h2><p>两组4笔净收益至少30%的已结束交易都贡献 <b>26.58万元</b>；其余312笔合计分别亏 <b>24.55万元</b>、<b>22.11万元</b>。尾部大赢家没有增加，主要是普通交易少亏了2.44万元。斯达半导少亏2.38万元，约占总改善的97.5%；立昂微反而多亏约0.28万元。这种差额不能等同于选股能力提高。</p><div class="scroll">{st}</div><details><summary>展开逐笔差异较大的交易（按改善金额排序，仅作归因）</summary><div class="scroll">{top}</div><p class="muted">净贡献覆盖该次持仓完整周期；并非入场当日已知收益，也不作为筛选规则。</p></details><p>共享组半导体可用现金归属曾低至 <b>−11.77万元</b>，表示该行业动用了其他行业资金；整户真实可用现金始终非负。隔离后各行业不得借款。归属限制生效了，但整户最大回撤只减少0.11个百分点。</p><h2>这对此前全市场失败意味着什么</h2><p>此前“固定三个行业＋独立预算”与“动态补位”同时改变了行业序列和现金归属，不能把大幅收益差全归给预算。本次剥离现金因素后，只看到小幅改善。固定六股共享组的平均仓位约27%，此前全A S0约71%；扩大候选池使空仓期不断被新机会填满，账户承担的机会组合与风险暴露已经改变。这个证据支持继续检查机会选择和补位时机，尚不能把它们各自的因果份额定量拆开。</p><p>同时，“行业指数效果好”不能直接推导“该行业内任何股票效果都好”。复用上轮已存在的单股IX归一化结果，这六股中只有平安银行、广和通为正，两只半导体个股都亏；资金跨行业借用并不是这些弱单股轨迹的唯一来源。</p><details><summary>展开旧单股IX参照（只读复用，非本轮真实账户）</summary>{old}<p class="muted">旧归一化单股算子使用合成持仓、简化费用、开盘保护与期末平仓；真实账户使用原始股数、权益、交易规则和结算。因此仅用于辨认个股信号轨迹，不能与上方真实账户收益直接相减。</p></details><h2>下一步研究重点</h2><p><b>先做“板块信号到个股收益”的桥接拆解。</b>沿相同板块、相同区间与资金合同，分别定位：指数与成分股本身的差异、板块信号与个股信号的差异、板块内排序与晚入补位的差异。先复用事件与成交缓存检查少量因果配对，只有出现可解释的新证据才冻结一个账户对照。当前不启动全市场长矩阵、不添加新的强弱过滤器。</p><p>本次预算隔离保留为独立机制，不晋升、不作唯一解法，也不因一个样本收益为正而宣布全市场问题已解决。该样本仅有固定三个行业六只股票；动态行业选择、换行业时归属预算的传承尚未验证。</p><h2>固定设计与核验</h2><p>2020-12-31在三个行业内按原RS-H1各取前两股，已有源状态准备完成，后续不换名单。当前存续池、当前行业和市值快照仍存在已披露偏差；所有历史均为开发检验。</p>{scope_table}<p>原IX/E0、日有效与未成交重竞、整数股数、费用、权益和T+1均保留。两组单股初仓同为整户净值15%，六槽、每行业最多两股，新增总投入90%；隔离组只增加所属已结算现金约束，没有改成子账户净值决定仓位。保护点开盘缺口差异EXEC-GAP-01没有混入修复。</p><p>2个经济政策＋1个原引擎恒等控制。4200日日账独立重建股数/净值，最大差0元；两条归属账2800日及逐事件独立重算，最大差0元；2800次资格输入相同。物理截断至2023-12-29后，2181行日账和2181行决策与完整历史前缀一致。初次分析字段名错误与测试收据文件已存在错误均保留，没有经济重跑或结果后调参。</p><div class="card"><a href="../PROTOCOL.md">冻结协议</a> · <a href="../scope.csv">六股名单</a> · <a href="../analysis-v2/summary.csv">汇总CSV</a> · <a href="../analysis-v2/entry-pairs.csv">全部入场配对CSV</a> · <a href="../analysis-v2/accounting.json">独立核账</a> · <a href="../technical/prefix.json">前缀核验</a> · <a href="http://127.0.0.1:8795/report/">上一轮诊断</a></div></html>'''
 (out/'index.html').write_text(body)
 print('report written')
if __name__=='__main__':main()
