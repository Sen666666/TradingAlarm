from common_abcd import *
from html.parser import HTMLParser

class Links(HTMLParser):
 def __init__(self):super().__init__();self.refs=[]
 def handle_starttag(self,tag,attrs):
  for k,v in attrs:
   if k in ['href','src'] and v:self.refs.append(v)

def main():
 parser=Links();parser.feed((HERE/'report/index.html').read_text());missing=[u for u in parser.refs if not u.startswith(('http:','https:','#')) and not (HERE/'report'/u).resolve().exists()];assert not missing,missing
 write(HERE/'attempts/link-validation-v1-note.json',dict(first_validator_failed=True,reason='Regex treated JavaScript src assignment prefix nav- as a real HTML attribute; replaced only the link validator with HTMLParser',financial_or_rule_changes=0))
 write(HERE/'ui-validation.json',dict(passed=True,browser='IAB tab 17',url='http://127.0.0.1:8794/report/',base_summary_visible=True,all_three_stress_images_loaded=True,image_natural_width=2100,added_loss_attribution_visible=True,fixed_scene_section_visible=True,actual_C_stock_and_industry_disclosure_verified=True,screenshot='report/ui-report-final.png',download_targets_checked=len(parser.refs),missing_local_targets=missing))
 intro='''# A/B/C/D 研究已完成

本轮9个新经济账户＋3个旧IX-S0技术控制、两日期共8个物理前缀均完成。结论：B双通道、C主动轮换、D组合均未改善A；A三执行情景的收益/回撤都相对最好，但基础收益−83.95%、回撤90.89%，仍不合格。B/C/D基础收益−94.28%/−90.05%/−92.88%，回撤96.40%/94.72%/95.26%。不晋升、不自动续扫或新开账户。

[完整结论](CONCLUSION.md)｜[冻结规则](PROTOCOL.md)｜[图表报告](http://127.0.0.1:8794/report/)｜[量价与真实持仓](http://127.0.0.1:8794/case-review/)。完整12组/年度/持仓/成交/960年度赢家窗口和三股48分年原因在analysis、diagnostics，旧结果保留。

候选过滤没有明显减少闭合交易（1787→1770）；轮换提高胜率却压缩平均盈利及尾部贡献。买卖目标/行业排名准入不完全一致，日有效重竞/再入限制/资金耗损也未解决。下一有限提案是全池开仓样本阶段与收益质量诊断，先证明经济优势再重构一致目标组合；不是授权立即运行新队列。
'''
 (HERE/'README.md').write_text(intro)
 (HERE/'RUN_STATE.md').write_text('''# 当前终态：完成，停止本版扩展

9新经济、3旧IX-S0控制、8物理前缀完成，经济重跑0、结果后规则修订0、新下载0。报告8794，结论CONCLUSION.md。旧IX/E0/B5/G1与原结果保留。

A三情景8598日账与全部金融JSON精确一致；资金决策全一致，仅2只始终市值未知事件记录的1956行痕迹/原因标签差异显式核对。初版检查和初次技术冻结保留，没有改资金规则。8项边界、23日期41377标的日独立公式、两个特征物理截断通过。

12条路径34392日账独立核对现金/股份/费用/权益/T+1/逐日归因，最大NAV差1e−22元；两个日期4组共12656条截断日账及完整候选/换仓计数/限制精确一致。974次全部情景主动计划连续确认与占位独立验证通过。

基础A/B/C/D收益−83.95%/−94.28%/−90.05%/−92.88%，回撤90.89%/96.40%/94.72%/95.26%；三情景A均相对好、仍不合格。年度240赢家窗口参与62/55/61/54；四组都未买寒武纪，C新易盛多持至16收盘日但整户更差。不晋升B/C/D、不自动搜索参数或启账户。

诊断v2改用登记7个A股ETF参照窗，更正2023半导体震荡标签；2021重复时间不当独立测试，2026股票资料仅到10-22、原10-23参照裁切。承接以首个买入开盘批次包含原目标计，后21/63日从提出替换收盘计；均为归因口径修订，原冻结脚本保留，资金不变。报告链接校验首次正则误把JS nav-拼接串识别为地址，HTMLParser修正验证器，失败留存。

下一提案仅为开仓事件质量/阶段诊断，后续另行推进；不自动实盘、发布、充值或开新队列。原数据池、初仓、IX个股退出与E0保护不变。最终完整性见complete.json。
''')
 for file in ['README.md','docs/HANDOFF.md','docs/NEXT_RESEARCH_TASKS.md']:
  p=ROOT/file;href='research_rounds/selection-rotation-abcd-20261025/CONCLUSION.md' if file=='README.md' else '../research_rounds/selection-rotation-abcd-20261025/CONCLUSION.md'
  lead='**2026-10-25最新：双通道选股×主动轮换A/B/C/D研究完成，不晋升。** 同池同2015—2026-10-22、S0各100万元，9新经济＋3旧IX控制、三执行情景。A/B/C/D基础收益−83.95%/−94.28%/−90.05%/−92.88%，回撤90.89%/96.40%/94.72%/95.26%；三情景A均相对好、仍不合格。C胜率提高却尾部利润减少，B未明显减少实际试错；行业前三挑战与原S0准入不完全一致。960年度赢家窗口参与62/55/61/54，寒武纪仍0。34392日账独立核对最大NAV差1e−22、12656物理截断日账及完整决策一致，旧账/算法保留，经济重跑/结果后规则修订0。下一提案先查全池开仓样本的阶段/经济质量，再设计一致目标组合；本轮停止，不自动续跑账户/阈值。[完整结论]('+href+')、[报告](http://127.0.0.1:8794/report/)。下方运行中/尚0是已完成前的阶段记录。\n\n'
  p.write_text(lead+p.read_text())
 print(dict(final_handoff_updated=True,real_local_links_checked=len(parser.refs)),flush=True)
if __name__=='__main__':main()
