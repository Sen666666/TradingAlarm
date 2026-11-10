"""Non-economic full-market feature preparation. Never imports an economic engine."""
from pathlib import Path
import ast, io, json, hashlib, datetime
import numpy as np
import pandas as pd
O = Path(__file__).resolve().parent
P = O.parent
R = P.parent
E = R / 'm3_stock_birth_during_sector_v1'
U = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
H = Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
KNOWN = 'CALENDAR_COMPUTABLE_RELEASE_UNKNOWN'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x): Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False,default=str)+'\n')
def load_formula():
    text=(P/'compute_features.py').read_text()
    node=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name=='calc')
    code=ast.get_source_segment(text,node)
    with np.load(H,allow_pickle=False) as h: cal=pd.DatetimeIndex(h['dates'])
    cal=pd.DatetimeIndex(sorted(cal.unique()))
    lastday=pd.Series(cal,index=cal.to_period('M')).groupby(level=0).max()
    ns=dict(np=np,pd=pd,lastday=lastday)
    exec(compile(code,str(P/'compute_features.py')+':calc_only','exec'),ns)
    return ns['calc'], hashlib.sha256(code.encode()).hexdigest()
def inputs():
    spec=json.loads((P/'SPECIFICATION_FREEZE.json').read_text())
    fp=P/'CH3_factors_monthly_202608.xlsx'
    assert sha(fp)==spec['factor']['sha256']
    f=pd.read_excel(fp,sheet_name='Returnseries')
    f.index=pd.to_datetime(f.pop('mnthdt').astype(str),format='%Y%m%d').dt.to_period('M')
    f=f.apply(pd.to_numeric).sort_index()
    assert f.index.equals(pd.period_range('2000-01','2026-08',freq='M'))
    ev=pd.read_csv(E/'SEALED_ALL_BIRTH_EVENTS.csv',parse_dates=['day'],low_memory=False)
    ev=ev[ev.window.astype(str).isin(['2022','2024_924']) & ev.event_type.isin(['A_SECTOR_BIRTH','B_STOCK_BIRTH_DURING_SECTOR'])].copy()
    ev['window']=ev.window.astype(str); ev['month']=ev.day.dt.to_period('M').astype(str)
    assert len(ev)==19795 and not ev.duplicated(['window','day','sid']).any()
    assert ev.groupby('window').size().to_dict()=={'2022':12917,'2024_924':6878}
    assert ev[ev.window.eq('2022')].day.between('2022-01-01','2022-12-31').all()
    assert ev[ev.window.eq('2024_924')].day.between('2024-09-01','2024-12-31').all()
    manifest={x['symbol']:x for x in json.loads((U/'STOCK_MANIFEST.json').read_text())}
    return f,ev,manifest

def prepare():
    assert not (O/'FEATURE_SEAL.json').exists(), 'Feature preparation is already sealed'
    f,ev,manifest=inputs(); calc,calc_hash=load_formula()
    hashes={str(p):sha(p) for p in [P/'SPECIFICATION_FREEZE.json',P/'compute_features.py',P/'CH3_factors_monthly_202608.xlsx',U/'STOCK_MANIFEST.json',H,E/'SEALED_ALL_BIRTH_EVENTS.csv',E/'EVENT_SEAL.json']}
    source_seal=json.loads((E/'EVENT_SEAL.json').read_text())
    for p,h in source_seal['source_hashes'].items(): assert sha(p)==h;hashes[p]=h
    for p,h in source_seal['outputs'].items(): assert sha(E/p)==h
    rows=[]; qa=[];paths={}
    for j,(sid,g) in enumerate(ev.groupby('sid',sort=True)):
        m=manifest[sid];sp=next(x for x in m['source_sha256'] if x.endswith('/signal.parquet'))
        assert sha(sp)==m['source_sha256'][sp];hashes[sp]=sha(sp);paths[sid]=sp
        p=pd.read_parquet(sp).sort_index()
        for month,mm in g.groupby('month',sort=True):
            day=mm.day.min(); r=calc(p,f,day)
            prefix=calc(p.loc[p.index<=day],f.loc[f.index<day.to_period('M')],day)
            assert r==prefix,(sid,month,'prefix')
            pp=p.copy();pp.loc[pp.index>day,'close']*=17
            ff=f.copy();ff.loc[ff.index>=day.to_period('M'),:]=999
            assert r==calc(pp,ff,day),(sid,month,'future perturbation')
            assert r['fit_first']==str(pd.Period(month)-36) and r['fit_last']==str(pd.Period(month)-1)
            assert r['formation_first']==str(pd.Period(month)-12) and r['formation_last']==str(pd.Period(month)-2)
            if r['status']==KNOWN: assert pd.Timestamp(r['max_input_date'])<day and np.isfinite([r['RM'],r['RAW_MOM11']]).all()
            rows.append(dict(sid=sid,month=month,first_signal_day=str(day.date()),**r))
            qa.append(dict(sid=sid,month=month,prefix_equal=True,future_equal=True))
        if (j+1)%200==0: print('FEATURE_STOCKS',j+1,'MONTHS',len(rows),flush=True)
    z=pd.DataFrame(rows);assert len(z)==14635 and not z.duplicated(['sid','month']).any()
    old=pd.read_csv(P/'STOCK_MONTH_FEATURES_PRELABEL.csv')
    common=z.merge(old,on=['sid','month'],suffixes=('_all','_phase1'),validate='one_to_one')
    assert len(common)==8020 and common.status_all.equals(common.status_phase1)
    for col in ['RM','RAW_MOM11','alpha','beta_market','beta_size','beta_value','residual_sd']:
        assert np.isclose(common[col+'_all'],common[col+'_phase1'],rtol=1e-12,atol=1e-14,equal_nan=True).all(),col
    z.to_csv(O/'ALL_MARKET_STOCK_MONTH_FEATURES.csv',index=False)
    pd.DataFrame(qa).to_csv(O/'FEATURE_CLOCK_QA.csv',index=False)
    ev[['event_id','window','day','sid','month','sector','event_type']].to_csv(O/'ALL_MARKET_EVENT_KEYS.csv',index=False)
    save(O/'FEATURE_SOURCE_HASHES.json',hashes);save(O/'STOCK_SOURCE_PATHS.json',paths)
    save(O/'FEATURE_QA.json',dict(market_events=len(ev),stock_months=len(z),stocks=z.sid.nunique(),same_phase1_features=len(common),additional_stock_months=len(z)-len(common),prefix_checks=len(z),future_perturbation_checks=len(z),calc_definition_sha256=calc_hash,status_counts=z.status.value_counts().to_dict(),not_PIT=True,no_economic_engine_imported=True))
    files=['ALL_MARKET_STOCK_MONTH_FEATURES.csv','FEATURE_CLOCK_QA.csv','ALL_MARKET_EVENT_KEYS.csv','FEATURE_SOURCE_HASHES.json','STOCK_SOURCE_PATHS.json','FEATURE_QA.json']
    save(O/'FEATURE_SEAL.json',dict(sealed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),files={n:sha(O/n) for n in files},source_hashes=hashes))
    print('FULL_MARKET_FEATURES_SEALED',len(z),flush=True)
if __name__=='__main__': prepare()
