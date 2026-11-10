from common_abcd import *
import pandas as pd

def main():
 p=HERE/'report/index.html';s=p.read_text();backup=HERE/'attempts/report-v2';backup.mkdir(parents=True,exist_ok=False);backup.joinpath('index.html').write_text(s)
 fragment='''<h2>这版为什么没有改善</h2><p><b>选得更窄，并未减少实际试错。</b>B仍闭合1770次，A为1787次；B闭合尾部周期60→49，单次盈利幅度也缩小。</p><p><b>胜率提高，盈利端却变小。</b>C胜率30.22%→33.02%，平均盈利周期12.87%→10.52%，平均亏损仍约6.1%。普通净损耗减少25.99万元，尾部利润减少32.41万元，整体仍更差。</p><p><b>卖出与承接目标未完全一致。</b>C的240次操作，出清后首个买入批次仅124次包含原挑战目标；D为95/179。每天资格和排序会变化，腾出位置不等于抓住原目标。主动换出后的再入限制还挡住C的23个年度赢家窗口。</p><p>目前应先研究实际开仓样本的收益质量、行业确认时机及尾部保留，再设计一致的目标组合。停止扩大本版换仓账户，不按本轮收益继续扫阈值。完整推导见结论。</p>'''
 s=s.replace('<h2>收益来自哪里</h2>',fragment+'<h2>收益来自哪里</h2>')
 f=pd.read_csv(HERE/'diagnostics/fixed-scenario-slices.csv');f=f[f.scenario.eq('base')].copy();f['net_return']=f.net_return.map(lambda x:f'{x:.2%}');f['max_drawdown']=f.max_drawdown.map(lambda x:f'{x:.2%}');f['initial_nav']=f.initial_nav.map(lambda x:f'{x/10000:.2f}万');f=f[['scheme','window','start','end','initial_nav','net_return','max_drawdown']]
 fragment='<details><summary>展开固定场景的连续资金切片（基础组）</summary><p>标签来自原ETF参照，同一2021时间窗会因参照不同出现重复，不能当成多个独立全A场景；资金/持仓不重置。2026资料仅至10-22。</p>'+f.to_html(index=False,border=0,classes='data')+'</details>'
 s=s.replace('<h2>三只已知赢家',fragment+'<h2>三只已知赢家')
 labels={'scheme':'方案','scenario':'执行情景','net_return':'净收益','max_drawdown':'最大回撤','fees_cny':'显式费用','year':'年份','main_reason':'主要原因','industry':'行业','symbol':'代码','name':'名称','net_pnl':'净损益','campaigns':'持仓周期数','window':'原参照窗口','start':'开始','end':'结束','initial_nav':'期初净值','base':'基础','cost2':'成本加倍','delay1':'多一次执行延迟','common_ready:unknown':'共同历史准备未知','no_original_IX_event':'当年无原IX买入事件','sector_slots_full':'三个行业名额已满','sector_up:unknown':'行业趋势资料未知','stock_rs_ready_fresh:unknown':'个股RS不可算或非当日','total_slots_full':'六个总名额已满','accepted_without_actual_fill':'接纳过但当年未实际成交','buy_allowed:unknown':'可买资格或新通道资料未知','dual_sector_absolute_or_breadth_gate':'行业绝对上涨或扩散未过门槛','dual_stock_channel_gate':'个股两条通道均不合格','sector_issuer_slots_full':'行业内两个公司名额已满','rotation_reentry_not_requalified':'主动换出后未重新合格'}
 for a,b in labels.items():s=s.replace('>'+a+'<','>'+b+'<')
 extra='<a href="../diagnostics/closed-cycle-quality.csv">实际闭合样本质量</a><a href="../diagnostics/entry-rank-alignment-summary.csv">行业排名与真实买入</a>'
 s=s.replace('<div class="downloads">','<div class="downloads">'+extra);p.write_text(s)
 write(HERE/'report-augmentation.json',dict(recorded_at=now(),static_only=True,financial_or_rule_changes=0,original_html_preserved='attempts/report-v2/index.html',added_actual_loss_attribution=True,original_fixed_scenarios_seven=True,reason_labels_translated=True))
 print('report attribution added',flush=True)
if __name__=='__main__':main()
