from pathlib import Path
import json,hashlib,datetime,shutil
import pandas as pd,numpy as np
R=Path(__file__).resolve().parent;P=R/'../three-layer-prototype-20261024';OLD=R/'../exit-posture-20261024'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
(R/'inputs').mkdir(exist_ok=False)
cases=json.loads((R/'review/candidate-list.json').read_text())
for x in cases:x['type']=x.pop('requested_type').replace('候选','');x['selection']='calendar-year, prior raw-price review; no new-window strategy results used'
cases.append(dict(id='semi_ytd26',symbol='USHJ512480',name='半导体ETF',start='2026-01-01',end='2026-10-23',type='今年完整区间',selection='user requested current year through Oct24; Oct24 is Saturday, last observed closeOct23'))
metadata=[]
for sym in sorted({c['symbol'] for c in cases}):
 src=P/'inputs'/f'{sym}.parquet';old=pd.read_parquet(src);d=old[['open','high','low','close','volume']].copy();meta={'symbol':sym,'source':str(src),'source_sha256':sha(src),'original_last':str(d.index[-1].date())}
 if sym=='USHJ512480':
  hp=R/'tail-download/history/USHJ512480.json';h=json.loads(hp.read_text());raw=pd.DataFrame(h['bars']);raw['date']=pd.to_datetime(raw.date);raw=raw.set_index('date');common=old.index.intersection(raw.index)
  diff=max(float((old.loc[common,'raw_'+k]-raw.loc[common,k]).abs().max()) for k in ['open','high','low','close']);assert diff<1e-10
  ratio=raw.loc[common,'volume']/old.loc[common,'raw_volume'];unit=float(ratio.median());assert abs(unit-100)<1e-8
  verr=((raw.loc[common,'volume']/unit-old.loc[common,'raw_volume']).abs()/old.loc[common,'raw_volume']).max();assert verr<1e-5
  rights_path=next((R/'tail-download/rights/USHJ512480').glob('attempt-*/decoded.json'));rights=json.loads(rights_path.read_text());assert {int(x['1']) for x in rights}=={20210329,20260703};assert not any(int(x['1'])>20261016 for x in rights)
  assert old.adjustment_factor.iloc[-1]==4 and old.volume_factor.iloc[-1]==.25
  new=raw.loc[raw.index>old.index[-1],['open','high','low','close','volume']].copy();assert len(new)==5 and str(new.index[-1].date())=='2026-10-23'
  new[['open','high','low','close']]*=4.;new.volume=new.volume/unit*.25
  d=pd.concat([d,new]);d.index.name='date'
  meta.update(tail_source=str(hp),tail_source_sha256=sha(hp),rights_source=str(rights_path),rights_sha256=sha(rights_path),raw_ohlc_overlap=len(common),max_ohlc_diff=diff,volume_wire_ratio=unit,max_relative_normalized_volume_overlap_error=float(verr),added_dates=[str(t.date()) for t in new.index],adjustment_factor=4.,volume_factor=.25,tail_rights='two fund splits, no event after prior cutoff; retain old factor4',price_basis='same frozen causal adjusted price/volume; append THS raw OHLCx4 and wirevolume/100x0.25, old rows unchanged')
 else:meta['price_basis']=next(x['price_basis'] for x in json.loads((P/'input-freeze.json').read_text())['series'] if x['symbol']==sym)
 assert d.index.is_unique and d.index.is_monotonic_increasing and np.isfinite(d).all().all() and (d>0).all().all();assert (d.low<=d[['open','close']].min(axis=1)).all() and (d.high>=d[['open','close']].max(axis=1)).all()
 dst=R/'inputs'/f'{sym}.parquet';d.to_parquet(dst);meta.update(input_sha256=sha(dst),rows=len(d),first=str(d.index[0].date()),last=str(d.index[-1].date()));metadata.append(meta)
for x in ['model.py','engine.py']:
 assert sha(OLD/x)==json.loads((OLD/'freeze.json').read_text())['sha256'][x];shutil.copyfile(OLD/x,R/x)
(R/'cases.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2));(R/'inputs.json').write_text(json.dumps({'prepared_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'series':metadata,'tail_quote_requests':2,'wechat_operations':0,'universe':'512480 sector proxy per prior task; no claim of all constituent stocks','scope_assumption':'Optional clarification unanswered; retain recommended priorETF scope and distinguish directional bias from amplitude'},ensure_ascii=False,indent=2))
print('Prepared',len(metadata),'series,',len(cases),'cases; tail overlap:',next(x for x in metadata if x['symbol']=='USHJ512480'))
