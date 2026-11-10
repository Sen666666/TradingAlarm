from pathlib import Path
import json,numpy as np,pandas as pd
HERE=Path(__file__).resolve().parent
def main():
    info=json.loads((HERE/'measurement.json').read_text());p=pd.read_csv(HERE/'pixel-bands.csv');d=pd.read_csv(HERE/'measured-daily.csv');out=[]
    legend=np.array(info['legend_rgb'])
    for delta in [-.05,0,.05]:
        palette=255+(legend-255)*(info['global_alpha']+delta);changed=retained=0;hist={i:0 for i in range(1,5)}
        for r in d.loc[d.known.eq(1)&d.level.gt(0)].itertuples():
            q=p.loc[p.x.between(r.x-1,r.x+1)&p.coverage.ge(.2)]
            v=q[['r','g','b']].to_numpy();dist=np.linalg.norm(v[:,None,:]-palette[None,:,:],axis=2);classes=dist.argmin(axis=1)+1
            if len(classes) and len(set(classes))==1:
                value=int(classes[0]);retained+=1;changed+=int(value!=r.level);hist[value]+=1
        out.append(dict(alpha_delta=delta,same_day_count_retained=retained,changed_color_labels=changed,class_counts=hist))
    (HERE/'color-alpha-sensitivity.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(out)
if __name__=='__main__':main()
