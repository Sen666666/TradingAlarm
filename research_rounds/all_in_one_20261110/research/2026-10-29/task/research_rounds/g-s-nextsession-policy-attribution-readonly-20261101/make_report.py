"""Summarize already read-only results with labels verified from original master."""
from analyze import O,BASE,read,sha,save
from pathlib import Path
from decimal import Decimal as D
import csv
def f(x):return f'{D(x):,.2f}'
def main():
 r=read(O/'RESULTS.json');a=r['2025_26'];b=r['2022']
 sel=read(BASE/'inputs/2025_26/selection.json');mp=Path(sel['industry_resolution_evidence']['path']);assert sha(mp)==sel['industry_resolution_evidence']['sha256']
 master={z['symbol']:z for z in csv.DictReader(mp.open())}
 text=['最小只读政策归因：K等分与刚买即筹资请求','',
 '技术账正确不代表配置合理。没有按每日H1/PVR名次卖出，但确有“新需求→K增项→旧行业等分目标变低→减有效旧仓筹资”的轮换。被减股票/行业无需示弱，当日新买也没有豁免。','',
 'Jul3四只新买后被请求减持（均mobile/confirmed，只是下一日请求）：',
 '股票/用途 | 买入→请求减股数 | 原→新行业S目标(元) | 选择原因 | 收盘/实际保护线(原始价域)']
 for z in a['new_buy_then_trim']:
  target='无S席位' if z['original_K_target'] is None else f(z['original_K_target'])+'→'+f(z['new_K_target'])
  why='G用途先筹资' if z['original_use']=='G' else 'S超等分目标组按比例减'
  text.append(f"{z['name']} {z['sid']} {z['original_use']} | {z['actual_bought_qty']}→{z['requested_exit_qty']} | {target} | {why} | {D(z['close']):.4f}/{D(z['actual_line']):.4f}")
 text += ['',
 '四股原股票Q/I均True、当日fresh CP1均无、均未破实际保护线；新疆众和另有原core事件。行业A均有效，除宏达行业尚未成熟外其余行业S成熟且P为True，原全球G也仍P/A为True。没有新意图不能误写成原Q失败。',
 '宏达原S因permission拒，走G；新疆众和原S余预算224.78元不足100股，走G。新疆众和与北方铜业同属工业金属，收盘53118元，新的S目标46966.29元；江苏金租行业55000元。先减G组，再对S超额组统一比例减，未按新买年龄或H1强弱选。表中S目标不是G订单原额度。','',
 '新需求（CLOSE计划，仍须下一OPEN完整重验；不是已成交）：',
 '股票 | 固定映射行业 | 计划股数 | 毛额 | 含费现金']
 for x in a['fresh_demands']:
  m=master[x['sid']];text.append(f"{m['name']} {x['sid']} | {m['industry_name']} | {x['q']} | {f(x['gross'])} | {f(x['cash'])}")
 text += [f"Jul3含费需求{f(a['all_demand_cash'])}；现金{f(a['available_cash'])}，10%现金底线{f(a['cash_floor'])}，可花{f(a['spendable'])}，缺{f(a['raw_cash_shortfall'])}；既有筹资覆盖0。16项新退出预计回{f(a['estimated_new_reduction_proceeds'])}，比缺口多{f(a['whole_unit_overshoot'])}（整手/费用离散）。预计回款仍不可花。",
 '所有筹资单绑定四个需求goal集合，账上未一一分配“某笔旧仓专供某只新股”，因此不能伪造这种因果。四只刚买股只是16项中的4项。G先于S-excess、mobile先于core、组内按比例和稳定代码顺序；没有负面价格证据判定。',
 '博敏电子OPEN已按旧CP1义务实卖6400股，CLOSE fresh CP1又提出4500股计划再入，尚未真正再买。',
 f"Jan6需求只有天山股份1900股，含费{f(b['all_demand_cash'])}；现金{f(b['available_cash'])}，底线{f(b['cash_floor'])}，可花{f(b['spendable'])}，缺{f(b['raw_cash_shortfall'])}，既有覆盖0。9项S-excess筹资预计{f(b['estimated_new_reduction_proceeds'])}，不是持仓保护失效。",'',
 'K与结构性稀释：',
 'K序列Jul1/2/3为12/14/17；Jan4/5/6为22/25/26。targets=0.8×决策NAV/len(K)。Jul3每行业S目标5.7143%→4.7059%（56585.94→46966.29元）；Jan6为3.2000%→3.0769%（31799.13→30715.47元）。',
 'Jul3新增K为元件（博敏电子再入见证）、风电设备、能源金属；后两行业当天price_advance成熟，元件上次推进Jul1。Jan6新增建筑材料，当天推进成熟。因此不能把所有新席位称为无新证据。',
 'K的holding见证只需有非零、I有效且无待退仓及行业A/成熟，无需新CP1或新推进：Jul3为14/17席、Jan6为25/26席。其中同预热成熟context分别11/23席；再限定启动后无新前沿推进且见证股当日无fresh CP1为8/11席，占现资本498823元(49.98%NAV)/381381元(38.20%NAV)。这证明续证要求较弱，不能据此称全是弱仓。']
 for k,z in [('Jul3',a),('Jan6',b)]:
  rows=[x for x in z['K_rows'] if x['warm_hold_without_new_frontier'] and not x['witness_fresh_CP1']]
  text.append(k+'这组行业：'+'、'.join(x['industry'] for x in rows)+'。逐席见同名K.csv，含见证/最后推进日/P/A/实际资本/原Q。')
 text += [
 'Jan6消费电子P暂停但A有效，继续占K是持有规则。S通道在当前K下单行业只获4.7059%/3.0769%授权；单主题80%仅K=1才在等分公式上可达。实际最大7.19%/4.11%高于新目标，来自旧12/22席时代投入、价格变化及仍未实卖的库存。G仍可支持到单行业20%，所以4.71/3.08不是全用途绝对硬限，但G也不能使单行业80%可达。','',
 '一个最小改善方向（设计建议，未实现）：把持有支持目录与主动资本承诺分开；K新增不自动等分稀释同context内旧承诺。新增机会先用真实未承诺资本或独立退出后结算资金，不能仅因多一席就把有效旧层变成“超额”。若需要替换有效旧仓，另行明确可知替代证据。',
 '代价：没有闲钱或独立退出时新主题会等待；去掉K等分本身尚未定义新的主题资本目标，也不能宣称单主题80%已解决。不得凭空承诺新旧各80%。下一最小验证应是同证据只增加候选/持有见证，检查旧资本是否被无证据稀释，以及新需求的真实资金来源；本轮不执行。',
 '支持的机制：K等分+新需求触发有效旧仓筹资。否定的具体解释：四股因I/原Q失效、破保护或原G撤销而退。未知：换出是否改善未来收益、哪条主题应获更多资本；这几日不能回答。金融试验前须冻结目标/替代语义，并先过资金不重计、旧赢家继续涨而新主题失败等反例。','',
 '源码：原policy.py:89-113；native_capital.py:348-429（需求与筹资）、430起（单纯K变化不强退，但需求到来后仍减）。持有/资本/排序是不同职能，技术正确不证明经济合理。',
 '只读分析修正：v1用OPEN后的fills长度寻找当日新买导致空集合，已保留failed-v1源/结果；现按fill.at过滤并断言7/2买与4/0项当日减持。报告草案手写001267行业为环保设备被原master核验拦住，最终使用冻结映射通信设备。原Q与新意图资格分列，不能混称。',
 '本轮金融事件0、账户恢复0、新指标0；原前缀索引b85aafe358213f1ae5dac3a55fb9644746dee9f4048e9b439626787119feba4f未变。未修改任何订单、指标或冻结策略。']
 (O/'REPORT.txt').write_text('\n'.join(text)+'\n')
 ver=read(BASE/'run/saved-state-audit/VERIFICATION.json')
 for x in ver['checkpoint_restores']:assert sha(Path(x['checkpoint']))==x['checkpoint_sha256']
 assert sha(BASE/'INPUT_OUTPUT_SHA256.json')=='b85aafe358213f1ae5dac3a55fb9644746dee9f4048e9b439626787119feba4f'
 save(O/'ANALYSIS_ERRATA.json',dict(old_source='analyze.failed-v1.txt',old_output='RESULTS.failed-v1.json',cause='post-OPEN fills slice empty; corrected by actual fill date',report_label_guard=dict(sid='001267.SZ',unpublished_assumption='环保设备',frozen_master='通信设备'),financial_replay=False,original_seven_checkpoint_hashes_unchanged=True))
 save(O/'ARTIFACT_SHA256.json',{str(p.relative_to(O)):sha(p) for p in sorted(O.iterdir()) if p.is_file() and p.name!='ARTIFACT_SHA256.json'})
 print('REPORT',sha(O/'REPORT.txt'),'INDEX',sha(O/'ARTIFACT_SHA256.json'))
if __name__=='__main__':main()
