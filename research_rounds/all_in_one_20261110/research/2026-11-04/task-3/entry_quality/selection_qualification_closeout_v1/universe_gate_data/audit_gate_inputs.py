"""Read current THS maps/cap and ninety existing industry series; no models."""
from pathlib import Path
from collections import Counter
import csv,json,hashlib,math
import pandas as pd
import pyarrow.parquet as pq

O=Path(__file__).resolve().parent;EQ=O.parents[1]
BASE=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024')
OLD=BASE.parent/'current-pool-20261022'
NATIVE=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
DAY='2024-09-24';bindings={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bind(p):p=Path(p);bindings[str(p)]=sha(p);return p
def js(p):return json.loads(bind(p).read_text())
def clean(v):
 if isinstance(v,dict):return {str(k):clean(x)for k,x in v.items()}
 if isinstance(v,(list,tuple)):return [clean(x)for x in v]
 if v is None or v is pd.NA:return None
 if isinstance(v,pd.Timestamp):return str(v)
 if hasattr(v,'item'):v=v.item()
 if isinstance(v,float)and not math.isfinite(v):return None
 return v
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def csvread(p):
 with bind(p).open()as f:return list(csv.DictReader(f))
canonical={r['symbol']for r in csvread(EQ/'local_universe_data_audit_v1/bars/BAR_SYMBOL_COVERAGE.csv')};assert len(canonical)==5517
old_manifest=js(NATIVE/'STOCK_MANIFEST.json');oldids={r['symbol']for r in old_manifest};assert len(oldids)==1709
resolved=csvread(OLD/'audit-snapshot/current-stock-master.industry-resolved.csv');assert len(resolved)==5576
byid={r['current_symbol']:r for r in resolved};roster=js(BASE/'inputs-v2/roster-dispositions.json');rbyid={r['symbol']:r for r in roster}
metadata=js(BASE/'inputs-v2/metadata.json');sel=js(BASE/'inputs-v2/selection.json')
prep=js(BASE/'prepared-v2/manifest.json');series={r['series_id']:r for r in prep['series']}
industries={s:r for s,r in series.items()if s.startswith('URFI')};assert len(industries)==90
native_manifest=js(NATIVE/'INDUSTRY_MANIFEST.json');nby={r['series']:r for r in native_manifest};assert len(nby)==90
assert set(industries)==set(nby)
assert set(byid)==set(rbyid)
for sid,r in rbyid.items():assert r.get('sector_id','')==byid[sid]['industry_index_symbol']

def row(p,cols=None):
 return pd.read_parquet(p,columns=cols,filters=[('date','==',pd.Timestamp(DAY))])
sector_rows=[]
for sid,rec in sorted(industries.items()):
 item=dict(sector_id=sid,status='READ_EXISTING_SERIES',day=DAY,files={},data={})
 try:
  for kind in ['signal','events','states']:
   spec=rec['files'][kind];p=BASE/'prepared-v2'/spec['path'];h=sha(p)
   assert h==spec['sha256'],('prepared SHA mismatch',sid,kind)
   bindings[str(p)]=h
   schema=pq.ParquetFile(p).schema.names
   fields={'signal':['close','source_kind','source_path','observed_bar','synthetic_event_bar','price_eligible','volume_eligible','source_invalid','segment_id'],
    'events':['event','target','structure_floor_price','confirmed_pivot_price','segment_id'],
    'states':['target','floor','ready','rs','segment_id']}[kind]
   f=row(p,[x for x in fields if x in schema]);item['files'][kind]=dict(path=str(p),schema=schema,sha256=h)
   item['data'][kind]=dict(exact_rows=len(f),row=None if len(f)!=1 else f.iloc[0].to_dict())
  native_path=next(Path(p)for p in nby[sid]['source_sha256']if'/industry-facts/'in p)
  h=sha(native_path);assert h==nby[sid]['source_sha256'][str(native_path)]
  bindings[str(native_path)]=h;f=row(native_path)
  item['files']['native_E0_sector_facts']=dict(path=str(native_path),sha256=h,schema=pq.ParquetFile(native_path).schema.names)
  item['data']['native_E0_sector_facts']=dict(exact_rows=len(f),row=None if len(f)!=1 else f.iloc[0].to_dict())
 except Exception as e:item['status']='SOURCE_READ_ERROR';item['error']=repr(e)
 sector_rows.append(item)
save('ALL90_THS_SECTOR_FIXED_DAY_SOURCE_ROWS.json',sector_rows)

joined=[]
for sid in sorted(canonical):
 rr=byid.get(sid);r=rbyid.get(sid);cap=None if r is None else r.get('cap_cny');sector=None if rr is None else rr.get('industry_index_symbol')or None
 cap_status='NOT_IN_CURRENT_ROSTER'if r is None else'CURRENT_CAP_UNKNOWN'if cap is None else'CURRENT_CAP_GT10BN'if cap>10_000_000_000 else'CURRENT_CAP_NOT_GT10BN'
 joined.append(dict(symbol=sid,in_old1709=sid in oldids,in_filtered_metadata1711=sid in metadata,
  in_current_roster5576=rr is not None,current_THS_sector=sector,current_THS_industry=None if rr is None else rr.get('industry_name'),
  industry_mapping_basis=None if rr is None else rr.get('industry_mapping_basis'),industry_source_observed_at=None if rr is None else rr.get('observed_at'),
  industry_snapshot_date=None if rr is None else rr.get('snapshot_date'),sector_existing_prepared=sector in industries if sector else False,
  current_cap_cny=cap,current_cap_status=cap_status,cap_observed_at=None if r is None else r.get('cap_observed_at'),
  old_stock_G1_I_facts_cached=sid in oldids,new_canonical_qfq_stock_G1_I='STRUCTURAL_OWNER_SEPARATE_OUTPUT_NOT_COMPUTED_HERE',
  historical_ST_halt_and_buy_allowed='NOT_CERTIFIED_EXISTING_MARKET_RULES_ARE_PROXY',historical_cap='NOT_AVAILABLE_FROM_CURRENT_SNAPSHOT'))
save('CANONICAL5517_MAP_CAP_DATA_AVAILABILITY.json',joined)
with (O/'CANONICAL5517_MAP_CAP_DATA_AVAILABILITY.csv').open('w')as f:w=csv.DictWriter(f,fieldnames=list(joined[0]));w.writeheader();w.writerows(joined)
outside=[r for r in joined if not r['in_old1709']]
sector_good=[r for r in sector_rows if r['status']=='READ_EXISTING_SERIES']
def nrow(kind):return sum(r['data'][kind]['exact_rows']==1 for r in sector_good)
native_ready=sum(bool((r['data']['native_E0_sector_facts']['row']or{}).get('e0_ready'))for r in sector_good)
native_up=sum(bool((r['data']['native_E0_sector_facts']['row']or{}).get('e0_target'))for r in sector_good)
states_rs=sum(pd.notna((r['data']['states']['row']or{}).get('rs'))for r in sector_good)
summary=dict(status='READ_ONLY_CURRENT_MAP_CAP_AND_EXISTING90SECTOR_DATA_AUDIT',day=DAY,canonical_symbols=len(canonical),
 inputs_metadata_stock_keys=len(metadata),metadata_schema_counts=dict(Counter(tuple(sorted(v))for v in metadata.values())),
 prepared_series=len(series),prepared_stock_series=len(series)-len(industries),prepared_THS_sector_series=len(industries),
 full_current_roster=len(resolved),full_current_THS_map_nonempty=sum(bool(r['industry_index_symbol'])for r in resolved),
 full_current_THS_sectors=len({r['industry_index_symbol']for r in resolved if r['industry_index_symbol']}),
 canonical_in_current_roster=sum(r['in_current_roster5576']for r in joined),canonical_with_current_THS_map=sum(bool(r['current_THS_sector'])for r in joined),
 canonical_with_prepared_THS_sector=sum(r['sector_existing_prepared']for r in joined),canonical_in_filtered_metadata1711=sum(r['in_filtered_metadata1711']for r in joined),
 canonical_cap_status=dict(Counter(r['current_cap_status']for r in joined)),
 outside_old1709=len(outside),outside_old_with_current_THS_map=sum(bool(r['current_THS_sector'])for r in outside),
 outside_old_with_prepared_THS_sector=sum(r['sector_existing_prepared']for r in outside),outside_old_cap_status=dict(Counter(r['current_cap_status']for r in outside)),
 source90_read_errors=[r for r in sector_rows if r['status']!='READ_EXISTING_SERIES'],sector_exact_day_signal=nrow('signal'),sector_exact_day_events=nrow('events'),sector_exact_day_states=nrow('states'),sector_exact_day_native_E0=nrow('native_E0_sector_facts'),
 sector_native_E0_ready=native_ready,sector_native_E0_up=native_up,sector_prepared_individual_RS_nonmissing=states_rs,
 current_selection_observed_at=sel['observed_at'],current_selection_cap_observed_date=sel['cap_observed_date'],current_selection_limit=sel['universe_limit'],
 scope_upper_bound_current_THS_map_and_existing_sector_sources=sum(r['sector_existing_prepared']for r in joined),
 strict_original_current_cap_gate_outside_old_known_pass=sum(r['current_cap_status']=='CURRENT_CAP_GT10BN'for r in outside),
 no_SW_substitution=True,new_models=0,new_eligibility_computations=0,new_accounts=0,new_network=0,
 stock_price_domain_warning='Existing1711 stock signal/state is legacy corporate-action bridge, not the newly fixed canonical5517 qfq input. Do not transplant I/G1 or individual RS to a different price domain.',
 H1_warning='Old H1 cache is universe-dependent; existing individual RS/state.rs is not itself a freshly comparable full5517 H1 percentile.',
 source_sha256=bindings)
summary['metadata_schema_counts']=[dict(fields=list(k),n=v)for k,v in summary['metadata_schema_counts'].items()]
save('AUDIT_RECEIPT.json',summary)
print(json.dumps(clean({k:v for k,v in summary.items()if k not in ['source_sha256','source90_read_errors','metadata_schema_counts']}),ensure_ascii=False))
