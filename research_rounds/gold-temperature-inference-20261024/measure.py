from pathlib import Path
import os,json,hashlib,datetime
import numpy as np,pandas as pd
from PIL import Image
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];PRIOR=ROOT/'research_rounds/gold-chart-fit-20261024'
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.tools/czsc/mpl'))
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
FONT=FontProperties(fname='/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
NAMES=['非右侧/未标色','立夏','夏至','小暑','大暑'];COLORS=['#edf0f2','#f1e4e8','#ead8da','#e0cccd','#dcbdc1']
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False,default=str)+'\n')
def main():
    im=np.array(Image.open(PRIOR/'inputs/user-chart.png').convert('RGB')).astype(float)
    points=json.loads((PRIOR/'targets.json').read_text());a=points['alignment']['pixels_per_observation'];b=points['alignment']['x_intercept']
    legend=np.array([np.median(im[311:328,x0:x1].reshape(-1,3),axis=0) for x0,x1 in [(414,437),(585,609),(756,779),(927,949)]])
    rows=[]
    for x in range(133,923):
        z=im[352:650,max(0,x-1):x+2].reshape(-1,3);r,g,bb=z.T
        keep=(r-g>=5)&(np.abs(g-bb)<=10)&(r>200)&(bb>175)
        rgb=np.median(z[keep],axis=0) if keep.any() else np.full(3,np.nan)
        expected=any(p['x']+2<=x<=q['x']-2 for p,q in zip(points['points'][::2],points['points'][1::2]))
        rows.append(dict(x=x,coverage=float(keep.mean()),r=rgb[0],g=rgb[1],b=rgb[2],expected_rightside=expected))
    cols=pd.DataFrame(rows);good=cols.expected_rightside&cols.coverage.ge(.2)&np.isfinite(cols.r)
    pixels=cols.loc[good,['r','g','b']].to_numpy()
    # One global alpha, from image colors only, no market/signal outcome used.
    candidates=[]
    for alpha in np.arange(.6,1.001,.01):
        palette=255+(legend-255)*alpha;dist=np.linalg.norm(pixels[:,None,:]-palette[None,:,:],axis=2)
        candidates.append((float(np.median(dist.min(axis=1))),float(alpha)))
    err,alpha=min(candidates);palette=255+(legend-255)*alpha
    predicted=[]
    for row in cols.itertuples():
        dd=np.linalg.norm(palette-np.array([row.r,row.g,row.b]),axis=1);order=np.argsort(dd)
        label=int(order[0]+1) if row.coverage>=.2 and np.isfinite(dd).all() else None
        conf=bool(label is not None and dd[order[0]]<=8 and dd[order[1]]-dd[order[0]]>=1.5)
        predicted.append((label,float(dd[order[0]]) if np.isfinite(dd[order[0]]) else None,float(dd[order[1]]-dd[order[0]]) if np.isfinite(dd).all() else None,conf))
    cols[['color_level','nearest_color_distance','margin','color_confident']]=predicted
    cols.to_csv(HERE/'pixel-bands.csv',index=False)
    bars=pd.read_csv(PRIOR/'data/sina-AU0.csv',index_col='date',parse_dates=True).loc['2025-01-01':points['alignment']['inferred_last_date']]
    labels=[]
    for i,date in enumerate(bars.index):
        x=b+a*i;near=cols.loc[cols.x.between(x-1,x+1)]
        active=any(s['index']<=i<t['index'] for s,t in zip(points['points'][::2],points['points'][1::2]))
        boundary=any(abs(i-p['index'])<=max(1,p['uncertainty_observations']) for p in points['points'])
        level=None;measured=False
        if not active and not boundary:level=0;measured=True
        elif active and not boundary:
            q=near.loc[near.color_confident]
            if len(q) and q.color_level.nunique()==1:level=int(q.color_level.iloc[0]);measured=True
        labels.append(dict(date=str(date.date()),index=i,x=x,rightside=int(active),level=level,known=int(measured),boundary_ambiguous=int(boundary),pink_coverage=float(near.coverage.mean())))
    daily=pd.DataFrame(labels).set_index('date');daily.to_csv(HERE/'measured-daily.csv')
    summary=[]
    for k,(s,t) in enumerate(zip(points['points'][::2],points['points'][1::2]),1):
        z=daily.iloc[s['index']:t['index']];sequence=[]
        for r in z.itertuples():
            if r.known and r.level is not None and np.isfinite(r.level):
                value=int(r.level)
                if not sequence or sequence[-1]['level']!=value:sequence.append(dict(date=r.Index,level=value,label=NAMES[value]))
        summary.append(dict(pair=k,start=s['date'],end=t['date'],observations=len(z),known=int(z.known.sum()),max_level=int(z.level.max()) if z.level.notna().any() else None,transitions=sequence))
    info=dict(created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_image_sha256=hashlib.sha256((PRIOR/'inputs/user-chart.png').read_bytes()).hexdigest(),legend_rgb=legend.tolist(),global_alpha=alpha,median_RGB_distance=err,matched_palette=palette.tolist(),
      class_counts={str(k):int((daily.level.eq(k)&daily.known.eq(1)).sum()) for k in range(5)},unknown_observations=int(daily.known.eq(0).sum()),rightside_pairs=summary,
      limitations=['Class bins are pixel inferences. Alpha/compression/color boundaries uncertain; no source per-day temperatures.','Class0 is no marked rightside, not an observed global temperature.','Daily labels depend on existing geometric date alignment, with additional uncertainty at color boundaries.','Numbers1..4 order legend colors only; they are not new trading recommendations.'])
    dump(HERE/'measurement.json',info)
    fig,axs=plt.subplots(3,1,figsize=(15,9),sharex=True,gridspec_kw={'height_ratios':[3,1.2,1.2]})
    # Original top color strip is summarized as measured RGB; not a recolored source image.
    xs=cols.x.to_numpy();rgba=np.ones((1,len(cols),4));rgba[0,:,:3]=np.nan_to_num(cols[['r','g','b']].to_numpy()/255,nan=1)
    rgba[0,:,3]=np.where(cols.coverage.ge(.2),1,0)
    axs[0].imshow(rgba,extent=[133,923,0,1],aspect='auto');axs[0].set_ylim(0,1);axs[0].set_yticks([]);axs[0].set_title('黄金原图色带：测得颜色与四种热区细分（遮挡保持未知）',fontproperties=FONT,loc='left')
    axs[1].scatter(cols.x,cols.color_level,c=[COLORS[int(v)] if pd.notna(v) else '#fff' for v in cols.color_level],edgecolors='#8c7b7c',s=10,linewidths=.3);axs[1].set_yticks(range(1,5));axs[1].set_yticklabels(NAMES[1:],fontproperties=FONT);axs[1].set_ylim(.5,4.5)
    axs[2].plot(cols.x,cols.coverage,color='#698a95');axs[2].axhline(.2,c='#bb8d75',ls='--');axs[2].set_ylabel('可识别粉色占比',fontproperties=FONT);axs[2].set_xlabel('原图横向像素；日线日期映射另含误差',fontproperties=FONT)
    for p in points['points']:
        for ax in axs:ax.axvline(p['x'],color='#9b8a5e',lw=.5,alpha=.5)
    for ax in axs:ax.grid(alpha=.12)
    fig.tight_layout();fig.savefig(HERE/'color-measurement.png',dpi=130);plt.close(fig)
    print(json.dumps(info,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
