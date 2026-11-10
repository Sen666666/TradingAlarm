"""Source-aligned DAILY chart diagnostics. No entry signals or economic accounts."""
from pathlib import Path
from datetime import datetime, timezone
import csv, json, hashlib, collections, shutil
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
import pyarrow.parquet as pq

HERE=Path(__file__).resolve().parents[1]
ROOT=HERE.parents[1]
PRIOR=ROOT/'research_rounds/a-share-local-entry-reentry-20261026'
IX=ROOT/'research_rounds/ix-a-share-entry-20261025'

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for part in iter(lambda:f.read(1024*1024),b''):h.update(part)
    return h.hexdigest()

def save(p,x):
    with p.open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')

def main():
    raw=HERE/'raw';ema=HERE/'ema';facts=HERE/'daily-facts';source=HERE/'source';data=HERE/'data'
    for p in [raw,ema,facts,source,data]:p.mkdir(exist_ok=False)
    transcript=Path('/private/tmp/tiktok-transcript-20261026/视频配音完整文字稿.txt')
    shutil.copyfile(transcript,source/'video-transcript.txt')
    market=ROOT/'TradingAlarm/data/market.json';d=json.loads(market.read_text());snap=[]
    for s in d['stocks']:
        x=s.get('intraday',[])
        if x:snap.append(dict(symbol=s['symbol'],name=s['name'],rows=len(x),dates=sorted({r['date'] for r in x}),fields=list(x[0]),minute_ohlc=all(k in x[0] for k in ['open','high','low','close'])))
    schemas=collections.Counter();schema_examples={};parquets=list((ROOT/'TradingAlarm/research/data').rglob('*.parquet'))
    for p in parquets:
        q=pq.ParquetFile(p);key=tuple((x.name,str(x.type)) for x in q.schema_arrow)
        schemas[key]+=1;schema_examples.setdefault(key,str(p.relative_to(ROOT)))
    inventory=dict(recorded_at=datetime.now(timezone.utc).isoformat(),scope='Repository saved market snapshot and research/data parquet inventory; not a claim that no external vendor can supply minutes.',
        market_snapshot=dict(path=str(market.relative_to(ROOT)),sha256=sha(market),captured_at=d.get('capturedAt'),stocks=len(d['stocks']),intraday_series=snap),
        parquet_files=len(parquets),parquet_schemas=[dict(count=n,example=schema_examples[k],columns=[dict(name=a,type=b) for a,b in k]) for k,n in schemas.items()],
        verified_historical_1min_OHLCV_dataset=None,financial_admission=False,new_downloads=0,
        missing=['Multi-day historical 1min OHLCV and amount for fixed A-share pools/date range','Minute-to-daily/rights/calendar reconciliation','Intrabar trigger/stop order evidence','Deterministic discretionary video exits'])
    save(data/'inventory.json',inventory)
    cases=pd.read_csv(PRIOR/'raw/cases.csv');cases.to_csv(raw/'cases.csv',index=False)
    hashes={str((HERE/'PROTOCOL.md').relative_to(ROOT)):sha(HERE/'PROTOCOL.md'),str(Path(__file__).relative_to(ROOT)):sha(__file__),str((PRIOR/'raw/cases.csv').relative_to(ROOT)):sha(PRIOR/'raw/cases.csv'),str(transcript):sha(transcript)}
    for _,z in cases.iterrows():
        src=PRIOR/'raw'/(z['case']+'.png');shutil.copyfile(src,raw/src.name);hashes[str(src.relative_to(ROOT))]=sha(src)
    scope=json.loads((ROOT/'research_rounds/sector-ix-i-20261026/scope.json').read_text());cache={};summaries=[]
    for group,ids in scope['groups'].items():
        for sid in ids:
            p=IX/'signals'/(sid+'.parquet');hashes[str(p.relative_to(ROOT))]=sha(p)
            f=pd.read_parquet(p,columns=['segment_id','open','high','low','close','volume']).copy()
            for n in [9,21,50,150]:f['ema'+str(n)]=f.groupby('segment_id',sort=False).close.transform(lambda x:x.ewm(span=n,adjust=False,min_periods=n).mean())
            same=f.segment_id.eq(f.segment_id.shift());f['inside_day']=(same&f.high.le(f.high.shift())&f.low.ge(f.low.shift()))
            f['typical_EMA_alignment']=(f.ema9>f.ema21)&(f.ema21>f.ema50)&(f.ema9.diff()>0)&(f.ema21.diff()>0)&(f.ema50.diff()>0)&same
            for n in [9,21]:
                prev=f['ema'+str(n)].shift();f['touch_known_ema'+str(n)]=same&f.low.le(prev)&f.high.ge(prev)
            f['range_pct']=f.high/f.low-1
            f.to_parquet(facts/(sid+'.parquet'));cache[sid]=f
            q=f.loc['2021-01-04':'2026-10-16']
            summaries.append(dict(group=group,symbol=sid,name=scope['meta'][sid]['name'],daily_rows=len(q),typical_aligned_days=int(q.typical_EMA_alignment.sum()),inside_days=int(q.inside_day.sum()),touch_previous_ema9_days=int(q.touch_known_ema9.sum()),touch_previous_ema21_days=int(q.touch_known_ema21.sum()),not_entry_signals=True))
    pd.DataFrame(summaries).to_csv(data/'daily-description.csv',index=False)
    for _,z in cases.iterrows():
        f=cache[z.symbol];d=pd.Timestamp(z.anchor);i=f.index.get_loc(d);g=f.iloc[max(0,i-80):i+81]
        fig,(ax,v,rng)=plt.subplots(3,1,figsize=(13,8),sharex=True,gridspec_kw={'height_ratios':[4,1,1]})
        colors=np.where(g.close>=g.open,'#bd4e4b','#2b897c');ax.vlines(g.index,g.low,g.high,colors=colors,linewidth=.8);ax.vlines(g.index,g.open,g.close,colors=colors,linewidth=2.3);v.bar(g.index,g.volume/1e6,color=colors,width=1)
        for n,c in [(9,'#216ca7'),(21,'#d98729'),(50,'#7d66ad'),(150,'#777777')]:ax.plot(g.index,g['ema'+str(n)],color=c,lw=1.2,label='EMA'+str(n))
        ins=g[g.inside_day];ax.scatter(ins.index,ins.high*1.02,marker='v',s=15,color='#444',label='Inside day (not buy)')
        rng.bar(g.index,g.range_pct*100,color='#8197a4',width=1)
        for a in [ax,v,rng]:a.axvline(d,color='#345a7b',ls='--');a.axvspan(d,g.index[-1],color='#7b96ad',alpha=.06);a.grid(alpha=.15)
        ax.legend(fontsize=8,ncol=5);ax.set_title(f'{z["case"]} {z.symbol} | DAILY EMA context only; minute entry / AVWAP anchor unresolved');ax.set_ylabel('Causal OHLC price');v.set_ylabel('Volume / 1e6');rng.set_ylabel('H/L - 1 (%)')
        fig.tight_layout();fig.savefig(ema/(z['case']+'.png'),dpi=140);plt.close(fig)
    # Compact contacts preserve ordering; no new selection by model output.
    for folder in [raw,ema]:
        for k,groups in enumerate([['SEMI','COMM'],['DRUG','BANK']],1):
            sheet=Image.new('RGB',(2100,960 if folder==ema else 780),'white');height=480 if folder==ema else 390
            for row,group in enumerate(groups):
                for col,role in enumerate(['strong','middle','weak']):
                    im=Image.open(folder/(group+'_'+role+'.png'));im.thumbnail((700,height));sheet.paste(im,(700*col,height*row))
            sheet.save(folder/f'contact-{k}.png')
    save(HERE/'daily-freeze.json',dict(recorded_at=datetime.now(timezone.utc).isoformat(),economic_accounts=0,raw_windows=12,ema_windows=12,daily_series=256,entry_signals=0,source_hashes=hashes,
         indicators='EMA span 9/21/50/150, recursive alpha=2/(n+1), seed first close, min_periods=n, independent source segments',
         caveats=['Known EMA touch uses preceding close EMA, descriptive only','Inside day not an entry','No AVWAP anchor or ADR window invented','No synthetic minute OHLC from point samples','Daily trend facts do not satisfy minute setup or financial admission']))
    print(json.dumps(dict(snapshot_intraday_series=len(snap),snapshot_complete_minute_OHLC=sum(x['minute_ohlc'] for x in snap),parquet_files=len(parquets),parquet_schemas=len(schemas),raw_windows=12,ema_windows=12,daily_series=256,entry_signals=0,economic_accounts=0),ensure_ascii=False))

if __name__=='__main__':main()
