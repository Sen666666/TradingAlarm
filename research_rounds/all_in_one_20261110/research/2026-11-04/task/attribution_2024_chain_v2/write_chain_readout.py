"""Compact explanatory chains from frozen native records; no new signals."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import json, hashlib, importlib.util
O=Path(__file__).resolve().parent;T=O.parent;Z=D(0)
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
 with (O/p).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str)
def fmt(v):return f'{D(str(v)):,.2f}'
summary=read(O/'SUMMARY.json');chains={};exitgroups={}
pricepath=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/c1-drawdown-capacity-20261101/analyze_saved.py')
sp=importlib.util.spec_from_file_location('existing_fixed_case_raw_price_reader',pricepath);A=importlib.util.module_from_spec(sp);sp.loader.exec_module(A)
silver_facts=Path(A.SM['300085.SZ']['refs']['facts'])
save('FIXED_300085_OBSERVED_CLOSES.json',dict(sid='300085.SZ',observed_raw_close={d:A.price('300085.SZ',d) for d in ['2024-10-09','2024-10-10','2024-10-11']},scope='Original stored facts raw_close copied by existing saved reader; descriptive mark at completed CLOSE, not added signal or new source.',source=str(silver_facts),source_sha256=sha(silver_facts),reader_sha256=sha(pricepath)))
for arm in ['No60','D_GROSS10']:
 tr=read(O/(arm+'_ALL_2024_TRADES.json'));au=read(O/(arm+'_ALL_2024_EXIT_REQUESTS_AND_CA.json'));rr=read(O/(arm+'_post_oct8_ALL_LAYERS.json'));ac=read(O/(arm+'_ALL_HISTORICAL_ENTRY_ACTIONS.json'));am={x['layer']:x for x in ac};cases={}
 selected=set(['300085.SZ','601360.SH','002583.SZ','002131.SZ','601601.SH'])
 for phase in ['pre924','post_oct8']:
  for k in ['top10_loss_stocks','top10_gain_stocks']:selected.update(x['sid'] for x in summary[arm][phase][k][:5])
 for sid in sorted(selected):
  tt=[t for t in tr if t['security_id']==sid]
  cases[sid]=dict(name=next((x['name'] for p in summary[arm].values() for k in ['top10_loss_stocks','top10_gain_stocks'] for x in p[k] if x['sid']==sid),None),selection='fixed illustrative + complete top5 positive and negative stocks in each pre/post phase; posterior diagnostic only',actual_trades=tt,actual_entry_actions=[am[t['layer']] for t in tt if t['side']=='buy'],all_2024_exit_requests=[x for x in au if x['kind']=='pilot_layer_exit' and x.get('sid')==sid],phase_rows={p:[x for x in read(O/(arm+'_'+p+'_ALL_STOCKS.json')) if x['sid']==sid] for p in ['pre924','924_six_closes','post_oct8','year2024']})
 chains[arm]=cases;gg=[]
 for group in ['held_at_start_CLOSE','new_actual_fill_in_phase']:
  for reason in sorted({x['final_exit_reason'] for x in rr if x['group']==group}):
   q=[x for x in rr if x['group']==group and x['final_exit_reason']==reason]
   gg.append(dict(group=group,final_exit_reason=reason,layers=len(q),period_wealth=sum((D(x['wealth']) for x in q),Z),positive_period_wealth=sum((max(Z,D(x['wealth'])) for x in q),Z),negative_period_wealth=sum((min(Z,D(x['wealth'])) for x in q),Z),scope='Final native exit-reason group, not proof the exit caused the loss; includes positive counterexamples; no new signal.'))
 exitgroups[arm]=gg
save('NATIVE_STOCK_TRADE_CHAINS.json',chains);save('POST_ALL_FINAL_EXIT_REASON_GROUPS.json',exitgroups)
lines=[
'2024为何遇到924仍全年亏损｜各自原路径，不作新实验',
'复用冻结native book/daily、原saved LAYERS、原raw_close reader与split-aware entry_actions。零新账户、零新指标。新增派生算术已逐股对齐，独审状态另外列。',
'所有元数为财富变化，含实际买卖费/日线proxy滑点、已确认股息权益及边界存货估值，不是全额现金盈亏。每段起点是各自前一个真实CLOSE。10月8日是已固定诊断边界，不作为可交易峰值。',
'',
'1. 两条路径的直接答案',
'No60：年初承接745426.96 → 9/23 625724.23（−119702.72）→ 10/8 805043.93（+179319.69）→ 年末637989.61（−167054.32），全年−107437.35/−14.41286%。它实际参与了924；此前亏掉11.97万，随后又亏16.71万，因此超级行情盈利没有转化为全年盈利。9/23以后仍净+12265.38，但不足补此前亏损。',
'D_GROSS10：承接858950.90 → 9/23 825930.51（−33020.39）→ 10/8 905257.60（+79327.09）→ 年末718642.10（−186615.50），全年−140308.80/−16.33490%。其此前少亏，但自身ACT让924前4个OPEN仍停机，9/27 CLOSE才恢复；后段ND撤销新增10%门后仍有高额新增试错。两种失效互相独立。',
'两臂年初资金不同，不能把年末净元差当2024增益。D不等于同一篮子乘10%；历史仓位、暂停、恢复后信号/资金和下单量均改变。',
'',
'2. 分层核账与首次/追加/重入',
]
for arm in ['No60','D_GROSS10']:
 for phase in ['pre924','924_six_closes','post_oct8','year2024']:
  p=summary[arm][phase];g=p['layer_groups'];acts=p['newfill_actions']
  lines.append(f"{arm} {phase}: 合计{fmt(p['NAV_change'])}；起点已持{g['held_at_start_CLOSE']['layers']}层{fmt(g['held_at_start_CLOSE']['wealth'])}；期间新fill{g['new_actual_fill_in_phase']['layers']}层{fmt(g['new_actual_fill_in_phase']['wealth'])}；新fill first/add/reentry = "+' / '.join(f"{v['layers']}层 {fmt(v['wealth'])}" for v in acts.values()))
lines += [
'first/add/reentry从2022以来每笔实际trade顺序与split后的股票数量决定；不是订单kind=add，也不是按2024重新当首次。D跨年21层−217.28已分离，未套用No60年初股票为空的事实。',
'No60六CLOSE的已持58层+145291.12，占179319.69的81.02%；新17层+34028.57。主力行业保险+45771.78、证券+34532.04、多元金融+24580.46。故‘完全错过924’不适用于No60这段。',
'D六CLOSE起点股票为空，53新层+79327.09；这53层年底全生命周期合计仍+17421.26，10/8后回吐61905.83。其后新311层另亏124709.67，不能全部归罪924那一篮子。',
'D后段新mobile227层−107345.19（全后段净损耗57.52%），其中62盈利层+101070.69、165亏损层−208415.88；No60新mobile250层−101296.16。存在同状态赢家，关掉全部新买的节省金额没有被验证。',
'',
'3. 行业和股票规模（完整正负零母体在ALL文件，不把最差股当实时标签）',
]
for arm in ['No60','D_GROSS10']:
 for phase in ['pre924','post_oct8']:
  p=summary[arm][phase]
  lines.append(arm+' '+phase+' 行业最负5：'+'；'.join(x['industry']+' '+fmt(x['wealth']) for x in p['top5_loss_industries']))
  lines.append(arm+' '+phase+' 股票负5：'+'；'.join(x['sid']+' '+x['name']+' '+fmt(x['wealth']) for x in p['top10_loss_stocks'][:5]))
  lines.append(arm+' '+phase+' 股票正5：'+'；'.join(x['sid']+' '+x['name']+' '+fmt(x['wealth']) for x in p['top10_gain_stocks'][:5]))
lines += [
'',
'4. 原过程可核原因与反例',
'已核可归因：D原自身ACT在9/24、25、26、27 OPEN关闭，首买9/30；这是真实权限约束。post全NOT_DOWN，10%额外准入门不生效；调低DOWN上限不能直接覆盖这段主损耗。10/8两者已高仓，No60约89.82%、D约87.17%。因而宏观DOWN准入门没有解决恢复参与及ND新买质量。',
'银之杰300085：D 10/9以47.263620买200股，10/10以49.874925再买300股；10/10 CLOSE原CP1_add_protection请求退出，10/11 OPEN以30.194895卖500股，含费用实际亏9342.84。原No60只在10/10买300股，亏5920.08。原reader 10/10 raw_close37.76意味着D当日收盘已亏5546.77，次OPEN净卖款再少3796.07；退出已下一OPEN执行，不能将全部亏损归为拖延多日或费用。这个例子不是实时过滤器。',
'三六零601360：D 11/18 mobile1200股→11/19 CLOSE请求→11/20卖出；随后11/25重新core500、11/26 mobile1000，11/28再次请求→11/29卖mobile，core到12/24 ACT卖出，股票后段合计−6240.66。No60相同日期但实际数量不同，合计−4014.56。它展示先失败、重入、追加、再次失败，不足以推出所有重入无效。完整原流水及入口类别见NATIVE_STOCK_TRADE_CHAINS。',
'赢家反例海能达002583：D 10/15小core100，10/21、22、23 mobile1300/1100/100，11/4 CLOSE请求退出mobile，11/5以22.98850卖2500，core11/27卖，股票+25818.54。No60同类过程+21949.16。不能仅因CP1追加保护结束或后来大幅上涨/下跌，推导当时许可必坏。',
'post新层按最终退出reason分组：D CP1_add_protection148层−83684.09，I_structure_exit74层−24774.00，ACT_pause89层−16251.58。CP1退出组同时有+75424.18正贡献；reason是退出路线，不是亏损根因或删掉这类交易可获的收益。完整原层/退出字段保留。',
'',
'5. 成本、估值、公司行动和因果限制',
'post实际手续费No60 5140.54、D5359.38，约占各净损耗3.08%/2.87%；主损耗来自价格与持仓路径，费用不是全部解释。交易gross含原slippage，不能把手续费单列当全部交易摩擦。未运行零成本反事实。',
'全年已确认股息No60 11642.13、D5854.72；末股票库存均0，但No60股息应收18404.97、D16014.17仍为资产，期末NAV并非全部现金。年初应收也沿各自真实账户承接；回款不是新收益。未创建新的已实现/未实现成本模型。',
'边界未卖仓位按原日线raw_close与原CA调整后qty计值，原split事件用于入口数量顺序，source facts SHA已保存；未再造复权行情。原native split/fraction/issuer处理的真实经济适当性沿既有审查范围，不新增发行人零股待遇认证。',
'后验行业/股票、正负层、final exit reason和10/8分组只解释实际钱从哪里变化，不自动证明可预见、可避免或某条新规则有效。没有资格、排序、资金、退出逐项反事实消融，不能把差额叫算法alpha。',
'',
'6. 交付与审查',
'SUMMARY.json含两臂各4期的层、action、role、行业/股票统计；每臂每期ALL_LAYERS/ALL_STOCKS/ALL_INDUSTRIES保留完整母体；全部2024原trades/exit+CA、从2022起入口分类、正反原股票链均保存。SOURCE_BINDING指向各自原book/daily/已存LAYERS与facts SHA。',
'本脚本已检查每边界层财富→NAV、原qty×rawmark→inventory、每股交易现金+股息+库存差→同股层变化、阶段→各自NAV、3段→全年。金额沿现有saved reader，不称独立金融引擎双算。audit_2024_account_v2/POST_OCT8_CLASSIFICATION_REVIEW.json独审PASS：直接原audit fill和split时序核全历史B2265/D1783入口分类exact，post各first/add/reentry计数、元额、正负母体exact，旧新总账接回NAV。该独审不含逐股边界mark和industry metadata；不能将其扩称完整三阶段逐股独审。ACCOUNT_2024_INDEPENDENT_AUDIT另审总账及时间切片，范围以其收据为准。',
'当前快照A股1709/日线执行proxy/100万开发账户限制保留；未验PIT/OOS/H股、120万离散实盘或交易所排队。这里没有重跑稳健性或修复新系统。',
]
(O/'READOUT.txt').write_text('\n'.join(lines)+'\n')
postreview=T/'audit_2024_account_v2/POST_OCT8_CLASSIFICATION_REVIEW.json'
save('EXPLANATION_BINDING.json',dict(script_sha256=sha(__file__),source_summary_sha256=sha(O/'SUMMARY.json'),source_binding_sha256=sha(O/'SOURCE_BINDING.json'),outputs={str(O/p):sha(O/p) for p in ['READOUT.txt','NATIVE_STOCK_TRADE_CHAINS.json','POST_ALL_FINAL_EXIT_REASON_GROUPS.json','FIXED_300085_OBSERVED_CLOSES.json']},post_independent_review_path=str(postreview),post_independent_review_sha256=sha(postreview),review='PASS_INDEPENDENT_POST_ACTIONS_POSITIVE_NEGATIVE_COHORTS_AND_OLD_NEW_TOTAL_MONEY; PER_STOCK_BOUNDARY_MARKS_AND_METADATA_NOT_INDEPENDENTLY_REVIEWED'))
print('WROTE',O/'READOUT.txt')
