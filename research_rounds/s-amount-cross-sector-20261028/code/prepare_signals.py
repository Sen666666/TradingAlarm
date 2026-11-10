from sa_common import *
import sys
sys.path.insert(0,str(FORM/'code'))
from s_amount import calculate

def main(sector):
 assert read(O/'raw-review.json')['reviewed']
 assert read(O/'data-validation.json')['passed']
 registry=read(FORM/'registry.json')
 for name,h in registry['source_sha256'].items():assert sha(ROOT/name)==h,name
 out=O/'signals'/sector;out.mkdir(parents=True,exist_ok=False)
 coverage=[];prefixes=[];changes=[];inputs={}
 for n,sid in enumerate(pool(sector).symbol):
  fp=PREPS[sector]/'facts'/f'{sid}.parquet';sp=PREPS[sector]/'signals'/f'{sid}.parquet';op=OLD_TABLES[sector]/f'{sid}.parquet'
  facts=pd.read_parquet(fp);signal=pd.read_parquet(sp)
  assert facts.index.isin(signal.index).all(),sid
  f=signal.reindex(facts.index)
  z=calculate(f,facts.i_buy.astype(bool));old=pd.read_parquet(op).reindex(f.index)
  assert old.strict_target.notna().all(),sid
  z.to_parquet(out/f'{sid}.parquet')
  for cutoff in ['2024-12-31','2026-06-30']:
   short=calculate(f.loc[:cutoff],facts.i_buy.loc[:cutoff].astype(bool))
   # An empty pre-IPO prefix has object segment dtype; values remain exact.
   pd.testing.assert_frame_equal(short.drop(columns='segment_id'),z.loc[:cutoff].drop(columns='segment_id'),check_exact=True)
   pd.testing.assert_series_equal(short.segment_id,z.loc[:cutoff].segment_id,check_dtype=False,check_exact=True)
   prefixes.append({'symbol':sid,'cutoff':cutoff,'rows':len(short)})
  period=f.index>='2024-01-01';buy=facts.i_buy.astype(bool);a=buy&old.strict_target.astype(bool);b=buy&z.strict_target
  assert not (b&~buy).any()
  coverage.append(dict(symbol=sid,source_rows=len(signal),fact_rows=len(f),original_buy_days=int(buy[period].sum()),old_buy_days=int(a[period].sum()),new_buy_days=int(b[period].sum()),removed=int((a&~b)[period].sum()),added=int((b&~a)[period].sum()),old_up_events=int((old.event.eq(1)&period).sum()),new_up_events=int((z.event.eq(1)&period).sum())))
  ix=f.index[period&(a!=b)]
  for day in ix:
   changes.append(dict(symbol=sid,date=str(day.date()),old_buy=bool(a.loc[day]),new_buy=bool(b.loc[day]),close=float(f.loc[day,'close']),amount=float(f.loc[day,'amount']),old_floor=float(old.loc[day,'strict_floor']),new_floor=float(z.loc[day,'strict_floor']),new_event=int(z.loc[day,'event']),new_frontier=float(z.loc[day,'frontier']),new_credit=float(z.loc[day,'credit']),new_threshold=float(z.loc[day,'threshold'])))
  for p in [fp,sp,op]:inputs[str(p)]=sha(p)
  if (n+1)%50==0:print(sector,n+1,flush=True)
 pd.DataFrame(coverage).to_csv(O/f'signal-coverage-{sector}.csv',index=False)
 pd.DataFrame(changes).to_parquet(O/f'signal-differences-{sector}.parquet',index=False)
 save(O/f'signal-validation-{sector}.json',dict(passed=True,stocks=len(coverage),prefixes=len(prefixes),prefix_rows=sum(r['rows'] for r in prefixes),strict_buy_subset_original_I=True,input_sha256=inputs,output_sha256={str(p):sha(p) for p in out.glob('*.parquet')}))
 print(sector,'complete',len(coverage),flush=True)
if __name__=='__main__':main(sys.argv[1])
