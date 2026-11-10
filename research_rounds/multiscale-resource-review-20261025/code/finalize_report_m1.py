"""Post-review presentation only; original analytical outputs remain unchanged."""
from common_m1 import *
import pandas as pd
def main():
 verify();p=HERE/'report/index.html';s=p.read_text();assert '门控归因' not in s
 stats=read(HERE/'gate-audit/E0-context-summary.json');assert stats[0]['stock_days']==110098 and stats[1]['stock_days']==13985
 gate='''<div class="box"><h2>门控归因：候选分已暖，实际等级还在冷区</h2><p>2023年以来全1709股、长通道准备完成的1,476,692个股票日中，110,098日出现原G1候选至少暖、实际冷且升温被挡；104,635日E0仍为上行。慢推进子集中为13,985日、涉及1495股，其中13,206日E0仍上行。</p><p>这提示恢复凭据可能过窄：一次冲击降冷后，如果没有新E0上行事件、结构新确认或旧结构新高，渐进恢复未必能升温。它不是程序算错，也不证明这些天都该买。日数连续相关，本轮没有给这些非IX日生成新未来收益标签。</p><p>下一有限问题是从风险后的局部低点累计新的价格前沿和成交量信用，使恢复可以发生在历史前高以下；不靠旧数据出窗，不取消量价确认。<a href="../RECOVERY_EVIDENCE_DESIGN.md">恢复凭据设计（尚未实现/回测）</a></p></div>'''
 marker='<div class="box"><h2>全A原IX事件：后续63交易日价格标签</h2>'
 assert marker in s;s=s.replace(marker,gate+marker)
 s=s.replace('原分已经可以是75','原候选分已经可以是75（实际分还受升温凭据门控）')
 s=s.replace('1679只有IX事件','1679只产生过IX事件')
 # Translate visible aggregate table headers without altering numeric cells.
 names={'scope':'区间','field':'分组依据','group':'类别','horizon':'交易日','events':'事件数','labels':'完整标签数','mean':'均值','median':'中位数','p10':'P10','p90':'P90','positive':'上涨比例','stock_year_mean':'股年等权均值','stock_year_groups':'股年数','kind':'诊断层','all_capacity_rejected_events':'原容量拒绝数','days_with_true_next_exit':'次日确退出日数','unique_stocks':'股票数','days':'日期数','complete_63_labels':'完整63日标签','mean63':'63日均值','median63':'63日中位','positive63':'上涨比例','stock_year_mean63':'股年等权均值'}
 for a,b in names.items():s=s.replace(f'<th>{a}</th>',f'<th>{b}</th>')
 for a,b in {'recent':'2023以后','profile':'推进档案','individual_capacity_fit':'单独可容纳','capacity_selected':'按原排序竞争后','lot_aware_selected':'再加最小单位'}.items():s=s.replace(f'<td>{a}</td>',f'<td>{b}</td>')
 s=s.replace('<td>同向下降</td>','<td>21/126净推进均负</td>')
 note='<p class="muted">“21/126净推进均负”仍可能已有当日快速启动并被原IX接纳，不代表所有短周期都在下跌。分类不是新买入门槛。</p>'
 s=s.replace('<h2>自然退出资源交接：原路径容量上限</h2>',note+'<h2>自然退出资源交接：原路径容量上限</h2>')
 p.write_text(s)
 diag={x['symbol']:x for x in read(HERE/'analysis/series-diagnostics.json')};write(HERE/'report/asset-diagnostics.json',list(diag.values()))
 write(HERE/'report/finalization.json',dict(recorded_at=now(),posthoc_gate_section=True,numerical_outputs_changed=False,unique_series=len(diag)))
if __name__=='__main__':main()
