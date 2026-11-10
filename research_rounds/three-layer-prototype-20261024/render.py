"""Post-result presentation only; never changes model inputs or signals."""
from pathlib import Path
import json,html,hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from run_study import clean,dump
HERE=Path(__file__).resolve().parent;OUT=HERE/'results/v0'
FONT=FontProperties(fname='/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
plt.rcParams['axes.unicode_minus']=False
COLORS=['#dae1e8','#f8e7b8','#edc473','#df8d52','#bf4d43']
NAMES={'original':'原结构算法','temperature':'旧七级·4级准入','new':'新三层原型','price':'新原型去量','no_background':'移除下降背景门槛','no_danger':'移除放量危险退出'}
def annotate_axis(ax):
    for t in ax.get_yticklabels()+ax.get_xticklabels():t.set_fontproperties(FONT)
    ax.grid(alpha=.15)
def chart(d,title,path):
    fig,ax=plt.subplots(7,1,figsize=(15,10),sharex=True,gridspec_kw={'height_ratios':[4.5,.55,.55,.65,1.2,1.2,1.3]})
    x=np.arange(len(d));c=d.close.to_numpy()
    ax[0].vlines(x,d.low,d.high,color='#c2cbd2',lw=.6)
    ax[0].plot(x,c,color='#233d53',lw=1.1,label='收盘（冻结信号口径）')
    ax[0].plot(x,d.ma20,color='#cf9a45',lw=.7,label='MA20');ax[0].plot(x,d.ma63,color='#8592a5',lw=.7,label='MA63')
    ax[0].plot(x,d.new_floor,color='#9ba869',lw=.8,ls='--',label='新原型结构下沿')
    for col,color,mark,label in [('new_entered','#168578','^','新开仓信号'),('new_exited','#c04545','v','新卖出信号')]:
        k=np.flatnonzero(d[col].to_numpy());ax[0].scatter(k,c[k],marker=mark,s=36,c=color,label=label,zorder=5)
    ax[0].set_title(title+' | 收盘信号，下一可成交时点执行；无账户回测',fontproperties=FONT,fontsize=13,loc='left')
    ax[0].legend(prop=FONT,fontsize=8,ncol=4,loc='upper left')
    for a,m,color in zip(ax[1:4],['original','temperature','new'],['#8897a6','#637fc4','#209689']):
        if m=='new':
            cc=[COLORS[int(s)] if t else '#f1f3f5' for s,t in zip(d.display_stage,d.new_target)]
            a.bar(x,np.ones(len(d)),color=cc,width=1,edgecolor='none')
            a.plot(x,d.new_target,color='#209689',lw=.5)
        else:a.fill_between(x,0,d[m+'_target'],step='mid',color=color,alpha=.7)
        a.set_ylim(0,1.05);a.set_yticks([]);a.set_ylabel(NAMES[m],fontproperties=FONT,rotation=0,ha='right',va='center',fontsize=9)
    ax[4].bar(x,d.q,color=np.where(d.exit_kind.eq('放量急跌'),'#c04545','#b3c1cd'),width=.85)
    ax[4].axhline(1.5,color='#c6ad81',ls=':',lw=.8);ax[4].axhline(2,color='#bf6464',ls=':',lw=.8);ax[4].set_ylabel('相对量 q',fontproperties=FONT)
    ax[5].plot(x,d.g,color='#c16e43',lw=1,label='当前推进/起点σ');ax[5].plot(x,d.peak_g,color='#ad9e8e',lw=.7,ls='--',label='最高推进记忆')
    for cut in [np.sqrt(20),np.sqrt(63),2*np.sqrt(63)]:ax[5].axhline(cut,color='#c7b6a1',lw=.6,ls=':')
    ax[5].set_ylabel('热段推进 g',fontproperties=FONT);ax[5].legend(prop=FONT,fontsize=8,loc='upper left',ncol=2)
    ax[6].plot(x,d.net63*100,color='#777ba8',lw=.9,label='63观察净变化%')
    ax[6].fill_between(x,0,1,where=d.background.eq('下降'),transform=ax[6].get_xaxis_transform(),color='#a5b6c5',alpha=.25,step='mid')
    ax[6].scatter(x[d.blocked.eq(1)],np.zeros(int(d.blocked.sum())),marker='x',color='#bb6c40',s=22,label='接受但未准入')
    ax[6].axhline(0,lw=.5,color='grey');ax[6].set_ylabel('背景',fontproperties=FONT);ax[6].legend(prop=FONT,fontsize=8,loc='upper left',ncol=2)
    ticks=np.unique(np.linspace(0,max(0,len(d)-1),8,dtype=int));ax[-1].set_xticks(ticks);ax[-1].set_xticklabels([str(d.index[k].date()) for k in ticks],rotation=0,fontsize=8)
    for a in ax:annotate_axis(a)
    fig.text(.13,.006,'热段颜色：灰=温/转弱整理；浅黄=立夏；黄=夏至；橙=小暑；红=大暑。热度不是盈利概率，升降温不自动买卖。',fontproperties=FONT,fontsize=9)
    fig.tight_layout(rect=(0,.018,1,1));fig.savefig(path,dpi=115);plt.close(fig)
def main():
    charts=HERE/'charts';charts.mkdir(exist_ok=False)
    fr=json.loads((HERE/'input-freeze.json').read_text());cases=json.loads((HERE/'cases.json').read_text())
    frames={r['symbol']:pd.read_parquet(OUT/'daily'/(r['symbol']+'.parquet')) for r in fr['series']}
    names={r['symbol']:r['name'] for r in fr['series']};menu=[]
    for sid,d in frames.items():
        name='full-'+sid;chart(d,names[sid]+' '+sid+' 完整历史',charts/(name+'.png'))
        menu.append(dict(id=name,symbol=sid,title=names[sid]+' · 完整历史',start=str(d.index[0].date()),end=str(d.index[-1].date())))
    for c in cases:
        sid=c['symbol'];d=frames[sid].loc[c['start']:c['end']];name='case-'+c['id']
        chart(d,names[sid]+' '+c['id']+' '+c['start']+'—'+c['end'],charts/(name+'.png'))
        menu.append(dict(id=name,symbol=sid,title=names[sid]+' · '+c['id']+' · '+c['start']+' 至 '+c['end'],start=c['start'],end=c['end']))
    # All fixed windows remain visible in a five-page contact sheet; individual images retain readability.
    from PIL import Image,ImageDraw,ImageFont
    for page in range(0,len(cases),5):
        canvas=Image.new('RGB',(1500,5*650),'white')
        for j,c in enumerate(cases[page:page+5]):
            im=Image.open(charts/('case-'+c['id']+'.png'));im.thumbnail((1500,650));canvas.paste(im,((1500-im.width)//2,j*650))
        canvas.save(charts/f'contact-{page//5+1:02}.png')
    s=pd.read_csv(OUT/'series-summary.csv');p=s[s.primary]
    totals={m:{k:int(p[m+'_'+k].sum()) for k in ['starts','days','ends10','down_starts','carry','censored10']} for m in NAMES}
    diag=json.loads((OUT/'diagnostics.json').read_text());checks=json.loads((OUT/'checks.json').read_text())
    payload={}
    for sid,d in frames.items():
        z=d
        cols=['close','original_target','temperature_target','new_target','new_entered','new_exited','phase','background','display_stage','stage','max_stage','new_floor','q','daily_z','g','blocked','accepted','entry_kind','exit_kind','reason']
        payload[sid]=[dict(date=str(dt.date()),**clean(row.to_dict())) for dt,row in z[cols].iterrows()]
    dump(HERE/'viewer-data.json',dict(menu=menu,daily=payload,names=names))
    cards=''.join(f'<div class="card"><small>{NAMES[m]}</small><strong>{totals[m]["starts"]}<em>次新起点</em></strong><span>{totals[m]["days"]:,} / 6,085 参与观察 · {totals[m]["ends10"]}次在10观察内撤销</span></div>' for m in ['original','temperature','new'])
    rows=''.join('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in [r['name'],r['original_starts'],r['temperature_starts'],r['new_starts'],r['original_days'],r['temperature_days'],r['new_days'],r['new_ends10']])+'</tr>' for r in s.to_dict('records'))
    abrows=''.join(f'<tr><td>{NAMES[m]}</td><td>{totals[m]["starts"]}</td><td>{totals[m]["days"]}</td><td>{totals[m]["ends10"]}</td><td>{totals[m]["down_starts"]}</td></tr>' for m in ['new','price','no_background','no_danger'])
    template='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>三层量价原型 · 2026-10-24</title>
<style>:root{--ink:#213747;--teal:#168578;--muted:#6b7b89}*{box-sizing:border-box}body{margin:0;background:#f3f5f7;color:var(--ink);font:15px/1.7 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}main{max-width:1320px;margin:auto;padding:34px 26px 80px}h1{font-size:31px;margin:8px 0}h2{font-size:21px;margin:0 0 12px}h3{font-size:16px}p{margin:8px 0}.eyebrow{font-size:12px;letter-spacing:1.5px;color:var(--teal)}.lead{font-size:18px;max-width:1000px}.muted,small{color:var(--muted)}section{background:white;border:1px solid #e0e6eb;border-radius:12px;padding:24px;margin:20px 0}.notice{border-left:4px solid #b7693e;background:#fff7ed;padding:15px 20px;margin:22px 0}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.card{padding:20px;border:1px solid #dfe6ec;border-radius:10px;background:white}.card strong{display:block;font-size:32px}.card em{font-size:13px;font-weight:400;font-style:normal;margin-left:9px}.card span{font-size:12px;color:var(--muted)}.controls{display:flex;gap:12px;align-items:center;flex-wrap:wrap}select,input,button{font:inherit;border:1px solid #ced9e2;background:white;color:var(--ink);border-radius:7px;padding:8px 12px}select{max-width:100%}button{cursor:pointer}img{display:block;width:100%;height:auto}.chartbox{margin:14px -15px}.evidence{background:#f5f8fa;padding:16px;border-radius:8px;min-height:130px}table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;border-bottom:1px solid #e5ebef;padding:10px}th{background:#f1f5f7;font-weight:500}.tablewrap{overflow:auto}.rules{display:grid;grid-template-columns:repeat(3,1fr);gap:22px}.tag{font-size:11px;background:#e4f2ee;border-radius:4px;padding:3px 7px;color:#206f64}a{color:#177f75}details{margin-top:14px}code{font-size:13px;background:#f0f4f6}footer{color:var(--muted);font-size:12px}@media(max-width:800px){.cards,.rules{grid-template-columns:1fr}main{padding:20px 12px}section{padding:16px}h1{font-size:26px}}</style>
<main><div class="eyebrow">独立开发原型 / 19序列 / 21固定窗口 / 账户运行 0</div><h1>分开判断趋势、温度与危险</h1><p class="lead">这版过滤了部分下降背景的反弹，但仍会参与失败反弹，也把长趋势切得更碎。当前不能判为优于旧算法。</p>
<div class="notice"><b>最关键的反例：</b>沪金主连2026-08-10被新背景规则拦下，仍于08-27在995.30产生开仓信号、09-16在940.52产生卖出信号。只是推迟参与，并没有排除整轮失败反弹。上述价格是信号收盘，不是成交或策略收益。</div>
<div class="cards">@@CARDS@@</div><p class="muted">9个固定主样本，2024-01-01—2026-10-16，合计6,085个资产观察。新起点不含左端继承；10观察内撤销不是亏损交易。主样本包含黄金现货ETF和期货连续两种相关资产，不能视作独立验证。</p>
<section><h2>逐图对照与当日证据</h2><div class="controls"><label>固定窗口 <select id="view"></select></label><a id="originalImage" target="_blank">打开原图</a></div><div class="chartbox"><img id="chart" alt="三算法量价轨迹对照"></div><div class="controls"><button id="prev">前一观察</button><label>证据日期 <input id="date" type="date"></label><button id="next">后一观察</button><span id="count" class="muted"></span></div><div id="evidence" class="evidence"></div><p class="muted">新原型的绿/红三角是开仓/卖出信号。三条色带分别是原结构、旧七级4级准入、新三层的参与状态。新原型热色由浅至深为四档；灰色表示段仍在但正在整理/转弱。图表不读取截图的起止标记。</p></section>
<section><h2>三层各自回答一个问题</h2><div class="rules"><div><span class="tag">1 · 独立起点</span><h3>量价事件能否建立上行热段？</h3><p>突破前20观察收盘高点，放量1.5倍且收盘在振幅上1/3，或5观察内三次守位且上涨日相对量不弱于下跌日。</p><p>63观察净变化与MA63方向都向下时先等待；突破63观察收盘新高允许直接反转。通过当天才创建起点，不回填最低点。</p></div><div><span class="tag">2 · 推进与降温</span><h3>当前在推进，还是只在整理？</h3><p>收盘在MA20之上且20观察净变化为正是热；证据分歧是温/整理。热段用起点固定波动尺度分四档。</p><p>升档可跳跃；降档有1个起点日波动的滞回。保留最高推进记忆。温度变化本身不下单。</p></div><div><span class="tag">3 · 危险与撤销</span><h3>什么证据足以结束这一热段？</h3><p>①日跌幅达到2个过去波动尺度且量≥2倍；②收盘跌破结构下沿；③连续3观察低于MA20且20观察净变化非正。</p><p>放量危险后，先等收复危险日前收盘，或跌破危险日低点使旧恢复假说失效。随后仍检查新起点和背景。</p></div></div>
<div class="tablewrap"><table><thead><tr><th>热中推进档</th><th>当前推进 g 的升档界线</th><th>这一档提供的依据</th></tr></thead><tbody><tr><td>立夏·启动</td><td>新段成立，g&lt;4.47</td><td>起点已确认，尚未推进一个月噪声尺度</td></tr><tr><td>夏至·推进</td><td>g≥√20≈4.47</td><td>超过一个月的平方根时间噪声尺度</td></tr><tr><td>小暑·延伸</td><td>g≥√63≈7.94</td><td>超过一季的噪声尺度</td></tr><tr><td>大暑·远程推进</td><td>g≥2√63≈15.87</td><td>超过两倍一季噪声尺度</td></tr></tbody></table></div><p class="muted">g=ln(当前收盘/量价事件起点)/起点前63观察日变化RMS。四档是可解释的推进刻度，尚非四档质量优势的证据，也不是趋势动物专有公式或概率检验。降档须跌过本档下界再减1。新段在立夏即可产生开仓信号，本轮没有“必须等大暑才买”的附加策略。</p><p><b>买卖：</b>新热段建立＝开仓信号；热段存续＝参与；危险、结构破坏或持续转弱＝卖出信号。当天收盘才知道，实际应用须下一可成交时点。没有仓位、资金和成交模拟。没有按浮盈或峰值回吐比例锁盈。</p><a href="PROTOCOL.md">完整冻结协议</a> · <a href="freeze.json">运行前代码/协议哈希</a></section>
<section><h2>好处与代价同时看</h2><div class="tablewrap"><table><thead><tr><th>固定案例</th><th>观察结果</th><th>边界</th></tr></thead><tbody>
<tr><td>沪金2026年下行</td><td>4月起仅14个观察参与，旧两版为125、48</td><td>8月27日仍介入失败反弹；降低参与不是成功选时</td></tr>
<tr><td>半导体2024年9月启动</td><td>新原型与旧温度版均9月27日，原算法9月24日</td><td>确认晚3个A股观察；不是完整保留最快启动</td></tr>
<tr><td>京东2024年9月</td><td>新原型9月24日直接启动</td><td>快速窗口17观察只参与6个；10月初危险退出，截断后续延续</td></tr>
<tr><td>沪金2025年9月</td><td>9月3日自己建立起点，10月20日危险退出</td><td>没有拟合成截图9月1日—10月22日；快危险比截图提前</td></tr>
<tr><td>沪金2025至2026年1月</td><td>参与139/263观察，新起点6次</td><td>旧温度版263/263；长趋势明显被切碎</td></tr>
<tr><td>江苏银行2024至2025年6月</td><td>参与219/359观察，新起点7次</td><td>旧温度版277/359、2次；对慢趋势代价明显</td></tr>
</tbody></table></div><p>主要问题已从“只看是否涨得够热”转成两个可定位的机制：背景确认改善后仍可接近反弹后段才接受；快危险和三观察转弱会截断正常整理。此次不按这些结果继续增加门槛或修改参数。</p></section>
<section><h2>全部19序列共同统计期</h2><p class="muted">包括主样本和既定反例。下表为单资产状态，指数不是可直接交易品种；没有账户收益或胜率。</p><div class="tablewrap"><table><thead><tr><th>资产</th><th>原起点</th><th>旧温度起点</th><th>新起点</th><th>原参与观察</th><th>旧温度参与</th><th>新参与</th><th>新10观察撤销</th></tr></thead><tbody>@@ROWS@@</tbody></table></div></section>
<section><h2>机制拆解与复核</h2><div class="tablewrap"><table><thead><tr><th>预先固定版本</th><th>新起点</th><th>参与观察</th><th>10观察内撤销</th><th>下降背景内起点</th></tr></thead><tbody>@@ABROWS@@</tbody></table></div><p>去掉背景门槛，下降背景内起点从0变成33个。去掉快危险与恢复记忆，参与从2,031变成2,476个观察，10观察内撤销从23变成8。它们说明规则确实改变了行为，不能证明这些变化提高了收益。</p><p>76个真实截断前缀逐列完全一致；19个旧控制逐行量价/哈希核对通过。另保留19个真实危险日只减少当日量的反事实，以及全部历史量改为常量、去量对照的逐事件差异。</p><p>三对A股与行业：江苏银行—银行、古越龙山—饮料制造、重庆燃气—燃气，统一用两层参与状态交集作诊断。当前分类、当前存续开发样本，未纳入市值资格，不是历史全池选股。港股行业未核实，不伪造行业。</p><a href="results/v0/checks.json">因果/量反事实核验</a> · <a href="results/v0/diagnostics.json">快启动、长趋势、行业交集与危险后收复</a> · <a href="results/v0/intervals.csv">全部信号区间</a> · <a href="results/v0/window-summary.csv">21固定窗口统计</a></section>
<footer>独立候选1个，结果后机制修订0次，账户运行0，行情下载0。旧两种算法及旧结果保持原样。AU0是未经独立认证换月复权的供应商连续序列，黄金ETF不是同一品种。一般序列截止2026-10-16，行业至10-22，AU0至10-23。全部历史已用于开发，不能称样本外。没有恢复趋势动物的专有公式，没有证明少参与即可多赚钱。</footer></main>
<script>let DATA,cur=[],pos=0;const $=id=>document.getElementById(id);function fmt(x){return x==null?'—':typeof x==='number'?Number(x.toFixed(4)):x}function paint(){if(!cur.length)return;const r=cur[pos];$('date').value=r.date;$('count').textContent=`${pos+1} / ${cur.length} 个窗口观察`;$('evidence').innerHTML=`<b>${r.date}　收盘 ${fmt(r.close)}　${r.phase}</b><br>背景：${r.background} · 热中显示档 ${r.display_stage} · 段内推进档 ${r.stage} · 曾达最高档 ${r.max_stage}<br>参与：原结构 ${r.original_target} / 旧温度 ${r.temperature_target} / 新三层 ${r.new_target}　　新开仓 ${r.new_entered} / 卖出 ${r.new_exited}<br>相对量 ${fmt(r.q)} · 当日变化/σ ${fmt(r.daily_z)} · 推进g ${fmt(r.g)} · 结构下沿 ${fmt(r.new_floor)}<br>${r.reason}`;}function select(){const m=DATA.menu.find(v=>v.id===$('view').value);cur=DATA.daily[m.symbol].filter(r=>r.date>=m.start&&r.date<=m.end);pos=cur.length-1;$('chart').src='charts/'+m.id+'.png';$('originalImage').href=$('chart').src;paint();}fetch('viewer-data.json').then(r=>r.json()).then(d=>{DATA=d;$('view').innerHTML=d.menu.map(m=>`<option value="${m.id}">${m.title}</option>`).join('');$('view').value='case-AU-REBOUND';select();});$('view').onchange=select;$('prev').onclick=()=>{pos=Math.max(0,pos-1);paint()};$('next').onclick=()=>{pos=Math.min(cur.length-1,pos+1);paint()};$('date').onchange=()=>{let k=cur.findIndex(r=>r.date>=$('date').value);pos=k<0?cur.length-1:k;paint()};</script></html>'''
    (HERE/'index.html').write_text(template.replace('@@CARDS@@',cards).replace('@@ROWS@@',rows).replace('@@ABROWS@@',abrows))
    dump(OUT/'report-metrics.json',dict(primary_totals=totals,statistic_period=['2024-01-01','2026-10-16'],asset_observations=6085))
    print('rendered',len(menu),'charts and five contact sheets')
if __name__=='__main__':main()
