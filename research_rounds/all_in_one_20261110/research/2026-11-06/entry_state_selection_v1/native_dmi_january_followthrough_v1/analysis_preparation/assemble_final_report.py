"""Assemble final reports and three observed identity examples; no economic execution."""
from pathlib import Path
import csv,json,hashlib,argparse

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def main(p):
 parts=[p/'REPORT.md',p/'treatment_period_supplement/REPORT_SUPPLEMENT.md',p/'ACT_and_924_supplement/REPORT_ACT_AND_924.md'];assert sha(parts[0])==read(p/'REPORT_SOURCE_SHA256.json')['REPORT.md']
 for q in parts[1:]:assert sha(q)==read(q.parent/'OUTPUT_SHA256.json')[q.name]
 s=read(p/'SUMMARY.json');rr=list(csv.DictReader((p/'ALL_ROUNDS.csv').open()));sample=[r for r in rr if r['account'] in ['PVR_ORIGINAL','DMI_FROM_2022JAN'] and r['sid'] in ['920808.BJ','001203.SZ','600396.SH']]
 out=p/'identity_case_supplement';out.mkdir(exist_ok=False)
 with (out/'THREE_STOCK_ALL_ACTUAL_ROUND_CHAINS.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(sample[0]));w.writeheader();w.writerows(sample)
 cases='''# 三个大额尾部身份例子

比较对象为 DMI_FROM_2022JAN 与 PVR_ORIGINAL。完整费后尾部80对73，由精确 sid + opened 身份计数得到：同身份双方尾部44、仅DMI观察到尾部36、仅PVR观察到尾部29。这些不是新增/丢失股票数，也不是因果追回金额。

1. 920808.BJ：PVR于2023-04-14首BUY，5/8闭合，净+51,104.24，125.18%；DMI于4/18首BUY，5/8闭合，净+56,491.37，111.39%。两边都实际参与，同股不同opened，因此各落入一项单边身份尾部。不能称一边漏掉这只股票。此后PVR5/29与DMI6/7分别另开一次亏损round，均6/27闭合，分别-5,319.03与-5,437.39；后继round不替代或合并前次结果。

2. 001203.SZ：PVR于2025-10-27首BUY，11/25闭合，净+23,289.92，45.02%；DMI于10/31首BUY，同11/25闭合，净+12,133.71，20.19%。DMI有实际同股路径，但开日不同且未达30%完整尾部阈值。2025年六月两边各自已有另一round，不可将六月小赢替换十月事件，或声称追回了两者盈亏差。

3. 600396.SH：两边同2026-03-17首BUY。PVR首层native kind=add，3/31闭合，净+26,398.80，38.69%；DMI首层kind=core，截至5/15仍未闭，标记净+20,600.59，37.84%。DMI有真实参与，未闭即便标记超过30%也不计完整尾部。差异不能写成DMI没有买到或已经少赚/损失5,798.21。

完整同股历史及每个opened/closed身份见THREE_STOCK_ALL_ACTUAL_ROUND_CHAINS.csv。没有反事实交易、替代事件、调参或新增研究。
'''
 (out/'REPORT_IDENTITY_CASES.md').write_text(cases)
 (out/'OUTPUT_SHA256.json').write_text(json.dumps({q.name:sha(q) for q in out.iterdir() if q.is_file()},indent=2))
 readout='''# 最终结论摘要

这次连续账没有给出“DMI提高首仓胜率”的一致证据。2022起全处理期首BUY层闭合胜率29.81%，低于PVR30.39%；2026起处理期25.25%，低于PVR25.91%。一月固定cohort的完整round结果有所改善，不能替代全处理期首层结论。

- DMI_FROM_2022JAN期末NAV 1,275,424.35，比PVR多20,827.39；全期收益6.2854%对4.5497%，最大回撤-47.9911%对-47.7166%，未改善最深回撤。
- 2022Jan固定101轮全部闭合，13胜88负，净-112,142.81，无≥30%完整肥尾。原PVR105轮、10胜95负、净-133,949.40。首层胜率则12.87%对14.29%。严格末NAV差额：一月cohort少亏21,806.59，其后一切新round合计少979.20，净差20,827.39。
- DMI_FROM_2026JAN从原PVR2025末状态出发，期末NAV 1,245,684.93，比PVR低8,912.04。一月54轮中53闭，18胜35负、净+72,092.00，另1未闭；不能将该未闭标记算赢家或完整肥尾。
- 全2026新开DMI267轮，198闭45胜153负、净+63,473.05，69未闭标记+136,669.30；PVR257轮，193闭41胜152负、净+34,835.77，64未闭标记+173,277.30。闭合净额改善并未使期末账户更高。严格差额桥：一月新round +19,849.87，二月起新round -27,820.59，处理前已开round -941.31，合计-8,912.04。
- 924六交易日，2022DMI实际持有57股、14次新开和9次持有中ADD；PVR持有52股、7次新开和7次持有中ADD。江丰/珂玛2026路径在三账户中均相同，分别闭合亏损1,405.27和1,475.64。未用后见MFE代替真实持仓。
- 2022DMI与PVR的原ACT开关有18个CLOSE不同；排序变化能通过原现金/成交/收益反馈改变ACT轨迹。2023-07-31至2024-04-30的DMI182CLOSE确为全关全空仓，不能把末权益差孤立归因于个股质量。
- 5/15三账户所有期末持仓均有当日有效估值，stale=0；1/30的江丰1/29旧价和002969 1/23旧价仍按原账披露。缺bar原因UNKNOWN，不等于确认停牌。

三个账户均以真实连续祖先账独立统计，未拼两条DMI支。固定未来1709股票/90行业池为NON-PIT，日线OPEN±5bp条件研究账；2022与2026至共同终点暴露期不同。统计是开发期/已见条件研究，不能据此认定稳健选股优势或实盘可执行性。所有费用、权益、库存、round及期间贡献桥通过只读对账，账户经济运行在本分析中为0。

后续正文依次提供完整主报告、处理期全部新开round两套分母、ACT/实际空仓/924补充及三个尾部身份案例。
'''
 (p/'FINAL_READOUT.md').write_text(readout)
 full=p/'REPORT_COMPLETE.md';assert not full.exists();full.write_text(readout+'\n\n'+'\n\n'.join(q.read_text() for q in parts)+'\n\n'+cases)
 seal={'FINAL_READOUT.md':sha(p/'FINAL_READOUT.md'),'REPORT_COMPLETE.md':sha(full),'source_reports':{str(q):sha(q) for q in parts},'identity_case_report':sha(out/'REPORT_IDENTITY_CASES.md'),'assembler_SHA256':sha(Path(__file__))}
 (p/'REPORT_COMPLETE_SHA256.json').write_text(json.dumps(seal,indent=2));print(full)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--analysis',type=Path,required=True);args=ap.parse_args();main(args.analysis)
