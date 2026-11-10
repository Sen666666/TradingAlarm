"""Assemble an offline viewer from verified comparison artifacts."""
from pathlib import Path
import json
import pandas as pd

HERE=Path(__file__).resolve().parent
OUT=HERE/'outputs/v2'

def main():
    summary=json.loads((OUT/'summary.json').read_text())
    verified=json.loads((OUT/'verification.json').read_text())
    assert verified['status']=='passed'
    data={}
    fields=['close','target','floor','entered','exited','independent_entry','volume_ratio',
            'czsc_latest_bi_direction','czsc_latest_bi_end','czsc_unfinished_direction',
            'rs_score','rank_score','peer_count']
    for s in summary:
        d=pd.read_csv(OUT/'data'/f"{s['symbol']}-daily-output.csv",index_col='date')
        d=d.loc['2024-01-01':'2026-10-16',fields].reset_index()
        data[s['symbol']]=json.loads(d.to_json(orient='records',double_precision=12))
    page=r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CZSC × 冻结趋势算法 · 本地对照</title>
<style>
:root{--ink:#203447;--muted:#657789;--line:#e0e7ed;--green:#16836b;--blue:#487db6;--paper:#f5f7f8}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:14px/1.65 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}
main{max-width:1500px;margin:auto;padding:36px 38px 30px}header{display:flex;justify-content:space-between;gap:25px;align-items:start}.eyebrow{font-size:11px;letter-spacing:2px;color:#607d82;font-weight:700}h1{font-size:31px;line-height:1.3;letter-spacing:-.8px;margin:10px 0 12px}p{margin:6px 0;color:var(--muted)}.badge{white-space:nowrap;background:#e4f0eb;color:#25745d;border:1px solid #cee2d9;padding:7px 13px;border-radius:20px;font-size:12px;margin-top:18px}
.stocks{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:24px 0 18px}button{cursor:pointer;font:inherit;color:inherit;background:white;border:1px solid var(--line);border-radius:8px;padding:11px 17px}.stock{text-align:left;transition:.15s;padding:13px 18px}.stock strong{display:block;font-size:16px}.stock small{color:var(--muted);font-size:11px;letter-spacing:.8px}.stock.active{background:#203c4c;color:white;border-color:#203c4c}.stock.active small{color:#b8cfdb}
.cards{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;margin-bottom:18px}.card{background:white;border:1px solid var(--line);border-radius:10px;padding:16px 20px;min-height:117px}.card .label{font-size:12px;color:var(--muted)}.value{font-size:23px;font-weight:650;letter-spacing:-.6px;margin:5px 0}.green{color:var(--green)}.blue{color:var(--blue)}.card .detail{font-size:12px;color:var(--muted)}
.explain{background:#edf2f4;border-left:3px solid #9fb8c4;padding:14px 18px;border-radius:0 8px 8px 0;margin:0 0 22px;color:#465e70}.explain b{color:#243d50}.toolbar{display:flex;justify-content:space-between;align-items:center;gap:18px;margin:13px 0 10px}.tabs{display:flex;gap:5px;flex-wrap:wrap}.tab{border:none;background:transparent;padding:7px 14px;color:var(--muted)}.tab.active{background:white;color:var(--ink);box-shadow:0 1px 4px #142a4412}.link{font-size:12px;color:var(--blue);text-decoration:none}.canvas{background:white;border:1px solid var(--line);border-radius:10px;overflow:hidden}iframe{width:100%;height:1090px;border:0;display:block}#raw{width:100%;display:none}.note{padding:11px 18px;background:#fff9ec;color:#8b713e;font-size:12px;border-top:1px solid #eee2c9}
.inspection{background:white;border:1px solid var(--line);border-radius:10px;margin-top:22px;overflow:hidden}.inspection-head{padding:17px 21px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--line);gap:20px}.inspection-head h2{font-size:17px;margin:0}.inspection-head p{font-size:12px}input{font:inherit;border:1px solid var(--line);border-radius:6px;padding:7px 10px;color:var(--ink)}.facts{padding:14px 22px;display:grid;grid-template-columns:repeat(4,1fr);gap:15px}.facts span{display:block;color:var(--muted);font-size:12px}.facts b{font-size:17px;font-weight:550}.tablewrap{overflow:auto;max-height:320px}table{border-collapse:collapse;width:100%;font-size:12px;text-align:right;white-space:nowrap}th{background:#f4f7f9;color:var(--muted);font-weight:500;position:sticky;top:0}td,th{padding:9px 15px;border-bottom:1px solid #edf1f4}th:first-child,td:first-child{text-align:left}.selected td{background:#edf6f2}
.methods{display:grid;grid-template-columns:1fr 1fr;gap:22px;margin-top:24px}.methods h3{font-size:15px;margin:0 0 8px}.methods p{font-size:13px}footer{margin-top:28px;padding-top:16px;border-top:1px solid var(--line);font-size:12px;color:var(--muted)}footer a{color:var(--blue);margin-right:18px}
@media(max-width:800px){main{padding:22px 14px}h1{font-size:25px}.stocks{grid-template-columns:repeat(2,1fr)}.cards{grid-template-columns:1fr}.badge{display:none}.facts{grid-template-columns:repeat(2,1fr)}.methods{grid-template-columns:1fr}iframe{height:1120px}.toolbar{align-items:start}.inspection-head{align-items:start;flex-direction:column}}
</style></head><body><main>
<header><div><div class="eyebrow">LOCAL RESEARCH / CZSC 1.0.2 / 23 OCT 2026</div>
<h1>把两种输出，放在同一条行情里看</h1>
<p>四只固定股票 · 同一份因果复权日线 · 图示 2024-01-01 — 2026-10-16</p></div>
<div class="badge">冻结算法未改 · 3,921 个观察日精确复现</div></header>
<nav class="stocks" id="stocks"></nav>
<section class="cards">
<div class="card"><div class="label">我们的冻结趋势算法 · 快照末日</div><div class="value green" id="ours"></div><div class="detail" id="floor"></div></div>
<div class="card"><div class="label">CZSC · 结构列表末笔 / 当前未完成笔</div><div class="value blue" id="chan"></div><div class="detail" id="endpoint"></div></div>
<div class="card"><div class="label">图示区间内的输出规模</div><div class="value" id="counts"></div><div class="detail" id="revision"></div></div>
</section>
<div class="explain" id="insight"></div>
<div class="toolbar"><div class="tabs">
<button class="tab active" data-view="comparison">同轴对照</button>
<button class="tab" data-view="native">CZSC 原生图</button>
<button class="tab" data-view="raw">原始量价先看</button></div>
<a class="link" id="chartlink" target="_blank">在新标签打开图表 ↗</a></div>
<section class="canvas"><iframe id="chart" title="算法与缠论输出图表"></iframe><img id="raw" src="outputs/v2/charts/raw-overview.png" alt="四只股票原始量价">
<div class="note" id="chartnote"></div></section>
<section class="inspection"><div class="inspection-head"><div><h2>查看某个收盘时刻的输出</h2><p>选择日期后取该股截至当天最后一条真实观察；下方表格保留此前 20 条。</p></div><input id="asof" aria-label="查看日期" type="date" min="2024-01-01" max="2026-10-16" value="2026-10-16"></div>
<div class="facts" id="facts"></div><div class="tablewrap"><table><thead><tr><th>实际观察日期</th><th>结构状态</th><th>保护点</th><th>CZSC 末笔</th><th>末笔端点</th><th>未完成笔</th><th>相对成交量</th></tr></thead><tbody id="history"></tbody></table></div></section>
<section class="methods"><div><h3>我们的输出：参与资格与撤销条件</h3><p>target=1 表示上行结构已建立且尚未被保护点否决；target=0 表示未建立。绿线是当时的保护点，三角标的是结构建立和失效。它们不是已经成交的交易记录。</p><p>成交量参与原通道确认及独立跨日收复。原有相对强弱分数与旧小池排名保留在 CSV 中，未把这四只股票重新混池排名。</p></div>
<div><h3>CZSC 的输出：行情的几何结构</h3><p>分型、上下笔和重叠中枢描述行情内部的往返。末笔方向与当前未完成笔须分别看，不能把它们直接改名为持仓或买卖建议。</p><p>末日结构图会回画较早端点，笔也可能延伸或被调整。第四条轨迹和逐日表记录当时可见的结构列表；保留 16 组截断重建核查。</p></div></section>
<footer>仅使用已有快照。算法改动 0 · 行情下载 0 · 账户运行 0。价格是既有信号复权坐标，非原价报价；这是已见历史的输出比较。<br>
<a href="REPORT.md">阅读具体差异与复盘</a><a href="outputs/v2/verification.json">核查收据</a><a href="PROTOCOL.md">事前范围</a><a href="outputs/v2/summary.json">完整统计</a></footer>
</main><script>
const S=__SUMMARY__, D=__DAILY__;
const INSIGHTS={
"600919.SH":"<b>观察重点：长段上涨里的内部回调。</b> 我们的结构常在短期回调中保留，CZSC 把同一段行情拆成多条上下笔。两种输出的时间尺度和职责不同。",
"600059.SH":"<b>观察重点：最后一笔向上，不等于当前仍看多。</b> 截至 10 月 16 日，我们的上行结构已失效；CZSC 结构列表末笔仍向上，但正在发展的未完成笔向下。可把日期拨到 10 月上旬逐日看。",
"600917.SH":"<b>观察重点：短期上行结构与长期偏弱可以并存。</b> 末日 target=1 只表示局部上行假说尚未被保护点否决；旧 A 股小池相对强弱排名仍在末位。不能把一个状态当成全面转强。",
"HK00700":"<b>观察重点：长段推进后的回撤与重建。</b> 两者都描画出 2025 年中之后的回落。我们的上行假说会失效并在反弹中重建，CZSC 更细地呈现摆动及重叠区；本次不评价收益高低。"
};
const params=new URLSearchParams(location.search);
let sid=S.some(s=>s.symbol===params.get("symbol"))?params.get("symbol"):S[0].symbol;
let view=params.get("view")==="native"?"native":"comparison";
const el=id=>document.getElementById(id);
const dir=n=>n===1?"向上":n===-1?"向下":"暂无";
const num=x=>x===null||x===undefined?"—":Number(x).toFixed(3);
el("stocks").innerHTML=S.map(s=>'<button class="stock" data-symbol="'+s.symbol+'"><strong>'+s.name+'</strong><small>'+s.symbol+'</small></button>').join("");
document.querySelectorAll(".stock").forEach(b=>b.addEventListener("click",()=>{sid=b.dataset.symbol;render()}));
document.querySelectorAll(".tab").forEach(b=>b.addEventListener("click",()=>{view=b.dataset.view;showChart()}));
el("asof").addEventListener("change",inspect);
function showChart(){
 document.querySelectorAll(".tab").forEach(b=>b.classList.toggle("active",b.dataset.view===view));
 const raw=view==="raw";el("raw").style.display=raw?"block":"none";el("chart").style.display=raw?"none":"block";
 const url=raw?"outputs/v2/charts/raw-overview.png":"outputs/v2/charts/"+sid+"-"+view+".html";
 if(!raw&&el("chart").getAttribute("src")!==url)el("chart").src=url;
 el("chartlink").href=url;
 el("chartnote").textContent=raw?"原价行情用于先看路径；对照图使用已验证的因果复权坐标。":view==="native"?"CZSC 原生图：分型、笔、均线、成交量、MACD；这里显示完整可得输入，最后的未完成笔请结合逐日表查看。原生均线和 MACD 未加入我们的策略。":"上两图使用相同价格与日期。第二图是末日结构回画；第四图和下表是逐日当时可见的末笔方向。末端灰虚线是未完成笔。";
}
function inspect(){
 const rows=D[sid].filter(r=>r.date<=el("asof").value),r=rows.at(-1);
 if(!r)return;
 const cells=[["实际观察日期",r.date],["我们的上行结构",r.target===1?"有效":"未建立"],["CZSC 列表末笔",dir(r.czsc_latest_bi_direction)],["CZSC 未完成笔",dir(r.czsc_unfinished_direction)]];
 el("facts").innerHTML=cells.map(x=>"<div><span>"+x[0]+"</span><b>"+x[1]+"</b></div>").join("");
 el("history").innerHTML=rows.slice(-20).reverse().map((x,i)=>'<tr class="'+(i===0?"selected":"")+'"><td>'+x.date+"</td><td>"+(x.target===1?"1 · 有效":"0 · 未建")+"</td><td>"+num(x.floor)+"</td><td>"+dir(x.czsc_latest_bi_direction)+"</td><td>"+(x.czsc_latest_bi_end||"—")+"</td><td>"+dir(x.czsc_unfinished_direction)+"</td><td>"+num(x.volume_ratio)+"×</td></tr>").join("");
}
function render(){
 const s=S.find(x=>x.symbol===sid),l=s.latest;
 document.querySelectorAll(".stock").forEach(b=>b.classList.toggle("active",b.dataset.symbol===sid));
 el("ours").textContent=l.target===1?"上行结构有效":"上行结构未建立";
 el("floor").textContent="截至 "+l.date+" · 当前有效保护点 "+num(l.target===1?l.floor:null);
 el("chan").textContent=dir(l.czsc_bi_direction)+" / "+dir(l.czsc_unfinished_direction);
 el("endpoint").textContent="列表末笔端点 "+l.czsc_bi_end+" · 未完成笔仍会变化";
 el("counts").textContent=s.entries+" 次建态 · "+s.displayed_final_bis+" 条笔";
 el("revision").textContent=s.displayed_final_zs+" 个末日中枢 · "+s.bi_list_revision_days+" 日有旧笔替换/延伸";
 el("insight").innerHTML=INSIGHTS[sid];
 showChart();inspect();
}
render();
</script></body></html>'''
    page=page.replace('__SUMMARY__',json.dumps(summary,ensure_ascii=False)).replace('__DAILY__',json.dumps(data,ensure_ascii=False))
    (HERE/'index.html').write_text(page)
    print('Created',HERE/'index.html')

if __name__=='__main__':
    main()
