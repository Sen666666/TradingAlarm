"""Two bounded public gold-data requests, based on locally inspected AkShare sources."""
from pathlib import Path
import datetime as dt, json, hashlib
import requests
import pandas as pd

HERE=Path(__file__).resolve().parent
def save_json(path, x): path.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def main():
    raw=HERE/'raw'; raw.mkdir(exist_ok=True)
    out=HERE/'data'; out.mkdir(exist_ok=True)
    plan=json.loads((HERE/'source-amendment.json').read_text())
    records=[]
    for name,src in zip(['sina-AU0','sge-Au9999'],plan['sources']):
        meta={'source':name,'started_at':dt.datetime.now(dt.timezone.utc).isoformat(),'request':src}
        try:
            if src['method']=='GET':
                r=requests.get(src['url'],params=src['params'],timeout=(10,35))
            else:
                r=requests.post(src['url'],data=src['data'],headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.sge.com.cn/sjzx/mrhq','X-Requested-With':'XMLHttpRequest'},timeout=(10,35))
            (raw/(name+'.response')).write_bytes(r.content)
            meta.update(http_status=r.status_code,sha256=hashlib.sha256(r.content).hexdigest(),bytes=len(r.content))
            r.raise_for_status()
            if name=='sina-AU0':
                data=json.loads(r.text.split('=(',1)[1].rsplit(');',1)[0])
                df=pd.DataFrame(data)
                if len(df.columns)!=8: raise ValueError('unexpected Sina schema')
                df.columns=['date','open','high','low','close','volume','hold','settle']
            else:
                df=pd.DataFrame(r.json()['time'])
                df.columns=['date','open','close','low','high']
            df['date']=pd.to_datetime(df.date).dt.strftime('%Y-%m-%d')
            for c in df.columns.drop('date'):df[c]=pd.to_numeric(df[c],errors='coerce')
            meta['all_rows']=len(df);meta['all_first']=str(df.date.min());meta['all_last']=str(df.date.max())
            df=df.sort_values('date').loc[lambda x:x.date.between(plan['warmup_start'],plan['cutoff'])].copy()
            df.to_csv(out/(name+'.csv'),index=False);df.to_parquet(out/(name+'.parquet'),index=False)
            meta.update(status='parsed',rows=len(df),first=None if df.empty else str(df.date.iloc[0]),last=None if df.empty else str(df.date.iloc[-1]),duplicate_dates=int(df.date.duplicated().sum()),null_values=int(df.isna().sum().sum()),bad_ohlc=int(((df.low>df[['open','close','high']].min(axis=1)) | (df.high<df[['open','close','low']].max(axis=1))).sum()))
        except Exception as e:meta.update(status='failed',error_type=type(e).__name__,error=str(e)[:300])
        records.append(meta);save_json(HERE/'collection.json',records)
        print(json.dumps({k:v for k,v in meta.items() if k!='request'},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
