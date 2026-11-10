"""Embed the written verdict in the local report, preserving its prior render."""
import json
import shutil

from common import ROOT, sha, write, now
from report import HTML, build_payload, clean


RESULTS = '''<section class="panel" id="verdict"><h2>本轮裁决：保留为指标层，不晋升账户策略</h2>
<p><strong>新增证据机制成立，阴跌表达和快启动有具体改善；平滑迟滞与陈旧结构仍然存在。</strong>同7标的22窗，账户回测0。469次真实向上结构确认均有当日正收益和新增前沿；这项技术事实不等于盈利证据。</p>
<div class="scroll"><table><thead><tr><th>固定案例</th><th>本轮读数</th><th>与旧B3对照及边界</th></tr></thead><tbody>
<tr><td>沪金阴跌<br>2026-04-13—06-05</td><td>37观察、价格−6.65%；μ21有<strong>31观察为负</strong>，较大结构始终向下。</td><td>B3全部neutral；局部仍有30观察保留旧反弹确认，未将真实反弹抹掉。</td></tr>
<tr><td>半导体下行<br>2026-08-13—09-10</td><td>21观察、价格−8.61%；μ21有<strong>18观察为负</strong>，21观察结构双下。</td><td>B3全部neutral；这描述已发生推进，不保证随后继续下跌。</td></tr>
<tr><td>中芯快启动<br>2024-09-26／27</td><td>S21在<strong>09-26</strong>、S63在<strong>09-27</strong>确认上行；09-27 μ21为+93.12 log基点／观察。</td><td>B3在09-27仍cold、09-30为neutral；确认语义不同，不能将日期领先当作收益领先。</td></tr>
<tr><td>德明利转弱<br>2025-12-19</td><td>单日约−7.01%；μ21降至<strong>−105.51</strong>，S21保持下，没有新向上确认。</td><td>旧B3 cold→warm；本轮没有自动转暖，但S63仍为旧向上结构，且当天未达急跌资格。</td></tr>
</tbody></table></div>
<h3>两项必须保留的反例</h3><div class="scroll"><table><thead><tr><th>反例</th><th>未解决的限制</th></tr></thead><tbody>
<tr><td>半导体 2026-07-02</td><td>急跌和μ5转负已可见，μ21仍+77.54且结构双上。S21到07-15、S63到07-17才翻下，较06-30已分别跌约18.00%、28.79%；急跌标记不能掩盖结构迟滞。</td></tr>
<tr><td>黄金ETF 2026-05-08—06-05</td><td>连续21观察结构双上，μ21却全部为负；价格−6.36%。<strong>旧结构向上不等于当前强势</strong>，AU0局部改善不能外推为全部解决。</td></tr>
</tbody></table></div>
<p class="sub">定量事实及其他反例来自本轮 <a href="../CONCLUSION.md">完整结论</a>；页面下方保存全文快照。不同量的结构差异、箱体过零、失败反弹和全部技术边界均保留。</p></section>
'''


def main():
    conclusion = ROOT / 'CONCLUSION.md'
    if not conclusion.exists():
        raise FileNotFoundError('A completed conclusion is required for finalization')
    target = ROOT / 'report'
    previous = ROOT / 'report-v2'
    previous.mkdir(exist_ok=False)
    shutil.copy2(target / 'index.html', previous / 'index.html')
    if (target / 'build-receipt.json').exists():
        shutil.copy2(target / 'build-receipt.json', previous / 'build-receipt.json')
    payload = build_payload()
    assert payload['conclusion']
    encoded = json.dumps(clean(payload), ensure_ascii=False, allow_nan=False).replace('</', '<\\/')
    html = HTML.replace('<div class="three">', RESULTS + '<div class="three">', 1)
    html = html.replace('__PAYLOAD__', encoded)
    temporary = target / 'index.html.tmp'
    temporary.write_text(html)
    temporary.replace(target / 'index.html')
    receipt = {'recorded_at': now(), 'action': 'display_only_conclusion_snapshot',
               'prior_html': str(previous / 'index.html'), 'prior_sha256': sha(previous / 'index.html'),
               'final_html': str(target / 'index.html'), 'final_sha256': sha(target / 'index.html'),
               'conclusion_sha256': sha(conclusion), 'html_bytes': len(html.encode()),
               'model_run': False, 'plots_regenerated': False, 'results_modified': False,
               'top_summary_source': 'CONCLUSION.md; four fixed cases and two retained counterexamples'}
    write(target / 'finalize-receipt.json', receipt)
    print(receipt, flush=True)


if __name__ == '__main__':
    main()
