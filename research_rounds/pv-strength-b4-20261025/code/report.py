"""Self-contained local B4 reader. Reads frozen results; never executes models."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from common import ROOT, NAMES, read, write, now


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [clean(v) for v in value]
    if isinstance(value, (np.integer, np.floating, np.bool_)):
        value = value.item()
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    return value


def build_payload():
    assets = {}
    for sid, name in NAMES.items():
        f = pd.read_parquet(ROOT / 'results' / f'{sid}.parquet').loc['2021-01-01':]
        journal = read(ROOT / 'results' / f'{sid}-events.json')
        displayed_events = [e for e in journal if e.get('kind') in {
            'structure_confirmed', 'acute_down', 'acute_up', 'source_discontinuity'}]
        assets[sid] = {'name': name, 'dates': [str(d.date()) for d in f.index],
                       'fields': {str(c): clean(f[c].tolist()) for c in f.columns},
                       'events': clean(displayed_events), 'journal_count': len(journal)}
    synthetic = [{**x, 'kind': 'synthetic'} for x in
                 read(ROOT / 'figures' / 'synthetic-manifest.json')['plots']]
    derived = ROOT / 'figures' / 'derived-manifest.json'
    if derived.exists():
        synthetic += [{**x, 'kind': 'derived'} for x in read(derived)['plots']]
    else:
        raise FileNotFoundError('The one frozen derived-path figure is required')
    conclusion = ROOT / 'CONCLUSION.md'
    return {'generated_at': now(), 'assets': assets,
            'windows': read(ROOT / 'figures' / 'real-manifest.json')['plots'],
            'synthetic': synthetic, 'protocol': (ROOT / 'PROTOCOL.md').read_text(),
            'conclusion': conclusion.read_text() if conclusion.exists() else None,
            'counts': {'assets': len(assets), 'windows': 22, 'synthetic': 24, 'derived': 1,
                       'accounts': 0}}


HTML = r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>PVS-B4 · 方向、推进与结构</title><style>
:root{--ink:#253f4b;--muted:#65777e;--up:#b86233;--down:#3579a1;--line:#dbe3e1;--paper:#f4f5f0;--accent:#38776d}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.65 system-ui,-apple-system,BlinkMacSystemFont,sans-serif}main{max-width:1480px;margin:auto;padding:36px 30px}h1{font-size:34px;line-height:1.25;margin:10px 0 18px}h2{font-size:23px;margin:0 0 14px}h3{font-size:17px;margin:12px 0 8px}p{margin:9px 0 15px}.kicker{font-size:12px;letter-spacing:1.8px;color:#557d73}.lead{font-size:18px;max-width:1080px}.muted,.sub,small{color:var(--muted)}.sub{font-size:12px}.panel{background:#fff;border:1px solid var(--line);border-radius:13px;padding:23px;margin:22px 0}.three{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.definition{padding:18px;border:1px solid var(--line);border-top:4px solid var(--accent);border-radius:10px;background:white}.definition strong{font-size:20px}.definition p{font-size:14px;margin:8px 0 0}.toolbar,.cases,.downloadbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:12px 0}select,input,button{font:inherit;color:var(--ink);padding:7px 10px;background:#fff;border:1px solid #b8c9c8;border-radius:6px}select{max-width:570px}button{cursor:pointer}button:hover{background:#edf4f0}.cases button{font-size:13px}a{color:#276e8b;text-decoration-thickness:1px;text-underline-offset:3px}#slider{width:100%;padding:0;accent-color:#4a7f74}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:16px 0}.card{border:1px solid var(--line);border-radius:9px;padding:13px}.value{font-size:25px;font-weight:650;line-height:1.35;margin:5px 0}.notice{padding:12px 15px;background:#edf5f2;border-left:4px solid #609285;margin:13px 0}.notice.attention{background:#fff5e5;border-left-color:#bd8239}.note{padding:11px 15px;background:#f7f3e9;border-left:4px solid #c5a16e}.scroll{overflow:auto}table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}th{background:#f2f5f1;font-weight:600}code{background:#eef2ec;padding:1px 4px;border-radius:3px}details{margin:12px 0}summary{cursor:pointer;font-weight:600;padding:5px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f5f2;padding:14px;border-radius:8px;font:12px/1.55 ui-monospace,SFMono-Regular,monospace;max-height:480px;overflow:auto}.plot{width:100%;height:auto;display:block;border:1px solid var(--line);margin-top:10px}#chart{width:100%;height:auto;display:block;touch-action:pan-y;border:1px solid var(--line);border-radius:8px;background:#fff}.chartshell{position:relative;margin-top:14px}#chart text{font-family:system-ui,-apple-system,sans-serif}.legend{display:flex;gap:18px;flex-wrap:wrap;font-size:12px;margin:8px 0}.legend i{display:inline-block;width:20px;height:3px;vertical-align:middle;margin-right:5px}.mono{font-family:ui-monospace,SFMono-Regular,monospace}footer{font-size:12px;color:var(--muted);margin:30px 0}.pill{display:inline-block;padding:2px 8px;border-radius:20px;background:#edf3f0;font-size:12px}.rowlinks{display:flex;gap:15px;flex-wrap:wrap}.empty{color:var(--muted);padding:9px 0}@media(max-width:850px){main{padding:22px 12px}h1{font-size:28px}.panel{padding:16px}.three{grid-template-columns:1fr}.cards{grid-template-columns:1fr 1fr}.toolbar{align-items:flex-start}select{max-width:100%;width:100%}.toolbar label{max-width:100%}.value{font-size:22px}}@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto}}
</style></head><body><main>
<div class="kicker">PVS-B4 · LOCAL RESEARCH · 2026-10-25</div>
<h1>方向、推进大小和结构，分开读</h1>
<p class="lead">同样一次反弹，可以有<strong>正向净推进</strong>，也仍处在<strong>旧下行结构</strong>中。这一轮分别记录平滑推进、事件结构和当日冲击，逐条展示新确认的量价证据；保留 E0 与旧 B3 对照。</p>
<p class="note">同7标的、22固定真实窗；24旧合成路径＋1条冲击后阴跌派生路径。已见历史开发研究，账户回测 0。结构确认不代表持仓、上涨概率或交易信号。</p>
<div class="three">
<div class="definition"><strong>平滑净推进 μ5 / μ21</strong><p>带符号的 log 基点／有效观察。符号是该平滑尺度的方向，绝对值是推进大小；负数接近零表示下降减速，不自动叫升温。</p></div>
<div class="definition"><strong>事件结构 S21 / S63</strong><p>最近确认方向：上、下或未确认。21／63是两种预设位移分辨率系数，不是21／63天滚动窗口；锚日不同，实际门槛不保证严格嵌套。结构可能陈旧，必须与当前推进一起看。</p></div>
<div class="definition"><strong>当日急性事件</strong><p>q、q_eff 及急涨／急跌标记。标记只描述当天；次日标记消失不代表昨天跌幅已收回，也不是恢复入口。</p></div>
</div>

<section class="panel"><h2>同一批窗口，逐日核对</h2>
<div class="cases"><button data-case="au_user_consolidation|2025-07-31">黄金整理</button><button data-case="au_user_decline|2026-04-01">黄金阴跌与反弹</button><button data-case="au_2025_26|2026-02-02">黄金急跌</button><button data-case="semi_2026|2026-08-10">半导体反弹</button><button data-case="semi_2022|2022-08-05">2022失败反弹</button><button data-case="688981_SH_2024_26|2024-10-08">中芯快启动</button><button data-case="001309_SZ_2024_26|2026-07-15">德明利转弱</button></div>
<div class="toolbar"><label>固定窗口 <select id="window" aria-label="固定窗口"></select></label><label>观察日期 <input id="date" type="date" aria-label="观察日期"></label><button id="previous" aria-label="上一观察">←</button><button id="next" aria-label="下一观察">→</button><span id="dateText" class="muted"></span></div>
<input id="slider" type="range" aria-label="逐日观察游标"><div id="cards" class="cards"></div>
<div id="status" class="notice" aria-live="polite"></div>
<p class="sub">“接近零”仅使用 |μ21| &lt; 1 log基点／观察作为页面描述提示，不参与算法、确认或交易。结构同上并不命名为 hot。</p>
<div class="toolbar"><label><input id="showDaily" type="checkbox"> 推进面板同时显示当日log收益（共轴）</label><span class="sub">移动或点击图表选择最近观察；日期控件与图上游标同步。</span></div>
<div class="legend"><span><i style="background:#b86233"></i>μ5 / S21</span><span><i style="background:#3579a1"></i>μ21 / S63</span><span><i style="background:#d6a770"></i>E0有效底纹，非持仓</span><span>○ S21新确认　◇ S63新确认</span></div>
<div class="chartshell"><svg id="chart" viewBox="0 0 1200 855" role="img" aria-label="价格、量、平滑推进、结构、当日冲击与旧B3，同步日期游标"></svg></div>
<div class="downloadbar"><a id="pngOpen" target="_blank" rel="noopener">打开完整PNG</a><a id="pngDownload" download>下载PNG</a><a id="csvLink">逐日CSV</a><a id="eventsLink">完整事件日志JSON</a><span id="sourceCutoff" class="sub"></span></div>
<details><summary>查看完整静态图（含旧B1）</summary><img id="plot" class="plot" alt="固定窗口：原始量价、E0、B4分量和旧B3/B1对照"></details>

<details open><summary>当前结构与新确认收据</summary>
<div id="structureDetails" class="scroll"></div>
<p class="sub">下表为<strong>日末仍活跃的反向候选</strong>。确认当日消耗的旧候选已写入独立 receipt；不能拿重置后的日末候选解释当日确认门槛。</p>
<div id="candidateDetails" class="scroll"></div>
<h3>所选日新确认及急性事件</h3><div id="events"></div>
<details><summary>最近两尺度确认的完整 receipt</summary><div id="lastReceipts"></div></details>
</details>
<details><summary>所选日全部字段（未知保留）</summary><div id="fields" class="scroll"></div></details>
</section>

<section class="panel"><h2>机制与限制</h2><div class="three">
<div><h3>方向没有波动门槛</h3><p>μ按日log收益作指数平滑，α=2/(h+1)，h=5、21。它没有被压成0—100，也没有用RMS把较小下降强制归零。平滑仍会迟滞，巨大旧涨后小幅阴跌可能暂时保留正值。</p></div>
<div><h3>确认要有真实新价格</h3><p>候选从真实极值冻结锚、δ和成交量参照。仅在同向新价格前沿累计 Q；确认同时要求 x≥δ、Q≥δ，以及今天确有同向新前沿。箱内来回不会反复刷量证据。</p></div>
<div><h3>量参与，但不保证延续</h3><p>新前沿权重 w=clip(√(V/v_anchor),0.5,2)。高量不豁免真实位移门槛；首次低量走过的旧价格被高量重访，也不会补旧分。这是假说限制，真实强反弹仍可能失败。</p></div>
</div><p class="note">没有按日龄、滚动窗口遗忘或旧冲击过期而向上升级的出口。代价仍可能包括确认迟滞、长期陈旧结构，以及失败反弹触发双尺度向上；技术检查不能替代这些行为评价。</p>
<details><summary>展开本轮冻结公式与协议</summary><pre id="protocol"></pre></details></section>

<section class="panel"><h2>固定合成与唯一派生压力路径</h2>
<div class="toolbar"><label>路径 <select id="synthetic" aria-label="合成路径"></select></label><a id="syntheticOpen" target="_blank" rel="noopener">打开PNG</a><a id="syntheticDownload" download>下载PNG</a></div>
<img id="synthPlot" class="plot" alt="固定合成或派生压力路径，B4分量展示">
<p class="sub">全部24旧路径保留；唯一派生 <code>shock_then_slow_decline</code> 保持前191行、随后120行改为−0.001 log收益及量100。静止、全负后缀和真实反弹分开核验，路径不是可交易资产。</p></section>

<section class="panel"><h2>结论与可追溯材料</h2><div id="conclusionStatus" class="notice"></div>
<div class="rowlinks"><a href="../CONCLUSION.md">完整结论与反例</a><a href="../PROTOCOL.md">公式协议</a><a href="../reviews/raw/RAW_REVIEW.md">22窗原始量价审查</a><a href="../reviews/raw/RAW_RECEIPT.json">实际看图收据</a><a href="../validation/checks.json">技术检查</a><a href="../freeze.json">冻结与哈希</a><a href="../results/summary.json">结果摘要</a></div>
<details id="conclusionBlock"><summary>展开生成页面时的结论快照</summary><pre id="conclusion"></pre></details>
<p>逐日数据：<span id="downloads"></span></p>
<p class="sub">研究页面只读取已计算结果，无模型运行、外部脚本、CDN或网络行情。账户0；E0/R/R1、RS与换仓未改。源数据、复权与连续合约限制沿用原轮。</p></section>
<footer id="footer"></footer></main>

<script>
'use strict';
const payload=__PAYLOAD__;
const Q=id=>document.getElementById(id), UP='#b86233', DOWN='#3579a1', INK='#253f4b';
const finite=v=>v!==null&&v!==undefined&&typeof v!=='boolean'&&Number.isFinite(Number(v));
const fmt=(v,d=2)=>finite(v)?Number(v).toLocaleString('zh-CN',{minimumFractionDigits:d,maximumFractionDigits:d}):'未知';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const direction=v=>!finite(v)?'未知':Number(v)===1?'上':Number(v)===-1?'下':'未确认';
const phaseNames={unknown:'预热或无效观察',unconfirmed:'两尺度尚未确认',building:'部分尺度确认',aligned_up:'双尺度向上确认',aligned_down:'双尺度向下确认',rebound:'局部上／较大下：反弹',pullback:'局部下／较大上：回撤或转弱'};
const gradeNames={'-2':'freeze','-1':'cold','0':'neutral','1':'warm','2':'hot'};
let currentWindow, asset, indices=[], currentIndex=0, chartX=null;
function value(k,i=currentIndex){return asset.fields[k]?.[i]??null}
function eventList(){return asset.events.filter(e=>e.date===asset.dates[currentIndex])}
function latestConfirm(h){const date=asset.dates[currentIndex];return asset.events.filter(e=>e.kind==='structure_confirmed'&&e.horizon===h&&e.date<=date).at(-1)||null}
function setLink(id,href,download=false){Q(id).href=href;if(download)Q(id).download=href.split('/').at(-1)}
function table(headers,rows){return '<table><thead><tr>'+headers.map(x=>'<th>'+esc(x)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(row=>'<tr>'+row.map(x=>'<td>'+x+'</td>').join('')+'</tr>').join('')+'</tbody></table>'}
function jsonBlock(data){return '<pre>'+esc(JSON.stringify(data,null,2))+'</pre>'}
function showWindow(id,date){
  currentWindow=payload.windows.find(w=>w.id===id);if(!currentWindow)return;
  Q('window').value=id;asset=payload.assets[currentWindow.asset];
  indices=asset.dates.map((d,i)=>d>=currentWindow.start&&d<=currentWindow.end?i:-1).filter(i=>i>=0);
  if(!indices.length)throw Error('No observations in '+id);
  Q('slider').min=0;Q('slider').max=indices.length-1;
  Q('date').min=asset.dates[indices[0]];Q('date').max=asset.dates[indices.at(-1)];
  const png='../figures/real/'+id+'.png';Q('plot').src=png;setLink('pngOpen',png);setLink('pngDownload',png,true);
  setLink('csvLink','../results/'+currentWindow.asset+'.csv');setLink('eventsLink','../results/'+currentWindow.asset+'-events.json');
  Q('sourceCutoff').textContent='此资产源末日 '+asset.dates.at(-1)+'；当前窗 '+indices.length+' 个观察';
  drawChart();showDate(date||asset.dates[indices.at(-1)]);
}
function showDate(date){const eligible=indices.filter(i=>asset.dates[i]<=date);showRow(eligible.at(-1)??indices[0])}
function showRow(i){
  currentIndex=i;Q('slider').value=indices.indexOf(i);Q('date').value=asset.dates[i];Q('dateText').textContent=asset.name+' · 当日收盘已知';
  const mu5=value('mu5_bp'),mu21=value('mu21_bp'),s21=value('S21'),s63=value('S63');
  const acute=value('acute_down')===1?'当日急跌':value('acute_up')===1?'当日急涨':finite(value('acute_down'))?'无当日急性事件':'未知';
  const cards=[['平滑净推进 μ5',fmt(mu5),'log基点／有效观察；大小 '+fmt(value('mu5_magnitude_bp'))],['平滑净推进 μ21',fmt(mu21),'log基点／有效观察；大小 '+fmt(value('mu21_magnitude_bp'))],['事件结构 S21 / S63',direction(s21)+' / '+direction(s63),'最近确认方向，可能陈旧'],['当日急性事件',acute,'q '+fmt(value('q'))+' · q_eff '+fmt(value('qeff'))]];
  Q('cards').innerHTML=cards.map((x,j)=>'<div class="card"><div>'+esc(x[0])+'</div><div class="value" style="color:'+(j<2?(Number(j===0?mu5:mu21)<0?DOWN:UP):INK)+'">'+esc(x[1])+'</div><div class="sub">'+esc(x[2])+'</div></div>').join('');
  let messages=[phaseNames[value('phase')]||'未知结构'];let attention=false;
  if(s21===1&&s63===1&&finite(mu21)&&mu21<0){messages.push('两尺度旧结构仍向上，但 μ21 已为负；当前平滑净推进下降，不能把结构标签当成正向热度。');attention=true}
  if(finite(mu21)&&Math.abs(mu21)<1){messages.push('μ21 接近零（仅页面描述：绝对值 < 1 log基点／观察），结构保留不等于仍在推进。');attention=true}
  if(s21===-1&&s63===-1&&finite(mu21)&&mu21>0){messages.push('旧结构仍向下，但 μ21 为正；这是当前推进与事件结构的尺度差异，不能把真实反弹抹掉。');attention=true}
  if(finite(mu21)&&mu21<0)messages.push('负值向零靠近只表示下行减速，不自动叫升温。');
  messages.push('E0结构：'+(value('e0_target')===1?'有效，非实际持仓':finite(value('e0_target'))?'无效':'未知')+'。旧B3：'+(gradeNames[value('b3_grade')]||'未知')+'，仅作旧版对照。');
  Q('status').className='notice'+(attention?' attention':'');Q('status').textContent=messages.join(' ');
  const structureRows=[21,63].map(h=>{let e=latestConfirm(h);return ['S'+h,direction(value('S'+h)),e?esc(e.date):'尚无公开确认',value('confirmed_'+h)===1?'今天新确认':'延续旧确认／未确认','当前μ21 '+fmt(mu21)+'；不得据此称 hot']});
  Q('structureDetails').innerHTML=table(['尺度','最近确认方向','最近确认日','今天是否新确认','阅读边界'],structureRows);
  const rows=[];for(const h of [21,63])for(const side of ['up','down']){const k=x=>side+'_'+x+'_'+h;if(value(k('active'))!==1)continue;rows.push(['S'+h+' '+(side==='up'?'向上候选':'向下候选'),esc(value(k('anchor_date'))||'未知')+'<br>锚价 '+fmt(value(k('anchor_price')),4),fmt(value(k('threshold'))*10000),fmt(value(k('x'))*10000),fmt(value(k('frontier'))*10000),fmt(value(k('credit'))*10000),fmt(value(k('frontier_increment'))*10000),fmt(value(k('volume_weight')),3)])}
  Q('candidateDetails').innerHTML=rows.length?table(['日末活跃候选','冻结锚','δ logbp','x logbp','前沿 F logbp','证据 Q logbp','今日新增前沿','今日量权重 w'],rows):'<div class="empty">当前没有公开活跃候选（可能仍在预热或无效观察）。</div>';
  const events=eventList();Q('events').innerHTML=events.length?events.map(e=>'<details'+(e.kind==='structure_confirmed'?' open':'')+'><summary>'+esc(e.kind)+(e.horizon?' · S'+e.horizon+' '+direction(e.direction):'')+'</summary>'+jsonBlock(e)+'</details>').join(''):'<div class="empty">当天没有新的结构确认或急性事件。没有新急跌不等于过去跌幅已收复。</div>';
  Q('lastReceipts').innerHTML=[21,63].map(h=>{let e=latestConfirm(h);return '<h3>S'+h+' 最近确认</h3>'+(e?jsonBlock(e):'<p class="empty">尚无确认收据。</p>')}).join('');
  Q('fields').innerHTML=table(['字段','当天值'],Object.keys(asset.fields).map(k=>[esc(k),value(k)===null?'未知':typeof value(k)==='number'?esc(Number(value(k)).toPrecision(10)):esc(value(k))]));
  if(chartX){const x=chartX(i);Q('cursor').setAttribute('x1',x);Q('cursor').setAttribute('x2',x);Q('cursorLabel').setAttribute('x',Math.max(90,Math.min(1110,x)));Q('cursorLabel').textContent=asset.dates[i]}
}

function drawChart(){
  const svg=Q('chart'), W=1200,L=92,R=23,plotW=W-L-R;let content=[];
  const t=i=>Date.parse(asset.dates[i]+'T00:00:00Z'),t0=t(indices[0]),t1=t(indices.at(-1));
  chartX=i=>L+(t(i)-t0)/Math.max(1,t1-t0)*plotW;
  const text=(x,y,s,extra='')=>content.push('<text x="'+x+'" y="'+y+'" font-size="11" fill="#62767e" '+extra+'>'+esc(s)+'</text>');
  const line=(x1,y1,x2,y2,color,width=1,extra='')=>content.push('<line x1="'+x1+'" y1="'+y1+'" x2="'+x2+'" y2="'+y2+'" stroke="'+color+'" stroke-width="'+width+'" '+extra+'/>');
  function bounds(keys,transform=x=>x,includeZero=false){let v=[];for(const k of keys)for(const i of indices){const x=value(k,i);if(finite(x))v.push(transform(Number(x)))}v=v.filter(Number.isFinite);if(includeZero)v.push(0);if(!v.length)return[-1,1];let a=Math.min(...v),b=Math.max(...v);if(a===b){const pad=Math.abs(a)*.05||1;a-=pad;b+=pad}let pad=(b-a)*.08;return[a-pad,b+pad]}
  function panel(y,h,title,domain,format=x=>Number(x).toFixed(1)){const scale=v=>y+h-(v-domain[0])/(domain[1]-domain[0])*h;text(7,y+12,title);for(let j=0;j<3;j++){const v=domain[0]+j*(domain[1]-domain[0])/2,Y=scale(v);line(L,Y,W-R,Y,'#e5eae7',.7);text(L-9,Y+4,format(v),'text-anchor="end"')}return scale}
  function path(key,scale,transform=x=>x,color=INK,width=1,extra=''){let d='',open=false;for(const i of indices){let v=value(key,i);if(!finite(v)||!Number.isFinite(transform(Number(v)))){open=false;continue}d+=(open?'L':'M')+chartX(i).toFixed(2)+','+scale(transform(Number(v))).toFixed(2);open=true}content.push('<path d="'+d+'" fill="none" stroke="'+color+'" stroke-width="'+width+'" '+extra+'/>')}
  const priceValues=[];for(const i of indices){const c=value('close',i),f=value('e0_floor',i);if(finite(c)&&c>0)priceValues.push(Math.log(c));if(value('e0_target',i)===1&&finite(f)&&f>0)priceValues.push(Math.log(f))}let priceLo=Math.min(...priceValues),priceHi=Math.max(...priceValues);let pricePad=Math.max((priceHi-priceLo)*.08,.001);const priceY=panel(32,195,'研究价 · log',[priceLo-pricePad,priceHi+pricePad],v=>Number(Math.exp(v)).toPrecision(4));
  for(let n=0;n<indices.length;n++){const i=indices[n];if(value('e0_target',i)===1){const left=chartX(i),right=n+1<indices.length?chartX(indices[n+1]):W-R;content.push('<rect x="'+left+'" y="32" width="'+Math.max(.6,right-left)+'" height="195" fill="#d6a770" opacity=".12"/>')}}
  path('close',priceY,Math.log,INK,1.3);
  let floor='',open=false;for(const i of indices){const v=value('e0_floor',i);if(value('e0_target',i)!==1||!finite(v)||v<=0){open=false;continue}floor+=(open?'L':'M')+chartX(i)+','+priceY(Math.log(v));open=true}content.push('<path d="'+floor+'" fill="none" stroke="#ab8355" stroke-width=".8"/>');
  for(const h of [21,63])for(const i of indices){if(value('confirmed_'+h,i)!==1)continue;const x=chartX(i),y=priceY(Math.log(value('close',i))),color=value('confirmed_direction_'+h,i)===1?UP:DOWN;if(h===21)content.push('<circle cx="'+x+'" cy="'+y+'" r="3.2" stroke="'+color+'" stroke-width="1.2" fill="white"/>');else content.push('<path d="M'+x+','+(y-4)+'l4,4 -4,4 -4,-4Z" stroke="'+color+'" stroke-width="1.2" fill="white"/>')}
  const maxVol=Math.max(1,...indices.map(i=>finite(value('volume',i))?value('volume',i):0));const volY=panel(254,55,'量 / 百万',[0,maxVol/1e6],v=>v.toFixed(1));
  const barW=Math.max(.5,Math.min(5,plotW/indices.length*.6));for(const i of indices){const v=value('volume',i);if(!finite(v))continue;let y=volY(v/1e6);content.push('<rect x="'+(chartX(i)-barW/2)+'" y="'+y+'" width="'+barW+'" height="'+(309-y)+'" fill="'+(value('r',i)>=0?'#c3a38a':'#91afbf')+'"/>')}
  const paceKeys=Q('showDaily').checked?['mu5_bp','mu21_bp','r_bp']:['mu5_bp','mu21_bp'];const paceY=panel(340,120,'净推进 logbp',bounds(paceKeys,x=>x,true),v=>v.toFixed(1));line(L,paceY(0),W-R,paceY(0),'#9caaa8',.8);if(Q('showDaily').checked)path('r_bp',paceY,x=>x,'#b7c1c5',.7);path('mu5_bp',paceY,x=>x,UP,1.4);path('mu21_bp',paceY,x=>x,DOWN,1.4);
  const structY=v=>544-v*25;for(const v of [-1,0,1]){line(L,structY(v),W-R,structY(v),'#e4e9e7',.7);text(L-9,structY(v)+4,direction(v),'text-anchor="end"')}text(7,500,'事件结构');text(7,514,'可陈旧');
  for(const h of [21,63]){const offset=h===21?-2:2,color=h===21?UP:DOWN;let d='',prev=null;for(const i of indices){const v=value('S'+h,i);if(!finite(v)){prev=null;continue}const x=chartX(i),y=structY(v)+offset;if(prev===null)d+='M'+x+','+y;else d+='H'+x+'V'+y;prev=v;if(value('confirmed_'+h,i)===1)content.push('<circle cx="'+x+'" cy="'+y+'" r="3" fill="'+color+'"/>')}content.push('<path d="'+d+'" fill="none" stroke="'+color+'" stroke-width="1.2"/>')}
  const shockY=panel(610,102,'当日冲击',bounds(['q','qeff'],x=>x,true),v=>v.toFixed(1));line(L,shockY(0),W-R,shockY(0),'#a5b1af',.7);path('q',shockY,x=>x,'#a6b4bc',.75);path('qeff',shockY,x=>x,'#725b83',1);for(const i of indices){if(value('acute_down',i)!==1&&value('acute_up',i)!==1)continue;const x=chartX(i),y=shockY(value('qeff',i)),dir=value('acute_up',i)===1?1:-1;colorSafeMarker(x,y,dir)}
  function colorSafeMarker(x,y,dir){content.push('<path d="M'+x+','+(y-dir*4)+'l4,'+(dir*7)+' -8,0Z" fill="'+(dir===1?UP:DOWN)+'"/>')}
  const b3Y=v=>774-v*13;for(const v of [-2,0,2]){line(L,b3Y(v),W-R,b3Y(v),'#e4e9e7',.7);text(L-9,b3Y(v)+4,gradeNames[v],'text-anchor="end"')}text(7,740,'旧B3');text(7,754,'仅对照');path('b3_grade',b3Y,x=>x,'#8c9293',.9);
  for(let n=0;n<5;n++){const j=Math.round(n*(indices.length-1)/4),i=indices[j];text(chartX(i),832,asset.dates[i],'text-anchor="middle"')}
  content.push('<line id="cursor" x1="'+L+'" x2="'+L+'" y1="26" y2="810" stroke="#4b7069" stroke-width="1" stroke-dasharray="5 3" pointer-events="none"/><text id="cursorLabel" x="'+L+'" y="18" text-anchor="middle" font-size="12" font-weight="600" fill="#355b51"></text><rect x="'+L+'" y="26" width="'+plotW+'" height="784" fill="transparent" id="hitArea"/>');
  svg.innerHTML=content.join('');
  const pick=event=>{const box=svg.getBoundingClientRect(),x=(event.clientX-box.left)/box.width*W;let nearest=indices[0],distance=Infinity;for(const i of indices){let dist=Math.abs(chartX(i)-x);if(dist<distance){distance=dist;nearest=i}}showRow(nearest)};
  Q('hitArea').addEventListener('pointermove',event=>{if(event.pointerType!=='touch'||event.buttons)pick(event)});Q('hitArea').addEventListener('click',pick);
}

for(const w of payload.windows){let o=document.createElement('option');o.value=w.id;o.textContent=w.name+' · '+w.start+'—'+w.end+' · '+w.id;Q('window').append(o)}
Q('window').onchange=()=>showWindow(Q('window').value);Q('date').onchange=()=>showDate(Q('date').value);
Q('slider').oninput=()=>showRow(indices[Number(Q('slider').value)]);
Q('previous').onclick=()=>showRow(indices[Math.max(0,indices.indexOf(currentIndex)-1)]);Q('next').onclick=()=>showRow(indices[Math.min(indices.length-1,indices.indexOf(currentIndex)+1)]);
Q('showDaily').onchange=()=>{drawChart();showRow(currentIndex)};
document.querySelectorAll('[data-case]').forEach(b=>b.onclick=()=>{const [id,date]=b.dataset.case.split('|');showWindow(id,date)});
for(const s of payload.synthetic){const o=document.createElement('option');o.value=s.id;o.textContent=(s.kind==='derived'?'派生 · ':'合成 · ')+s.id;Q('synthetic').append(o)}
Q('synthetic').onchange=()=>{const s=payload.synthetic.find(s=>s.id===Q('synthetic').value),p='../figures/'+s.kind+'/'+s.id+'.png';Q('synthPlot').src=p;setLink('syntheticOpen',p);setLink('syntheticDownload',p,true)};
Q('synthetic').value='shock_then_slow_decline';Q('synthetic').onchange();
Q('protocol').textContent=payload.protocol;Q('conclusionStatus').textContent=payload.conclusion?'本轮结论已写入；下面保留生成页面时的完整文字快照，最新文件见“完整结论与反例”。':'图表与证据展示已生成，最终裁决尚未写入。本页面不预判通过或晋升；请以结论文件为准。';
if(payload.conclusion)Q('conclusion').textContent=payload.conclusion;else Q('conclusionBlock').hidden=true;
Q('downloads').innerHTML=Object.entries(payload.assets).map(([sid,a])=>'<a href="../results/'+esc(sid)+'.csv">'+esc(a.name)+'</a>').join(' · ');
Q('footer').textContent='生成时间 '+payload.generated_at+' · 7标的22窗 · 原24合成＋1派生 · 账户0。AU0主连拼接/切换口径未完全核实；股票使用既有因果研究坐标，原价阶跃需结合权益口径。';
showWindow('au_user_consolidation','2025-07-31');
</script></body></html>'''


def main():
    payload = build_payload()
    target = ROOT / 'report'
    target.mkdir(exist_ok=False)
    encoded = json.dumps(clean(payload), ensure_ascii=False, allow_nan=False).replace('</', '<\\/')
    html = HTML.replace('__PAYLOAD__', encoded)
    (target / 'index.html').write_text(html)
    write(target / 'build-receipt.json', {'generated_at': now(), 'bytes': len(html.encode()),
                                        **payload['counts'], 'external_dependencies': [],
                                        'model_executed_by_report': False})
    print({'report_bytes': len(html.encode()), 'assets': len(payload['assets']),
           'windows': len(payload['windows']), 'synthetic_and_derived': len(payload['synthetic'])}, flush=True)


if __name__ == '__main__':
    main()
