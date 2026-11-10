"""Render immutable v0 output into diagnostic figures and a self-contained viewer."""
from pathlib import Path
import os,json,base64,html,hashlib
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OUT=HERE/'results/v0'
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.tools/czsc/mpl'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.font_manager import FontProperties
from matplotlib.colors import ListedColormap,BoundaryNorm
FONT=FontProperties(fname='/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
COLORS=['#c4ced8','#9bbfbd','#e9ce8e','#cda1a0','#eea46b','#e46f50','#ad3b46']
NAMES=['冷','回暖','突破待验','量价立态','有效推进','多尺度强趋势','放量扩张']
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ranges(ax,index,values,color,lo,hi):
    if not len(index):return
    starts=np.flatnonzero(values & ~np.r_[False,values[:-1]])
    ends=np.flatnonzero(values & ~np.r_[values[1:],False])
    for a,b in zip(starts,ends):ax.axvspan(index[a],index[b]+pd.Timedelta(days=1),ymin=lo,ymax=hi,color=color,alpha=.85,lw=0)
def draw(spec,d,name,path):
    z=d.loc[spec['start']:spec['end']];fig,axs=plt.subplots(5,1,figsize=(15,11),sharex=True,gridspec_kw={'height_ratios':[3.3,1,1.3,1.3,1.2]})
    fig.suptitle(name+'｜'+spec['id']+'｜温度原型与原算法',fontproperties=FONT,fontsize=16,x=.065,ha='left')
    a=axs[0];a.plot(z.index,z.close,color='#2a3e4d',lw=1.1,label='相同复权口径收盘')
    a.fill_between(z.index,z.low,z.high,color='#536c80',alpha=.13)
    a.plot(z.index,z.baseline_floor,color='#c47c7a',lw=.9,ls='--',label='原算法保护点')
    a.plot(z.index,z.floor,color='#168576',lw=1,label='原型结构下沿')
    for k in range(4,7):ranges(a,z.index,z.level.eq(k).to_numpy(),COLORS[k],0,1)
    # Low opacity keeps the actual price trace legible over the temperature background.
    for patch in a.patches:patch.set_alpha(.11)
    for flag,color,marker,label in [('baseline_entered','#537cb3','o','原算法新参与'),('entered','#097e6e','^','原型新参与')]:
        q=z.loc[z[flag].eq(1)];a.scatter(q.index,q.close,c=color,marker=marker,s=38,zorder=5,label=label)
    a.set_yscale('log');a.set_ylim(float(z.low.min())*.96,float(z.high.max())*1.04)
    a.legend(prop=FONT,loc='upper left',fontsize=8,ncol=3,framealpha=.85)
    a.set_ylabel('复权价／对数',fontproperties=FONT)
    a=axs[1];a.bar(z.index,z.q,color=np.where(z.close.diff().ge(0),'#83a7b3','#cf9994'),width=1.5)
    for y in [1.5,2]:a.axhline(y,color='#8c8791',ls='--',lw=.7)
    a.set_ylabel('量比 q',fontproperties=FONT)
    a=axs[2];a.step(z.index,z.level,where='post',c='#5d6170',lw=.8);a.scatter(z.index,z.level,c=[COLORS[int(k)] if k>=0 else '#fff' for k in z.level],s=12)
    a.axhline(3.5,color='#bb6844',ls=':',lw=.8);a.set_yticks(range(7));a.set_yticklabels([str(i)+' '+s for i,s in enumerate(NAMES)],fontproperties=FONT,fontsize=8);a.set_ylim(-.5,6.5)
    a=axs[3]
    lanes=[('baseline_target','原算法结构参与','#537cb3'),('structure','原型结构即参与','#8795a1'),('target','原型4级触发后延续','#168576'),('hot','当日温度≥4','#e58e58')]
    for i,(col,label,color) in enumerate(lanes):
        v=z.level.ge(4).to_numpy() if col=='hot' else z[col].astype(bool).to_numpy()
        ranges(a,z.index,v,color,i/4+.03,(i+1)/4-.03)
    a.set_ylim(0,4);a.set_yticks(np.arange(4)+.5);a.set_yticklabels([x[1] for x in lanes],fontproperties=FONT,fontsize=8)
    a=axs[4];a.plot(z.index,z.z20,c='#3e8fa7',lw=1,label='20观察推进Z');a.plot(z.index,z.z63,c='#aa7290',lw=1,label='63观察推进Z');a.axhline(1,c='#8f9199',ls='--',lw=.7);a.axhline(0,c='#b7bdc3',lw=.5)
    a.legend(prop=FONT,loc='upper left',fontsize=8,ncol=2)
    for a in axs:
        a.grid(alpha=.12);a.spines[['top','right']].set_visible(False);a.tick_params(labelsize=8)
    axs[-1].xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    fig.text(.07,.012,'信号观察原型，无成交／收益。温度下降不自动退出；第3条参与带可跨越整理。保护点较宽会影响失效频率，不能据此认定经济改善。',fontproperties=FONT,fontsize=9,color='#53626d')
    fig.tight_layout(rect=(0,.035,1,.96));fig.savefig(path,dpi=125);plt.close(fig)

def main():
    fr=json.loads((HERE/'input-freeze.json').read_text());prot=json.loads((HERE/'protocol.json').read_text());result=json.loads((OUT/'complete.json').read_text())
    charts=HERE/'charts';charts.mkdir(exist_ok=True)
    records={r['symbol']:r for r in fr['series']};frames={sid:pd.read_parquet(OUT/'daily'/(sid+'.parquet')) for sid in records}
    specs=[dict(id='full-'+sid,symbol=sid,start='2023-01-01',end='2026-10-22') for sid in fr['primary']]
    specs+=json.loads((HERE/'cases.json').read_text())
    for s in specs:draw(s,frames[s['symbol']],records[s['symbol']]['name'],charts/(s['id']+'.png'))
    # Compact main panel; all full figures remain available for close reading.
    fig,axs=plt.subplots(4,1,figsize=(14,12),sharex=True)
    for a,sid in zip(axs,['USHJ518880','USHJ512480','600919.SH','600917.SH']):
        z=frames[sid].loc['2024-01-01':'2026-10-16'];a.plot(z.index,z.close,c='#30495a',lw=1.1)
        for k in [4,5,6]:
            ranges(a,z.index,z.level.eq(k).to_numpy(),COLORS[k],0,1)
        for p in a.patches:p.set_alpha(.15)
        for flag,color,marker in [('baseline_entered','#537cb3','o'),('entered','#0b8776','^')]:
            q=z.loc[z[flag].eq(1)];a.scatter(q.index,q.close,c=color,s=28,marker=marker,zorder=4)
        r=next(r for r in result['series'] if r['symbol']==sid)
        a.set_title(f"{records[sid]['name']}｜原算法 {r['baseline_starts']} 次 → 原型结构 {r['structure_starts']} 次 → 4级触发 {r['temperature_starts']} 次",fontproperties=FONT,loc='left',fontsize=12)
        a.set_yscale('log');a.grid(alpha=.15);a.spines[['top','right']].set_visible(False)
    fig.suptitle('七级温度原型｜2024—2026本地信号对照',fontproperties=FONT,fontsize=17,x=.065,ha='left')
    fig.text(.07,.015,'蓝点：原算法新参与  ·  绿三角：原型新参与  ·  暖色：当日4—6级。次数不含期初承接；不是实际开仓或收益。',fontproperties=FONT,fontsize=10)
    fig.tight_layout(rect=(0,.04,1,.96));fig.savefig(HERE/'preview.png',dpi=125);plt.close(fig)
    cols=['open','high','low','close','volume','level','target','entered','exited','floor','baseline_target','baseline_entered','baseline_floor','structure','q','z5','z20','z63','er20','er63','clv','guard','guard_reclaim','fast','overextended','phase','reason','heat_cross','accepted','accept_kind','price_target']
    payload={}
    for sid,d in frames.items():
        z=d.loc['2022-01-01':].copy();z['date']=z.index.strftime('%Y-%m-%d')
        payload[sid]=json.loads(z[['date']+cols].to_json(orient='records',force_ascii=False))
    levels=''.join(f'<tr><td><b style="color:{COLORS[i]}">{i} {n}</b></td><td>{html.escape(prot["levels"][str(i)])}</td></tr>' for i,n in enumerate(NAMES))
    rows=''.join('<tr>'+''.join(f'<td>{html.escape(str(r[k]))}</td>' for k in ['name','baseline_starts','structure_starts','temperature_starts','price_only_starts','heat_crosses','baseline_days','temperature_days'])+'</tr>' for r in result['series'] if r['primary'])
    windows=''.join('<tr>'+''.join(f'<td>{html.escape(str(r[k]))}</td>' for k in ['id','symbol','baseline_starts','temperature_starts','baseline_carry','temperature_carry','baseline_failure10','temperature_failure10'])+'</tr>' for r in result['windows'])
    pairs=''.join('<tr>'+''.join(f'<td>{html.escape(str(r[k]))}</td>' for k in ['symbol','sector','baseline_starts','temperature_starts','baseline_days','temperature_days'])+'</tr>' for r in result['pairs'])
    options=''.join(f'<option value="{i}">{html.escape(records[s["symbol"]]["name"]+" · "+s["id"])}</option>' for i,s in enumerate(specs))
    page=HTML.replace('@@LEVELS@@',levels).replace('@@ROWS@@',rows).replace('@@WINDOWS@@',windows).replace('@@PAIRS@@',pairs).replace('@@OPTIONS@@',options)
    page=page.replace('@@PAYLOAD@@',json.dumps(payload,ensure_ascii=False,separators=(',',':')).replace('</','<\\/'))
    page=page.replace('@@SPECS@@',json.dumps(specs,ensure_ascii=False)).replace('@@RECORDS@@',json.dumps(records,ensure_ascii=False)).replace('@@PAIRMAPPING@@',json.dumps(fr['pairs'])).replace('@@PRIMARY@@',json.dumps(fr['primary']))
    (HERE/'index.html').write_text(page)
    dump(HERE/'render-manifest.json',dict(figure_count=len(specs),html_sha256=sha(HERE/'index.html'),preview_sha256=sha(HERE/'preview.png'),render_code_sha256=sha(__file__),model_sha256=sha(HERE/'temperature.py'),account_runs=0))
    print(json.dumps({'figures':len(specs),'html_bytes':len(page.encode()),'preview':str(HERE/'preview.png')},ensure_ascii=False))

HTML='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>七级温度原型 量价依据与图表对照</title><style>
*{box-sizing:border-box}body{margin:0;background:#f3f6f7;color:#243945;font:15px/1.7 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}main{max-width:1240px;margin:auto;padding:34px 24px}h1{font-size:30px;line-height:1.3;margin:0 0 12px}h2{font-size:22px;margin:0 0 14px}p{margin:10px 0}.lead{max-width:950px;color:#4f6571}.badge{font-size:12px;color:#167d70;background:#e3f1ec;padding:5px 9px;border-radius:4px}.card{background:#fff;border:1px solid #dce4e8;border-radius:12px;padding:24px;margin:22px 0}.notice{background:#fff5e7;border-left:4px solid #d59a41;padding:14px 18px}.controls{display:flex;gap:16px;align-items:center;flex-wrap:wrap;margin:12px 0}select,input,button{font:inherit}select{max-width:100%;padding:8px;border:1px solid #c9d6dc;border-radius:6px}input[type=range]{width:100%}svg{display:block;width:100%;background:#fff;touch-action:pan-y}#details{background:#f5f8fa;border-radius:8px;padding:12px 16px;min-height:110px}.muted,small{color:#647986}table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;padding:10px;border-bottom:1px solid #e4ebef;vertical-align:top}th{background:#f2f6f8;white-space:nowrap}.scroll{overflow:auto}a{color:#137e82}code{background:#edf2f4;padding:1px 4px}img{max-width:100%}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.metrics b{display:block;font-size:25px}.metrics>div{background:#f4f7f8;padding:14px;border-radius:8px}details{margin-top:14px}summary{cursor:pointer;font-weight:600}.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:#59717f}@media(max-width:650px){main{padding:20px 12px}.card{padding:16px}h1{font-size:25px}.metrics{grid-template-columns:1fr}table{min-width:680px}}
</style><main><span class="badge">本地研究原型 · 一个冻结候选 · 无账户回测</span><h1>七级温度原型<br>先分清结构有效与当前推进</h1><p class="lead">从回暖、突破待验到有效推进、多尺度支持与放量扩张，每级增加不同证据。原算法完整保留；资料来自既有黄金ETF、半导体和股票历史。已见开发样本，不能视为样本外或真实成交。</p>
<div class="notice"><b>这版的主要发现：</b>参与事件减少，但主要来自结构解析和更宽的结构下沿，温度门槛额外减少有限。快速启动与长趋势通道保留；弱反弹仍会出现，3级与4级切换较多，成交量的经济增量尚未证明。不能用少交易或10日内少失效宣称改进盈利。</div>
<section class="card"><h2>图表与逐日解释</h2><div class="controls"><label>样本窗口 <select id="view">@@OPTIONS@@</select></label><label><input id="hidefuture" type="checkbox"> 隐藏检查日之后行情</label><a id="figure" target="_blank">打开完整静态图</a><a id="download">逐日CSV</a></div><p id="windowInfo" class="muted"></p><div class="plotwrap"><svg id="plot" viewBox="0 0 1120 760"></svg></div><div class="legend"><span>蓝点／蓝带 原算法</span><span>绿三角／绿带 原型参与</span><span>暖色 温度≥4</span><span>灰带 原型结构即参与</span></div><label>检查日 <b id="date"></b><input id="cursor" aria-label="检查日" type="range" min="0" value="0"></label><div id="details"></div><p class="muted">连续绿带表示4级触发后的结构延续，不等于每日都在高温，也不是每天重复开仓。窗口左端已经参与时为期初承接；新点只画真实发生在窗口内的事件。</p></section>
<section class="card"><h2>七个等级的独立依据</h2><div class="scroll"><table><thead><tr><th>等级</th><th>量价依据</th></tr></thead><tbody>@@LEVELS@@</tbody></table></div><p><b>共同尺度：</b>量比＝当日量／前21观察中位数；Z＝h观察对数净涨／前63单日收益RMS／√h；带方向ER＝对数净涨／单日对数变动绝对值之和。零路径ER为0。收盘位置＝(收盘−最低)/(最高−最低)。这些值不解释为上涨概率。</p><p><b>升降级：</b>每天取当时满足的最高级，可直接跳级。3级以上必须有已接受的结构；推进减弱可回3级而保留结构。放量下跌且低于20均价会留下前收盘记忆，在收复前温度封顶3，普通量收复也可解除。新高扩张可到6级，次日不再扩张即可回5级。</p><p><b>结构撤销：</b>首次接受突破时，下沿取突破前20观察最低价；新接受突破只可抬高，收盘≤下沿撤销。4级只触发一次参与，随后不因温度下降清零；结构破坏后才能开启下一轮。温度来回跨越次数另报。</p><p><b>过度偏离：</b>偏离MA20达到3倍单日背景波动单列提示，不自动降级、止盈或收紧退出。5、20、63尺度及所有阈值均在运行前固定，无参数搜索。温度是证据分级，不是肥尾保证。</p></section>
<section class="card"><h2>同段历史中的参与事件</h2><p>统一统计2024-01-01至2026-10-16；不含期初承接。结构对照用相同原型结构直接参与，去量对照取消量门和量价冲突记忆。价格与结构变化贡献不能都归因于温度。</p><div class="scroll"><table><thead><tr><th>样本</th><th>原算法</th><th>新结构即参与</th><th>4级触发</th><th>去量触发</th><th>温度跨过4级次数</th><th>原参与观察日</th><th>新参与观察日</th></tr></thead><tbody>@@ROWS@@</tbody></table></div><p class="muted">各样本并非独立，半导体ETF与行业指数尤为相关；次数不是成交笔数。新下沿较宽，有时参与日反而更多，必须同时看持有范围和延迟。</p></section>
<section class="card"><h2>具体取舍</h2><p><b>快速启动：</b>半导体ETF与行业指数在2024-09-27达到4级，无需回抽；但比原算法9月24日晚3个交易观察。期间ETF价格已上涨12.29%，行业指数上涨12.05%，这是确认延迟的代价，不是成交收益。2024-09-30快速通道已通过。京东9月24日虽有强脉冲，未收复的量价冲突仍将其封顶3，9月26日才解除；快速通道并非无条件覆盖其他否决。</p><p><b>持续推进：</b>黄金2024—2025、腾讯2025年的参与带可以跨越整理，温度可回落到3级。3级是结构存续，不能宣传为始终强势。</p><p><b>尚未解决：</b>古越龙山2024-08-05仍发生后来失败的提前尝试；重庆燃气仍有多次反弹参与，其2024-03-12触发时收盘到结构下沿距离16.06%，只是信号保护距离，不是保证止损幅度。高温不能事先保证肥尾，模型未消除初期不可辨识性。</p><p><b>归因：</b>八主样本原算法109次新事件→新结构37次→4级触发31次，温度直接跨入4级却有153次。多数减少来自20观察结构下沿和一结构一次触发，温度门槛贡献较小，不能称温度本身已经稳定。6级更像短时扩张事件，部分样本未出现；其独立等级价值仍待判断。未运行账户，不能推断收益、普通损耗或回撤改善。</p></section>
<section class="card"><h2>板块与个股的联动检查</h2><p>仅三只已有匹配同源行业的A股。原算法两级状态相交；原型需板块和个股同日≥4才触发，之后任一结构破坏才结束。当前行业分类固定；港股本次缺已核板块，单股图不冒充两级选股结论。</p><div class="scroll"><table><thead><tr><th>股票</th><th>行业</th><th>原联合事件</th><th>新联合事件</th><th>原联合观察日</th><th>新联合观察日</th></tr></thead><tbody>@@PAIRS@@</tbody></table></div></section>
<section class="card"><h2>全部固定窗口与失败保留</h2><p>18个旧固定窗全保留，窗口重叠，不能相加称独立样本。10观察内失效只描述结构触及下沿，不是亏损，且不同保护宽度会直接影响该数。</p><div class="scroll"><table><thead><tr><th>窗口</th><th>代码</th><th>原新事件</th><th>新事件</th><th>原期初承接</th><th>新期初承接</th><th>原10观察内失效</th><th>新10观察内失效</th></tr></thead><tbody>@@WINDOWS@@</tbody></table></div><details><summary>复核与文件</summary><p>72组真实前缀重算一致，14条旧序列的原算法逐观察一致；温度按连续源段独立预热，缺失不填冷。同价异量、普通量后续守位、冲突后普通量收复、破坏与快速跳级等6组合成检查通过。</p><p>有限单位检查中，温度、结构、参与均一致；古越龙山有2天的量价冲突标记受收盘恰等MA20的浮点边界影响，不宣称全字段单位不变或生产准入。首轮对照时钟适配错误已保留，修复未更改温度公式。</p><p><a href="protocol.json">冻结规则</a> · <a href="raw-review.json">先看原始量价的记录</a> · <a href="results/v0/verification.json">前缀、反事实及单位检查</a> · <a href="results/v0/numerical-limit.json">数值边界</a> · <a href="results/v0/series-summary.csv">全18序列汇总</a> · <a href="results/v0/window-summary.csv">固定窗汇总</a></p><p>黄金使用518880 ETF作本地代理，不能冒充截图未知合约。旧输入截至2026-10-16，行业截至2026-10-22；同段比较统一截至16日。公司行为口径复用已核资料，行业为技术观察，无执行认证。账户回测0，行情下载0，旧算法修改0，运行后机制修订0。</p></details></section></main>
<script>const data=@@PAYLOAD@@,specs=@@SPECS@@,records=@@RECORDS@@,pairmap=@@PAIRMAPPING@@;const colors=['#c4ced8','#9bbfbd','#e9ce8e','#cda1a0','#eea46b','#e46f50','#ad3b46'],names=['冷','回暖','突破待验','量价立态','有效推进','多尺度强趋势','放量扩张'];const svg=document.getElementById('plot'),view=document.getElementById('view'),cursor=document.getElementById('cursor'),hide=document.getElementById('hidefuture');let rows=[];
const fmt=(x,n=2)=>x==null?'未知':Number(x).toFixed(n),esc=x=>String(x).replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function load(){let s=specs[view.value];rows=data[s.symbol].filter(r=>r.date>=s.start&&r.date<=s.end);cursor.max=rows.length-1;cursor.value=rows.length-1;document.getElementById('windowInfo').textContent=records[s.symbol].name+' · '+rows[0].date+' — '+rows.at(-1).date+' · '+rows.length+'个观察';document.getElementById('figure').href='charts/'+s.id+'.png';document.getElementById('download').href='results/v0/daily/'+s.symbol+'.csv';draw()}
function draw(){let ix=+cursor.value,r=rows[ix],all=hide.checked?rows.slice(0,ix+1):rows,sw=Math.max(400,Math.min(1120,svg.parentElement.clientWidth)),L=105,R=sw-15,W=R-L;svg.setAttribute('viewBox','0 0 '+sw+' 760');let x=i=>L+W*i/Math.max(1,all.length-1),lo=Math.log(Math.min(...all.map(r=>r.low)))*1,hi=Math.log(Math.max(...all.map(r=>r.high))),pad=Math.max(1e-6,(hi-lo)*.06);lo-=pad;hi+=pad;let y=p=>280-(Math.log(p)-lo)/(hi-lo)*250;let o='';let text=(xx,yy,t,size=12,col='#5b7381')=>`<text x="${xx}" y="${yy}" fill="${col}" font-size="${size}">${esc(t)}</text>`;
for(let i=0;i<5;i++){let yy=30+i*62.5;o+=`<line x1="${L}" y1="${yy}" x2="${R}" y2="${yy}" stroke="#e9eef1"/>`;o+=text(8,yy+4,Math.exp(hi-(hi-lo)*i/4).toFixed(2))}
for(let i=0;i<all.length;i++){let a=all[i],xx=x(i),w=W/Math.max(1,all.length-1)+.5;if(a.level>=4)o+=`<rect x="${xx}" y="30" width="${w}" height="250" fill="${colors[a.level]}" opacity=".13"/>`}
const line=(key,yy,color,width=1,dash='')=>{let points=all.map((a,i)=>a[key]==null?null:`${x(i)},${yy(a[key])}`).filter(Boolean);return `<polyline fill="none" stroke="${color}" stroke-width="${width}" stroke-dasharray="${dash}" points="${points.join(' ')}"/>`};
o+=line('close',y,'#294558',1.8);let inrange=a=>a!=null&&Math.log(a)>=lo&&Math.log(a)<=hi;function floorpath(key,color,dash=''){let started=false,path='';for(let i=0;i<all.length;i++){let v=all[i][key];if(!inrange(v)){started=false;continue}path+=(started?'L':'M')+x(i)+','+y(v);started=true}return `<path d="${path}" fill="none" stroke="${color}" stroke-dasharray="${dash}"/>`}o+=floorpath('baseline_floor','#bd7b7e','4 3');o+=floorpath('floor','#178675');
for(let i=0;i<all.length;i++){let a=all[i],xx=x(i),yy=y(a.close);if(a.baseline_entered)o+=`<circle cx="${xx}" cy="${yy}" r="3.5" fill="#537cb3"/>`;if(a.entered)o+=`<path d="M${xx},${yy-6}l-5,9h10z" fill="#13816d"/>`}
o+=text(7,22,'复权价格／对数');o+=text(7,320,'量比 q');let maxq=Math.max(3,...all.map(a=>a.q??0));for(let i=0;i<all.length;i++)o+=`<rect x="${x(i)}" y="${386-(all[i].q??0)/maxq*65}" width="${Math.max(1,W/all.length)}" height="${(all[i].q??0)/maxq*65}" fill="#9ab1bc"/>`;for(let q of [1.5,2])o+=`<line x1="${L}" x2="${R}" y1="${386-q/maxq*65}" y2="${386-q/maxq*65}" stroke="#9a9198" stroke-dasharray="3 4"/>`;
for(let k=0;k<7;k++){o+=text(5,490-k*14,k+' '+names[k],11);o+=`<line x1="${L}" x2="${R}" y1="${486-k*14}" y2="${486-k*14}" stroke="#eef2f4"/>`}o+=line('level',v=>486-v*14,'#7e7886',1);for(let i=0;i<all.length;i++)o+=`<circle cx="${x(i)}" cy="${486-all[i].level*14}" r="2.5" fill="${colors[all[i].level]??'#bbb'}"/>`;
const lanes=[['baseline_target','原算法','#537cb3'],['structure','原型结构','#8795a1'],['target','4级触发后延续','#168576'],['hot','当日≥4','#e58e58']];lanes.forEach(([key,name,col],j)=>{let yy=525+j*24;o+=text(3,yy+13,name,11);o+=`<rect x="${L}" y="${yy}" width="${W}" height="17" fill="#f1f5f7"/>`;for(let i=0;i<all.length;i++){let a=all[i];if(key==='hot'?a.level>=4:a[key])o+=`<rect x="${x(i)}" y="${yy}" width="${W/Math.max(1,all.length-1)+.5}" height="17" fill="${col}"/>`}});
o+=text(4,659,'推进 Z');let maxz=Math.max(3,...all.flatMap(a=>[Math.abs(a.z20??0),Math.abs(a.z63??0)]));let yz=v=>683-v/maxz*47;o+=`<line x1="${L}" x2="${R}" y1="683" y2="683" stroke="#ced8df"/>`;o+=line('z20',yz,'#3e8fa7',1.3);o+=line('z63',yz,'#aa7290',1.3);
let ticks=sw<600?3:5;for(let k=0;k<ticks;k++){let i=Math.round((all.length-1)*k/(ticks-1));o+=text(Math.min(x(i),R-65),751,all[i].date.slice(0,7),11)}let xi=x(Math.min(ix,all.length-1));o+=`<line x1="${xi}" x2="${xi}" y1="25" y2="731" stroke="#263e50" stroke-dasharray="3 4" opacity=".5"/>`;svg.innerHTML=o;
let paired='';let ss=pairmap[specs[view.value].symbol];if(ss){let b=data[ss].find(z=>z.date===r.date);paired=`<br>同日板块 ${esc(records[ss].name)}：${b?b.level+'级 '+names[b.level]:'未知'}；板块与个股均≥4：${b&&b.level>=4&&r.level>=4?'是':'否'}。`}document.getElementById('date').textContent=r.date;document.getElementById('details').innerHTML=`<b>${r.date} · ${r.level>=0?r.level+'级 '+names[r.level]:'预热未知'} · ${esc(r.phase)}</b><br>收盘 ${fmt(r.close,3)}；原保护点 ${fmt(r.baseline_floor,3)}；新结构下沿 ${fmt(r.floor,3)}。<br>量比 ${fmt(r.q)}；Z5/20/63 ${fmt(r.z5)} / ${fmt(r.z20)} / ${fmt(r.z63)}；ER20/63 ${fmt(r.er20)} / ${fmt(r.er63)}。<br>${esc(r.reason)}${r.guard?'；待收复 '+fmt(r.guard_reclaim,3):''}。${r.overextended?' 偏离提示：当前离20均价较远，不自动止盈。':''}<br><span class="muted">原参与 ${r.baseline_target?'是':'否'}；原型参与延续 ${r.target?'是':'否'}；原型当日新触发 ${r.entered?'是':'否'}；当日温度跨入4级 ${r.heat_cross?'是':'否'}。</span>${paired}`}
view.addEventListener('change',load);cursor.addEventListener('input',draw);hide.addEventListener('change',draw);window.addEventListener('resize',draw);svg.addEventListener('pointermove',e=>{if(hide.checked)return;let b=svg.getBoundingClientRect(),sw=Math.max(400,Math.min(1120,svg.parentElement.clientWidth)),xx=(e.clientX-b.left)/b.width*sw;let i=Math.max(0,Math.min(rows.length-1,Math.round((xx-105)/(sw-120)*(rows.length-1))));cursor.value=i;draw()});load();</script></html>'''
if __name__=='__main__':main()
