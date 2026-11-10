"""Publish local inspectable evidence. No market requests, signals or accounts."""
from pathlib import Path
import os,json,html,hashlib
import numpy as np,pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OUT=HERE/'results/v0'
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.tools/czsc/mpl'))
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt,matplotlib.dates as mdates
from matplotlib.font_manager import FontProperties
FONT=FontProperties(fname='/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
NAMES={'original':'原量价算法·结构持有','price_ablation':'原算法去量对照','temperature_structure':'温度原型·结构即参与','temperature_entry4':'温度原型·4级触发后持有','temperature_daily4':'当日温度≥4（状态诊断）','trail-40-2':'40日突破＋2ATR保护','volume-trail-40-2':'上项加放量入场门槛'}
COLORS={'reference':'#ae8e25','original':'#537cb3','temperature_entry4':'#078679','temperature_daily4':'#e5a267','trail-40-2':'#746ba3','volume-trail-40-2':'#ad647b'}
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def shade(ax,index,values,color,lo=0,hi=1):
    starts=np.flatnonzero(values&~np.r_[False,values[:-1]]);ends=np.flatnonzero(values&~np.r_[values[1:],False])
    for a,b in zip(starts,ends):ax.axvspan(index[a],index[b]+pd.Timedelta(days=1),ymin=lo,ymax=hi,color=color,lw=0,alpha=.8)
def main():
    result=json.loads((OUT/'complete.json').read_text());target=json.loads((HERE/'targets.json').read_text())
    d=pd.read_parquet(OUT/'evidence.parquet');spot=pd.read_csv(HERE/'data/sge-Au9999.csv',index_col='date',parse_dates=True)
    models={k:pd.read_parquet(OUT/'daily'/(k+'.parquet')) for k in NAMES}
    source=np.zeros(len(d),bool)
    for a,b in zip(target['points'][::2],target['points'][1::2]):source[(d.index>=a['date'])&(d.index<b['date'])]=True
    charts=HERE/'charts';charts.mkdir(exist_ok=True)
    for key,start,end in [('overview','2025-01-01','2026-10-23'),('sep-oct','2025-08-01','2025-11-21'),('winter','2025-11-24','2026-03-31')]:
        z=d.loc[start:end];idx=z.index
        fig,axs=plt.subplots(4,1,figsize=(16,12),sharex=True,gridspec_kw={'height_ratios':[3.5,1,1.4,2.5]})
        a=axs[0];a.plot(idx,z.close,c='#293e4e',lw=1.1,label='沪金主连 AU0 收盘');a.plot(idx,spot.close.reindex(idx),c='#b6a880',lw=.7,alpha=.8,label='Au99.99 收盘')
        a.fill_between(idx,z.low,z.high,color='#697e8c',alpha=.09)
        shade(a,idx,source[d.index.get_indexer(idx)],'#d2b96b');
        for pp in a.patches:pp.set_alpha(.12)
        for k,col in [('original','original_floor'),('temperature_entry4','temperature_floor')]:a.plot(idx,z[col],c=COLORS[k],ls='--',lw=.9,label=NAMES[k]+'保护点')
        a.plot(idx,models['trail-40-2'].floor.reindex(idx),c=COLORS['trail-40-2'],lw=.9,label='2ATR保护点')
        for point in target['points']:
            dt=pd.Timestamp(point['date'])
            if dt in idx:
                a.axvspan(pd.Timestamp(point['earliest']),pd.Timestamp(point['latest']),alpha=.08,color='#ae8e25',lw=0)
                a.scatter(dt,z.loc[dt,'close'],marker='^' if point['kind']=='start' else 'v',c='#a67e1d',s=45,zorder=5)
                a.annotate(str(point['id'])+('始' if point['kind']=='start' else '终'),(dt,z.loc[dt,'close']),xytext=(2,12 if point['kind']=='start' else -15),textcoords='offset points',fontproperties=FONT,fontsize=8)
        a.set_yscale('log');a.set_ylabel('元／克·对数',fontproperties=FONT);a.legend(prop=FONT,fontsize=8,ncol=3,loc='upper left')
        a=axs[1];a.bar(idx,z.temperature_q,width=1.3,color=np.where(z.close.diff().ge(0),'#9db2bc','#d1a3a3'));a.axhline(1.5,c='#b4837f',ls='--',lw=.7);a.axhline(2,c='#7d8fa1',ls=':',lw=.7);a.set_ylabel('相对成交量 q',fontproperties=FONT)
        a=axs[2];a.step(idx,z.temperature_level,where='post',lw=.9,color='#a67860');a.axhline(3.5,color='#9ba8b0',ls='--',lw=.6);a.set_yticks(range(7));a.set_ylim(-.3,6.5);a.set_ylabel('原型温度等级',fontproperties=FONT)
        a=axs[3];lanes=[('reference','截图蓝点之间·估计')]+[(k,NAMES[k]) for k in ['original','temperature_entry4','temperature_daily4','trail-40-2','volume-trail-40-2']]
        for j,(k,label) in enumerate(lanes):
            vals=source[d.index.get_indexer(idx)] if k=='reference' else models[k].target.reindex(idx).astype(bool).to_numpy()
            shade(a,idx,vals,COLORS[k],j/6+.018,(j+1)/6-.018)
        a.set_yticks(np.arange(6)+.5);a.set_yticklabels([r[1] for r in lanes],fontproperties=FONT,fontsize=9);a.set_ylim(0,6)
        for a in axs:
            a.grid(alpha=.13);a.spines[['top','right']].set_visible(False);a.tick_params(labelsize=8)
            if idx[-1]>pd.Timestamp(result['evaluation_last']):a.axvspan(pd.Timestamp(result['evaluation_last'])+pd.Timedelta(days=1),idx[-1],color='#d3d9de',alpha=.2,lw=0)
        axs[-1].xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d' if key!='overview' else '%Y-%m'))
        fig.suptitle('沪金主连｜截图趋势段、原算法、温度原型与有限拟合',fontproperties=FONT,fontsize=17,x=.06,ha='left')
        fig.text(.065,.016,'金色点/带为截图蓝点的日期投影；除09/01、10/22外均有±3观察误差。灰尾为截图推定截止日之后的新增行情。仅比较信号，未模拟交易。',fontproperties=FONT,fontsize=9,color='#566975')
        fig.tight_layout(rect=(0,.035,1,.96));fig.savefig(charts/(key+'.png'),dpi=130);plt.close(fig)
    payload=[]
    for dt,r in d.loc['2025':].iterrows():
        row={'date':str(dt.date()),'open':r.open,'high':r.high,'low':r.low,'close':r.close,'volume':r.volume,'sge':spot.close.get(dt),'q':r.temperature_q,'level':int(r.temperature_level),'reason':r.temperature_reason,'guard':int(r.temperature_guard)}
        for k in NAMES:
            for c in ['target','entered','exited','floor']:row[k+'_'+c]=models[k].loc[dt,c]
        payload.append(row)
    payload=json.loads(pd.DataFrame(payload).to_json(orient='records',force_ascii=False))
    ranking=pd.read_csv(OUT/'ranking.csv');matches=pd.read_csv(OUT/'event-matches.csv')
    tr=lambda cells:'<tr>'+''.join('<td>'+html.escape(str(s))+'</td>' for s in cells)+'</tr>'
    target_rows=''.join(tr([str((r['id']+1)//2), '开始' if r['kind']=='start' else '结束',r['date'],r['earliest']+' — '+r['latest'],'图上月日' if not r['uncertainty_observations'] else '曲线对齐估计']) for r in target['points'])
    metric_rows=''
    for k in ['original','temperature_entry4','temperature_daily4','trail-40-2','volume-trail-40-2']:
        r=ranking.loc[ranking.model.eq(k)].iloc[0]
        metric_rows+=tr([NAMES[k],int(r.starts),int(r.carry_in),int(r.ends),int(r.active_days),f'{int(r.within_target_band)}/10',int(r.extras),int(r.missing)])
    match_rows=''
    for p in target['points']:
        cells=[p['date']+(' 开始' if p['kind']=='start' else ' 结束')]
        for k in ['original','temperature_entry4','trail-40-2','volume-trail-40-2']:
            rr=matches.loc[matches.model.eq(k)&matches.target_id.eq(p['id'])]
            row=rr.iloc[0]
            cells.append('未匹配' if row.action!='match' else str(row.predicted_date)+f'（{int(row.offset):+}观察）')
        match_rows+=tr(cells)
    rows=''.join(tr([NAMES.get(r.model,r.model),f'{r.score:.3f}',int(r.starts),int(r.ends),int(r.within_target_band),int(r.extras),int(r.missing)]) for r in ranking.itertuples())
    page=HTML.replace('@@TARGETS@@',target_rows).replace('@@METRICS@@',metric_rows).replace('@@MATCHES@@',match_rows).replace('@@RANKING@@',rows).replace('@@PAYLOAD@@',json.dumps(payload,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')).replace('@@POINTS@@',json.dumps(target['points'],ensure_ascii=False)).replace('@@NAMES@@',json.dumps(NAMES,ensure_ascii=False))
    (HERE/'index.html').write_text(page)
    dump(HERE/'render-manifest.json',dict(figures=3,html_sha256=hashlib.sha256((HERE/'index.html').read_bytes()).hexdigest(),render_code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
    print('rendered',len(page.encode()),'bytes')

HTML='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>沪金主连｜截图信号拟合与算法对照</title><style>
*{box-sizing:border-box}body{margin:0;background:#f3f5f5;color:#233b49;font:15px/1.75 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}main{max-width:1260px;padding:30px 24px;margin:auto}h1{font-size:30px;line-height:1.35;margin:0}h2{font-size:21px;margin:0 0 12px}p{margin:10px 0}.lead{color:#526b78}.card{padding:24px;background:#fff;border:1px solid #dce4e7;border-radius:12px;margin:22px 0}.notice{border-left:4px solid #c89f49;background:#fff6e5;padding:12px 18px}.scroll{overflow:auto}table{width:100%;border-collapse:collapse;white-space:nowrap;font-size:13px}td,th{text-align:left;padding:9px 11px;border-bottom:1px solid #e8edef}th{background:#f0f4f5}a{color:#247a85}button,select,input{font:inherit}button,select{background:#fff;border:1px solid #bfcdd3;padding:6px 10px;border-radius:5px}input[type=range]{width:100%}.controls{display:flex;gap:16px;align-items:center;flex-wrap:wrap}svg{width:100%;display:block}img{max-width:100%;height:auto}details summary{cursor:pointer;font-weight:600}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.stat{background:#f0f5f6;padding:10px;border-radius:6px;font-size:13px}.stat b{display:block;font-size:19px;color:#284d5e}#detail{font-size:13px}.small{font-size:13px;color:#607581}@media(max-width:700px){main{padding:18px 12px}.card{padding:16px}h1{font-size:24px}.grid{grid-template-columns:repeat(2,1fr)}}
</style><main><h1>沪金主连：五段“趋势右侧”如何拟合</h1><p class="lead">2025年1月—2026年10月｜补数、图片日期测量、固定算法对照、36个有限拟合候选。现有算法与温度原型保留，账户回测0。</p>
<div class="notice"><b>核心发现：</b>“突破＋波动保护”更接近截图的分段形态；我们的持有投影把多段上涨合为长结构。单看当日温度≥4又会反复切换。没有一个候选复现全部开始/结束，也未识别出对方专有公式。</div>
<section class="card"><h2>数据补到了哪里</h2><div class="grid"><div class="stat">沪金主连 AU0<b>2026-10-23</b>2024年以来678个观察，2025年以来436个</div><div class="stat">Au99.99交叉核对<b>2026-10-23</b>同段436个价格观察，不提供成交量</div><div class="stat">截图推定截止日<b>2026-10-13</b>误差范围10月8日—16日；新增尾段单列</div><div class="stat">输入质量<b>0异常OHLC</b>无重复日、无空值、主连无零成交量</div></div><p>两者在2024年以来共同日期的日对数涨跌相关约0.979；截图评价段约0.980。方向高度接近，期货期限价差、换月拼接和交易时段会影响逐日值。<a href="https://www.sge.com.cn/cpfw/Au9999">Au99.99是现货实盘合约</a>；AU0是<a href="https://github.com/akfamily/akshare/blob/main/docs/data/futures/futures.md">新浪连续行情代码</a>，不是可直接成交的一张固定合约，拼接及调整规则未独立认证。</p><p>截图写“指数计价”，标价低点640.67、峰值1264.76；AU0同段收盘低点624.14、峰值1249.12。曲线很接近，但尚不能认定是同一原价序列。“+24%/+23%”没有被当成蓝点间收益。2025年以来两源日期完全相同；不据此声称已逐日核验交易所完整日历。</p><p><a href="data/sina-AU0.csv">沪金OHLCV</a> · <a href="data/sge-Au9999.csv">Au99.99价格</a> · <a href="collection.json">请求与原始响应哈希</a> · <a href="results/v0/quality.json">数据核查</a></p></section>
<section class="card"><h2>同一条沪金曲线上的逐日对照</h2><div class="controls"><label>窗口 <select id="window"><option value="full">完整2025—2026</option><option value="sep">2025年9—10月启动</option><option value="winter">2025年底—2026年初</option></select></label><label><input type="checkbox" id="floors" checked> 显示保护点</label><label><input type="checkbox" id="prefix"> 只看到游标当日</label></div><p class="small">保护点：<span style="color:#537cb3">蓝色＝原算法</span>　<span style="color:#078679">绿色＝温度原型</span>　<span style="color:#746ba3">紫色＝2ATR</span>；金色三角＝截图参照</p><svg id="plot" role="img" aria-label="沪金量价和六条参与状态对照"></svg><input id="cursor" type="range" min="0" value="0" aria-label="逐日观察游标"><div id="detail"></div><p class="small">金色三角：截图开始/结束日期的投影，非原图价格。金色区间：截图蓝点之间的估计状态。图中“参与”均为收盘信号投影，未撮合开仓/卖出；若转成交易，仍应下一可成交时点执行。灰尾为截图推定截止后数据。</p><p><a href="charts/overview.png">导出完整图</a> · <a href="charts/sep-oct.png">9—10月放大图</a> · <a href="charts/winter.png">年底至次年放大图</a> · <a href="results/v0/evidence.csv">全量逐日证据</a></p></section>
<section class="card"><h2>次数和持有范围，比“少开仓”更能解释差异</h2><div class="scroll"><table><thead><tr><th>方法</th><th>新开始</th><th>期初承接</th><th>结束</th><th>有效天数</th><th>10个点中落入日期带</th><th>多余事件</th><th>未匹配参照事件</th></tr></thead><tbody>@@METRICS@@</tbody></table></div><p class="small">统一评价2025-01-02—2026-10-13，共428观察。截图为5个开始、5个结束；非打印日期±3观察。多余事件按开始、结束分别计数。事件配对按类型及时间顺序，不保证同一个匹配开始和结束来自同一模型周期；完整周期见<a href="results/v0/episodes.csv">参与周期表</a>。</p><p><b>原算法：</b>从2024-08-13承接至2025-10-22，把截图前4段连成一个结构。2025-11-10再次参与，至2026-03-19结束。评价期400/428天处于参与状态；这张黄金图上，核心差异是较长持有，不能概括成“开仓过多”。</p><p><b>温度原型：</b>4级只管首次触发，降温不自动卖出；2024-04-12的结构延续至2026-03-23，2026-08-10再触发。单看“当日≥4级”则有14段，会在强趋势内部反复切换。</p><p><b>40日突破＋2ATR：</b>9/10个参照点落入日期带，两处打印月日均相同；但总共7段，2025年底被拆为两次，2026年8月还多参与了一次反弹。9/10不等于复现率90%，额外4个事件已处罚。</p><p><b>加放量门槛：</b>综合拟合分数略好，主要因为少一个多余周期；但9月入场推迟到9月22日（晚15观察、价格高约5.5%），年底入场推迟到2026年1月21日（晚19观察、价格高约7.7%）。少信号与捕捉快速启动之间的取舍仍在。</p></section>
<section class="card"><h2>开始和结束，各由什么触发</h2><div class="scroll"><table><thead><tr><th>方法</th><th>开始依据</th><th>结束依据</th><th>这次显示出的取舍</th></tr></thead><tbody><tr><td>原量价算法</td><td>波动归一的反向推进＋区间量确认；或高量下跌后的跨日收复</td><td>收盘触及已确认摆动低点形成的结构保护点</td><td>保留长结构，但低温/盘整也会继续持有</td></tr><tr><td>温度原型4级</td><td>突破被量价接受后，净推进与路径效率通过，或快速启动跳级</td><td>收盘触及可上移的20观察结构下沿</td><td>温度降低只提示转弱，当前规则并不退出</td></tr><tr><td>价格拟合</td><td>收盘高于此前40个收盘最大值</td><td>收盘≤只升不降的最高收盘减2倍此前14观察平均真实波幅</td><td>分段更像截图，仍有额外退出及反弹参与</td></tr><tr><td>量价拟合</td><td>价格拟合条件＋量/前21中位量≥1.5且收盘位于当日振幅上1/3</td><td>与价格拟合同一保护规则</td><td>入口减少，快速启动明显延迟</td></tr></tbody></table></div><p>这里ATR用此前14观察的真实波幅均值，当天价格或量均只在收盘时可知。保护点在参与后只上移。规则是本次有限拟合对照，不替换现有算法。截图只能支持“更像分段趋势状态”的行为假说，无法证明其确实采用突破或ATR。</p></section>
<section class="card"><h2>逐个蓝点的日期对照</h2><div class="scroll"><table><thead><tr><th>截图参照（中心）</th><th>原算法</th><th>温度4级持有</th><th>价格拟合</th><th>量价拟合</th></tr></thead><tbody>@@MATCHES@@</tbody></table></div><p class="small">括号为相对参照中心的行情观察差；尚未扣除日期误差带。“未匹配”表示未找到值得按冻结代价匹配的同类型事件，不等于当时没有持有。</p><details><summary>日期本身如何测得</summary><div class="scroll"><table><thead><tr><th>组</th><th>动作</th><th>估计中心</th><th>允许日期带</th><th>证据</th></tr></thead><tbody>@@TARGETS@@</tbody></table></div><p>截图横轴按行情观察对齐，09/01、10/22年号根据整图推定为2025。其余点依据坐标和沪金价格形态推定。线形对齐中位绝对误差3.72像素，90分位12.09像素；日期带是几何误差容许范围，不是统计置信区间。图末仅写2026/10，不能把10月23日当作原图的确切截止日。</p><a href="alignment.png"><img src="alignment.png" alt="截图曲线与AU0价格的对齐"></a><p><a href="inputs/user-chart.png">查看原始截图</a> · <a href="targets.json">点位与误差</a> · <a href="target-points.csv">点位表</a></p></details></section>
<section class="card"><h2>这次能判断什么</h2><p>可以判断：仅提高开仓温度，仍不能得到截图那样的稀疏分段。必须先明确“高温趋势段何时结束”和“持仓结构何时失效”是否为两套状态；当前持有规则会跨越不少低温区间。</p><p>不能判断：对方具体公式、四种温度的定义、连续合约拼接方式、百分比含义，以及这些信号能否改善交易收益。对截图拟合更好，不等于更容易赚到肥尾；正常趋势回吐也没有被设为优化目标。此次没有账户回测、锁盈规则、股票池变更或原算法修改。</p><details><summary>冻结协议、全部候选和验证</summary><p>事前冻结36个候选：9个EMA带、9个突破通道、12个ATR跟踪、6个量价ATR。评分=0.5×日期带外逐日状态不一致率＋0.5×事件编辑代价/300；漏参照或多余事件各罚30观察。分数不是概率或收益。按该分数，量价ATR第一；按日期贴近程度，价格ATR更好，不能只报一个“最优”。</p><div class="scroll"><table><thead><tr><th>候选/控制</th><th>拟合分数↓</th><th>开始</th><th>结束</th><th>带内点</th><th>多余</th><th>漏点</th></tr></thead><tbody>@@RANKING@@</tbody></table></div><p>72个固定参数前缀核对通过，温度完整字段另做8个前缀核对。误差带±1/±5观察和图末±3观察的敏感性检查未改变这两种主要拟合的差异。参数是在整张已看过的图上挑选的；前缀通过仅证明运行时因果一致，不构成样本外验证。</p><p>首次像素跟踪误入金色文字，导致价格轴方向错误；在信号拟合前修复，原失败保留于attempt-01-ridge-trace-failure。未在失败标签上运行拟合。36候选运行后规则修订0次，旧代码哈希不变。</p><p><a href="fit-protocol.json">事前协议</a> · <a href="results/v0/ranking.csv">全部分数</a> · <a href="results/v0/event-matches.csv">包含多余/漏点的事件明细</a> · <a href="results/v0/sensitivity.csv">日期敏感性</a> · <a href="results/v0/verification.json">前缀验证</a> · <a href="results/v0/proxy-reference.json">旧黄金ETF参考</a></p></details></section></main>
<script>const data=@@PAYLOAD@@,points=@@POINTS@@,names=@@NAMES@@;const svg=document.getElementById('plot'),cursor=document.getElementById('cursor'),win=document.getElementById('window');let rows=[];const lanes=[['reference','截图日期段','#ae8e25'],['original','原算法持有','#537cb3'],['temperature_entry4','温度4级持有','#078679'],['temperature_daily4','当日≥4','#e5a267'],['trail-40-2','突破＋2ATR','#746ba3'],['volume-trail-40-2','另加放量入场','#ad647b']];const esc=x=>String(x).replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])),f=(x,n=2)=>x==null?'—':Number(x).toFixed(n);let text=(x,y,t,s=12,c='#536c79')=>`<text x="${x}" y="${y}" font-size="${s}" fill="${c}">${esc(t)}</text>`;
function load(){let bounds=win.value==='sep'?['2025-08-01','2025-11-21']:win.value==='winter'?['2025-11-24','2026-03-31']:['2025-01-01','2026-10-23'];rows=data.filter(r=>r.date>=bounds[0]&&r.date<=bounds[1]);cursor.max=rows.length-1;cursor.value=rows.length-1;draw()}
function draw(){let ix=+cursor.value,cur=rows[ix],all=document.getElementById('prefix').checked?rows.slice(0,ix+1):rows,W=Math.max(420,Math.min(1170,svg.parentElement.clientWidth)),L=112,R=W-18,span=R-L,xx=i=>L+span*i/Math.max(1,all.length-1);svg.setAttribute('viewBox',`0 0 ${W} 755`);let lo=Math.log(Math.min(...all.map(r=>r.low)))*1,hi=Math.log(Math.max(...all.map(r=>r.high))),pad=(hi-lo)*.08;lo-=pad;hi+=pad;let yy=p=>280-(Math.log(p)-lo)/(hi-lo)*245,html='';for(let i=0;i<5;i++){let y=35+i*61.25;html+=`<line x1="${L}" x2="${R}" y1="${y}" y2="${y}" stroke="#e7eef0"/>`+text(8,y+4,Math.exp(hi-(hi-lo)*i/4).toFixed(1))}
function line(key,fn,color,dash=''){let path='',on=false;all.forEach((r,i)=>{let v=r[key];if(v==null){on=false;return}path+=(on?'L':'M')+xx(i)+','+fn(v);on=true});return `<path d="${path}" fill="none" stroke="${color}" stroke-width="1.4" stroke-dasharray="${dash}"/>`}
for(let i=0;i<all.length;i++){let r=all[i];if(r.date>'2026-10-13')html+=`<rect x="${xx(i)}" y="28" width="${span/Math.max(1,all.length-1)+.5}" height="670" fill="#a8b3bd" opacity=".12"/>`}
html+=line('sge',yy,'#bcb091')+line('close',yy,'#2b4656');if(document.getElementById('floors').checked){for(let [key,col]of[['original','#537cb3'],['temperature_entry4','#078679'],['trail-40-2','#746ba3']])html+=line(key+'_floor',yy,col,'4 3')}
points.forEach(p=>{let i=all.findIndex(r=>r.date===p.date);if(i<0)return;let x=xx(i),y=yy(all[i].close),sgn=p.kind==='start'?-1:1;html+=`<path d="M${x},${y+sgn*7}l-5,${-sgn*9}h10z" fill="#ab8524"/>`+text(x+5,y-9,p.id,10,'#9c791f')});html+=text(4,20,'价格 元/克·对数');
html+=text(4,325,'相对量 q');let qmax=Math.max(3,...all.map(r=>r.q??0));all.forEach((r,i)=>html+=`<rect x="${xx(i)}" y="${385-(r.q??0)/qmax*60}" width="${Math.max(1,span/all.length)}" height="${(r.q??0)/qmax*60}" fill="#a4b7c1"/>`);for(let q of[1.5,2])html+=`<line x1="${L}" x2="${R}" y1="${385-q/qmax*60}" y2="${385-q/qmax*60}" stroke="#bd9692" stroke-dasharray="3 4"/>`;
html+=text(4,425,'原型温度');for(let k=0;k<7;k++)html+=text(70,486-k*10,k,10);html+=line('level',v=>482-v*10,'#a4775d');lanes.forEach(([key,label,color],j)=>{let y=520+j*29;html+=text(3,y+14,label,11);html+=`<rect x="${L}" y="${y}" width="${span}" height="19" fill="#f0f4f5"/>`;all.forEach((r,i)=>{let yes=key==='reference'?points.some((p,k)=>k%2===0&&r.date>=p.date&&r.date<points[k+1].date):r[key+'_target'];if(yes)html+=`<rect x="${xx(i)}" y="${y}" width="${span/Math.max(1,all.length-1)+.5}" height="19" fill="${color}"/>`})});let ticks=W<650?3:5;for(let k=0;k<ticks;k++){let i=Math.round((all.length-1)*k/(ticks-1));html+=text(Math.min(xx(i),R-82),735,all[i].date,10)}let x=xx(Math.min(ix,all.length-1));html+=`<line x1="${x}" x2="${x}" y1="25" y2="700" stroke="#324e5f" stroke-dasharray="3 4" opacity=".65"/>`;svg.innerHTML=html;
let detail=`<b>${cur.date}</b>　沪金 ${f(cur.close)}　Au99.99 ${f(cur.sge)}　量 ${Number(cur.volume).toLocaleString()}　相对量 ${f(cur.q)}　温度 <b>${cur.level}</b>　${esc(cur.reason)}<div class="scroll"><table><thead><tr><th>方法</th><th>状态</th><th>开始／结束</th><th>保护点</th></tr></thead><tbody>`;for(let key of['original','temperature_entry4','trail-40-2','volume-trail-40-2'])detail+=`<tr><td>${esc(names[key])}</td><td>${cur[key+'_target']?'参与':'等待'}</td><td>${cur[key+'_entered']?'开始':cur[key+'_exited']?'结束':'延续'}</td><td>${f(cur[key+'_floor'])}</td></tr>`;detail+='</tbody></table></div>';document.getElementById('detail').innerHTML=detail;}
cursor.addEventListener('input',draw);win.addEventListener('change',load);document.getElementById('floors').addEventListener('change',draw);document.getElementById('prefix').addEventListener('change',draw);window.addEventListener('resize',draw);load();</script></html>'''
if __name__=='__main__':main()
