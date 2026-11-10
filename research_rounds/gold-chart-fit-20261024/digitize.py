"""Screenshot measurement only; no trading signal parameters selected here."""
from pathlib import Path
import os,hashlib,json,shutil,datetime
os.environ.setdefault('MPLCONFIGDIR',str(Path(__file__).resolve().parents[2]/'.tools/czsc/mpl'))
import numpy as np,pandas as pd
from PIL import Image
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent
SOURCE=Path('/var/folders/sj/6vknnkzj0_q6yp4myjk4mtt00000gn/T/codex-clipboard-c789a5ed-a2ce-4eab-82e1-eddf7f9092c4.png')
POINTS=[(159.36,886.83),(202.14,851.48),(219.86,822.89),(247.88,799.54),(253.27,769.19),(269.65,726.16),(434.62,712.74),(491.29,570.94),(572.62,520.53),(621.73,411.92)]
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def main():
    inp=HERE/'inputs';inp.mkdir(exist_ok=True)
    if not (inp/'user-chart.png').exists():shutil.copyfile(SOURCE,inp/'user-chart.png')
    im=np.array(Image.open(inp/'user-chart.png').convert('RGB'));r,g,b=im.astype(float).transpose(2,0,1)
    mask=(r>125)&(r<220)&(g>90)&(g<185)&(b<90)&(r-g>8)&(r-g<75)&(g-b>60)
    # Keep large connected ochre curve fragments. The blue point markers split
    # the curve; small disconnected gold glyphs are excluded geometrically.
    mask[:348]=False;mask[921:]=False;mask[:,:130]=False;mask[:,930:]=False
    seen=np.zeros(mask.shape,bool);ridge=np.zeros(mask.shape,bool);components=[]
    for y,x in zip(*np.where(mask)):
        if seen[y,x]:continue
        stack=[(y,x)];seen[y,x]=True;pixels=[]
        while stack:
            yy,xx=stack.pop();pixels.append((yy,xx))
            for ny,nx in [(yy-1,xx),(yy+1,xx),(yy,xx-1),(yy,xx+1)]:
                if 0<=ny<mask.shape[0] and 0<=nx<mask.shape[1] and mask[ny,nx] and not seen[ny,nx]:
                    seen[ny,nx]=True;stack.append((ny,nx))
        if len(pixels)>=140:
            py,px=np.array(pixels).T;ridge[py,px]=True
            components.append(dict(pixels=len(pixels),xmin=int(px.min()),xmax=int(px.max()),ymin=int(py.min()),ymax=int(py.max())))
    dump(HERE/'ridge-components.json',components)
    xs=np.arange(133,923);ys=[]
    for x in xs:
        yy=np.flatnonzero(ridge[:,x]);ys.append(float(np.median(yy)) if len(yy) else np.nan)
    curve=pd.DataFrame({'x':xs,'y':ys});curve['y']=curve.y.interpolate(limit=14,limit_direction='both')
    curve.to_csv(HERE/'digitized-curve.csv',index=False)
    bars=pd.read_csv(HERE/'data/sina-AU0.csv',index_col='date',parse_dates=True).loc['2025':]
    # Two dates are printed by the source. Compare a finite geometric alignment
    # neighborhood, using the price ridge only, never algorithm outputs.
    anchors=[(161,434.62),(192,491.29)]
    rows=[];logc=np.log(bars.close.to_numpy());di=np.arange(len(bars))
    # x=b+a*observation_index. Printed date coordinates have line/label ambiguity.
    # Residuals use robust absolute error so gold text contamination cannot dominate.
    for a in np.arange(1.78,1.961,.002):
      for shift in np.arange(126,143.01,.5):
        q=(xs-shift)/a;valid=(q>=0)&(q<=len(bars)-1)&np.isfinite(curve.y)
        pred=np.interp(q[valid],di,logc)
        xx=np.c_[np.ones(valid.sum()),pred];coef=np.linalg.lstsq(xx,curve.y.to_numpy()[valid],rcond=None)[0]
        res=np.abs(xx@coef-curve.y.to_numpy()[valid]);anchors_error=np.mean([abs(shift+a*i-x) for i,x in anchors])
        score=float(np.median(res)+anchors_error)
        rows.append((score,a,shift,float(coef[0]),float(coef[1]),float(np.median(res)),float(np.quantile(res,.9)),anchors_error))
    best=min(rows);score,a,shift,y0,scale,mae,p90,anchorerror=best
    assert -1200<scale<-500 and mae<25, 'Invalid image ridge/calibration; do not fit signals'
    pd.DataFrame(rows,columns=['score','pixels_per_observation','x_intercept','y_intercept','logprice_slope','median_abs_pixel_error','p90_abs_pixel_error','anchor_error']).sort_values('score').head(50).to_csv(HERE/'alignment-top50.csv',index=False)
    observations=[]
    for k,(x,y) in enumerate(POINTS):
        n=int(np.clip(round((x-shift)/a),0,len(bars)-1))
        # +/-3 observations for unprinted points includes finite alignment
        # uncertainty plus +/-1 px marker center, but cannot certify source identity.
        exact='2025-09-01' if k==6 else '2025-10-22' if k==7 else None
        if exact:n=bars.index.get_loc(exact)
        observations.append({'id':k+1,'kind':'start' if k%2==0 else 'end','x':x,'y':y,'date':str(bars.index[n].date()),'earliest':str(bars.index[max(0,n-(0 if exact else 3))].date()),'latest':str(bars.index[min(len(bars)-1,n+(0 if exact else 3))].date()),'date_source':'printed month/day; year inferred from chart' if exact else 'geometric inference, not a source timestamp','index':n,'uncertainty_observations':0 if exact else 3})
    end_index=int(np.clip(round((922-shift)/a),0,len(bars)-1))
    cutoff=str(bars.index[end_index].date())
    info={'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'image_sha256':hashlib.sha256((inp/'user-chart.png').read_bytes()).hexdigest(),'points':observations,'alignment':dict(pixels_per_observation=a,x_intercept=shift,y_intercept=y0,logprice_slope=scale,median_abs_pixel_error=mae,p90_abs_pixel_error=p90,printed_anchor_mean_error_pixels=anchorerror,inferred_last_date=cutoff,inferred_last_earliest=str(bars.index[max(0,end_index-3)].date()),inferred_last_latest=str(bars.index[min(len(bars)-1,end_index+3)].date())), 'limits':['Geometric/date inference is conditional on AU0 shape alignment, not proof of exact source or roll adjustment.','No source end day printed: use inferred end point and +/-3-observation sensitivity; do not label the extra downloaded tail as a screenshot signal error.','Five blue start/end pairs manually interpreted. Percentage annotations retained as source text, not target realized return.'], 'source_percent_labels':[6.1,5.1,12,24,23]}
    dump(HERE/'targets.json',info);pd.DataFrame(observations).to_csv(HERE/'target-points.csv',index=False)
    fig,ax=plt.subplots(figsize=(15,7));ax.plot(xs,curve.y,color='#b19b16',lw=1,label='digitized image ridge');q=(xs-shift)/a;ok=(q>=0)&(q<=len(bars)-1);ax.plot(xs[ok],y0+scale*np.interp(q[ok],di,logc),c='#3e718d',lw=1,label='aligned AU0 log close')
    for row in observations:ax.scatter(row['x'],row['y'],c='#2783ac');ax.annotate(row['date'],(row['x'],row['y']),xytext=(7,-15 if row['kind']=='start' else 15),textcoords='offset points',fontsize=8)
    ax.invert_yaxis();ax.legend();ax.set_xlabel('Screenshot x pixels, trading-observation clock');ax.set_ylabel('Screenshot y pixels');ax.grid(alpha=.15);fig.tight_layout();fig.savefig(HERE/'alignment.png',dpi=130);plt.close(fig)
    print(json.dumps(info,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
