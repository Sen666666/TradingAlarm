"""Post-fit reporting only; never changes models, thresholds or selection."""
from pathlib import Path
import json,html,hashlib
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
HERE=Path(__file__).resolve().parent;OUT=HERE/'results/v0';CHART=HERE/'charts'
CHART.mkdir(exist_ok=True)
for p in ['/System/Library/Fonts/Supplemental/Arial Unicode.ttf','/System/Library/Fonts/PingFang.ttc']:
    if Path(p).exists():font_manager.fontManager.addfont(p);plt.rcParams['font.family']=font_manager.FontProperties(fname=p).get_name();break
plt.rcParams.update({'axes.unicode_minus':False,'font.size':10,'figure.facecolor':'#faf9f6','axes.facecolor':'#faf9f6','savefig.facecolor':'#faf9f6'})
rank=pd.read_csv(OUT/'ranking.csv');scores=pd.read_csv(OUT/'stage-scores.csv');ref=json.loads((OUT/'reference.json').read_text());points=ref['points']
d=pd.read_csv(HERE.parent/'gold-chart-fit-20261024/data/sina-AU0.csv',index_col='date',parse_dates=True)
rs=pd.read_csv(OUT/'reference-state.csv',index_col='date',parse_dates=True);idx=rs.index
labels=pd.read_csv(HERE.parent/'gold-temperature-inference-20261024/measured-daily.csv',index_col='date',parse_dates=True)
pack=np.load(OUT/'all-states.npz',allow_pickle=False);names=pack['models'].tolist();pos={n:i for i,n in enumerate(names)}
best='slope-20-PV-e1-x0-trail2-broken_peak';all10='breakout-63-PV-none-trail2-rolling'
models=[('读图右侧区间',None),('现有原算法','old:original'),('七级温度原型','old:temperature_entry4'),('三层独立原型','old:three_layer'),('本轮：分段最接近',best),('同公式：去掉成交量',best.replace('-PV-','-P-')),('同公式：不保留旧峰',best.replace('broken_peak','rolling')),('本轮：10点全覆盖',all10)]
colors=['#a89aa4','#64748b','#8a70b5','#497986','#b45b38','#9f8c65','#819868','#c49a32']
def spans(ax,z,color,alpha=.75):
    zz=np.r_[False,np.array(z,dtype=bool),False];starts=np.flatnonzero(np.diff(zz.astype(int))==1);ends=np.flatnonzero(np.diff(zz.astype(int))==-1)
    for a,b in zip(starts,ends):
        ax.axvspan(idx[a],idx[b] if b<len(idx) else idx[-1]+pd.Timedelta(days=1),color=color,alpha=alpha,lw=0)
def plot_window(start,end,path,title):
    fig,axes=plt.subplots(10,1,figsize=(16,12),sharex=True,gridspec_kw={'height_ratios':[4,1.1]+[.55]*8},layout='constrained')
    axes[0].plot(d.index,d.close,color='#a48319',lw=1.6,label='沪金主连 AU0，收盘价代理');axes[0].set_yscale('log');axes[0].set_ylabel('价格（对数轴）')
    state=pd.read_parquet(OUT/'daily'/f'{best}.parquet')
    for t in points:
        dt=pd.Timestamp(t['date']);kind=t['kind'];axes[0].scatter(dt,d.loc[dt,'close'],marker='^' if kind=='start' else 'v',s=55,c='#2879a5',zorder=4)
        axes[0].axvspan(pd.Timestamp(t['earliest']),pd.Timestamp(t['latest']),color='#2879a5',alpha=.06,lw=0)
    for col,marker in [('entered','^'),('exited','v')]:
        z=state.loc[state[col].eq(1)];axes[0].scatter(z.index,z.close,marker=marker,s=55,facecolors='none',edgecolors='#c34f30',lw=1.4,zorder=5)
    axes[0].set_title(title+'\n蓝色实心：读图开始/结束；红色空心：本轮分段最接近者；日期带为原估计范围',loc='left',fontweight='bold');axes[0].legend(loc='upper left',fontsize=9)
    axes[1].bar(d.index,d.volume/10000,color='#b6b1a6',width=1.8);axes[1].set_ylabel('成交量\n万单位')
    for j,(label,name) in enumerate(models):
        ax=axes[j+2];z=rs.reference_rightside.to_numpy() if name is None else pack['target'][pos[name]][(d.index>=idx[0])&(d.index<=idx[-1])]
        spans(ax,z,colors[j]);ax.set_yticks([]);ax.set_ylabel(label,rotation=0,ha='right',va='center',labelpad=9,fontsize=9)
        if name is None:
            for t in points:ax.axvspan(pd.Timestamp(t['earliest']),pd.Timestamp(t['latest']),color='#faf9f6',alpha=.65,hatch='//',lw=0)
    axes[-1].set_xlim(pd.Timestamp(start),pd.Timestamp(end));axes[-1].set_xlabel('全部为已见历史开发资料；有色条表示信号状态，不是账户实际仓位。')
    for ax in axes:ax.grid(axis='x',alpha=.13);ax.spines[['top','right']].set_visible(False)
    fig.savefig(path,dpi=145);plt.close(fig)
plot_window('2025-01-02','2026-10-13',CHART/'full-comparison.png','黄金：完整右侧分段与旧算法对照')
plot_window('2025-01-02','2025-05-15',CHART/'first-three.png','前三段：结束日期较吻合，第二段开始仍晚')
plot_window('2025-08-01','2026-02-10',CHART/'late-starts.png','后两段：9月启动的迟入与旧峰值记忆')
plot_window('2026-02-01','2026-10-13',CHART/'downtrend.png','下跌时期：减少反弹参与的来源与代价')

stagepred=pd.read_parquet(OUT/'stage-predictions.parquet');key=best+'|volume_peak';pal=['#f7f4ef','#f1e4e8','#ead8da','#e0cccd','#dcbfc1'];fig,axes=plt.subplots(3,1,figsize=(16,7),sharex=True,gridspec_kw={'height_ratios':[3,1,1]},layout='constrained')
axes[0].plot(d.index,d.close,c='#a48319');axes[0].set_yscale('log');axes[0].set_title('四夏季阶段：必须使用候选自己识别的起点，漏掉的右侧日也计错',loc='left',fontweight='bold')
for ax,z,label in [(axes[1],labels.level,'原图颜色（像素推断）'),(axes[2],stagepred[key],'本轮候选（47/68相同）')]:
    zz=z.reindex(idx)
    for i,dt in enumerate(idx):
        nxt=idx[i+1] if i+1<len(idx) else dt+pd.Timedelta(days=1)
        if ax is axes[1] and (labels.loc[dt,'known']!=1):ax.axvspan(dt,nxt,color='#b7b6b1',alpha=.25,hatch='//',lw=0)
        elif pd.notna(zz.loc[dt]) and int(zz.loc[dt])>0:ax.axvspan(dt,nxt,color=pal[int(zz.loc[dt])],lw=0)
    ax.set_yticks([]);ax.set_ylabel(label,rotation=0,ha='right',va='center',labelpad=10)
axes[-1].set_xlim(idx[0],idx[-1]);axes[-1].set_xlabel('灰斜线：原图颜色未知；白色：未标右侧，不代表全局温度为“平”。四档阈值在全图回溯校准。')
fig.savefig(CHART/'summer-stages.png',dpi=145);plt.close(fig)

matches=pd.read_csv(OUT/'event-matches.csv');mt=matches.loc[matches.model.eq(best)].copy()
mt['类型']=mt.kind.map({'start':'开始','end':'结束'});mt['原图估计中心']=mt.target_date;mt['本轮公式']=mt.predicted_date;mt['交易观察偏差']=mt.offset.astype(int);mt['日期带外误差']=mt.outside_band.astype(int)
mt[['类型','原图估计中心','本轮公式','交易观察偏差','日期带外误差']].to_csv(OUT/'best-ten-point-comparison.csv',index=False)
table=[]
for label,name in models[1:]:
    r=rank.loc[rank.model.eq(name)].iloc[0];table.append(dict(方法=label,开始次数=int(r.starts),结束次数=int(r.ends),右侧日数=int(r.active_days),蓝点在日期带内=f'{int(r.within_band)}/10',额外事件=int(r.extras),漏事件=int(r.missing),状态不一致=f'{100*r.state_mismatch:.1f}%'))
comparison=pd.DataFrame(table);comparison.to_csv(OUT/'readable-comparison.csv',index=False)
def tbl(df):return df.to_html(index=False,border=0,classes='data',escape=True)
early=pd.read_csv(OUT/'transfer-selection.csv').head(2)
stagebest=scores.loc[scores.split.eq('all_visible')].sort_values(['balanced_mae','mae']).groupby('model',sort=False).head(1).merge(rank,on='model')
stageview=stagebest[['model','feature','accuracy','score','within_band','extras']].sort_values('score')
summary=json.loads((OUT/'complete.json').read_text());audit=json.loads((OUT/'independent-audit.json').read_text())
body=f'''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>黄金量价公式辨识</title><style>
body{{font:16px/1.75 -apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;color:#273036;background:#faf9f6;margin:0}}main{{max-width:1340px;margin:40px auto;padding:0 28px}}h1{{font-size:32px;line-height:1.3}}h2{{font-size:23px;margin-top:36px}}p{{max-width:1000px}}.lead{{font-size:20px}}.note{{background:#eee9de;padding:18px 24px;border-left:4px solid #ac8743}}.cards{{display:flex;gap:18px;flex-wrap:wrap}}.card{{border:1px solid #d9d3c8;background:#fffdf8;padding:16px;min-width:180px;flex:1}}.num{{font-size:30px;color:#9b643a}}img{{width:100%;height:auto;border:1px solid #e1dbd1}}table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{text-align:left;padding:9px 12px;border-bottom:1px solid #ded8cd}}th{{background:#eee9de}}.scroll{{overflow-x:auto}}a{{color:#1d647e}}code{{background:#eee9de;padding:2px 5px;overflow-wrap:anywhere}}details{{margin:22px 0}}small{{color:#68645d}}
</style><main><h1>用量价公式直接辨识黄金分段</h1><p class="lead">已实际计算1152组有明确机制的组合。存在能覆盖全部10个蓝点日期带的候选，但它多出四段机会；分段最接近的候选没有多报，仍有三处开始偏差，四节气也未恢复。</p>
<p>2026-10-24 · 离线研究 · 原算法保留 · 账户回测0 · 微信操作0 · 新行情请求0</p>
<div class="cards"><div class="card">分段最接近者<div class="num">5开始 / 5结束</div>7/10点在原日期带内，额外段0</div><div class="card">结束日期<div class="num">5/5中心相同</div>其中4个仍是读图估计，并非原始时间戳</div><div class="card">四夏季阶段<div class="num">47 / 68</div>使用自己识别的起点，不能认领原公式</div><div class="card">覆盖全部蓝点者<div class="num">10 / 10</div>却产生9段，额外开始/结束各4</div></div>
<p class="note">本轮输入是AU0主连价格代理，原图注明指数计价，精确输入口径仍未确认。只有09/01、10/22月日印在图上，其余日期带是既有像素推断。全部为已看过的开发材料；即使一张图完全匹配，也不能据此证明数学实现唯一。</p>
<h2>与现有算法在同一窗口比较</h2><p>参考右侧共104个观察日。下面“参与”均为收盘信号状态，不是实际开仓成交，不计算收益或资金。额外事件同时计开始和结束；多两个事件通常意味着多一整段。</p><div class="scroll">{tbl(comparison)}</div><img src="charts/full-comparison.png" alt="黄金完整量价和八行状态对照">
<h2>当前分段最接近者的确切规则</h2><p><code>{best}</code></p><ol><li>将最近20个收盘价取对数，按成交量相对过去21日中位量的平方根加权，拟合时间斜率。以此前63日收益波动归一化，得到S＝斜率×√20/σ。S≥1时具备开始证据。</li><li>结束后记住已失效各段的最高收盘，新开始还要超过这个高点。该版本永久不遗忘旧峰。这是待证伪的机制假说，并非原产品已确认规则。</li><li>右侧期间以段内最高对数收盘减2倍此前14日相对真实波幅作只升不降的保护线；收盘跌破保护线，或S≤0，结束。五个目标结束均由保护线触发，当日S仍大于1。</li><li>本段从自己识别的开始日累计w×log(C/前收)，取其历史最大值并除以开始时σ，作为阶段推进G。全图回溯校准的三个分界为3.3485、9.7327、13.0227，依次映射立夏、夏至、小暑、大暑；结束后不再标夏季阶段。它只有47/68颜色相同，留一整段校准后为30/68，不能当作原版温度公式。</li></ol>
<h2>十个蓝点逐项对比</h2><div class="scroll">{tbl(mt[['类型','原图估计中心','本轮公式','交易观察偏差','日期带外误差']])}</div><p>当前分段最接近者的374个日期明确观察中，6日右侧状态不同；事件日期带外误差合计9个交易观察。各模型同用“状态误差＋有序事件匹配代价”评分，漏报和多报均计入，未以收益选公式。</p>
<h2>哪些机制有效，哪些已被这张图否定</h2><p><b>旧趋势记忆确实会改变反复重入。</b>同一20日量加权斜率，去掉旧峰限制后从5段变为10段，2026年4月以后多出20个右侧日；所以这次减少反弹参与主要依靠重启记忆，不能全部归功于温度。</p><p><b>永久旧峰限制又确实太强。</b>原图9月1日已开始，而AU0收盘802.20仍低于4月段峰值831.42；永久峰门槛必然拒绝该开始。20日斜率当天也仅0.173，至9月4日才超过1，而价格到9月9日涨至837.10，才越过831.42的旧峰，因此迟入有两个独立原因。原版若是因果模型，需要允许在某种量价整理后重置旧趋势记忆，且开始证据比此慢斜率更及时。</p><p><b>成交量在本样本有实际影响，尚无通用优势结论。</b>同参数去量后多报一段、右侧日数92→79；576对机制相同的P/PV对照里365对误差下降、179对上升、32对相同。这些配置高度相关，不能当作576次独立验证。常量成交量反事实已核对等于对应价格模型。</p><p><b>蓝点和颜色必须同时解释。</b>63日突破版本能让10个蓝点都在日期带内，却多报四段；阶段颜色较好的版本59/68相同，也仍多报段落。分段最接近者的阶段只有47/68相同。不能分别拿两种最优结果拼成一套“完全还原”。</p>
<img src="charts/summer-stages.png" alt="原图四夏季颜色和自主起点预测对比">
<h2>换时间以后有没有保持</h2><p>只用2025年9月以前挑参数，PV最优者在前三段能做到日期带内和明确右侧状态全对；固定到后段仍多报一段、一个点在日期带外。永久旧峰类全图最优的好成绩也不稳定：对代理价格施加最高±0.25%的平滑扰动，会改变部分开始和段数。因此不能把全图最优直接拿去实用。</p><div class="scroll">{tbl(early[['volume','model','training_score','score','reference_events','within_band','extras','missing']])}</div>
<details><summary>展开：各机制的阶段拟合与分段误差</summary><div class="scroll">{tbl(stageview)}</div><p>accuracy为68个颜色点相同率；score为起止状态总误差；extras为额外事件。只有既定入围公式校准了颜色，未声称其余所有配置的颜色都差。</p></details>
<details open><summary>展开：前三段放大</summary><img src="charts/first-three.png" alt="前三段放大"></details><details><summary>展开：后两段开始偏差</summary><img src="charts/late-starts.png" alt="后两段放大"></details><details><summary>展开：2026下跌段</summary><img src="charts/downtrend.png" alt="2026下跌段放大"></details>
<h2>本轮结论和下一处可证伪问题</h2><p>这轮已把“完全不知道”缩小为具体矛盾：①单独的慢方向强度不能解释急跌结束；②独立的波动破坏机制对五个结束较有解释力；③没有重启记忆会多报，永久不遗忘又错过9月；④阶段推进的锚点错了，后续颜色再调阈值也无法恢复整套行为。</p><p>下一处值得辨识的是<b>整理到什么量价条件，旧峰约束可以撤销</b>，以及<b>快启动证据如何与慢方向分开</b>。本轮不再追加参数或新模型；未运行账户、未修改现有算法，没有得到原始服务器公式。</p>
<h2>原始结果与核验</h2><p>一次冻结1152配置（576量价＋576价格消融），另42个旧对照；保存1194条完整状态。{summary['prefix_checks']}次真实前缀计算通过；独立最小二乘重建614行、最优状态重建678行及50个冻结代码/输入哈希通过。核验第一轮日期数组的安全读取失败保留，之后从冻结CSV重建日期轴，不开启pickle、不改信号/评分。</p><p><a href="PROTOCOL.md">完整协议</a> · <a href="README.md">说明与复现</a> · <a href="results/v0/ranking.csv">全部排名CSV</a> · <a href="results/v0/event-matches.csv">全部事件误差</a> · <a href="results/v0/stage-scores.csv">阶段误差</a> · <a href="results/v0/volume-pairs.csv">量消融配对</a> · <a href="results/v0/quote-sensitivity.csv">报价敏感性</a> · <a href="results/v0/independent-audit.json">独立核验</a></p></main></html>'''
with (HERE/'index.html').open('x') as fp:fp.write(body)
dump=dict(charts={str(p.relative_to(HERE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in CHART.glob('*.png')},index_sha256=hashlib.sha256((HERE/'index.html').read_bytes()).hexdigest(),report_only=True)
with (HERE/'render-manifest.json').open('x') as fp:json.dump(dump,fp,ensure_ascii=False,indent=2);fp.write('\n')
print('rendered',len(dump['charts']),'charts and report')
