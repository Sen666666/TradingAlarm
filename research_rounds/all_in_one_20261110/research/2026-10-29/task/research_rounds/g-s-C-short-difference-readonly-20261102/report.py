from pathlib import Path
from decimal import Decimal as D
import json,hashlib
P=Path(__file__).resolve().parent
def read(n):return json.loads((P/n).read_text())
def money(x):return f'{D(x):,.2f}'
def main():
 a=read('ATTRIBUTION.json');rt=read('ROUNDTRIPS.json');checks=read('CHECKS.json');assert checks['passed']
 rows=['短窗差额与角色回转：只读归因（C20−C10）',
 '原四账户止于Jan12/Jul9，金融事件0、规则修改0；旧214项冻结产物及运行源码/入口/输入身份未变。下列是实际账的分解，不是删交易或换持仓的反事实收益。',
 '', '1. 两种正交会计分解，不能跨表相加。',
 '净贡献分解（已含全部费用）：2022=已实现+1,864.58149449 + 未实现+1,877.90826084 = +3,742.48975532；2025=已实现−900.74380936 + 未实现+872.03424625 = −28.70956311。股息与核销差均0。',
 '为单列费用，下表先把各层实际买/卖费加回，得到毛价格贡献；最后仅减一次两档费用差。',
 '类别 | 2022差额 | 2025差额']
 cats=[('same_entry_different_quantity','同一入场证据/时点但数量不同'),('same_entry_equal_quantity_different_holding_exit','同一入场且数量相同，后续保留/退出不同'),('different_entry_or_role_same_stock','同股不同入场/角色/再入'),('stock_exclusive_participation','另一档从未获资的股票参与'),('fee_saved','全部费用节省')]
 for key,label in cats:
  vals=[a[w]['fee_saved'] if key=='fee_saved' else a[w]['gross_price_accounting_categories'].get(key,{}).get('gross_delta','0') for w in ('2022','2025_26')]
  rows.append(f'{label} | {money(vals[0])} | {money(vals[1])}')
 rows+=['匹配键=股票+原信号决策时点+实际入场时点+role/pool/用途+原epoch+canonical receipt/source。未用后续收益或最终获资结果筛配对。',
 '“数量不同”行也含后续持有/退出变化，不冒称纯数量因果；不能凭该分解推断把股数换过去就会得到同样结果。全匹配键及零差项保留。',
 '', '2. 2022中药为何优势大于整户优势：',
 '仅Jan7原五股的首轮（截至Jan10全部实卖）C10−11,415.34504492、C20−7,248.88517836，C20净优势4,166.45986656。其外所有层合计−423.97011123，才得到整户+3,742.48975532。',
 '首轮差的组成：白云山未参与+4,053.44；达仁堂未参与+345.55；康恩贝少700股+72.36；天士力未参与−304.89；羚锐数量相同，差0。费用已含。',
 '首轮外主要正负项（净额、非独立因果）：']
 rr=a['2022']['other_stock_net_deltas'];chosen={'002558.SZ','600332.SH','000538.SZ','002603.SZ','601668.SH','300765.SZ','600085.SH','601019.SH'}
 for r in rr:
  if r['sid'] in chosen:rows.append(f"{r['sid']} {r['name']}: {money(r['delta'])}")
 rest=sum((D(r['delta']) for r in rr if r['sid'] not in chosen),D(0));rows.append('其余全股票合计 '+money(rest)+'。')
 rows+=['关键路径：巨人两档最初同买7600股，C10 Jan7全卖，C20仅卖3900、Jan12再卖3600后仍剩100，净贡献少2,712.97；石药创新Jan11 C10新买5200、C20仅2400，当前少承受亏损2,699.98。白云山Jan12为C10重入200、C20首次参与1200（非两档重入），C20这一笔浮亏多513.60。',
 '这说明省掉首轮假启动损耗，会被旧赢家退出时点及随后资金替代部分抵消，不是中药账错，也不是C20必胜。',
 '', '3. 2025差额全部非零股票：',
 '三七互娱：+2,565.97698369（C20保留5300股，C10已筹资卖4400、剩900）。',
 '世纪华通：−1,890.72229852（Jul9 C10追加7000、C20追加2800；终态全股7100/2900）。',
 '平安电工：−710.83598418（Jul9 C10全卖2500；C20仅卖1600、留900，实际已实现/未实现分开保存）。',
 '恺英网络：+6.87173590（C20 Jul9新获100股，C10未获资）。',
 '四项相加=−28.70956311；费用已在各股净贡献内。少费98.06693689不能再加一遍。保留旧强者、少加新股与新增试仓并存，均为真实投资取舍，不是财务错误。',
 '', '4. 全样本角色/买卖回转口径：',
 'A=同股票同开盘实际两方向成交，每组一次；B=自上一笔买入后实际卖出，再下一次买入角色不同，每段卖出不复用。A/B重叠不能相加。金额=这些卖与再买的实际毛额之和；费用只计这些腿，非原首次买入全生命周期费用，也非宣称可节省费用。',
 'arm | A全部数量/毛额/费用 | A跨角色数量/毛额/费用 | B跨角色数量/毛额/费用']
 for arm,s in rt['stats'].items():
  cells=[]
  for key in ('same_open_all_roles','same_open_cross_role','sell_since_previous_buy_then_different_role'):
   z=s[key];cells.append(f"{z['episodes']}/{money(z['gross_two_sided'])}/{money(z['fees'])}")
  rows.append(arm+' | '+' | '.join(cells))
 rows+=['跨角色B共5个账户实例、3个不同“股票/日期”案例，含两档重复观测；不是5个独立机会。A全部4个账户实例、2个不同案例。',
 '同开盘具体两例（两档完全相同）：',
 '• 浙商银行 Jul4：mobile/S/confirmed卖100，core/T/probe买500；卖与core资格已在Jul3同CLOSE已知，C目标Q=0、D=100。旧mobile线3.4345662，新core真实线3.39。最终买量在OPEN资源裁剪，不是假称收盘已知500。',
 '• 浙江东日 Jul7：mobile/G/confirmed卖300，mobile/T/probe买100；卖与原core/CP1资格已在Jul4同CLOSE已知，C目标Q=0、D=300。最终core未获准、T-mobile成功；具体core首拒因日志未保留，不猜。旧/新实际mobile线均26.9062636232303。毛卖8,638.6785、毛买2,882.4405、两腿费用15.05784298。',
 '它们都是C配置供资先卖，旧责任成交消失后，原独立T路径又申请同股。账本/guard并未越限，但C计划与残余T计划未在同股最终目标上共同协调。',
 '跨日其余角色变化：C10以岭药业Jan10卖mobile4900，Jan11新core决策、Jan12买100；两档重庆钢铁Jul8卖mobile300，Jul8收盘新core决策、Jul9买100。这些买决策均晚于实际卖出，非同批预知冲突。',
 '跨角色追加但无卖出桥：四臂2/3/2/2次，另列ROUNDTRIPS，不计回转金额。',
 '', '5. 最小建议（不实施）：',
 '优先审同批C供资与独立T的同股最终意图仲裁，而非加新门或禁止所有刚卖股。用浙商/浙江东日两例为正反语义用例，以以岭/重庆钢铁跨日退出后合法重参与为负控。',
 '不能直接净股数：浙商core/mobile保护与锁不同；浙江东日虽同线同role，G-confirmed与T-probe来源、receipt和池占用仍不同。需先明定保留旧量/真实迁池/新量的合同，且独立保护退出不得被抵销。',
 '其他财富差主要是持仓/数量/退出时点的投资取舍；现证据不足把这些差称为实现bug，也不足先定C20胜。当前源码、全部订单和账户保持不变；无新日期或参数。',
 '', '复核：python -B analyze.py && python -B report.py；仅读保存JSON。ATTRIBUTION/ROUNDTRIPS含完整分母、原时钟、原保存CLOSE/OPEN路径、各腿费用；CHECKS为精确桥。READ_INPUTS列来源SHA。']
 (P/'REPORT.txt').write_text('\n'.join(rows)+'\n')
 index={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(P.iterdir()) if p.is_file() and p.name!='ARTIFACT_SHA256.json'}
 (P/'ARTIFACT_SHA256.json').write_text(json.dumps(index,sort_keys=True,indent=2)+'\n')
 print('READ_ONLY_REPORT_READY',hashlib.sha256((P/'ARTIFACT_SHA256.json').read_bytes()).hexdigest())
if __name__=='__main__':main()
