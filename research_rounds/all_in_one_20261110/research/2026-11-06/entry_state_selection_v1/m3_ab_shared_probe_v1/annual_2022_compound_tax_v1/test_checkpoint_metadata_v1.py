"""Supplemental full pandas metadata fingerprint. Does not replace economic field equality
or claim legacy typed-v1 covered axis names. Pinned pickle5/pandas/Python verification only."""
from pathlib import Path
from decimal import Decimal as D
import copy,hashlib,json,pickle,platform,sys,time,resource
import pandas as pd
import numpy as np
import compound_bridge_v1 as E
P=Path(__file__).resolve().parent
def sha_object(x):return hashlib.sha256(pickle.dumps(x,protocol=5)).hexdigest()
def signature(runtime):
    frames=runtime['union']['cp_cache']
    return dict(format='SUPPLEMENTAL_PICKLE5_DATAFRAME_METADATA_V1',
      python_version=platform.python_version(),pandas_version=pd.__version__,pickle_protocol=5,
      legacy_typed_structure_sha256=E.structural_digest(runtime),
      cp_frame_fingerprints={sid:sha_object(df) for sid,df in frames.items()})
def main():
    label=sys.argv[1];assert label.startswith('qa_checkpoint_metadata_')
    out=P/label;out.mkdir(exist_ok=False);start=time.monotonic()
    df=pd.DataFrame({'price':[3.0,4.0],'count':[10,20]},
       index=pd.DatetimeIndex(['2022-06-22','2022-06-23'],tz='Asia/Shanghai',name='trade_day'))
    df.columns.name='fields';base=sha_object(df);changed={}
    variants={}
    x=df.copy();x.index.name='different_day';variants['index_name']=x
    x=df.copy();x.columns.name='different_fields';variants['column_axis_name']=x
    x=df.copy().astype({'price':'float32'});variants['dtype']=x
    x=df.copy();x.index=x.index.tz_convert('UTC');variants['timezone']=x
    x=df.copy();x.index=x.index+pd.Timedelta(days=1);variants['index_values']=x
    x=df.rename(columns={'price':'other_price'});variants['column_labels']=x
    x=df.copy();x.iloc[0,0]=np.nextafter(3.0,4.0);variants['one_ulp_value']=x
    x=df.copy();x.attrs={'test':'metadata'};variants['attrs']=x
    for name,x in variants.items():changed[name]=sha_object(x);assert changed[name]!=base,name
    series=df['price'].copy();old=sha_object(series);series.name='other';assert sha_object(series)!=old
    assert E.structural_digest(df)==E.structural_digest(variants['index_name'])
    # Explicitly disclose this legacy-v1 omission; supplemental hash catches it.
    paths=[P/'qa_attempt_02/PREFIX_CHECKPOINT.pkl',
      P/'qa_bounded_additional_01/pre/POST_EX_CHECKPOINT.pkl']
    sys.path.insert(0,'/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code')
    import sector_account
    reports=[]
    for path in paths:
        with path.open('rb') as f:runtime=pickle.load(f)
        current=signature(runtime);again=signature(pickle.loads(pickle.dumps(runtime,protocol=5)))
        assert current==again
        for sid,frame in runtime['union']['cp_cache'].items():assert sha_object(frame)==sha_object(copy.deepcopy(frame)),sid
        reports.append(dict(checkpoint=str(path),checkpoint_sha256=E.sha(path),frames=len(current['cp_frame_fingerprints']),
          roundtrip_and_deepcopy_metadata_exact=True,signature=current))
    result=dict(status='PASS_SUPPLEMENTAL_METADATA_ONLY',mutation_negatives=list(variants)+['series_name'],
      legacy_v1_did_not_cover_axis_name=True,economic_prefix_comparison_is_direct_fields_not_this_digest=True,
      sources=reports,seconds=time.monotonic()-start,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    assert result['peak_rss_bytes']<6*1024**3
    (out/'RESULT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n')
    (out/'OUTPUT_SEAL.json').write_text(json.dumps({p.name:E.sha(p) for p in out.iterdir() if p.is_file()},indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('status','mutation_negatives','seconds','peak_rss_bytes')},indent=2))
if __name__=='__main__':main()
