"""Static local report and date inspector. Reads saved results only."""
import json
from pathlib import Path
from common import ROOT,NAMES,read

folder=ROOT/'report';folder.mkdir(exist_ok=False)
plots=read(ROOT/'figures/real-manifest.json')['plots']
for x in plots:x['url']='../figures/real/'+Path(x['path']).name
syn=read(ROOT/'figures/synthetic-manifest.json')['plots']
labels={'fast_start':'快速启动','slow_rise':'持续慢涨','consolidation':'上涨后整理',
    'bear_rebound':'下降中反弹','true_weakening':'持续转弱','lowvol_selloff':'低量连续大跌',
    'one_pulse':'单次往返','same_end_recovery':'同端点：下跌后收复','same_end_retracement':'同端点：正在回吐',
    'mirror_fast_start':'快速下行镜像','mirror_lowvol_selloff':'低量急涨镜像','V_continues':'共同前缀：继续V形上行',
    'rebound_fails':'共同前缀：反弹后再跌','flat_box':'重要反例：窄箱体','constant':'常量价格',
    'single_lowvol_shock':'低量单次急跌后横盘','debt_partial_revisit':'部分收复后重访'}
html=r'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PVS-B2｜推进、结构与冲击</title>
<style>
:root{--ink:#263b49;--muted:#617580;--line:#dae3e7;--green:#168c76;--blue:#285f91;--red:#bf4756}*{box-sizing:border-box}body{margin:0;background:#f0f4f4;color:var(--ink);font:16px/1.75 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}main{max-width:1450px;margin:auto;padding:28px 24px 70px}h1{font-size:34px;line-height:1.4;margin:10px 0}h2{font-size:23px;margin:0 0 14px}h3{font-size:18px}p{margin:9px 0}a{color:#17618b;text-underline-offset:3px}.muted,small{color:var(--muted)}.eyebrow{font-size:12px;letter-spacing:.12em;color:#6f858d;font-weight:700}.lead{font-size:18px;max-width:1050px}.pill{display:inline-block;background:#e5ecee;border-radius:20px;padding:3px 11px;font-size:13px;margin:4px 7px 4px 0}.card{background:#fff;border:1px solid var(--line);border-radius:13px;padding:24px;margin-top:20px}.verdict{background:#ecf5f1;border-color:#b9d7c8}.limit{background:#fff5ea;border-color:#e6ccac}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.mini{background:#f2f6f7;padding:16px;border-radius:9px}.mini b{font-size:19px}.mini .letter{display:block;font-size:30px;font-weight:700}.controls{display:flex;gap:12px;align-items:end;flex-wrap:wrap}label{display:block;font-size:13px;color:var(--muted)}button,select,input{font:inherit;background:white;color:var(--ink);border:1px solid #c7d5dc;border-radius:7px;padding:9px 12px}select{max-width:100%;min-width:190px}button{cursor:pointer;background:#eef4f5}button:hover{background:#e0ecee}.buttons{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0}.buttons button{font-size:13px;padding:7px 10px}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:14px}.metric{padding:12px;border:1px solid var(--line);border-radius:9px;font-size:13px}.metric strong{display:block;font-size:23px;font-variant-numeric:tabular-nums}.metric.green{border-top:3px solid var(--green)}.metric.blue{border-top:3px solid var(--blue)}.metric.red{border-top:3px solid var(--red)}input[type=range]{padding:0;width:100%;accent-color:#285f91}.chart{display:block;width:100%;height:auto;margin-top:15px;border:1px solid var(--line)}.chart-link{display:block;text-align:right;font-size:13px}.note{border-left:3px solid #b38b59;padding-left:13px;color:#775a38}.scroll{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:14px}td,th{text-align:left;vertical-align:top;padding:12px;border-bottom:1px solid var(--line)}th{background:#edf2f4}td:first-child{font-weight:600;min-width:105px}details{margin-top:16px}summary{cursor:pointer;font-weight:600}pre{padding:17px;background:#f0f4f5;border-radius:8px;white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.8 ui-monospace,SFMono-Regular,Menlo,monospace}.links{display:flex;flex-wrap:wrap;gap:9px 24px}footer{font-size:13px;color:var(--muted);margin-top:24px}@media(max-width:750px){main{padding:17px 12px}.card{padding:16px}h1{font-size:27px}.grid{grid-template-columns:1fr}.metrics{grid-template-columns:repeat(2,1fr)}.controls>div{width:100%}select{width:100%;min-width:0}}
</style></head><body><main>
<div class="eyebrow">TRADINGALARM / PVS-B2 / 2026-10-25</div><h1>把推进、结构和冲击分开看</h1>
<p class="lead">回应黄金两段强度摆动：P 描述实际推进，R 描述一个明确结构还保留多少，D 显示即时冲击及量价位移的收复。<strong>不合成总分，不默认下降就卖。</strong></p>
<div><span class="pill">同7资产 · 22张真实图</span><span class="pill">17组合成 · 5位空白agent多轮审查</span><span class="pill">E0 / B1保留 · 账户0</span></div>
<section class="card verdict"><h2>本轮判断：分层描述有增量，统一判强仍未解决</h2><p>两个黄金窗口的区别更清楚了：整理时局部速度可来回，但上行成果仍保留；下降时短期反弹可为正，下降结构并未因此消失。急跌也有当天的直接读数。</p><p>代价同样明确：月度速度仍会滞后，R可能很晚才破坏，也会给小反弹一个“全部保留”的100%；窄箱体会切换小结构。<strong>这版还不能直接当温度等级、横向排名或开仓门槛。</strong></p></section>
<section class="card"><h2>你指出的两段，原因分别是什么</h2><p>逐日分解发现，2025年5—8月跳分的直接 μ / σ 绝对变化份额为98.52% / 1.48%；2026年3—6月为97.17% / 2.83%。这是同一递推的代数归因，不是独立因果方差解释率。tanh没有凭空产生过零；主要是B1在来回价格里反复改判局部漂移，且没有结构背景。</p><p>急跌是另一种机制：2026-02-02的价格残差主要被B1的“暂时项”吸收，旧正漂移留下，再被饱和映射压成接近满分。仅加长平滑或调整分母不能同时解决这两种问题。</p><div class="scroll"><table><thead><tr><th>精确主窗</th><th>旧B1</th><th>B2推进 / 结构</th><th>解释边界</th></tr></thead><tbody>
<tr><td>2025年5—8月<br>83观察，首末−1.23%</td><td>S −97.15～+83.79，过零14次</td><td>P21均值+0.052波动单位；过零8次。R保持上行方向，成果保留72.39%～91.92%。</td><td>P5仍过零16次，反映局部往返；R保留不等于正在强劲加速。9月真实推进另列。</td></tr>
<tr><td>2026年3—6月<br>82观察，首末−26.39%</td><td>S −98.07～+30.01，正值仅3日，过零3次</td><td>P21过零同为3次。R在3月23日换下行，此后局部反弹未把它改为上行。</td><td>不是把本窗误说成反复满分看多。P5仍有真实反弹；结构早期也有滞后。</td></tr>
</tbody></table></div><p class="muted">这些次数不是交易次数；P21与B1使用不同估计方式，更少过零不自动表示更好。精确窗不包含9月/7月，包含端点月的旧统计另存。</p></section>
<section class="card"><h2>三维各自有什么依据</h2><p class="muted">这里的R仅为B2内部保留比例记号（R_ret），不是项目已冻结的R敏感退出政策；E0/R/R1名称原义保持。</p><div class="grid">
<div class="mini"><span class="letter" style="color:var(--blue)">P</span><b>实际路径推进</b><p>最近5 / 21个有效观察，用已发生的log价格拟合斜率。既给原单位，也给自身波动单位；不再假设一个会自动恢复的暂时分量。</p><small>允许反弹时短期P为正。P21仍可能在急跌第一天为正。</small></div>
<div class="mini"><span class="letter" style="color:var(--green)">R</span><b>结构成果保留</b><p>起点固定，极值随真实推进更新。回撤达到冻结的2σ才记检查点；价格重返该点，才确认回撤低点/高点并推进支持。</p><small>跨回撤保存结构；R=100%只表示本段成果未回吐，必须同时看跨度、年龄和确认次数。</small></div>
<div class="mini"><span class="letter" style="color:var(--red)">D</span><b>冲击与实际收复</b><p>所有量下的当日r/σ都显示。双倍通常量且位移至少1σ，才登记量价区间；之后普通量价格也能部分或全部收复。</p><small>部分收复不复活，时间不自动治愈。D区域为0不是“没有风险”。</small></div>
</div><p class="note">量只改变D证据的建立与后续未收复记录，P/R是价格路径维度。没有把成交量读入后冒称三轴都受量驱动；量门槛是否有经济增量尚未证明。</p></section>
<section class="card" id="charts"><h2>同批黄金、半导体和股票：逐日对照</h2>
<div class="controls"><div><label for="asset">资产</label><select id="asset"></select></div><div><label for="window">固定观察窗</label><select id="window"></select></div><div><label for="date">日期（读取不晚于该日的实际观察）</label><input id="date" type="date"></div></div>
<div class="buttons"><button data-case="range">黄金整理</button><button data-case="decline">黄金下降</button><button data-case="crash">黄金急跌 2026-02-02</button><button data-case="semi">半导体反弹 2026-08-10</button><button data-case="bad-bounce">反例：半导体 2022-08-05</button><button data-case="smic">中芯启动</button><button data-case="demli">德明利低量跌势</button></div>
<input id="day" type="range" min="0" max="1" value="0" aria-label="逐观察日期"><p id="date-note" class="muted"></p>
<div class="metrics" id="metrics"></div><p id="structure-note" class="note"></p><p id="debt-note" class="muted"></p>
<details><summary>更多当日字段：原单位、保护点、历史记忆</summary><div class="scroll"><table id="detail"></table></div></details>
<p class="muted">原图从上至下：价格与E0/B2支持、量、旧B1分数、P5/P21、带方向的R、当日冲击、量价区域。R正负轴只编码结构方向，±100不是统一强弱满分。E0背景是有效状态，不是实际持仓；日期选择只更新读数，原图保持完整固定窗。</p>
<a class="chart-link" id="image-link" target="_blank">打开原图</a><img id="chart" class="chart" alt="量价、原E0、B1及PVS-B2三维对照">
</section>
<section class="card"><h2>几个关键正反例</h2><div class="scroll"><table><thead><tr><th>案例</th><th>当时输出</th><th>能说与不能说</th></tr></thead><tbody>
<tr><td>沪金2026-02-02<br>当日−13.16%</td><td>B1 +99.87；P5 −2.08，P21 +2.26；上行成果剩74.2%；即时冲击−8.47σ。</td><td>巨大反向冲击当天显露，不再只看到一个近满分。月度速度和旧大结构仍可正，不能任取一项宣布安全。</td></tr>
<tr><td>沪金2026-04-01<br>下降中的反弹</td><td>P5 +0.55、P21 −1.25；下行结构成果剩60.6%。</td><td>局部反弹与较大下降可以同时表达；当时并不知道之后一定再跌。</td></tr>
<tr><td>半导体2026-08-10</td><td>P5 +1.65、P21 −1.23；下行结构剩67.3%。</td><td>能显示“短期恢复、较大下降未消失”，不是自动排除/买入该标的。</td></tr>
<tr><td>半导体2026-07-02<br>当日约−8.3%</td><td>P21仍+2.59，R上行剩90.8%，下行量资格区域0；即时冲击−2.58σ。</td><td>若忽略即时冲击，仍会误读强。D区域0仅表示不满足该量资格记忆；低量/普通量下跌不是安全。</td></tr>
<tr><td>半导体2022-08-05<br>重要反例</td><td>新上行R=100%，已知年龄0、支持确认0、跨度14.32 log百分点。</td><td>反弹可以形成新的局部结构。此原型仍不能保证区分它与持续大趋势；新R=1绝不能当成熟强势。</td></tr>
<tr><td>中芯2024年9月底</td><td>P/冲击可提前显露推进；R到9月30日转上行时，本段已含34.70 log百分点。</td><td>结构确认存在明显滞后。不能承诺仅依R仍能早抓全部快速启动。</td></tr>
</tbody></table></div></section>
<section class="card limit"><h2>合成否证：不能只保留漂亮的黄金</h2><div class="controls"><div><label for="synthetic">17条固定路径</label><select id="synthetic"></select></div></div><img class="chart" id="synthetic-chart" alt="PVS-B2固定合成反例">
<p><strong>窄箱体：</strong>160观察反复切换小结构23次，每条小腿仅1.52 log百分点，但R可反复到±100；没有解决一般盘整的结构噪声。<strong>真实V：</strong>共同前缀后的上行到第37观察才改变R，已推进24.2 log百分点。<strong>持续转弱：</strong>P5第3次下跌转负、P21第10次，R第44次才破坏。</p>
<p><strong>单次往返：</strong>价格归位后P可归零，D仍可留下8 log百分点的历史向下区间。它满足账本定义，却不能叫当前下跌强度，更不能拿旧区间永久封杀新趋势。</p>
<p class="note">相同前缀的熊反弹与真V，在分叉之前必须同输出。没有用未来结局改当日标签。17/17指定单位变换检查通过，但严格触价对机器精度附近扰动仍敏感，不能把偶然少切换的箱体段认作稳定。</p></section>
<section class="card"><h2>这轮保留什么，暂不采用什么</h2><p><strong>保留：</strong>实际推进、结构成果和冲击分开描述；保留原单位、时间尺度、锚点身份及历史记忆年龄；量价冲击必须靠价格响应结算。它们构成比B1单分数更可核查的诊断工具。</p><p><strong>暂不采用：</strong>不把R=1、新结构、P为正或D为0当整体判强；不将P/R/D任意加权成总分，不接入选股排序、仓位和买卖。结构尺度过粗/过细与历史记忆职责仍需研究，账户层无法替这些语义问题作定义。</p><p>后续若继续，应先解决“局部新腿与较大结构如何表达关系”和“历史位移记忆怎样与当前反证区分”，再确定是否能合成有含义的强度等级。本轮不追加过滤条件、参数队列或账户。</p></section>
<section class="card"><h2>公式、来源与核验</h2><details><summary>展开完整模型职责和更新顺序</summary><pre>P：n=5/21，n+1个log收盘；beta = Σ(x−x̄)p / Σ(x−x̄)²
原速度=beta；n期幅度单位=100n beta；pace=√n beta / σ
σ=此前63个有效收益的RMS，a=今日量/此前21量median

R：d方向；A固定origin；E有利极值；S支持；K回撤检查点
真实新E冻结δE=2σ；E不动时δ不动
先破旧S → 否则确认旧K收复 → 刷新E → 创建新K
回到K才确认回撤pivot并推进S；A不换
破旧后还需从旧E足够反向位移才新建反向，否则未知
R=d(p−A)/[d(E−A)]；图值=100dR，不是总强度
旧破坏日按今日p和旧A/E另存R，不用新R=1覆盖它

D：当日r/σ全量显示；a≥2且|r|≥σ创建有量资格的位移区间
下行区间的已向上收复部分永久结清；上行镜像
两向独立，不相减；不按时间/结构换向清账
去量版只取消a门槛，P/R必须完全相同

第65有效收盘开始P/冲击；结构从该日等待因果建立
无效观察未知；源segment重启预热，并归档未决而非声称治愈
无向后平滑、全样本拟合、日期过滤、参数搜索或交易策略</pre><p>结构抽取借鉴<a href="https://arxiv.org/html/0809.1040v2">Glattfelder 等原始方向变化研究</a>。本项目的冻结2σ回撤/收复规则和量价区域账本是探索性假设，非论文原公式；论文没有证明本模型或A股交易优势。</p></details>
<p>正式合成首轮出现单位缩放下的包容等号尾差，v0代码/冻结/失败均保留；numerical-v1只统一相关机器精度比较，参数不变。88项正式技术检查与17合成先于真实B2；随后7资产17,605行×49字段独立复算最大差9.516×10⁻¹⁴，14物理输入前缀及事件日志一致；补充17条单位变换全通过。技术通过不等于语义或经济准入。</p>
<p>同批完整源历史预热，主展示2021起，德明利源从2022上市开始。黄金ETF末日2026-10-16，四股10-22，沪金/半导体10-23。股票/ETF因果研究价量、沪金连续拼接未知、换月量影响、已见开发历史等限制保留。</p>
<div class="links"><a href="../CONCLUSION.md">完整结论</a><a href="../PROTOCOL.md">原冻结协议</a><a href="../NUMERICAL_V1.md">唯一数值修复</a><a href="../freeze-v1.json">有效版本身份</a><a href="../reviews/rootcause/REVIEW.md">B1两窗归因</a><a href="../reviews/mechanism/MECHANISM_REVIEW.md">机制讨论</a><a href="../reviews/adversarial/SYNTHETIC_OUTPUT_REVIEW.md">17合成独立复评</a><a href="../reviews/output/OUTPUT_REVIEW.md">22真实图独立复评</a><a href="../reviews/implementation/POST_RESULTS_AUDIT.md">独立实现核验</a><a href="../reviews/implementation/NUMERICAL_SUPPLEMENT.md">补充数值边界</a><a href="../analysis/selected-facts.csv">事实表CSV</a><a id="csv-link">当前资产逐日CSV</a><a href="../complete.json">完成收据</a></div>
</section><footer>一个机制候选 · 数值修复1次 · 真实输出后机制/参数修订0 · 账户0 · 不替换E0 · 不认领已还原趋势动物或未见预测能力</footer>
</main><script>
const D=__DATA__,P=__PLOTS__,N=__NAMES__,S=__SYNTHETIC__;
const $=id=>document.getElementById(id);let rows=[];
Object.entries(N).forEach(([k,v])=>$('asset').add(new Option(v+' '+k,k)));
Object.entries(S).forEach(([k,v])=>$('synthetic').add(new Option(v,k)));
function fmt(v,n=2){return v===null||v===undefined||!Number.isFinite(Number(v))?'未知':Number(v).toFixed(n);}
function selectAsset(sid,wid,date){$('asset').value=sid;$('window').replaceChildren();P.filter(x=>x.asset===sid).forEach(x=>$('window').add(new Option(x.id+' | '+x.actual_first+'—'+x.actual_last,x.id)));if(wid)$('window').value=wid;selectWindow(date);}
function selectWindow(date){let p=P.find(x=>x.id===$('window').value);rows=D[p.asset].filter(x=>x.date>=p.start&&x.date<=p.end);$('chart').src=p.url;$('image-link').href=p.url;$('day').max=rows.length-1;$('date').min=rows[0].date;$('date').max=rows.at(-1).date;$('date').value=date||rows.at(-1).date;$('csv-link').href='../results/'+p.asset+'.csv';selectDate();}
function selectDate(){let idx=rows.findLastIndex(x=>x.date<=$('date').value);if(idx<0)idx=0;$('day').value=idx;render(idx);}
function render(i){let r=rows[i],ask=$('date').value,d=r.direction===1?'上行':r.direction===-1?'下行':r.direction===0?'未建立':'未知';$('date-note').textContent='实际观察 '+r.date+(ask!==r.date?'（请求 '+ask+'，沿用此前真实报价）':'')+' · 当前固定窗 '+rows.length+' 个源观察；预热来自更早源历史';
let metrics=[['P5 周观察速度',fmt(r.pace_5),'blue'],['P21 月观察速度',fmt(r.pace_21),'blue'],['R结构方向',d,'green'],['R成果保留',r.retention===null?'未知':fmt(100*r.retention)+'%','green'],['D当日冲击',fmt(r.shock)+' σ','red'],['D向下未收复区域',fmt(r.down_zone_log_pct)+' log百分点','red'],['原E0有效',r.e0_target===null?'未知':r.e0_target===1?'是':'否',''],['旧B1分数',fmt(r.b1_strength),'']];
$('metrics').replaceChildren(...metrics.map(([name,value,kind])=>{let el=document.createElement('div');el.className='metric '+kind;el.append(name);let v=document.createElement('strong');v.textContent=value;el.append(v);return el;}));
$('structure-note').textContent=r.direction?('此结构跨度 '+fmt(r.span_log_pct)+' log百分点，已知年龄 '+fmt(r.episode_age,0)+' 观察，支持推进 '+fmt(r.support_advances,0)+' 次，距最近推进 '+fmt(r.progress_age,0)+' 观察。'+(r.support_advances===0?'当前没有收复后支持推进确认；R高不代表成熟强势。':'保留比例不表示当前仍在加速。')):'尚未建立该定义的方向结构；不填中性/成熟强势。';
$('debt-note').textContent=(r.down_events===0?'当前无向下未决量价事件；':'D向下最老未决年龄 '+fmt(r.oldest_down_age,0)+' 观察；')+'向上历史位移区域 '+fmt(r.up_zone_log_pct)+' log百分点，最老 '+fmt(r.oldest_up_age,0)+' 观察。陈旧区域是历史账本，不能单独当当前趋势或交易门槛。';
let values=[['当日真实收盘变化',fmt(r.day_return_pct)+'%'],['过去5 / 21观察端点涨跌',fmt(r.return_5_pct)+'% / '+fmt(r.return_21_pct)+'%'],['P5 / P21原始推进幅度单位',fmt(r.amplitude_5)+' / '+fmt(r.amplitude_21)+' log百分点（速度换单位，非未来收益）'],['B1原始21观察漂移幅度单位',fmt(r.b1_amplitude_21_log_pct)+' log百分点'],['结构ID / 起点 / 当前极值',fmt(r.episode,0)+' / '+fmt(r.origin_price,4)+' / '+fmt(r.extreme_price,4)],['B2支持 / E0支持',fmt(r.support_price,4)+' / '+(r.e0_target===1?fmt(r.e0_floor,4):'未启用')],['量比 / 下行记忆事件数',fmt(r.activity)+' / '+fmt(r.down_events,0)],['今日破结构 / 当日旧R',r.structure_broken===1?'是 / '+fmt(100*r.old_retention_at_t)+'%':'否'],['解释', '所有字段只是量价描述，没有生成开仓、卖出、仓位或换仓指令']];
$('detail').replaceChildren(...values.map(([a,b])=>{let tr=document.createElement('tr'),x=document.createElement('td'),y=document.createElement('td');x.textContent=a;y.textContent=b;tr.append(x,y);return tr;}));}
$('asset').onchange=()=>selectAsset($('asset').value);$('window').onchange=()=>selectWindow();$('date').onchange=selectDate;$('day').oninput=()=>{$('date').value=rows[+$('day').value].date;render(+$('day').value);};
const cases={range:['AU0','au_user_consolidation','2025-07-31'],decline:['AU0','au_user_decline','2026-04-01'],crash:['AU0','au_2025_26','2026-02-02'],semi:['512480','semi_2026','2026-08-10'],'bad-bounce':['512480','semi_2022','2022-08-05'],smic:['688981.SH','688981_SH_2024_26','2024-10-08'],demli:['001309.SZ','001309_SZ_2024_26','2026-07-21']};document.querySelectorAll('[data-case]').forEach(b=>b.onclick=()=>selectAsset(...cases[b.dataset.case]));
function selectSynthetic(){$('synthetic-chart').src='../figures/synthetic/'+$('synthetic').value+'.png';}$('synthetic').onchange=selectSynthetic;$('synthetic').value='flat_box';selectSynthetic();selectAsset('AU0','au_user_consolidation','2025-07-31');
</script></body></html>'''
for token,value in [('__DATA__',read(ROOT/'analysis/viewer-data.json')),('__PLOTS__',plots),('__NAMES__',NAMES),('__SYNTHETIC__',labels)]:
    html=html.replace(token,json.dumps(value,ensure_ascii=False).replace('</','<\\/'))
(folder/'index.html').write_text(html)
print({'report':str(folder/'index.html'),'real':22,'synthetic':17})
