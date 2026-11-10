"""Self-contained human case-review page from verified local charts."""
import base64,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'results/tech-2026-review'

def main():
    report=json.loads((OUT/'report.json').read_text());rows=''
    for r in report['reports']:
        p=r['period_returns'];rows+=f"<tr><td>{r['symbol']}</td><td>{p['Jan-May']:+.2%}</td><td>{p['June']:+.2%}</td><td>{p['July-Oct16']:+.2%}</td></tr>"
    images=''.join(f'<figure><img alt="{name} 2026 price and strength" src="data:image/png;base64,{base64.b64encode((OUT/(name+".png")).read_bytes()).decode()}"></figure>' for name in ('USHJ512480','HK03033'))
    html='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>2026 科技行情：趋势拟合逐段复盘</title><style>body{font:17px/1.8 system-ui,sans-serif;max-width:1120px;margin:36px auto;padding:0 24px;color:#172b4d;background:#f8fafc}h1{font-size:30px}h2{margin-top:36px;font-size:23px}table{border-collapse:collapse;width:100%;background:white}td,th{padding:10px 14px;text-align:left;border-bottom:1px solid #dbe2ea}figure{margin:24px 0}img{width:100%;background:white;border-radius:8px}.note{background:#eaf0fb;padding:16px;border-radius:8px}.bad{color:#9f1239}li{margin:10px 0}</style><h1>2026 科技行情：趋势拟合逐段复盘</h1>
<p>本页依据项目本地行情，截至 2026-10-16。半导体 ETF 512480 与恒生科技 ETF 03033 是两个具体代理，不代表所有科技资产。6 月／7 月分界仅用于人工复盘，没有写入模型。</p>
<h2>先核对“牛市—转冷”发生在哪里</h2><table><thead><tr><th>代理</th><th>1—5 月</th><th>6 月</th><th>7 月—10 月16日</th></tr></thead><tbody>'''+rows+'''</tbody></table>
<p>半导体符合“前期强、后期急冷”，但 6 月仍是加速上涨，拐点接近 6 月末；恒生科技在 1—5 月已经下跌，不能套用同一段牛市叙事。价格使用现有公司行为调整，512480 的 7 月 3 日拆分不应当算作价格暴跌。</p>
<h2>半导体：模型做对了什么，又错在哪里</h2><ol>
<li><b>4—5 月上涨：</b>动态模型在 4 月 10 日给出进入信号，账户于 4 月 13 日买入，确实识别了这段上涨。</li>
<li><b>5 月末—6 月初回调：</b>6 月 1 日强度降至 1.62，6 月 2 日卖出。6 月 17 日才重新转强，18 日买回。两次成交开盘价之间，调整后价格上涨约 16.46%。这是主升过程中退出、恢复识别偏慢的具体代价；不是声称事前应该知道这次回调一定结束。</li>
<li><b>6 月末—7 月转冷：</b>6 月 30 日达到年内价格峰值时，动态强度仍为 9.88。7 月 6 日降至 2.28，7 月 7 日账户卖出；从峰值至实际卖出开盘价约回撤 12.81%。它识别了转弱，未提前识顶，也没有扛完整段后续跌幅。固定直线更晚，到 7 月 15 日才降到退出阈值。</li>
<li><b>8、9 月反弹：</b>模型分别于 8 月 12 日、9 月 21 日重新给出强趋势信号，随后退出。结合当时已经出现的下降结构看，它仍容易把局部反弹评得过强。这是需要修正的拟合问题，不能只靠调高买入阈值掩盖。</li></ol>
<h2>新原型不能只看“少亏”</h2><p class="bad">紫色的“无方向状态”原型避开了不少后期反弹，却在半导体 6 月整段大涨中没有达到进入条件；6 月 30 日强度也只有 6.82。它目前会漏掉我们要捕捉的机会，不能仅凭随机路径上的误报减少就宣布成功。它尚未完成市场账户回测。</p>
<h2>恒生科技：反弹误判是更清楚的反例</h2><p>年内峰值出现在 1 月 14 日。动态模型在 1 月 20 日判弱、21 日卖出，随后在 3、4、6、7 月的反弹中反复尝试。3—7 月每次买卖的原始成交价均以卖出较低结束（尚未计费用），说明仅识别短期上行动量不够。固定直线全年没有进入，“无方向”原型也未进入，但不能因此为港股单独挑模型；相同版本还必须抓得到半导体的上涨。</p>
<h2>下一轮怎样迭代</h2><p>评价应同时覆盖：4—6 月趋势启动与持有、6 月初回调中的误退出、7 月转弱的响应、8—9 月反弹的误识别，以及恒生科技下行中的反弹。改动仍放在量价轨迹的状态拟合，研究它能否区分“已有上升结构中的回调”与“已有下降结构中的反弹”，而非添加六月日历条件或市场专用阈值。此页已经用于开发诊断，今后不能再当盲测。</p>
<p class="note">先补一个数据语义检查：512480 的 2:1 拆分改变了股数和原始成交量单位。价格已调整，图中原始成交量仍会机械变化。既有几何模型使用原始成交量作权重，需要核对并用一致单位做对照，不能把这个跳变直接解释为资金参与增强。下图绿色／红色标记为既有账户成交日期，显示位置取当天调整后收盘价，并非成交价格。紫色竖线为事后识别的年内峰值。几何强度与紫色原型的模型概率分数含义不同。</p>
'''+images+'''<p>原始逐日分数、信号与实际成交明细保存在同目录 report.json 和 *-daily.parquet。两个示例仅用于解释模型，不构成收益或普适性验证。</p></html>'''
    (OUT/'review.html').write_text(html)
if __name__=='__main__':main()
