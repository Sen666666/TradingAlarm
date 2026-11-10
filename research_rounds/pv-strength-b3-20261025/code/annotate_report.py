"""Append observed findings to the already-rendered report; never changes model."""
from pathlib import Path
import hashlib,json
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'report/index.html';s=p.read_text();assert 'id="observed-verdict"' not in s
before=hashlib.sha256(s.encode()).hexdigest()
findings='''<section class="panel" id="observed-verdict"><h2 style="margin-top:0">实际裁决：两项改善，一项核心目标仍未解决</h2>
<div class="twocol"><div><h3>整理更稳，急跌能当天转 freeze</h3><p>黄金2025年5—8月只出现两次温度切换：初段真实下跌为freeze，随后warm整理，再到neutral。2026年1月29日hot，1月30日下跌7.02%时直接freeze；2月2日继续识别急跌。</p></div>
<div><h3>仍会漏掉缓慢走弱，尚不合格</h3><p><strong>黄金2026年3月10—20日仍warm，价格却下跌9.64%；4月13日—6月5日连续37观察neutral，价格下跌6.65%。</strong>急跌抬高波动尺度、旧窗口和方向门槛的共同作用，使当前阴跌未被及时确认为cold。</p></div></div>
<p>快速启动也有代价：中芯2024年9月30日仍neutral，10月8日才warm，10月23日才hot。半导体2026年8月13日—9月10日也有“neutral期间下跌8.61%”的反例。<strong>不能用少跳档或少hot证明趋势正确。</strong></p>
<p><a href="../CONCLUSION.md">查看完整结论、原因和全部正反例</a>。本版保留为独立研究对照，不替换E0；不跑账户，不继续按这些日期调参数。</p></section>'''
s=s.replace('<div class="five">',findings+'<div class="five">',1);p.write_text(s)
receipt={'recorded_at':datetime.now(timezone.utc).isoformat(),'action':'append_post_output_verdict_only',
 'before_sha256':before,'after_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'model_changed':False}
with (ROOT/'audit/report-annotation.json').open('x') as f:json.dump(receipt,f,ensure_ascii=False,indent=2)
print(receipt)
