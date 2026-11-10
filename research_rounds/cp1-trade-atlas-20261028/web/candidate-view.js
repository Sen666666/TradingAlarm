'use strict';

// Independent, read-only stock chart. Opening a competitor never replaces the trade being reviewed.
const candidateView={request:0,sid:null,trade:null,path:null,price:null,e0:null,chart:null,amount:null,series:{},sync:false};
function closeCandidateChart(){
  candidateView.request++;
  if($('candidateViewer').open)$('candidateViewer').close();
}
async function openCandidateChart(sid){
  const trade=state.selected,path=state.path,rating=state.rating;
  if(!trade||!path||!rating)return;
  const request=++candidateView.request,m=state.index.stocks[sid];
  if(!m)return;
  Object.assign(candidateView,{sid,trade,path,price:null,e0:null});
  $('candidateTitle').textContent=m.name+' '+sid+' · K 线';
  $('candidateContext').textContent='对照 '+trade.decision_at+' 的选股决策｜'+policy[trade.policy]+' · '+scenario[trade.scenario]+'｜原交易：'+trade.name;
  $('candidateSummary').textContent='当时 RS-H1 '+num(rating.stocks[sid]?.[0],6)+'，全池序位 '+(rating.stocks[sid]?.[1]??'—')+' / '+trade.pool_count+'。';
  $('candidatePrice').value=$('priceMode').value;
  $('candidateRange').value='decision';
  $('candidateLoading').hidden=false;
  $('candidateError').hidden=true;
  $('candidateChartArea').hidden=true;
  if(!$('candidateViewer').open)$('candidateViewer').showModal();
  try{
    const [price,e0]=await Promise.all([load('data/prices/'+sid+'.json'),load('data/e0-entry-v1/'+sid+'.json')]);
    if(request!==candidateView.request||!$('candidateViewer').open)return;
    candidateView.price=price;candidateView.e0=e0;
    $('candidateChartArea').hidden=false;
    await new Promise(resolve=>requestAnimationFrame(resolve));
    if(request!==candidateView.request||!$('candidateViewer').open)return;
    initCandidateCharts();
    renderCandidateChart();
  }catch(e){
    if(request!==candidateView.request)return;
    $('candidateError').textContent='该股票的 K 线加载失败：'+e.message;
    $('candidateError').hidden=false;
  }finally{
    if(request===candidateView.request)$('candidateLoading').hidden=true;
  }
}
function initCandidateCharts(){
  if(candidateView.chart)return;
  const opts={layout:{background:{type:'solid',color:'#ffffff'},textColor:'#596a7e',fontFamily:'-apple-system,PingFang SC,sans-serif',fontSize:12},grid:{vertLines:{color:'#f0f3f7'},horzLines:{color:'#eaf0f5'}},rightPriceScale:{borderColor:'#dce3ec',minimumWidth:65},timeScale:{borderColor:'#dce3ec',rightOffset:3,timeVisible:false},crosshair:{mode:LightweightCharts.CrosshairMode.Normal}};
  const chart=candidateView.chart=LightweightCharts.createChart($('candidatePriceChart'),{...opts,width:$('candidatePriceChart').clientWidth,height:320});
  const amount=candidateView.amount=LightweightCharts.createChart($('candidateAmountChart'),{...opts,width:$('candidateAmountChart').clientWidth,height:90});
  const s=candidateView.series;
  s.candle=chart.addCandlestickSeries({upColor:'#cf4550',downColor:'#168277',borderVisible:false,wickUpColor:'#cf4550',wickDownColor:'#168277'});
  s.e0=chart.addLineSeries({color:'#929cad',lineWidth:1,lineStyle:2,priceLineVisible:false,lastValueVisible:false,crosshairMarkerVisible:false});
  for(const [key,color] of [['buy','#cf4550'],['sell','#168277']])s[key]=chart.addLineSeries({color,lineVisible:false,pointMarkersVisible:true,pointMarkersRadius:5,priceLineVisible:false,lastValueVisible:false,crosshairMarkerVisible:false});
  s.amount=amount.addHistogramSeries({priceFormat:{type:'custom',formatter:x=>num(x,2)+'亿'},priceLineVisible:false,lastValueVisible:false});
  chart.timeScale().subscribeVisibleLogicalRangeChange(r=>{
    if(candidateView.sync||!r)return;
    candidateView.sync=true;amount.timeScale().setVisibleLogicalRange(r);candidateView.sync=false;
  });
  amount.timeScale().subscribeVisibleLogicalRangeChange(r=>{
    if(candidateView.sync||!r)return;
    candidateView.sync=true;chart.timeScale().setVisibleLogicalRange(r);candidateView.sync=false;
  });
  chart.subscribeCrosshairMove(p=>{
    if(!p.time||!candidateView.price)return;
    const row=candidateView.price.bars.find(r=>r[0]===dayOf(p.time));
    if(row)$('candidateCrosshair').textContent=candidateCandleText(row);
  });
  new ResizeObserver(()=>{if($('candidateViewer').open&&candidateView.price)resizeCandidateCharts()}).observe($('candidatePriceChart'));
}
function candidateCandleText(row){
  const raw=$('candidatePrice').value==='raw',factor=raw?1:row[6];
  return state.index.stocks[candidateView.sid].name+'｜'+row[0]+'｜'+(raw?'未复权':'因果复权')+' O '+num(row[1]*factor,4)+' H '+num(row[2]*factor,4)+' L '+num(row[3]*factor,4)+' C '+num(row[4]*factor,4)+'｜成交额 '+num(row[5]/1e8,3)+' 亿元｜E0开仓 '+(candidateView.e0?.entries.includes(row[0])?'是':'否');
}
function resizeCandidateCharts(){
  const w=$('candidatePriceChart').clientWidth;
  if(w>0&&candidateView.chart){candidateView.chart.resize(w,matchMedia('(max-width:760px)').matches?265:350);candidateView.amount.resize(w,85)}
}
function resetCandidateRange(){
  const v=candidateView;if(!v.chart||!v.price)return;
  const bars=v.price.bars;
  if($('candidateRange').value==='all'){v.chart.timeScale().fitContent();return}
  let i=bars.findIndex(r=>r[0]>=v.trade.decision_at);
  if(i<0)i=bars.length-1;
  const lo=Math.max(0,i-30),hi=Math.min(bars.length-1,i+60);
  v.chart.timeScale().setVisibleLogicalRange({from:lo-1,to:Math.max(lo+10,hi)+2});
}
function renderCandidateChart(){
  const v=candidateView;if(!v.price||!v.chart)return;
  const bars=v.price.bars,raw=$('candidatePrice').value==='raw',byDay=new Map(bars.map(r=>[r[0],r])),s=v.series;
  s.candle.setData(bars.map(r=>({time:r[0],open:r[1]*(raw?1:r[6]),high:r[2]*(raw?1:r[6]),low:r[3]*(raw?1:r[6]),close:r[4]*(raw?1:r[6])})));
  s.e0.setData(bars.map(r=>r[7]==null?{time:r[0]}:{time:r[0],value:r[7]/(raw?r[6]:1)}));
  s.e0.applyOptions({visible:$('candidateE0').checked});
  s.amount.setData(bars.map(r=>({time:r[0],value:r[5]/1e8,color:r[4]>=r[1]?'#da9da3':'#8ec1b9'})));
  const buys=new Map(),sells=new Map(),marks=[];
  if($('candidateEntry').checked)for(const date of v.e0?.entries||[])if(byDay.has(date))marks.push({time:date,position:'belowBar',shape:'square',color:'#7950b3',text:'E0开仓'});
  $('candidateEntrySummary').textContent='载入历史共 '+(v.e0?.entries.length||0)+' 次本股原始 E0 开仓信号；持续有效期间不重复标记。';
  for(const cycle of v.path.cycles){
    const row=state.index.cycles.find(t=>t.id===cycle.id);
    if(row.symbol!==v.sid)continue;
    for(const f of cycle.fills){
      const date=f.at.slice(0,10);if(!byDay.has(date))continue;
      (f.side==='buy'?buys:sells).set(date,{time:date,value:raw?f.raw_price:f.causal_price});
      marks.push({time:date,position:f.side==='buy'?'belowBar':'aboveBar',shape:f.side==='buy'?'arrowUp':'arrowDown',color:f.side==='buy'?'#cf4550':'#168277',text:(f.side==='buy'?'买 ':'卖 ')+num(f.shares,0)+'股'});
    }
  }
  if(byDay.has(v.trade.decision_at))marks.push({time:v.trade.decision_at,position:'aboveBar',shape:'circle',color:'#c98720',text:'原交易买入决策'});
  s.buy.setData([...buys.values()].sort((a,b)=>a.time.localeCompare(b.time)));
  s.sell.setData([...sells.values()].sort((a,b)=>a.time.localeCompare(b.time)));
  s.candle.setMarkers(marks.sort((a,b)=>a.time.localeCompare(b.time)));
  const decision=byDay.get(v.trade.decision_at),last=decision||bars.at(-1);
  $('candidateCrosshair').textContent=candidateCandleText(last);
  $('candidateSummary').textContent='决策日 RS-H1 '+num(state.rating.stocks[v.sid]?.[0],6)+'，全池序位 '+(state.rating.stocks[v.sid]?.[1]??'—')+' / '+v.trade.pool_count+'。本账户对该股共有 '+buys.size+' 次实际买入、'+sells.size+' 次实际卖出；未买入也完整展示行情。';
  resizeCandidateCharts();resetCandidateRange();
}
$('closeCandidate').onclick=closeCandidateChart;
$('candidateViewer').addEventListener('cancel',()=>{candidateView.request++});
$('candidatePrice').onchange=renderCandidateChart;
$('candidateRange').onchange=resetCandidateRange;
$('candidateReset').onclick=resetCandidateRange;
$('candidateE0').onchange=()=>candidateView.series.e0?.applyOptions({visible:$('candidateE0').checked});

$('candidateEntry').onchange=renderCandidateChart;
