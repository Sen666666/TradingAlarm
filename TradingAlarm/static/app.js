'use strict';
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = (n, d=2) => typeof n === 'number' && Number.isFinite(n) ? n.toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d}) : '—';
const compact = n => typeof n !== 'number' ? '—' : Math.abs(n)>=1e8 ? fmt(n/1e8)+' 亿' : Math.abs(n)>=1e4 ? fmt(n/1e4)+' 万' : fmt(n,0);
const sign = n => typeof n !== 'number' ? '—' : (n>0?'+':'') + fmt(n);
const change = (p,b) => typeof p==='number' && typeof b==='number' && b!==0 ? (p-b)/b*100 : null;
const direction = n => n===null || n===undefined || n===0 ? 'neutral' : n>0 ? 'up' : 'down';
let favorites;
try { favorites = new Set(JSON.parse(localStorage.getItem('tradingalarm-favorites') || '["USHA688008","USHJ518850","USZA300750"]')); } catch { favorites = new Set(); }
const state={config:null,universe:[],selected:null,view:'day',onlyFavorites:false,range:90,end:null,hover:-1,table:false,page:0,request:0,remote:null,searchRequest:0,searchBusy:false,searchError:null};
let geometry=null,toastTimer,drag=null;
function toast(text){$('#toast').textContent=text;$('#toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').hidden=true,6000);}
async function api(path,options){const response=await fetch(path,options);const data=await response.json();if(!response.ok){const error=new Error(data.error||'数据读取失败');error.status=response.status;error.data=data;throw error;}return data;}
function saveFavorites(){try{localStorage.setItem('tradingalarm-favorites',JSON.stringify([...favorites]));}catch{toast('浏览器无法保存自选，本次会话仍可使用。');}renderList();renderFavorite();}
function renderFavorite(){if(!state.selected)return;const saved=favorites.has(state.selected.symbol);$('#favorite').textContent=saved?'★':'☆';$('#favorite').classList.toggle('saved',saved);$('#favorite').setAttribute('aria-label',saved?'移出自选':'加入自选');$('#favorite').setAttribute('aria-pressed',String(saved));}
function renderList(){
  const query=$('#search').value.trim().toLowerCase();
  const remote=state.remote?.query===query?state.remote.stocks:null;
  const items=remote?remote.filter(s=>!state.onlyFavorites||favorites.has(s.symbol)):state.universe.filter(s=>(!state.onlyFavorites||favorites.has(s.symbol)) && `${s.name} ${s.code} ${s.symbol} ${s.aliases}`.toLowerCase().includes(query));
  $('#result-count').textContent=state.searchBusy?'在线搜索中…':`${remote?'在线 · ':''}${items.length} 个标的${items.length>80?' · 显示前 80 个':''}${state.searchError?' · 在线搜索失败':''}`;
  $('#fav-count').textContent=favorites.size;
  $('#stocks').innerHTML=items.length?items.slice(0,80).map(s=>{
    const pct=change(s.price,s.previousClose);
    return `<button class="stock-row ${s.symbol===state.selected?.symbol?'selected':''}" data-symbol="${esc(s.symbol)}" aria-label="${esc(s.name)} ${esc(s.code)}"><span><strong>${esc(s.name)}</strong><small>${esc(s.code)}${s.hasIntraday?' · 分时':''}${s.hasBars?' · K线':''}${s.liveSupported===false?' · 仅搜索':s.discoveredOnline?' · 在线标的':''}</small></span><span class="row-quote ${direction(pct)}"><b>${fmt(s.price,s.price<10?3:2)}</b><small>${pct===null?'—':sign(pct)+'%'}</small></span></button>`;
  }).join(''):'<div class="empty-list">没有找到匹配标的<br>试试股票代码或中文名称</div>';
}
function renderIndices(){const symbols=['USHI1A0001','USZI399001','USZI399006'];$('#indices').innerHTML=symbols.map(symbol=>{const s=state.universe.find(s=>s.symbol===symbol);if(!s)return '';const pct=change(s.price,s.previousClose);return `<button class="index-card" data-symbol="${esc(symbol)}"><div class="index-top">${esc(s.name)}<small>${esc(s.code)}</small></div><div class="index-bottom ${direction(pct)}"><strong>${fmt(s.price)}</strong><span>${pct===null?'—':sign(pct)+'%'}</span></div><span class="index-arrow ${direction(pct)}">${pct<0?'↘':'↗'}</span></button>`;}).join('');}
async function select(symbol){const request=++state.request;$('#workspace').setAttribute('aria-busy','true');try{const data=await api('/api/stocks/'+encodeURIComponent(symbol));if(request!==state.request)return;state.selected=data;state.range=90;state.end=null;state.hover=-1;state.page=0;if(state.view==='intraday'&&!data.intraday.length&&data.bars.length)state.view='day';else if(state.view!=='intraday'&&!data.bars.length&&data.intraday.length)state.view='intraday';render();if((data.discoveredOnline||state.remote?.stocks.some(r=>r.symbol===symbol))&&state.config.liveEnabled){if(['USHA','USHJ','USHI','USZA','USZJ','USZI'].includes(data.market))await refreshQuote();else toast('已找到该标的；当前在线行情仅支持沪深市场。');}}catch(error){toast(error.message);}finally{if(request===state.request)$('#workspace').setAttribute('aria-busy','false');}}
function render(){
  const s=state.selected,q=s.quote,p=q['10'],previous=q['6'],pct=change(p,previous),delta=pct===null?null:p-previous;
  $('#stock-name').textContent=s.name;$('#stock-code').textContent=s.code;
  $('#stock-market').textContent=s.market.startsWith('USH')?'上海证券交易所':s.market.startsWith('USZ')?'深圳证券交易所':s.market.startsWith('UHK')?'香港交易所':'其他市场';$('#exchange').textContent=s.market.startsWith('UHK')?'港股':s.market.endsWith('I')?'指数':'沪深市场';
  $('#quote-time').textContent=s.source==='live'?'在线查询 · '+s.capturedAt.slice(11):s.discoveredOnline?'在线搜索结果':'采集快照';
  $('#price').textContent=fmt(p,p<10?3:2);$('#price').parentElement.className='quote-main '+direction(delta);$('#change').textContent=sign(delta);$('#change-pct').textContent=pct===null?'—':sign(pct)+'%';
  const last=s.bars.at(-1),sameDay=last?.date===s.capturedAt.slice(0,10),fromBar=key=>sameDay?last[key]:undefined;
  const metric=[['今开',q['7']??fromBar('open'),'price'],['最高',q['8']??fromBar('high'),'price'],['最低',q['9']??fromBar('low'),'price'],['昨收',previous,'price'],['成交量',q['13']??fromBar('volume'),'volume'],['成交额',q['19']??fromBar('amount'),'volume']];
  $('#metrics').innerHTML=metric.map(([label,value,type])=>`<div class="metric"><span>${label}</span><b class="${type==='price'&&value!==undefined?direction(value-previous):''}">${type==='price'?fmt(value,value<10?3:2):compact(value)}</b></div>`).join('');
  $$('.chart-tabs button').forEach(b=>{b.classList.toggle('active',b.dataset.view===state.view);b.setAttribute('aria-selected',String(b.dataset.view===state.view));});
  $$('.range-buttons button').forEach(b=>b.classList.toggle('active',String(state.range)===b.dataset.range));
  $('.range-buttons').hidden=state.view==='intraday';
  $('#adjustment').textContent=state.view==='intraday'?'逐分钟采集':state.view==='day'?'复权待核实':'日 K 聚合';
  $('#legend').innerHTML=state.view==='intraday'?'<span class="ma5">● 分时价格</span><span>虚线：昨收</span>':'<span class="ma5">MA 5</span><span class="ma10">MA 10</span><span class="ma20">MA 20</span>';
  $('#chart-hint').textContent=state.view==='intraday'?'悬停查看价格与分钟成交量':'Ctrl + 滚轮缩放 · 拖动平移';
  $('#table-panel').hidden=!state.table;$('#table-button').textContent=state.table?'收起明细':'历史明细';
  $('#source-note').textContent=s.discoveredOnline&&s.source!=='live'?'标的来自同花顺在线搜索，行情尚未加载。可点击刷新查询；当前仅支持沪深市场。':s.source==='live'?`本人会话在线查询 · ${s.capturedAt} · 手动刷新，60 秒内复用缓存。成交量沿用协议原始口径。`:`真实采集数据 · ${s.capturedAt} · 非当前实时行情。仅展示已采集记录，成交量沿用原始口径。${['week','month'].includes(state.view)?'周/月 K 由已有日 K 聚合，边界周期可能不完整。':''}`;
  renderFavorite();renderList();draw();renderTable();
}
function aggregate(rows,period){
  if(period==='day')return rows;
  const groups=new Map();
  for(const r of rows){let key=r.date.slice(0,7);if(period==='week'){const d=new Date(r.date+'T00:00:00Z');d.setUTCDate(d.getUTCDate()-((d.getUTCDay()+6)%7));key=d.toISOString().slice(0,10);}
    if(!groups.has(key))groups.set(key,{...r,firstDate:r.date,count:1});
    else {const g=groups.get(key);g.high=Math.max(g.high,r.high);g.low=Math.min(g.low,r.low);g.close=r.close;g.date=r.date;g.count++;g.volume=g.volume===null||r.volume===null?null:g.volume+r.volume;g.amount=g.amount===null||r.amount===null?null:g.amount+r.amount;}
  }return [...groups.values()];
}
function allRows(){if(!state.selected)return [];if(state.view==='intraday'){const rows=state.selected.intraday;const date=rows.at(-1)?.date;return rows.filter(r=>r.date===date);}return aggregate(state.selected.bars,state.view);}
function sessionLength(){return state.selected?.market.startsWith('UHK')?330:240;}
function minuteIndex(time){const [h,m]=time.split(':').map(Number);const total=h*60+m;const morningEnd=state.selected?.market.startsWith('UHK')?720:690;return total<=morningEnd?total-570:(morningEnd-570)+total-780;}
function movingAverage(all,index,n){if(index<n-1)return null;return all.slice(index-n+1,index+1).reduce((a,b)=>a+b.close,0)/n;}
function draw(){
  const canvas=$('#chart'),box=$('#chart-container'),width=box.clientWidth,height=box.clientHeight,dpr=window.devicePixelRatio||1;
  canvas.width=Math.round(width*dpr);canvas.height=Math.round(height*dpr);const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);ctx.clearRect(0,0,width,height);
  const all=allRows(),intraday=state.view==='intraday';let end=Math.min(state.end??all.length,all.length);const count=state.range==='all'?all.length:Math.min(state.range,all.length);const start=intraday?0:Math.max(0,end-count);const rows=intraday?all:all.slice(start,end);
  $('#chart-empty').hidden=rows.length>0;$('#empty-switch').hidden=!(state.selected?.bars.length||state.selected?.intraday.length);
  geometry=null;if(!rows.length){$('#range-label').textContent='当前采集范围暂无数据';$('#tooltip').hidden=true;return;}
  $('#range-label').textContent=intraday?`${rows[0].date} · ${rows[0].time}–${rows.at(-1).time}`:`${rows[0].date} — ${rows.at(-1).date} · ${rows.length} 根`;
  const left=12,right=width-73,top=12,bottom=height*.65,volTop=height*.75,volBottom=height-29,plotWidth=right-left;
  let lows=rows.map(r=>intraday?r.price:r.low),highs=rows.map(r=>intraday?r.price:r.high);const previous=state.selected.quote['6'];
  if(intraday&&typeof previous==='number'){lows.push(previous);highs.push(previous);}
  if(!intraday)for(let i=start;i<end;i++)for(const n of [5,10,20]){const ma=movingAverage(all,i,n);if(ma!==null){lows.push(ma);highs.push(ma);}}
  let lo=Math.min(...lows),hi=Math.max(...highs);const pad=Math.max((hi-lo)*.12,Math.abs(hi)*.001,.01);hi+=pad;lo-=pad;
  const y=p=>bottom-(p-lo)/(hi-lo)*(bottom-top),x=i=>intraday?left+Math.max(0,Math.min(sessionLength(),minuteIndex(rows[i].time)))/sessionLength()*plotWidth:left+(i+.5)*plotWidth/rows.length;
  const maxVolume=Math.max(...rows.map(r=>r.volume||0),1);const vy=v=>volBottom-(v||0)/maxVolume*(volBottom-volTop);
  ctx.font='10px -apple-system, sans-serif';ctx.lineWidth=1;
  for(let i=0;i<5;i++){const yy=top+i*(bottom-top)/4;ctx.strokeStyle='#283135';ctx.setLineDash([3,5]);ctx.beginPath();ctx.moveTo(left,yy);ctx.lineTo(right,yy);ctx.stroke();ctx.setLineDash([]);ctx.fillStyle='#73858d';ctx.fillText(fmt(hi-i*(hi-lo)/4,hi<10?3:2),right+11,yy+3);}
  ctx.fillStyle='#6b7f88';ctx.fillText((intraday?'分钟成交量':'成交量')+(rows.every(r=>r.volume==null)?' · 未采集':''),left+2,volTop-10);ctx.fillText(compact(maxVolume),right+11,volTop+3);ctx.fillText('0',right+11,volBottom+3);
  if(intraday){
    if(typeof previous==='number'){ctx.strokeStyle='#788c8755';ctx.setLineDash([5,5]);ctx.beginPath();ctx.moveTo(left,y(previous));ctx.lineTo(right,y(previous));ctx.stroke();ctx.setLineDash([]);}
    ctx.beginPath();rows.forEach((r,i)=>i?ctx.lineTo(x(i),y(r.price)):ctx.moveTo(x(i),y(r.price)));ctx.lineTo(x(rows.length-1),bottom);ctx.lineTo(x(0),bottom);ctx.closePath();const gradient=ctx.createLinearGradient(0,top,0,bottom);gradient.addColorStop(0,'#d9bc752b');gradient.addColorStop(1,'#d9bc7500');ctx.fillStyle=gradient;ctx.fill();
    ctx.beginPath();rows.forEach((r,i)=>i?ctx.lineTo(x(i),y(r.price)):ctx.moveTo(x(i),y(r.price)));ctx.strokeStyle='#ddbf75';ctx.lineWidth=1.5;ctx.stroke();
  }else{
    const w=Math.max(1,Math.min(14,plotWidth/rows.length*.62));
    rows.forEach((r,i)=>{ctx.strokeStyle=ctx.fillStyle=r.close>=r.open?'#eb7f84':'#67b99f';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(x(i),y(r.high));ctx.lineTo(x(i),y(r.low));ctx.stroke();ctx.fillRect(x(i)-w/2,Math.min(y(r.open),y(r.close)),w,Math.max(1,Math.abs(y(r.open)-y(r.close))));});
    [5,10,20].forEach((n,j)=>{ctx.strokeStyle=['#ddbf75','#a49de2','#72a7c5'][j];ctx.lineWidth=1;ctx.beginPath();let begun=false;rows.forEach((_,i)=>{const v=movingAverage(all,start+i,n);if(v===null)return;if(!begun){ctx.moveTo(x(i),y(v));begun=true;}else ctx.lineTo(x(i),y(v));});ctx.stroke();});
  }
  const vw=Math.max(1,Math.min(14,plotWidth/(intraday?sessionLength():rows.length)*.62));rows.forEach((r,i)=>{const rising=intraday?r.price>=(rows[i-1]?.price??previous??r.price):r.close>=r.open;ctx.fillStyle=rising?'#c96a7088':'#4eae9188';ctx.fillRect(x(i)-vw/2,vy(r.volume),vw,volBottom-vy(r.volume));});
  ctx.strokeStyle='#303b3e';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(left,volBottom);ctx.lineTo(right,volBottom);ctx.stroke();ctx.fillStyle='#71828b';
  if(intraday){(sessionLength()===330?[['09:30',0],['11:00',90],['12:00 / 13:00',150],['14:30',240],['16:00',330]]:[['09:30',0],['10:30',60],['11:30 / 13:00',120],['14:00',180],['15:00',240]]).forEach(([text,m])=>{const xx=left+m/sessionLength()*plotWidth;ctx.textAlign=m===0?'left':m===sessionLength()?'right':'center';ctx.fillText(text,xx,height-9);});}
  else{const labels=Math.min(rows.length,width<500?3:4);for(let j=0;j<labels;j++){const i=Math.round(j*(rows.length-1)/Math.max(1,labels-1));ctx.textAlign=j===0?'left':j===labels-1?'right':'center';ctx.fillText(rows[i].date,x(i),height-9);}}
  ctx.textAlign='left';geometry={rows,start,all,left,right,top,bottom,volBottom,x,y,width,height};
  if(state.hover>=0&&state.hover<rows.length){const i=state.hover,r=rows[i],xx=x(i),yy=y(intraday?r.price:r.close);ctx.strokeStyle='#a7bebc80';ctx.setLineDash([3,4]);ctx.beginPath();ctx.moveTo(xx,top);ctx.lineTo(xx,volBottom);ctx.moveTo(left,yy);ctx.lineTo(right,yy);ctx.stroke();ctx.setLineDash([]);ctx.fillStyle='#a2e5c6';ctx.beginPath();ctx.arc(xx,yy,3,0,Math.PI*2);ctx.fill();}
}
function showTooltip(event){if(!geometry)return;const rect=$('#chart').getBoundingClientRect(),px=event.clientX-rect.left;let closest=0,distance=Infinity;geometry.rows.forEach((r,i)=>{const d=Math.abs(geometry.x(i)-px);if(d<distance){closest=i;distance=d;}});state.hover=closest;const r=geometry.rows[closest],intra=state.view==='intraday';const values=intra?[['价格',fmt(r.price)],['成交量',compact(r.volume)],['成交额',compact(r.amount)]]:[['开盘',fmt(r.open)],['最高',fmt(r.high)],['最低',fmt(r.low)],['收盘',fmt(r.close)],['成交量',compact(r.volume)],['成交额',compact(r.amount)]];const tooltip=$('#tooltip');tooltip.innerHTML=`<strong>${esc(r.date)}${intra?' '+esc(r.time):''}</strong>`+values.map(([label,value])=>`<div><span>${label}</span><b>${value}</b></div>`).join('');tooltip.hidden=false;tooltip.style.left=(px>geometry.width/2?Math.max(4,px-190):Math.min(geometry.width-185,px+18))+'px';tooltip.style.top='15px';draw();}
function tableValues(row){return state.view==='intraday'?[row.date+' '+row.time,row.price,row.volume,row.amount]:[row.date,row.open,row.high,row.low,row.close,row.volume,row.amount];}
function headers(){return state.view==='intraday'?['时间','价格','成交量','成交额']:['日期','开盘','最高','最低','收盘','成交量','成交额'];}
function renderTable(){if(!state.table)return;const rows=allRows().slice().reverse(),size=25;state.page=Math.min(state.page,Math.max(0,Math.ceil(rows.length/size)-1));const page=rows.slice(state.page*size,(state.page+1)*size);$('#table-head').innerHTML='<tr>'+headers().map(h=>`<th>${h}</th>`).join('')+'</tr>';$('#table-body').innerHTML=page.length?page.map(r=>'<tr>'+tableValues(r).map((v,i,a)=>`<td>${i===0?esc(v):i>=a.length-2?compact(v):fmt(v,v<10?3:2)}</td>`).join('')+'</tr>').join(''):`<tr><td colspan="7">暂无该周期数据</td></tr>`;$('#table-count').textContent=`共 ${rows.length} 条 · 第 ${rows.length?state.page+1:0} / ${Math.ceil(rows.length/size)} 页`;$('#prev-page').disabled=state.page===0;$('#next-page').disabled=(state.page+1)*size>=rows.length;$('#export').disabled=!rows.length;}
function setView(view){state.view=view;state.end=null;state.hover=-1;state.page=0;$('#tooltip').hidden=true;render();}
let searchTimer;
$('#search').addEventListener('input',()=>{
 clearTimeout(searchTimer);const sequence=++state.searchRequest;
 const query=$('#search').value.trim();state.remote=null;state.searchError=null;state.searchBusy=false;renderList();
 if(!query||!state.config?.searchEnabled)return;
 state.searchBusy=true;renderList();
 searchTimer=setTimeout(async()=>{
  try{const result=await api('/api/search',{method:'POST',headers:{'Content-Type':'application/json','X-TradingAlarm-Token':state.config.csrf},body:JSON.stringify({query})});
   if(sequence!==state.searchRequest)return;
   state.remote={query:query.toLowerCase(),stocks:result.stocks};
   for(const stock of result.stocks){const i=state.universe.findIndex(s=>s.symbol===stock.symbol);if(i<0)state.universe.push(stock);else Object.assign(state.universe[i],stock);}
  }catch(error){if(sequence!==state.searchRequest)return;state.searchError=error.message;toast(error.message);}
  finally{if(sequence===state.searchRequest){state.searchBusy=false;renderList();}}
 },400);
});
$('#all-tab').onclick=()=>{state.onlyFavorites=false;$('#all-tab').classList.add('active');$('#fav-tab').classList.remove('active');renderList();};
$('#fav-tab').onclick=()=>{state.onlyFavorites=true;$('#fav-tab').classList.add('active');$('#all-tab').classList.remove('active');renderList();};
for(const selector of ['#stocks','#indices'])$(selector).addEventListener('click',e=>{const button=e.target.closest('[data-symbol]');if(button)select(button.dataset.symbol);});
$('#favorite').onclick=()=>{if(!state.selected)return;const symbol=state.selected.symbol;favorites.has(symbol)?favorites.delete(symbol):favorites.add(symbol);saveFavorites();};
$$('.chart-tabs button').forEach(b=>b.onclick=()=>setView(b.dataset.view));
$$('.range-buttons button').forEach(b=>b.onclick=()=>{state.range=b.dataset.range==='all'?'all':Number(b.dataset.range);state.end=null;state.hover=-1;$('#tooltip').hidden=true;render();});
$('#table-button').onclick=()=>{state.table=!state.table;render();};
$('#prev-page').onclick=()=>{state.page--;renderTable();};$('#next-page').onclick=()=>{state.page++;renderTable();};
$('#export').onclick=()=>{const rows=allRows();if(!rows.length)return;const csv='\ufeff'+[headers(),...rows.map(tableValues)].map(row=>row.map(v=>'"'+String(v??'').replaceAll('"','""')+'"').join(',')).join('\r\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=`TradingAlarm-${state.selected.code}-${state.view}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
$('#empty-switch').onclick=()=>setView(state.selected.bars.length?'day':'intraday');
for(const selector of ['#help-button','#source-button'])$(selector).onclick=()=>$('#help').showModal();$('#close-help').onclick=()=>$('#help').close();
async function refreshQuote(){if(!state.config.liveEnabled){$('#help').showModal();return;}const symbol=state.selected.symbol,request=state.request;$('#refresh').disabled=true;$('#refresh').textContent='读取中…';try{const data=await api('/api/refresh',{method:'POST',headers:{'Content-Type':'application/json','X-TradingAlarm-Token':state.config.csrf},body:JSON.stringify({symbol})});if(request===state.request){state.selected=data;const item=state.universe.find(s=>s.symbol===symbol);Object.assign(item,{price:data.quote['10'],previousClose:data.quote['6'],hasBars:!!data.bars.length,hasIntraday:!!data.intraday.length});if(state.remote){const remote=state.remote.stocks.find(s=>s.symbol===symbol);if(remote)Object.assign(remote,item);}render();renderIndices();toast('在线行情已更新');}}catch(error){toast(error.message);if([401,409].includes(error.status))$('#auto-refresh').checked=false;}finally{$('#refresh').disabled=false;$('#refresh').textContent='↻ 刷新';await updateSession();}}
$('#refresh').onclick=refreshQuote;
$('#chart').addEventListener('pointermove',e=>{if(drag&&geometry&&state.view!=='intraday'){const count=state.range==='all'?geometry.all.length:state.range;const delta=Math.round((drag.x-e.clientX)/(geometry.right-geometry.left)*Math.min(count,geometry.all.length));state.end=Math.max(Math.min(count,geometry.all.length),Math.min(geometry.all.length,drag.end+delta));state.hover=-1;$('#tooltip').hidden=true;draw();}else showTooltip(e);});
$('#chart').addEventListener('pointerleave',()=>{if(!drag){state.hover=-1;$('#tooltip').hidden=true;draw();}});
$('#chart').addEventListener('pointerdown',e=>{if(geometry&&state.view!=='intraday'){drag={x:e.clientX,end:state.end??geometry.all.length};$('#chart').setPointerCapture(e.pointerId);}});
$('#chart').addEventListener('pointerup',()=>{drag=null;});$('#chart').addEventListener('pointercancel',()=>{drag=null;});
$('#chart').addEventListener('wheel',e=>{if(!geometry||state.view==='intraday'||!(e.ctrlKey||e.metaKey))return;e.preventDefault();const total=geometry.all.length;let count=state.range==='all'?total:state.range;state.range=Math.min(total,Math.max(Math.min(15,total),Math.round(count*(e.deltaY>0?1.15:.85))));state.hover=-1;$('#tooltip').hidden=true;$$('.range-buttons button').forEach(b=>b.classList.toggle('active',b.dataset.range===String(state.range)));draw();},{passive:false});
new ResizeObserver(()=>{if(state.selected)draw();}).observe($('#chart-container'));
document.addEventListener('keydown',e=>{if(e.key==='/'&&!['INPUT','TEXTAREA'].includes(document.activeElement.tagName)){e.preventDefault();$('#search').focus();}});
async function updateSession(){
 try{const s=await api('/api/session');const labels={ready:s.lastSuccess?'会话已通过在线验证':'本地票据已载入 · 待在线验证',expired:'会话已过期',rejected:'会话被拒绝 · 等待更新',backoff:'连接暂不可用 · 退避中',missing:'没有可用会话'};
 $('#session-label').textContent=labels[s.state]||'会话状态未知';
 $('#session-detail').textContent=(s.enabled?'在线模式':'在线模式未启用')+(s.expiresAt?' · 票据到期 '+s.expiresAt.slice(0,16).replace('T',' '):'')+(s.retryAfterSeconds?' · '+s.retryAfterSeconds+' 秒后重试':'')+(s.nearExpiry?' · 即将到期，请在同花顺正常登录':'');
 $('#auto-refresh').disabled=!s.enabled||['expired','rejected','missing'].includes(s.state);
 if($('#auto-refresh').disabled)$('#auto-refresh').checked=false;
 }catch{$('#session-label').textContent='会话状态读取失败';}
}
$('#auto-refresh').onchange=()=>{if($('#auto-refresh').checked){toast('已开启：仅页面可见时，每分钟刷新当前标的。');refreshQuote();}};
setInterval(()=>{if(document.visibilityState==='visible'){updateSession();if($('#auto-refresh').checked&&!$('#refresh').disabled)refreshQuote();}},60000);
async function init(){try{const [config,search]=await Promise.all([api('/api/config'),api('/api/search')]);state.config=config;state.universe=search.stocks;$('#capture-time').textContent=config.capturedAt;$('#library-count').textContent=`${config.searchEnabled?'在线搜索已接入':config.stockCount.toLocaleString()+' 个标的 · 本地目录'}`;$('#mode-badge').innerHTML=config.liveEnabled?'<i></i> 在线模式已启用':'<i></i> 采集数据';$('#refresh').textContent=config.liveEnabled?'↻ 刷新':'数据说明';renderIndices();renderList();await select('USHA688008');await updateSession();}catch(error){$('#stock-name').textContent='行情加载失败';toast(error.message);}}
init();
