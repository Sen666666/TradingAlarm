"""Read frozen local inputs and draw raw evidence; no account/model imports."""
from pathlib import Path
import json,hashlib,datetime,os
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/rs-h1-mpl')
import numpy as np
import pandas as pd
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'research_rounds/a-share-selection-e0-20261024'
NEW=['920045.BJ','920138.BJ','920186.BJ']
OLD=['001309.SZ','688981.SH','300750.SZ','600519.SH','600036.SH']
EXAMPLES=NEW+OLD+['601326.SH']
FONT=FontProperties(fname='/System/Library/Fonts/Supplemental/Arial Unicode.ttf')

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
def read(p):return json.loads(Path(p).read_text())
def write(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def main():
 out=HERE/'inputs';out.mkdir(exist_ok=False)
 prepared=read(SOURCE/'prepared-v2/manifest.json');pm={x['series_id']:x for x in prepared['series']}
 manifest=read(SOURCE/'inputs-v2/input-manifest.json');records={x['series_id']:x for x in manifest['series']}
 selection=read(SOURCE/'inputs-v2/selection.json');meta=read(SOURCE/'inputs-v2/metadata.json')
 symbols=sorted(x['security_id'] for x in selection['lines'] if (x.get('company_cap_cny') or 0)>1e10)
 assert len(symbols)==1709
 rules=read(SOURCE/'inputs-v2/market-rules.json')
 calendar=pd.DatetimeIndex([pd.Timestamp(x).tz_localize(None).normalize() for x in rules['calendars']['A']])
 calendar=calendar[(calendar>='2024-01-01')&(calendar<='2026-10-22')]
 fields=['close','raw_close','raw_volume','open','high','low','observed_bar','synthetic_event_bar','source_invalid','segment_id']
 matrices={k:np.full((len(calendar),len(symbols)),np.nan) for k in ['close','raw_close','volume','segment','old_rs','e0_ready','e0_up','obs_count']}
 facts={};sources=[]
 for j,sid in enumerate(symbols):
  item=pm[sid];assert item['blocked_reason'] is None
  for key in ['signal','states']:
   ref=item['files'][key];p=SOURCE/'prepared-v2'/ref['path'];assert sha(p)==ref['sha256'],str(p)
   sources.append({'symbol':sid,'kind':key,'path':str(p),'sha256':ref['sha256']})
  f=pd.read_parquet(SOURCE/'prepared-v2'/item['files']['signal']['path'],columns=fields)
  st=pd.read_parquet(SOURCE/'prepared-v2'/item['files']['states']['path'],columns=['ready','target','rs'])
  o=f[['open','high','low','close']]
  valid=(np.isfinite(o).all(axis=1)&o.gt(0).all(axis=1)&f.high.ge(f.low)
    &f.high.ge(f[['open','close']].max(axis=1))&f.low.le(f[['open','close']].min(axis=1))
    &f.observed_bar.astype(bool)&~f.synthetic_event_bar.astype(bool)&~f.source_invalid.astype(bool)
    &f.raw_volume.gt(0)&np.isfinite(f.raw_volume))
  real=f.loc[valid];aligned=real.reindex(calendar)
  for key,col in [('close','close'),('raw_close','raw_close'),('volume','raw_volume'),('segment','segment_id')]:matrices[key][:,j]=aligned[col]
  # Cumulative counts are observation facts, not filled prices.
  counts=pd.Series(np.arange(1,len(real)+1),index=real.index)
  matrices['obs_count'][:,j]=counts.reindex(counts.index.union(calendar)).sort_index().ffill().reindex(calendar).fillna(0)
  ss=st.reindex(calendar)
  for key,col in [('old_rs','rs'),('e0_ready','ready'),('e0_up','target')]:matrices[key][:,j]=pd.to_numeric(ss[col],errors='coerce')
  facts[sid]={'name':meta[sid]['name'],'industry':meta[sid]['industry'],'first_valid_close':str(real.index[0].date()),
   'declared_source_start':records[sid]['source_start'],'last_valid_close':str(real.index[-1].date()),
   'source_origin_is_not_necessarily_IPO':sid not in NEW,'full_observations':len(real)}
  if j%400==0:print({'loaded':j,'total':len(symbols)},flush=True)
 np.savez_compressed(out/'matrix.npz',dates=calendar.values,symbols=np.array(symbols),**matrices)
 write(out/'facts.json',facts)
 write(out/'source-manifest.json',{'recorded_at':now(),'sources':sources,'calendar_source':str(SOURCE/'inputs-v2/market-rules.json'),
  'calendar_source_sha256':sha(SOURCE/'inputs-v2/market-rules.json'),'prepared_manifest_sha256':sha(SOURCE/'prepared-v2/manifest.json'),
  'selection_sha256':sha(SOURCE/'inputs-v2/selection.json'),'preparer_sha256':sha(__file__),
  'protocol_sha256':sha(HERE/'PROTOCOL.md'),'matrix_sha256':sha(out/'matrix.npz'),'accounts_run':0,'network_requests':0})
 figures=HERE/'raw-review';figures.mkdir(exist_ok=False)
 for ids,label in [(NEW,'new'),(OLD,'old')]:
  fig,axes=plt.subplots(len(ids),2,figsize=(13,3.2*len(ids)),squeeze=False)
  for r,sid in enumerate(ids):
   j=symbols.index(sid);start='2025-08-01' if sid in OLD else facts[sid]['first_valid_close']
   use=(calendar>=start)&np.isfinite(matrices['raw_close'][:,j])
   ds=calendar[use];prices=matrices['raw_close'][use,j];vol=matrices['volume'][use,j]
   axes[r,0].plot(ds,prices,lw=1.2,color='#315d97');axes[r,0].set_title(sid+' '+facts[sid]['name']+' 原始收盘',fontproperties=FONT)
   axes[r,1].bar(ds,vol/1e6,width=1,color='#a8b8ca');axes[r,1].set_title('原始成交量（百万股）',fontproperties=FONT)
   for ax in axes[r]:ax.grid(alpha=.2);ax.tick_params(axis='x',labelrotation=20)
  fig.tight_layout();fig.savefig(figures/(label+'.png'),dpi=120);plt.close(fig)
 print({'done':True,'symbols':len(symbols),'dates':len(calendar)},flush=True)

if __name__=='__main__':main()
