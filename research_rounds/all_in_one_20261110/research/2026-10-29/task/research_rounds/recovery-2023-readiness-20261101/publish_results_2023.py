"""Publish only the two saved, approved 2023 continuations."""
from pathlib import Path
from decimal import Decimal as D
import json,hashlib
O=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text())
def f(x):return f'{D(str(x)):.2f}'
def wan(x):return f'{D(str(x))/10000:.4f}'
def main():
 assert read(O/'runs/COMPLETION.json')['completed']==2 and read(O/'FINAL_CHECKPOINT_VERIFICATION.json')['passed'] and read(O/'STATIC_GATES.json')['passed']
 ms={x['policy']:x for x in read(O/'COMPARISON_2023.json')};rest=read(O/'analysis/C1/RESTORATION.json');a,b=ms['Bdiag'],ms['C1']
 text=['2022深亏后连续2023恢复｜两条normal完成｜2026-11-01',
 '裁决：C1不晋升统一策略；低c确实限制后续扩张，全年没有恢复35%/60%，只保留降低参与/损耗的风险菜单。2023回撤较小，但上半年参与和尾部贡献明显减少，全年又仍亏损；不调函数救结果。两参考均未获实盘认证。',
 '', '范围与主矩阵',
 '原1709身份/90行业、固定2023-01-03至12-29共242日；各自承接2022末真实账户，未补新钱、重置H/ACT/锁/凭据/损耗，也未重跑2022。原normal、无R1/cost/D1/新stage，97N/A及1365权息未知代理保持。',
 '政策 | 承接NAV元 | 末NAV元 | 2023收益/DD% | 2022原1m以来累计收益/DD% | 2023平均/峰值曝险% | 费用元']
 for ref in ['Bdiag','C1']:
  m=ms[ref];text.append(f"{ref} | {f(m['opening_NAV'])} | {f(m['ending_NAV'])} | {f(m['year2023_return_pct'])}/{f(m['year2023_DD']['percent'])} | {f(m['cumulative_from_2022_return_pct'])}/{f(m['cumulative_from_2022_DD']['percent'])} | {f(m['mean_exposure_pct'])}/{f(m['peak_exposure_pct'])} | {f(m['fees_2023'])}")
 text+=['季度为各自连续账户区间，不能把新1m强窗拼回来：','季度 | Bdiag收益/平均曝险% | C1收益/平均曝险%']
 for x,y in zip(a['quarters'],b['quarters']):text.append(f"{x['quarter']} | {f(x['return_pct'])}/{f(x['mean_exposure_pct'])} | {f(y['return_pct'])}/{f(y['mean_exposure_pct'])}")
 text+=['', '① 公式恢复、实际空间、真钱投入分开',
 '两账1/19原ACT恢复，1/20均已有实际core和confirmed mobile买入；C1当时H仍100万元、c仍10%，ACT phase peak重设为796609.27元并未洗掉H。年末原已空仓，所以年初已有容量空位，最先等待的是原ACT/合法新信号，不是跨年存量锁死。',
 'C1第一笔confirmed mobile为1/20奥来德15902.52元；1/30国盛证券真实卖出1400股、净卖款13609.48元，同开盘另有新confirmed成交，证明10%内可回收再投，不存在v2旧grant用完永久禁用。全年真实confirmed新买101.9431万元，不把迁池当新投入。',
 'c首次高于10%在3/31（10.3632%），该收盘仍比许可超额2652.16元；4/3收盘才有4518.61元观测净空位，4/4出现其后第一笔fresh confirmed实际成交剑桥科技13065.55元。开盘又会有卖出/价格/原子预留变化，不能把4/3收盘空位单独当4/4成交因果。更早2/16收盘虽有498.50元净空位，亦不保证合法单位/其它资源可用。',
 'c最高5/4的18.1673%，H全年100万元；从未到35%或60%，176/242个收盘仍为10%，138日旧confirmed高于新cap（最大26497.65元），不强卖。全年confirmed平均/峰值实际占用10.53/18.16%，Q2全账户平均曝险也只有19.62%；不是恢复完整扩张。收盘空位正负切换、实际卖款和fill三个时钟完整另存。',
 '', '② 完整机会与约束的可证范围',
 '两账共同fresh CP1且原个股Q通过16966张，其中原市场行业confirmed/expanded资格9095张；ACT暂停在此共同候选中Bdiag2533、C1195张，保留不静默删除。数量不是独立样本，也不能证明被挡者后来必盈利。',
 '政策 | actual mobile route(全部阶段/共同confirmed候选交集) | confirmed路由最低单位拒绝 | 两路都拒且confirmed只剩pool_capital | confirmed预留receipt/实际有fill receipt']
 for ref in ['Bdiag','C1']:
  q=read(O/'analysis'/ref/'CAPACITY_FUNNEL.json');text.append(f"{ref} | {q['actually_entered_mobile_route_receipts']}/{q['actual_mobile_route_among_market_stage_candidates']} | {q['confirmed_minimum_unit_rejected']} | {q['all_routes_rejected_and_confirmed_minimum_only_pool_capital']} | {q['confirmed_reserved_receipts']}/{q['confirmed_receipts_with_actual_fill']}")
 text+=['例子按首次发生日期选，不按未来盈利选：C1中航西飞1/20—3/6同attempt有3张fresh凭据、华工科技1/20—2/23有2张；对应confirmed最低一手仅pool资本不容纳，同时probe路由被probe风险挡。当时现金充足不等于该pool获准。完整2065个stock×attempt此类组全部留存，其中732组多次发生，既不复活旧receipt，也不把多张机会当可同时持有。',
 '这些是原实际快照中的路由独占原因，不是“把c换60%后会怎样”的账户反事实；两臂已具有不同NAV/持仓/ACT，不把拒绝数量差全部归单一c。confirmed被拒但probe仍可买的Bdiag19/C125张另列。',
 '原始迁池失败与资本独占分开：行业事件confirmed_unfunded为Bdiag347/C1537个；其中带当前probe层的去重跟踪Bdiag79层→后来迁入51/先退出28/删失0，C189层→31/50/8。等待中位4、最长30观察只针对各自实际迁入51/31层。开盘mobile路由中未能迁池原始记录2761/4759另存，具体共存原因保留unknown，不能全叫C1 cap独占。',
 '', '③ 2022少亏与2023参与的取舍',
 '2023所有新层（万元，含费；闭合层贡献仍可含未到账分红权益）：','政策 | 新买款 | 闭合正 | 闭合负 | 未平净贡献 | +30%实际层尾部闭合/未平']
 for ref in ['Bdiag','C1']:
  z=ms[ref]['new2023_layers'];text.append(f"{ref} | {wan(z['buy_cash'])} | {wan(z['closed_positive'])} | {wan(z['closed_negative'])} | {wan(z['open_net'])} | {wan(z['closed_tail'])}/{wan(z['open_tail'])}")
 delta={k:D(b['new2023_layers'][k])-D(a['new2023_layers'][k]) for k in ['closed_positive','closed_negative','open_net']};assert abs(sum(delta.values())-((D(b['ending_NAV'])-D(b['opening_NAV']))-(D(a['ending_NAV'])-D(a['opening_NAV']))))<D('.00000001')
 text += [f"C1−Bdiag的2023财富增量差：闭合正{f(delta['closed_positive'])}元＋闭合负{f(delta['closed_negative'])}元＋未平{f(delta['open_net'])}元＝{f(sum(delta.values()))}元；不是只看少亏而漏掉利润牺牲，也不将费用重复另减。2022留下的资本优势129285.43元，至2023末缩为106167.46元，累计财富仍较高但尚未恢复原1m。",
 '上半年Bdiag Q1/Q2收益4.70/8.88%，C1仅0.61/0.64%；实际尾部闭合贡献15.9812万→4.8413万。剑桥科技两账全年贡献28806.42→9168.35元、曙光数创25527.31→-4651.61元只是已存资金路径对照，不把差额全归一笔错失或据此建名单。全部正负股票贡献与层链已保存。',
 'Bdiag 8/24再触发ACT pause、8/25完成剩余退出，Q4空仓无新买；C1全年只承接期初12个暂停收盘，此后未再pause，Q4仍试错并亏1.21%。因此C1全年亏更多不只因为上半年少赚，也包含不同内生ACT/持续试错轨迹。原退出规则未改。',
 '新record_only负实现加费用Bdiag238092.45元/C1107022.34元，不同于净层损益、不作为亏损封顶。C1期末库存111985元、未平净贡献3207.75元；Bdiag库存0。两账分红应收4604.19/1863.68元不可再投。原2022旧层在2023净贡献变动0，差额没有混入旧层全生命周期损益。',
 '', '验收/计算/边界',
 '本机门：两份2022原身份/源码/最终账/五流核同后显式全状态导入；两臂1/3物理前缀和同身份重启完全一致，原planning/opening实际函数身份不变；8份2023季度检查点身份/资金/股数/累计状态核同。两账各484日原journal NAV/数量桥均0（读取旧242日不等重跑），C1全484个H/c独立复算通过。新2023结果尚未冒称独立审计。',
 '原凭据补导126.10秒、主输入加载34.56秒、两门42.94/45.55秒，连续回放含核账/导出194.33/217.98秒，主进程539.83秒。前置另有一次47.20秒加载在经济段前停止，为9/28季度保存出口修正；失败源码/进程退出143/原验证快照保留，未重复任何完整经济路径。另修一处纯日志缩进，策略原源码未改。',
 '当前snapshot非PIT、历史全部消费、日线OHLCV/open成交可得性与同开盘卖款复用、权息时刻未知代理均保留；低曝险不是预测能力。此轮不能证明C1能在深亏后充分恢复扩张，停止其统一策略晋升，不调曲线，也不自动2024/latest/成本D1/常数预算对照。2026/6/30强窗未平贡献兑现仍是独立未决项。',
 '', '证据：COMPARISON_2023.json、analysis/*/METRICS.json、CAPACITY_FUNNEL.json、REPEATED_POOL_BLOCKS.json、MIGRATION_WAITS.json、C1/RESTORATION.json与RECYCLING_TIMELINE.json、FINAL_CHECKPOINT_VERIFICATION.json、STATIC_GATES.json、runs各完整账/冻结/季度checkpoint。']
 (O/'RUN_RESULTS.txt').write_text('\n'.join(text)+'\n')
 result=dict(completed=True,policies=['Bdiag','C1'],normal_continuations=2,year2022_rerun=False,new_cash_added=0,old_state_or_H_reset=False,decision='not_promoted; risk_menu_only; low-c expansion restoration not established',remaining='independent result audit not claimed; latest-tail realization remains unresolved',execution_blockers=[],all8_quarter_checkpoints_passed=True)
 (O/'RUN_COMPLETE.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 manifest={str(p.relative_to(O)):hashlib.sha256(p.read_bytes()).hexdigest() for p in O.rglob('*') if p.is_file() and p.name not in ['DELIVERABLE_SHA256.json'] and 'startup_before_quarter_save_fix' not in str(p) and not p.name.endswith('.pkl')}
 (O/'DELIVERABLE_SHA256.json').write_text(json.dumps(manifest,indent=2)+'\n');print('PUBLISHED',manifest['RUN_RESULTS.txt'],flush=True)
if __name__=='__main__':main()
