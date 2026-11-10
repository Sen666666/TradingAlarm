"""Read-only January R0 result and fixed winner control; no future labels."""
from pathlib import Path
from decimal import Decimal as D
from fractions import Fraction as F
import json,hashlib
P=Path(__file__).resolve().parent;O=P/'analysis'
def rd(p):return json.loads(Path(p).read_text())
def n(v):return f'{D(v):,.2f}'
def pct(v):return f'{D(v)*100:.4f}%'
def main():
 rr=rd(O/'RESULTS.json');old=rd(P/'baseline_readonly/RESULTS.json');ll=rd(O/'ALL_LAYERS.json');bl=rd(P/'baseline_readonly/ALL_LAYERS.json');risk=rd(O/'AUTHORIZATION_RISK_BRIDGES.json');fund=rd(O/'FUNDED_LAYER_CHANGES.json');vv=rd(O/'VERIFICATION.json');aa=rd(O/'ARCHIVE_AND_FINAL_RESTORE.json');assert vv['passed'] and aa['passed']
 text=['2022年1月4—28日：原100万独立起点C10/C20，仅新增R0','原始F1市场暖机，账户仓位/订单/损耗/receipt为0；未切换Jan13旧账户。原基线不重跑。','相同1709当前快照/90映射/信号/费用/日线执行代理；精确计算技术预算统一250000，未触上限。','', '档位 | 原收益 → R0 | 原DD → R0 | 财富差 | 原/新平均曝险'];cases={};comparisons=[]
 for r in rr:
  m=r['mode'];b=next(v for v in old if v['mode']==m);s=b['summary'];d=r['vs_original'];text.append(f"{m} | {pct(D(s['return_pct'])/100)} → {pct(r['return_from_1m'])} | {pct(D(s['close_drawdown']['max_drawdown_pct'])/100)} → {pct(r['max_close_DD'])} | {n(d['NAV_difference'])} | {pct(s['mean_close_invested_weight'])}/{pct(r['mean_close_exposure'])}")
 for r in rr:
  m=r['mode'];q=r['pnl'];d=r['vs_original'];v=risk[m];s=fund[m];text += ['',m+':',f"NAV {n(r['NAV'])}；实际卖出净损益{n(q['realized_actual_sales_net_buy_and_sell_fees'])}；残余未实现（含剩余买费、不含未来卖费）{n(q['unrealized_mark_minus_remaining_net_buy_cost'])}；股息/零股核销 {n(q['booked_dividends'])}/{n(q['fractional_writeoff'])}。",f"已平层正/负贡献 {n(q['closed_layer_positive'])}/{n(q['closed_layer_negative'])}；未平层贡献{n(q['open_layer_contribution'])}。",f"买/卖款 {n(r['buy_gross'])}/{n(r['sell_gross'])}；费用{n(r['fees'])}（原差{n(d['fee_difference'])}）；实际买/卖fill {r['buy_fills']}/{r['sell_fills']}；获资股票{r['actual_funded_stocks']}。",f"逐股正量C授权{v['positive_stock_authorizations']}项，来自{v['distinct_certificates']}张有正量证书；实际C成交{v['actual_C_filled_stock_authorizations']}项。全月总决策批19，不能把授权都称成交。"]
  groups={k:[] for k in ['smaller','larger','equal']}
  for z in s['matched']:
   a=z['new_layer'];b=z['old_layer'];k='smaller' if a['initial_qty']<b['initial_qty'] else 'larger' if a['initial_qty']>b['initial_qty'] else 'equal';groups[k].append(D(a['total_contribution'])-D(b['total_contribution']))
  out={k:dict(layers=len(v),contribution_difference=sum(v,D(0))) for k,v in groups.items()};new=s['new_actual_layer_totals'];lost=s['lost_old_actual_layer_totals'];delta=sum((v['contribution_difference'] for v in out.values()),D(0))+D(new['contribution'])-D(lost['contribution']);assert abs(delta-D(d['NAV_difference']))<D('1e-10')
  text.append('同股票/信号收盘/角色/池匹配层差额（会计归因，不是可交易反事实）：')
  for k,v in out.items():text.append(f" {k} {v['layers']}层：{n(v['contribution_difference'])}")
  text.append(f" 新出现{new['layers']}层贡献{n(new['contribution'])}；原{lost['layers']}层未出现，其原贡献{n(lost['contribution'])}。")
  for z in d['stock_differences'][:3]+list(reversed(d['stock_differences'][-3:])):text.append(f" {z['name']}：全股差{n(z['contribution_difference'])}，原/新买款{n(z['old_buy'])}/{n(z['new_buy'])}")
  hy=[v for v in ll[m] if v['sid']=='300199.SZ'];bh=[v for v in bl[m] if v['sid']=='300199.SZ'];pr=[v for v in risk[m]['rows'] if v['sid']=='300199.SZ'];cases[m]=dict(new_actual_layers=hy,old_actual_layers=bh,R0_authorizations=pr,new_total_contribution=sum((D(v['total_contribution']) for v in hy),D(0)),old_total_contribution=sum((D(v['total_contribution']) for v in bh),D(0)))
  comparisons.append(dict(mode=m,matched_quantity_groups=out,new_layer_totals=new,lost_layer_totals=lost,summary=r))
 text += ['', '翰宇药业固定赢家控制：']
 for m,z in cases.items():
  first=z['new_actual_layers'][0] if z['new_actual_layers'] else None;text.append(f" {m}: 原/新全股贡献{n(z['old_total_contribution'])}/{n(z['new_total_contribution'])}；新首买 {first['opened'] if first else '无'}，数量{first['initial_qty'] if first else 0}。")
  for a in z['R0_authorizations']:text.append(f" 原批准Q0={a['Q0']}，实际C成交锚数量={a['actual_C_fill_anchor_quantity']}，批准价={a['approved_price']}、原有效raw floor={a['approved_effective_raw_floor']}；该单未因R0缩量。")
 text += [' C10 Jan13首次6700股保留，Jan17实际部分卖6600，随后100股持有/角色回转与退出均保留；不能把全股收益差都归该笔R0。C20+R0全月未参与，原C20只有小额T参与，未用白名单补齐。', '', '结论：July两档小幅改善没有稳定迁移到January。C10约持平，C20损失进一步扩大；批准风险保持的逐单约束成立，不等于组合损耗或收益改善。两档仍有大量闭合亏损，不能据此替代趋势证据、集中风险与退出/再参与的主体研究。', '工程门：真实原起点OFF原生经济状态与订单/fill/预算输入/QD恒等；ON完整/物理文件截断与Jan4→Jan5新进程恢复核同。原C10 Jan5历史provider修复的来源/失败叙事单列，不伪称技术日志字节一样。', '全月各40事件/19决策，80检查点实际源身份与最终恢复核同，逐事件7桥0。Jan13/Jan27两项配股均原生不认购，现金0扣、实际股数不增，R0书不变；未知/未实现分支未被跳过。', '研究限制：当前成分快照回看非PIT全市场，原日线HLV执行/权息未知时点代理沿用；没有实盘认证。完成即停，不执行Feb或其他新路径。']
 (P/'REPORT.txt').write_text('\n'.join(text)+'\n');(P/'HANYU_ACTUAL.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2,default=str)+'\n');(P/'COMPARISON.json').write_text(json.dumps(comparisons,ensure_ascii=False,indent=2,default=str)+'\n')
 files=['REPORT.txt','HANYU_ACTUAL.json','COMPARISON.json','jan_r0.py','run_january.py','INPUT_IDENTITY.json','TWO_DAY_GATE.json','MONTH_AUTHORIZATION.json','analysis/VERIFICATION.json','analysis/ARCHIVE_AND_FINAL_RESTORE.json','analysis/AUTHORIZATION_RISK_BRIDGES.json','baseline_readonly/RESULTS.json']
 (P/'AUDIT_ENTRY.txt').write_text('Exactly two fresh Jan2022 R0 accounts; no baseline financial replay.\n'+'\n'.join(str((P/f).resolve())+' SHA256 '+hashlib.sha256((P/f).read_bytes()).hexdigest() for f in files)+'\nCheckpoints: runs/{C10,C_BATCH20}/PROGRESS.json; all original OPEN/CLOSE/ACTION states remain.\nScope endsJan28.\n')
 print('\n'.join(text[4:7]))
if __name__=='__main__':main()
