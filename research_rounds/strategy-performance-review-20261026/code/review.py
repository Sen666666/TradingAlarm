"""Read-only cross-study scorecard; no model/account recomputation."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,math
import pandas as pd
import numpy as np

HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1]
SOURCES={}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def csv(path):
 p=ROOT/path;SOURCES[path]=sha(p);return pd.read_csv(p)
def js(path):
 p=ROOT/path;SOURCES[path]=sha(p);return json.loads(p.read_text())
def pct(x):return '—' if pd.isna(x) else f'{x:+.2%}'
def rd(r):return f'{r.net_return:+.2%} / {abs(r.max_drawdown):.2%}'
def table(headers,rows):
 return '| '+' | '.join(headers)+' |\n| '+' | '.join(['---']*len(headers))+' |\n'+''.join('| '+' | '.join(map(str,r))+' |\n' for r in rows)

def main():
 out=HERE/'tables';out.mkdir(exist_ok=False);groupnames={'SEMI':'半导体126股','COMM':'通信设备43股','DRUG':'创新药48股','BANK':'银行39股'}
 # Canonical fixed-stock-pool matrix, deduplicating repeated I controls.
 inputs=[('research_rounds/ema-gate-e0-i-20261026/analysis/summary.csv','gate'),('research_rounds/a-share-local-entry-reentry-20261026/analysis-v1/summary.csv','local'),('research_rounds/sector-ix-i-20261026/analysis-v2/summary.csv','sector')]
 stocks=[]
 for path,kind in inputs:
  d=csv(path)
  for _,r in d.iterrows():
   stocks.append(dict(group=r.group,policy=r.policy,scenario=r.get('scenario','base'),net_return=r.net_return,max_drawdown=r.max_drawdown,exposure=r.get('mean_exposure',r.get('exposure',np.nan)),source=path,source_account=r.account))
 d=pd.DataFrame(stocks)
 for key,g in d.groupby(['group','policy','scenario']):
  assert g.net_return.max()-g.net_return.min()<1e-11,key
  assert g.max_drawdown.max()-g.max_drawdown.min()<1e-11,key
 d=d.drop_duplicates(['group','policy','scenario']);assert len(d)==52
 d.to_csv(out/'fixed-stock-pools-all-scenarios.csv',index=False);base=d[d.scenario.eq('base')];assert len(base)==28
 # Native single-asset policies: duplicate E0 controls are verified, not new evidence.
 one=[]
 for path,kind in [('research_rounds/strategy-switching-20261024/results/v0/summary.csv','switch'),('research_rounds/b5-g1-20261025/summary.csv','G1'),('research_rounds/r1-structural-reentry-20261024/results/v0/R1-summary.csv','R1')]:
  z=csv(path).copy();z['policy']=z.policy.replace({'G1_I':'I','G1_X':'X','G1_IX':'IX'});z['source']=path
  one.append(z[['case','symbol','name','role','start','end','policy','scenario','net_return','max_drawdown','exposure_fraction','source']])
 singles=pd.concat(one,ignore_index=True)
 for key,g in singles.groupby(['case','policy','scenario']):
  assert g.net_return.max()-g.net_return.min()<1e-10,key
  assert g.max_drawdown.max()-g.max_drawdown.min()<1e-10,key
 singles=singles.drop_duplicates(['case','policy','scenario']);assert len(singles)==702
 singles.to_csv(out/'single-assets-all-policies.csv',index=False)
 continuous=singles[singles.role.eq('continuous_check')&singles.scenario.eq('base')];assert len(continuous)==91
 continuous.to_csv(out/'single-assets-continuous-base.csv',index=False)
 means=singles.groupby(['role','scenario','policy']).agg(case_count=('case','size'),case_mean_return=('net_return','mean'),case_mean_drawdown=('max_drawdown','mean'),case_mean_exposure=('exposure_fraction','mean')).reset_index();means['not_portfolio_performance']=True;means.to_csv(out/'case-means-not-a-portfolio.csv',index=False)
 # Current broad-universe results, keeping legacy execution explicitly separate.
 broad=[]
 for path,study in [('research_rounds/rs-h1-execution-20261025/analysis-v2/summary.csv','E0_corrected_execution'),('research_rounds/ix-a-share-entry-20261025/analysis/summary.csv','IX_entry_variants'),('research_rounds/selection-rotation-abcd-20261025/analysis/summary.csv','rotation_ABCD'),('research_rounds/a-share-selection-e0-20261024/analysis-v2/summary.csv','E0_legacy_execution')]:
  z=csv(path)
  for _,r in z.iterrows():
   aid=r.account;scenario=r.get('scenario',aid.split('_')[-1]);scheme=r.get('entry_scheme',r.get('scheme','E0'));allocation=r.get('allocation','S0' if study=='rotation_ABCD' else aid.split('_')[0])
   broad.append(dict(study=study,policy=scheme,allocation=allocation,scenario=scenario,net_return=r.net_return,max_drawdown=r.max_drawdown,exposure=r.get('mean_exposure',np.nan),source=path,account=aid))
 broad=pd.DataFrame(broad);broad.to_csv(out/'broad-universe-all-scenarios.csv',index=False)
 # Early inventory is a separate, older engine and universe.
 model=js('TradingAlarm/research/results/trend-model-inventory/model-summary.json');pd.DataFrame(model).to_csv(out/'legacy-63-model-summary.csv',index=False)
 inv=csv('TradingAlarm/research/results/broad-shared-first-cross/summary.json') if False else js('TradingAlarm/research/results/broad-shared-first-cross/summary.json')
 oldp=ROOT/'TradingAlarm/research/results/trend-model-inventory/unique-cases.parquet';SOURCES[str(oldp.relative_to(ROOT))]=sha(oldp);legacy=pd.read_parquet(oldp);legacy.to_csv(out/'legacy-378-deduplicated-cases.csv',index=False)
 graded=js('TradingAlarm/research/results/strength-graded-exposure/results.json');graded=[r for r in graded if r['strategy']=='graded_pairwise_volume' and r['scenario']=='base']
 gold=csv('research_rounds/gold-czsc-backtest-20261024/results/v0/summary.csv');gold.to_csv(out/'gold-czsc-special-only.csv',index=False)
 protocol=js('TradingAlarm/research/results/broad-shared-first-cross/protocol.json')
 # Dataset registry makes incompatible scopes explicit.
 datasets=[dict(id='STOCK4',assets='半导体126/通信设备43/创新药48/银行39，共256只当前合格A股',period='2021-01-04—2026-10-16',engine='100万元独立共享资金账户；15%初仓、六槽/90%、RS-H1；原行业E0',limits='当前存续/市值/行业快照开发偏差；日线成交代理；不是全市场'),
 dict(id='SINGLE18',assets='512480半导体ETF、510300沪深300ETF、518880黄金ETF；中电、恒隆、京东、恒科ETF',period='7个2021-01-01—2026-10-16连续窗；另11主场景，2026场景止10-23',engine='每标的单独初始1、多头/现金、分数份额、统一费率/滑点、期末行政清算',limits='18窗重叠，非独立样本；ETF/港股统一价格代理，非四池100万元金融账户'),
 dict(id='A1709',assets='1709只当前市值合格A股＋2未知记录、90行业；原始股票池5576',period='2015首可用日—2026-10-22',engine='T0/T1/S0/S1各100万元；原E0行业/个股、RS-H1、六槽等',limits='当前存续/分类/市值开发偏差；I尚无同范围资金检验；旧执行与修正执行分开'),
 dict(id='LEGACY24',assets='ETF17与港股7两个固定小池',period='2022-01-03—2026-10-16',engine='早期equal_capital/分档仓位等协议；两个池独立、三压力情景',limits='不能与当前股票池直接排名；大量现金；378唯一case来自63名字/61路径指纹，不是独立OOS'),
 dict(id='A485',assets='500候选中通过检验的485只存续A股；相关性代理板块',period=protocol['start']+'—'+protocol['end'],engine='旧分数股/合成充裕流动性代理，9槽，group_gate_cap',limits='代理行业并非真实行业；缺真实手数/涨跌停/权息完整链；非当前1709全池'),
 dict(id='AU0_CZSC',assets='沪金主连AU0，CZSC1.0.2均线辅助买点',period='2025-01-02—2026-10-13',engine='1倍名义敞口连续价格代理，无真实保证金/整数手/逐合约换月',limits='只一项专项，不能外推到A股或原生缠论全体'),
 dict(id='FACT_ONLY',assets='B4/B5/RC1、B5-M1、I-RB1、VEMA-Q1/D1',period='各冻结/设计记录',engine='事实核、轨迹诊断或尚待审设计',limits='无对应独立资金收益，不将其他策略收益贴到这些名称')]
 pd.DataFrame(datasets).to_csv(out/'dataset-registry.csv',index=False)
 # Human-readable judgment, with rankings based on use-case rather than peak return.
 text='''# 当前趋势算法与交易策略综合评价（2026-10-26）

本次只复核已有结果，未重跑任何资金账户、没有新取数或调整策略。**没有已经验证成熟、可通用的全市场冠军。按当前“捕捉稀疏大赢家”的目标，I是股票组合优先研究候选，E0是最重要的结构持有基座；IX/X是有明确局部优势和反例的风险对照。早期分档量价仓位适合作低回撤参照，但收益小且现金多。**

所有收益均是相应区间累计净收益，非年化、非实盘。不能把不同资产池、日期或引擎的最大值直接排总榜，也不能按各板块事后择优拼成一个从未回测的组合。固定场景均值不是组合收益或组合回撤。

## 优先保留哪几个

|算法/政策|当前评价|已验证的主要范围|主要限制|
|---|---|---|---|
|I：G1入场＋E0持有|股票组合尾部捕捉优先候选|四固定池256股；7标的18窗单资产|四池回撤仍大；I还没有同口径1709股全市场资金结果|
|E0：量价结构持有|核心基座，保留长趋势的重要对照|7标的18窗、四固定池、1709股全市场|长期下跌与全市场持续补位会累积大损耗；不是通用成功策略|
|IX：增强入场＋敏感退出/恢复|半导体ETF收益/风险折中线索|7标的18窗、四固定池、全市场四分配/四入场变体|黄金等长趋势损伤；全市场基础失败|
|X：原入口＋G1敏感退出|特定单标的回撤控制参照|7标的18窗|主要伴随低暴露；黄金明显漏趋势，尚无四池/全市场同口径资金验证|
|graded_pairwise_volume：早期分档量价仓位|低回撤小池参照|ETF17、港股7，各三情景|平均约70%现金，累计收益小；不满足尾部主导的强证据|

## 一、当前四固定股票池：同范围可直接比较

2021-01-04—2026-10-16，每户100万元；单股首次15%、六槽、新增90%，原行业E0和RS-H1。每格为累计收益/最大回撤。不是全市场，不是一个四行业合成组合。

'''
 policies=['I','E0','IX','LH','LER','IG','E0G']
 rows=[]
 for policy in policies:
  row=[policy]
  for group in groupnames:
   q=base[base.policy.eq(policy)&base.group.eq(group)];assert len(q)==1;row.append(rd(q.iloc[0]))
  rows.append(row)
 text+=table(['政策']+list(groupnames.values()),rows)
 text+='''
I在半导体、通信设备、创新药三池优于同期原E0，银行则E0更好；这是事后评价，不授权按板块择优实盘。I目前最强的收益证据是通信设备+492.84%、半导体+205.89%，但48.68%和68.86%的回撤远大于20%研究目标。不能仅报收益而称可采用。

LH是新的局部入场＋仅E0退出；LER另加固定局部失效/再入；它们不是视频策略。IG/E0G仅增加EMA9>21>50且三线向上的入场过滤。LER、EMA过滤均未形成跨池普遍改善；银行LER22.40%/24.27%是局部线索，不能胜过银行E0收益31.51%就不报告。原I控制跨多个新实验重复出现，已在本表去重，不算独立新增验证。

## 二、连续单标的：2021年初—2026-10-16

以下均为单标的/现金代理账户，与四池整数股/真实费用账户不是同一引擎。不能把某ETF的优势直接外推全市场。每格仍为累计净收益/最大回撤。

'''
 cols=['E0','I','X','IX','R','R1'];rows=[]
 for symbol in ['USHJ512480','USHJ518880','USHJ510300','HK00002','HK00101','HK09618','HK03033']:
  q=continuous[continuous.symbol.eq(symbol)];row=[q.name.iloc[0]]
  for policy in cols:
   rr=q[q.policy.eq(policy)];assert len(rr)==1;row.append(rd(rr.iloc[0]))
  rows.append(row)
 text+=table(['标的']+cols,rows)
 text+='''
半导体ETF上IX142.81%/26.01%是较好的收益与风险折中，X104.13%/17.11%是较强的低回撤参照；同窗E0为108.71%/40.62%。但黄金ETF上，E0为83.15%/34.79%，X却−8.54%/11.69%，IX只有24.50%/24.70%。不能用G1温度敏感退出普遍替代结构持有。

R降低多数连续窗回撤，但黄金−15.61%；R1可恢复部分参与，却使黄金长趋势切碎、连续仅+0.13%，半导体137.43%/31.15%属局部优点。故R/R1留专题对照，不作默认升级。F、C2、E2、RC、RF、慢背景切换G的全部同窗结果已进入CSV，不能只看其最好案例。

11固定主场景还覆盖2021/2022/2023不同震荡/熊市及2025—2026半导体牛市。代表例：2025-01-02—2026-06-30半导体牛市E0+162.01%/16.59%、I+160.17%/15.03%、IX+156.48%/17.41%、X+77.74%/8.40%；2026-01-01—10-23单独场景X+60.60%/17.11%、R+54.82%/21.52%。这些窗口有重叠，不能换成主观事后择时组合。

## 三、全市场资金策略：尚无可采用方案

1709只当前合格A股、另2未知记录及90行业，2015首可用日—2026-10-22；当前存续/市值/分类回看历史。下表采用修正执行后的E0，以及同一主分配S0（先行业再行业内个股）。

'''
 bg=[]
 r=broad[(broad.study=='E0_corrected_execution')&(broad.account=='S0_base')].iloc[0];bg.append(['E0＋S0',rd(r)])
 for policy in ['IX','W23','W2H','C3']:
  r=broad[(broad.study=='IX_entry_variants')&(broad.allocation=='S0')&(broad.scenario=='base')&(broad.policy==policy)].iloc[0];bg.append([policy+'＋S0',rd(r)])
 text+=table(['全市场主账户','累计收益 / 最大回撤'],bg)
 text+='''
全市场IX的16基础分配/入场账户全亏；W23显著少亏但依然不盈利，严格事件稀少、漏跳级、成本敏感。W23-S1虽回撤约13%，平均暴露仅1.31%，并非兼顾收益的成功账户。动态配置A/B/C/D基础收益分别−83.95%/−94.28%/−90.05%/−92.88%，不晋升。

旧执行T1确曾+28.67%/65.25%，但RS缺失整批代码回退/陈旧买单等执行差异仍在；修正后−65.84%/83.33%。它不是“另一个当前最好策略”，也不能按旧收益更高反推缺陷有益。I尚未完成这里相同范围的全市场资金检验，不能把四池的高收益写成I已解决全市场。

## 四、早期低回撤与专项，不遗漏但不混排

早期库存63个名字、378个去重case、61组观察路径指纹；不是378次独立样本外。原库存中的80%门槛现只作愿景，不再用它否决旧模型。完整名字、收益和源路径见`tables/legacy-63-model-summary.csv`及`legacy-378-deduplicated-cases.csv`。

'''
 text+=table(['早期分档量价仓位数据池','累计收益 / 最大回撤','平均现金'],[[r['group'],f"{r['total_return']:+.2%} / {abs(r['max_drawdown']):.2%}",f"{r['average_cash_weight']:.2%}"] for r in graded])
 text+='''
期间2022-01-03—2026-10-16。该旧模型ETF/HK两池的基础、双成本、额外延迟六组均为正收益且回撤不超过20%，值得保留低回撤参照；但不是同等满仓下胜过I的证明，且HK基础没有30%闭合尾部。

旧A485相关性代理板块/初次过阈值group_gate_cap在2024-01-02—2026-10-16为+11.09%/16.23%，平均现金64.88%。分数股、合成充裕流动性和代理行业边界明显，不能拿来替代当前1709股真实行业研究。

沪金AU0缠论专项在2025-01-02—2026-10-13：均线辅助二买＋新卖点/结构退出23.34%/7.63%，只结构退出27.29%/24.52%，被动45.41%/30.37%。这只是连续价格/一倍名义敞口代理，非真实合约换月、整数手和保证金成绩，也不代表A股策略已验证。

## 五、没有收益的名称与当前取舍

B4是独立强度指标基线；B5是事实/政策兼容架构；RC1/B5-M1目前是事实恢复/多尺度诊断，不能给它们贴I/IX的账户收益。I-RB1、视频VEMA-Q1/D1尚未资金检验，不参加收益排名。数据、排名、资金分配、状态算法与持有政策必须分开评价。

现阶段保留I/E0作为股票参与及结构持有的主要研究基线，IX/X作为退出与再入的局部对照，graded_pairwise_volume作为低暴露小池风险参照。当前最薄弱的仍是全市场候选、资金占位与全部普通损耗的结合；没有证据支持只凭最优单例切换模型、按板块事后拼策略或自动实盘。

## 来源与复核

本次只聚合已有CSV/JSON。固定四池重复I控制数值核对后去重；18单资产窗口重复E0控制亦核对去重，独立CSV保留源路径。源哈希、行数、去重和完成状态见`REVIEW_RECEIPT.json`。这不是重新核账所有早期原始账户，旧数据与执行代理的限制沿用各源报告。

'''
 (HERE/'ASSESSMENT.md').write_text(text)
 index='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>趋势算法与策略综合评价</title><style>body{font:16px/1.7 system-ui;max-width:1500px;margin:30px auto;padding:0 22px;color:#24384a}table{border-collapse:collapse;font-size:13px}td,th{padding:9px;white-space:nowrap;border-bottom:1px solid #ddd;text-align:right}.scroll{overflow:auto}a{color:#24628b}</style><h1>趋势算法与交易策略综合评价</h1><p>股票组合优先候选I；结构持有基座E0；IX/X为局部风险对照；早期分档仓位为低暴露参照。尚无成熟全市场冠军。</p><p><a href="ASSESSMENT.md">完整评价与结论</a> · <a href="tables/dataset-registry.csv">数据范围登记</a> · <a href="tables/fixed-stock-pools-all-scenarios.csv">四池全部情景</a> · <a href="tables/single-assets-all-policies.csv">单标的全部政策/情景</a> · <a href="tables/broad-universe-all-scenarios.csv">全市场结果</a> · <a href="tables/legacy-63-model-summary.csv">早期63名字库存</a></p><h2>四固定股票池基础结果</h2><p>2021-01-04—2026-10-16，各100万元。非年化。当前快照开发历史。</p>'''
 block=base.copy();block['累计净收益']=block.net_return.map(pct);block['最大回撤']=block.max_drawdown.map(lambda x:f'{x:.2%}');index+='<div class="scroll">'+block[['group','policy','累计净收益','最大回撤']].to_html(index=False,border=0)+'</div><h2>7连续标的基础结果</h2><p>每标的独立运行2021年初—2026-10-16，统一单标的代理引擎，不能与四池直接混排。</p>'
 block=continuous.copy();block['累计净收益']=block.net_return.map(pct);block['最大回撤']=block.max_drawdown.map(lambda x:f'{x:.2%}');index+='<div class="scroll">'+block[['name','policy','累计净收益','最大回撤']].to_html(index=False,border=0)+'</div></html>'
 (HERE/'index.html').write_text(index)
 receipt=dict(recorded_at=datetime.now(timezone.utc).isoformat(),read_only_review=True,new_economic_accounts=0,new_market_downloads=0,stock_unique_rows=len(d),single_unique_rows=len(singles),single_continuous_base_rows=len(continuous),legacy_model_names=len(model),legacy_unique_cases=len(legacy),source_hashes=SOURCES,code_sha256=sha(Path(__file__)))
 with (HERE/'REVIEW_RECEIPT.json').open('x') as f:json.dump(receipt,f,ensure_ascii=False,indent=2);f.write('\n')
 print({k:v for k,v in receipt.items() if k!='source_hashes'})

if __name__=='__main__':main()
