"""Two completed July R0 accounts vs immutable audited baselines, saved only."""
from pathlib import Path
from decimal import Decimal as D
import json,hashlib
P=Path(__file__).resolve().parent;R=P.parent/'g-s-C-R0-continuous-july-v1-20261102';BASE=P.parent/'g-s-C-month-continuation-20261102/july_end_analysis'
def read(p):return json.loads(Path(p).read_text())
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def n(x):return f'{D(x):,.2f}'
def pct(x):return f'{D(x)*100:.4f}%'
def main():
 allnew=[read(R/'analysis/RESULTS.json')[0],read(P/'analysis/RESULTS.json')[0]];old=read(BASE/'RESULTS.json');out=[];text=['2025年7月：原100万元独立起点、连续C10/C20 + R0 对照','原基线与C10+R0不重跑。C20仅精确计算技术上限100000→250000，经济规则不变。','研究模拟；固定1709当前快照/90行业，原信号/费用/权息及日线执行代理。','', '档位 | 原收益 → +R0 | 原DD → +R0 | 财富差 | 原/新平均曝险']
 for r in allnew:
  m=r['mode'];o=next(z for z in old if z['arm']=='2025_26-'+m);d=r['vs_original'];text.append(f"{m} | {pct(o['return_from_original_1m'])} → {pct(r['return_from_1m'])} | {pct(o['max_close_drawdown'])} → {pct(r['max_close_DD'])} | {n(d['NAV_difference'])} | {pct(o['mean_close_exposure'])}/{pct(r['mean_close_exposure'])}")
 text+=['']
 for r in allnew:
  m=r['mode'];d=r['vs_original'];q=r['pnl'];root=R if m=='C10' else P;s=read(root/'analysis/FUNDED_LAYER_CHANGES.json')[m];risk=read(root/'analysis/AUTHORIZATION_RISK_BRIDGES.json')[m];g={k:[] for k in ['smaller','larger','equal']}
  for z in s['matched']:
   a=z['new_layer'];b=z['old_layer'];k='smaller' if a['initial_qty']<b['initial_qty'] else 'larger' if a['initial_qty']>b['initial_qty'] else 'equal';g[k].append((a,b))
  groups={k:dict(layers=len(v),contribution_difference=sum((D(a['total_contribution'])-D(b['total_contribution']) for a,b in v),D(0)),new_buy=sum((D(a['buy_gross']) for a,b in v),D(0)),old_buy=sum((D(b['buy_gross']) for a,b in v),D(0))) for k,v in g.items()}
  new_only=s['new_actual_layer_totals'];lost=s['lost_old_actual_layer_totals'];check=sum((z['contribution_difference'] for z in groups.values()),D(0))+D(new_only['contribution'])-D(lost['contribution']);assert abs(check-D(d['NAV_difference']))<D('1e-10')
  out.append(dict(mode=m,summary=r,matched_quantity_groups=groups,new_actual_layer_totals=new_only,lost_old_layer_totals=lost,R0_authorization_counts={k:v for k,v in risk.items() if k!='rows'}))
  text += [m+':',f"NAV {n(r['NAV'])}；实际卖出净损益 {n(q['realized_actual_sales_net_buy_and_sell_fees'])}；剩余持股未实现（扣剩余买费成本，未扣未来卖费）{n(q['unrealized_mark_minus_remaining_net_buy_cost'])}；确认股息 {n(q['booked_dividends'])}，其中应收 {n(q['dividend_receivable'])}；零股核销 {n(q['fractional_writeoff'])}。",f"已平层正/负贡献 {n(q['closed_layer_positive'])}/{n(q['closed_layer_negative'])}；未平层贡献 {n(q['open_layer_contribution'])}=实际已卖部分 {n(q['open_layer_realized_partials'])}+残余未实现+该类股息{n(q['open_layer_dividends'])}。不能把未平层贡献全称浮盈。",f"买/卖款 {n(r['buy_gross'])}/{n(r['sell_gross'])}；费用 {n(r['fees'])}（相对原差{n(d['fee_difference'])}）；实际买/卖fill {r['buy_fills']}/{r['sell_fills']}；获资股票 {r['actual_funded_stocks']}，全股新增/失去{len(d['new_funded_stocks'])}/{len(d['lost_funded_stocks'])}。",f"{risk['positive_stock_authorizations']}项逐股正量授权，分属{risk['distinct_certificates']}张证书；其中{risk['actual_C_filled_stock_authorizations']}项实际C成交。各项实际风险永久消耗均≤R0。授权不是成交。"]
  text.append('按股票+信号收盘+角色+池匹配实际层（不是独立胜率，也不是删除交易反事实）：')
  for k,z in groups.items():text.append(f" {k}: {z['layers']}层，贡献差{n(z['contribution_difference'])}")
  text += [f" 新出现{new_only['layers']}层贡献{n(new_only['contribution'])}；原{lost['layers']}层不再出现，原贡献{n(lost['contribution'])}。该层数不是净新股票数。",'全股贡献差额最大正/负：']
  dif=d['stock_differences']
  for z in dif[:4]+list(reversed(dif[-4:])):text.append(f" {z['name']} {z['sid']}: {n(z['contribution_difference'])}；原/新买款{n(z['old_buy'])}/{n(z['new_buy'])}")
  text.append('')
 text += ['机制结论：逐单批准风险保持在实际成交中生效，两档本月损失均有所减少；后排承接、后续目标变化和赢家缩量抵消部分收益。它没有解决同批行业相关风险或趋势证据到大额新增资本的映射，不能由本月改善宣布可实盘。','C10连续账户Jul23工程机械实际487450.60/7股（山推1600），不是固定单事件诊断493861.81/山推2200；铁建首层实际5385，不是固定诊断5363。父线程独立差额报告已核，不能混路径。','C20恢复：原失败f11f6656...e4dcb24与原证书未改；15已完成批次完整投影相等；同失败真实输入250k精确求解190889次，与原1m纯结果全体编码相等。只重试可选规划，必要F1/ACT/退出与历史损耗不重放，新来源身份明确。原生计划重新生成并验证可信授权，不直接注册旧纯结果。','恢复保留两次非经济出口失败：v1原生Decimal与JSON直接比较；v2恢复验证新增一次memo hit导致原始完全相等断言失败。正确Jul22收盘checkpoint保留，修正出口只排除已单列的hit155→156，其他完整字段相同，重复重试不变；不重跑正确规划/日期。','财务：两账户各69保存事件、23决策批次；各自独立7桥为0；C10独审已PASS；C20全部旧/新checkpoint及最终实际恢复核同。待独立审计，不再自动追加2022、8月或新策略。']
 save(P/'COMBINED_RESULTS.json',out);(P/'REPORT.txt').write_text('\n'.join(text)+'\n')
 # Include source references rather than rewriting frozen C10 artifacts.
 with (P/'AUDIT_ENTRY.txt').open('a') as f:
  f.write('\nCompleted July economic/audit outputs:\n')
  for path in [P/'REPORT.txt',P/'COMBINED_RESULTS.json',P/'analysis/VERIFICATION.json',P/'analysis/ARCHIVE_AND_FINAL_RESTORE.json',P/'analysis/AUTHORIZATION_RISK_BRIDGES.json',P/'analysis/FUNDED_LAYER_CHANGES.json',P/'RECOVERY_FINANCIAL_GATE.json',R/'analysis/RESULTS.json',R/'analysis/VERIFICATION.json']:
   f.write(str(path.resolve())+' SHA256 '+hashlib.sha256(path.read_bytes()).hexdigest()+'\n')
 print('\n'.join(text[4:7]))
if __name__=='__main__':main()
