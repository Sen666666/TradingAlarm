"""Read-only report renderer. Does not run model, strategy or account."""
import json
from pathlib import Path
from html import escape

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'report'
OUT.mkdir(exist_ok=False)
manifest = json.loads((ROOT / 'figures/manifest.json').read_text())
data = json.loads((ROOT / 'analysis/viewer-data.json').read_text())
plots = [{**x, 'url': '../figures/' + Path(x['path']).name} for x in manifest['plots']]
names = {x['asset']: x['name'] for x in plots}
synthetic = {
    'fast_start': '快速启动', 'slow_rise': '持续慢涨',
    'consolidation': '上涨后整理', 'bear_rebound': '下降中反弹',
    'true_weakening': '持续转弱', 'lowvol_selloff': '低量连续大跌',
    'one_pulse': '单次脉冲往返', 'same_end_recovery': '同端点：先跌后恢复',
    'same_end_retracement': '同端点：最后回落',
}
template = r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PVS-B1｜量价强度原型与 E0 对照</title>
<style>
:root{--ink:#21374a;--muted:#617381;--line:#dce4e8;--purple:#703ab2;--orange:#b56b41;--bg:#f2f5f5}
*{box-sizing:border-box}body{margin:0;color:var(--ink);background:var(--bg);font:16px/1.7 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}
main{max-width:1440px;margin:auto;padding:30px 24px 72px}h1{font-size:34px;line-height:1.3;margin:12px 0}h2{font-size:23px;margin:0 0 18px}h3{font-size:18px;margin:12px 0}p{margin:10px 0}a{color:#17618b;text-underline-offset:3px}small,.muted{color:var(--muted)}.eyebrow{letter-spacing:.1em;font-size:12px;font-weight:700;color:#5d737b}.lead{max-width:1050px;font-size:18px}.card{background:white;border:1px solid var(--line);border-radius:14px;padding:24px;margin-top:22px}.verdict{background:#fff5e9;border-color:#e8c59f}.pill{display:inline-block;border-radius:20px;padding:3px 12px;margin:4px 7px 4px 0;background:#e8eef0;font-size:13px}.pill.warn{background:#f7e4cf;color:#805022}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.mini{background:#f5f7f8;padding:16px;border-radius:10px}.mini strong{display:block;font-size:20px}.controls{display:flex;gap:12px;flex-wrap:wrap;align-items:end}label{display:block;font-size:13px;color:var(--muted)}select,input,button{font:inherit;color:var(--ink);border:1px solid #c8d5dc;border-radius:7px;padding:9px 12px;background:white}select{min-width:190px;max-width:100%}button{cursor:pointer;background:#edf4f6}button:hover{background:#dfecee}.example-buttons{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0}.example-buttons button{font-size:13px;padding:7px 10px}input[type=range]{padding:0;width:100%;margin:16px 0 6px;accent-color:var(--purple)}.readout{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:12px 0}.readout div{border:1px solid var(--line);border-radius:8px;padding:12px;font-size:13px}.readout b{display:block;font-size:22px;font-variant-numeric:tabular-nums}.chart{display:block;width:100%;height:auto;border:1px solid var(--line);margin-top:15px}.chart-link{display:block;text-align:right;font-size:13px}table{border-collapse:collapse;width:100%;font-size:14px}td,th{border-bottom:1px solid var(--line);text-align:left;vertical-align:top;padding:13px 12px}th{background:#edf2f3}td:first-child{min-width:100px;font-weight:600}code,pre{font:13px/1.7 ui-monospace,SFMono-Regular,Menlo,monospace}pre{background:#eef2f4;padding:18px;white-space:pre-wrap;overflow-wrap:anywhere;border-radius:8px}.links{display:flex;gap:12px 24px;flex-wrap:wrap}.note{border-left:3px solid #bb8a53;padding-left:14px;color:#6e533a}.purple{color:var(--purple)}.orange{color:var(--orange)}.cyan{color:#1599a0}details{margin-top:18px}summary{cursor:pointer;font-weight:600}.scroll{overflow-x:auto}footer{margin-top:24px;color:var(--muted);font-size:13px}@media(max-width:750px){main{padding:18px 12px}h1{font-size:27px}.card{padding:16px}.grid{grid-template-columns:1fr}.readout{grid-template-columns:repeat(2,1fr)}select{min-width:0;width:100%}.controls>div{width:100%}}
</style></head><body><main>
<div class="eyebrow">TRADINGALARM / 研究原型 / 2026-10-25</div>
<h1>量价强度 PVS-B1 与 E0 对照</h1>
<p class="lead">目标一致：<strong>强度算法描述当时的量价，交易策略选择何时开仓、持有与退出。</strong>强度下降没有默认卖出含义；可以另行选择较弱阈值，保留长趋势持有。</p>
<div><span class="pill">7 条本地资产</span><span class="pill">20 张真实图 · 9 组合成路径</span><span class="pill">4 位空白 agent 多轮审查</span><span class="pill">E0 保留 · 账户运行 0</span></div>
<section class="card verdict"><h2>本轮裁决：保留原型，尚未达到统一强度指标的要求</h2>
<p>B1 能补充 E0 没有的连续推进速度描述。但它有时把已经发生的急跌放进“暂时偏离”，持续漂移分数仍接近最强。<strong>这是模型解释的不足，不能靠选择卖出阈值宣称已解决。</strong></p>
<p>不以过零次数判断交易好坏，也不据本轮图形宣布 E0 更优。没有做账户回测、收益比较或退出阈值寻优。</p></section>
<section class="card"><h2>原型在估计什么</h2><div class="grid">
<div class="mini"><strong>持续漂移 μ</strong>模型认为底层价格正在以多快速度推进。主分数 S 描述这一项。</div>
<div class="mini"><strong>暂时偏离 T</strong>允许冲击暂时偏离底层价格，预设半衰期为 5 个有效观察。这是假设，不是真实交易动机。</div>
<div class="mini"><strong>成交量改变解释</strong>相对历史的量比进入状态创新方差，再影响状态更新。放量同时允许持续或暂时解释，不自动等于强势。</div>
</div><p>主分数 S = 100 × tanh(√21 × μ / σ)。σ 是此前 63 个有效观察的日对数收益 RMS，今日收益不进入今日的历史基准。S 是相对自身波动的有符号漂移，<strong>不是上涨概率、收益空间或已验证的跨股排名</strong>。</p>
<p class="muted">B1 的新增状态使用收盘价和成交量；OHLC 用于真实观察校验，原 E0 继续使用原量价事件与支持线。模型不读取 E0、成本价、浮盈或未来标签。</p></section>
<section class="card" id="real"><h2>真实走势：逐资产、逐日期对照</h2>
<div class="controls"><div><label for="asset">资产</label><select id="asset"></select></div><div><label for="window">固定观察窗</label><select id="window"></select></div><div><label for="date">查看日期（仅用不晚于此日的真实报价）</label><input id="date" type="date"></div></div>
<div class="example-buttons"><button data-case="gold-fall">急跌反例｜沪金 2026-02-02</button><button data-case="semi-fall">急跌反例｜半导体 2026-07-02</button><button data-case="smic-start">快速启动｜中芯 2024-10-08</button><button data-case="demli-bounce">反弹正例｜德明利 2026-07-21</button><button data-case="gold-range">整理｜黄金ETF 2025-07-31</button></div>
<input id="day" type="range" min="0" max="1" value="0" aria-label="逐观察日期"><div id="date-note" class="muted"></div>
<div class="readout" id="readout"></div>
<p class="muted"><span class="orange">橙色背景 / 支持线：原 E0 有效状态，非实际持仓。</span> <span class="purple">紫色：主 S。</span> 灰虚线：去量 a=1 对照。<span class="cyan">青色：含 T 的模型位移诊断。</span>后三者不能任选一条当作“真强度”。</p>
<a id="chart-link" class="chart-link" target="_blank">打开原图</a><img class="chart" id="chart" alt="所选资产的价格、原E0状态、成交量与PVS-B1强度对照">
<p class="note">上方日期只更新数值读取，原图保持完整固定窗，便于同时看上下文。真实样本均为已见历史开发材料；不能用后来涨跌倒填当日“整理 / 真反转”标签。日期读取不提供买卖建议。</p>
</section>
<section class="card"><h2>五类现象：有响应，但哪些还解释不好</h2><div class="scroll"><table><thead><tr><th>现象</th><th>本轮可观察增量</th><th>关键限制</th></tr></thead><tbody>
<tr><td>快速启动</td><td>中芯与半导体启动后，S 可以转强。</td><td>冲击先被分给 T，启动可能迟升。中芯 2024-10-08 主 S +80.93，含 T 诊断却 −91.18，模型分量存在明显分歧。</td></tr>
<tr><td>持续慢涨</td><td>沪金 2023、招商部分慢涨可得到正 S；不要求天天放量。</td><td>很小但平滑的推进也会接近 +100。它表达相对噪声的速度，尚不表示绝对机会大小或结构质量。</td></tr>
<tr><td>趋势内整理</td><td>黄金 2025 年 5—8 月 S 减弱，E0 较大结构仍有效，提供不同维度。</td><td>S 多次正负变化；合成整理最低 −62.53。它没有独立表达“推进慢了，但已有上行成果仍保留”。不能据变号自动退出。</td></tr>
<tr><td>跌势反弹</td><td>德明利 2026-07-21 涨 5.20%、明显放量，S 仍 −99.93，没有自动视为恢复。</td><td>下降中合成反弹的第 8 根，S 已升至 +71.54；半导体 2022 反弹也会升强。局部反弹与大结构恢复仍混淆。</td></tr>
<tr><td>真正转弱</td><td>德明利连续低量下跌时能转强负；部分下降后段响应清楚。</td><td>沪金 2026-02-02 当日 −13.16%，S 仍 +99.87；半导体 2026-07-02 约 −8.3%，S 仍 +99.32。不能宣称已可靠识别早期破坏。</td></tr>
</tbody></table></div><p>这些不是分类准确率；真实窗口重叠，也没有完整人工真值标签。评价依据是同一固定版本对正反例的解释是否自洽。</p></section>
<section class="card"><h2>合成反例：保留失败，不靠阈值美化</h2><div class="controls"><div><label for="synthetic">固定路径</label><select id="synthetic"></select></div></div><img class="chart" id="synthetic-chart" alt="固定合成路径的强度诊断">
<p>快速启动、慢涨、整理、下降反弹、连续转弱、低量大跌、单次往返以及相同端点不同顺序均保留。相同前缀在未来分叉之前必须同输出；不能要求模型预知后来结局。</p>
<p class="note">连续低量大跌的合成例中，主 S 仍能保持正值；它与德明利的成功窗口必须一起看。量价版也不总优于去量版：某个反弹日期分别为 +71.54 / −97.22，另一个转弱日期为 −92.90 / +69.64。量确实改变了计算，经济增量尚未证明。</p></section>
<section class="card"><h2>调研吸收了什么</h2><div class="scroll"><table><thead><tr><th>方向</th><th>有用之处</th><th>本轮取舍</th></tr></thead><tbody>
<tr><td>ADX / DMI</td><td>区分方向与趋势幅度，避免把所有“强”都理解成上涨。</td><td>不包含量，也不直接识别整理与破坏；已有方向运动研究不能只换名称。</td></tr>
<tr><td>KAMA / 路径效率</td><td>表达同样净涨幅下路径是否曲折，兼顾推进速度与噪声。</td><td>旧项目已有实现；仅净位移或效率不足以解释路径先后、量后响应和结构保留。</td></tr>
<tr><td>量价后续响应</td><td>量可能伴随延续，也可能伴随反转；含义要由之后已经发生的价格响应检验。</td><td>采纳竞争解释，未把放量固定当加分。参见 <a href="https://web.mit.edu/wangj/Public/Publication/Llorente-Michaely-Saar-Wang02.pdf">Llorente 等原文</a>、<a href="https://web.mit.edu/wangj/www/pap/CampbellGrossmanWang93.pdf">Campbell 等原文</a>。</td></tr>
<tr><td>前向状态过滤</td><td>随着新量价更新潜在漂移，保留未决解释，避免后视平滑。</td><td>实现 B1 的持续 / 暂时分解。方法参考 <a href="https://econweb.ucsd.edu/~jhamilto/palgrav1.pdf">Hamilton</a>；B1 并非其原公式，也未验证分量是真实经济状态。</td></tr>
<tr><td>事件响应 / 路径签名</td><td>分别提供冲击是否兑现与路径先后的表示。</td><td>作为设计审查方向保留，未接成补洞模型或新增算法队列。事件稀少会漏慢涨，路径表示本身不赋予强弱语义。</td></tr>
</tbody></table></div><p><a href="../reviews/theory/PRIMARY_SOURCE_REVIEW.md">完整第一手资料与机制审查</a> · <a href="https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/DMI">DMI / ADX 定义</a> · <a href="https://arxiv.org/abs/1603.03788">路径签名原文</a></p>
<details><summary>完整冻结公式与初值</summary><pre>yₜ = log(Cₜ / C_first)
Lₜ = Lₜ₋₁ + μₜ₋₁ + ηL
μₜ = μₜ₋₁ + ημ
Tₜ = ρ Tₜ₋₁ + ηT,    yₜ = Lₜ + Tₜ + ε
ρ = 2^(−1/5)
σₜ = max(RMS(r[t−63:t]), 10⁻⁸)   # 不含今日收益
aₜ = clip(Vₜ / median(V[t−21:t]), .25, 4)
三分支固定先验 = (19/21, 1/21, 1/21)
Q_normal / σ²     = diag(.01, 1/21², .01)
Q_persistent / σ² = diag(a, a/5², .01)
Q_transient / σ²  = diag(.01, 1/21², 4a)
R = .25 σ²
S = 100 tanh(√21 × μ / σ)

每期各分支前向更新 → 似然 × 固定先验 → 总均值/协方差矩匹配。
第65有效收盘初始化 L=y, μ=T=0；第66个收盘首次评分。
无效观察未知；明确源分段重启；无后向平滑、全样本拟合或参数扫描。</pre>
<p>5 / 21 / 63 是观察尺度，Q、R、先验是本轮探索性假设，未由文献校准。量同时扩大两种创新的容许范围，并不证明对每类路径都有利。</p>
<p>“21 期原始推进幅度”=100×expm1(21μ)，只是速度换单位。青色“含 T 位移”=21μ+(ρ²¹−1)T，从潜在拟合位置计；从实际收盘计还缺拟合残差。它仅用于揭示模型分歧，非收益预测、非第二候选。</p></details></section>
<section class="card"><h2>结论与后续研究边界</h2><p><strong>“连续强度作为 E0 增量”这个目标保留；PVS-B1 的单一漂移分数不足以完成它。</strong>本轮暴露了需要分别表达的三件事：当前推进速度、已形成结构保留多少、反向冲击是否持续兑现。将其中一项叫作全部强度，会混淆强反弹、正常整理和破坏。</p>
<p>若继续，优先解决这三者的定义、尺度和相互反证关系，再讨论是否能有依据地合成一个值。此次没有据结果追加条件、修改参数、重新分档，亦未启动新的交易实验。</p>
<p class="muted">E0 原输出保留，可以继续原策略。并未证明任何一个 S 阈值能精确重建 E0；也不会用 E0 反向定义 S 来制造“兼容”。</p></section>
<section class="card"><h2>可复算证据与数据口径</h2><p>本地已有全历史作预热，主展示 2021 年起；德明利源从 2022 上市开始。黄金 ETF 截至 2026-10-16，四股截至 10-22，沪金 / 半导体截至 10-23。股票与 ETF 使用既有因果研究坐标；沪金连续合约拼接和调整口径未知，换月可能影响量。研究价格不自动等于可成交原价。</p>
<p>30 项技术不变量、21 次实际截断前缀、9 组合成检查通过；独立实现复算 308,653 个有限值，最大差 9.36×10⁻⁹。原 E0/R/R1 登记 30 文件哈希保持。技术通过不等于模型语义正确或交易有效。</p>
<p>执行记录保留偏差：真实缓存生成早于合成检查，合成检查完成早于真实图揭示；参数与公式结果后修订 0。准备期 / 最终协议哈希阶段差异与字段解释均保留在补充说明。</p>
<div class="links"><a href="../PROTOCOL.md">冻结协议</a><a href="../freeze.json">版本哈希</a><a href="../CONCLUSION.md">完整结论</a><a href="../SEMANTIC_CLARIFICATIONS.md">语义与执行说明</a><a href="../validation/checks.json">因果检查</a><a href="../reviews/implementation/REVIEW.md">独立实现审计</a><a href="../reviews/definition/OUTPUT_REVIEW.md">定义复评</a><a href="../reviews/raw/ALL_FIGURES_REVIEW.md">20 图逐一复评</a><a href="../analysis/selected-facts.csv">关键事实 CSV</a><a href="../inputs/manifest.json">数据来源</a><a id="csv-link">当前资产逐日 CSV</a></div></section>
<footer>一个正式候选 · 参数结果后修订 0 · 账户运行 0 · 不构成原“趋势动物”算法还原 · 全部开发历史，未认领样本外表现。</footer>
</main><script>
const D=__DATA__,P=__PLOTS__,N=__NAMES__,Y=__SYNTHETIC__;
const $=id=>document.getElementById(id);let rows=[];
Object.entries(N).forEach(([k,v])=>$('asset').add(new Option(v+' '+k,k)));
Object.entries(Y).forEach(([k,v])=>$('synthetic').add(new Option(v,k)));
const fmt=(v,n=2)=>v===null||v===undefined||!Number.isFinite(Number(v))?'未知':Number(v).toFixed(n);
function chooseAsset(sid,wid,date){$('asset').value=sid;$('window').replaceChildren();P.filter(x=>x.asset===sid).forEach(x=>$('window').add(new Option(x.id+' | '+x.start+'—'+x.end,x.id)));if(wid)$('window').value=wid;chooseWindow(date);}
function chooseWindow(date){const p=P.find(x=>x.id===$('window').value);$('chart').src=p.url;$('chart-link').href=p.url;rows=D[p.asset].filter(x=>x.date>=p.start&&x.date<=p.end);$('day').max=rows.length-1;$('date').min=rows[0].date;$('date').max=rows.at(-1).date;$('csv-link').href='../results/'+p.asset+'.csv';$('date').value=date||rows.at(-1).date;chooseDate();}
function chooseDate(){let idx=rows.findLastIndex(x=>x.date<=$('date').value);if(idx<0)idx=0;$('day').value=idx;draw(idx);}
function draw(i){const r=rows[i],requested=$('date').value;$('date-note').textContent='实际观察：'+r.date+(requested!==r.date?'（请求 '+requested+'，没有把旧报价标成新数据）':'')+' · 当前固定窗 '+rows.length+' 个源观察；预热使用更早历史';
const fields=[['研究收盘',fmt(r.close,4)],['主强度 S',fmt(r.strength)],['原 E0 有效',r.e0_target===null?'未知':r.e0_target===1?'是':'否'],['E0 支持',r.e0_target===1?fmt(r.e0_floor,4):'未启用'],['原始推进 μ（21期幅度 %）',fmt(r.drift_21_pct)],['暂时偏离 T / σ',fmt(r.temporary_sigma)],['去量对照 S',fmt(r.price_only_strength)],['含 T 位移诊断',fmt(r.total_21_strength)]];
$('readout').replaceChildren(...fields.map(([a,b])=>{const el=document.createElement('div');el.append(a);const v=document.createElement('b');v.textContent=b;el.append(v);return el;}));}
$('asset').onchange=()=>chooseAsset($('asset').value);$('window').onchange=()=>chooseWindow();$('date').onchange=chooseDate;$('day').oninput=()=>{$('date').value=rows[Number($('day').value)].date;draw(Number($('day').value));};
function showSynthetic(){$('synthetic-chart').src='../figures/'+$('synthetic').value+'.png';}$('synthetic').onchange=showSynthetic;
const cases={'gold-fall':['AU0','au_2025_26','2026-02-02'],'semi-fall':['512480','semi_2026','2026-07-02'],'smic-start':['688981.SH','688981_SH_2024_26','2024-10-08'],'demli-bounce':['001309.SZ','001309_SZ_2024_26','2026-07-21'],'gold-range':['518880','gold_2024_25','2025-07-31']};document.querySelectorAll('[data-case]').forEach(b=>b.onclick=()=>chooseAsset(...cases[b.dataset.case]));
chooseAsset('AU0','au_2025_26','2026-02-02');showSynthetic();
</script></body></html>'''
for token, value in [('__DATA__', data), ('__PLOTS__', plots), ('__NAMES__', names), ('__SYNTHETIC__', synthetic)]:
    template = template.replace(token, json.dumps(value, ensure_ascii=False).replace('</', '<\\/'))
(OUT / 'index.html').write_text(template)
print({'report': str(OUT / 'index.html'), 'real_figures': len(plots), 'synthetic': len(synthetic)})
