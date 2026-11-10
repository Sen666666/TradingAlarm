"""Source readiness only; never computes v4 Rp values, ranks or maturity."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd

O=Path(__file__).resolve().parent;ROOT=O.parent;SELECTION=ROOT.parent
B=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
M=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data/ths-index-history-20261018')
OLD=SELECTION/'industry_selection/channels_v2';HASH={}
def bind(p,expected=None):
 p=Path(p).resolve();h=hashlib.sha256(p.read_bytes()).hexdigest()
 if expected is not None:assert h==expected,(str(p),'source SHA mismatch')
 HASH[str(p)]=h;return p
def read(p):return json.loads(bind(p).read_text())
def main():
 bind(__file__);sm=read(B/'STOCK_MANIFEST.json');im=read(B/'INDUSTRY_MANIFEST.json')
 checkpoint=read(M/'checkpoints/USHI1B0300.json')
 market=pd.read_csv(bind(M/'canonical/USHI1B0300.csv',checkpoint['canonical_sha256']),parse_dates=['date']).set_index('date')
 warm=market.index[(market.index>='2021-01-01')&(market.index<='2021-12-31')]
 i=market.index.get_loc(warm[0]);j=market.index.get_loc(warm[-1]);grid=market.index[i-60:j+1]
 existing=pd.read_parquet(bind(OLD/'INDUSTRY_OPPORTUNITIES_DAILY.parquet'),columns=['date','sector_id_static','B_now','dB5_paired','B_lag5_ownU','N_U_previous5'])
 assert existing.date.min()=='2022-01-04'and len(existing)==97650
 known=[]
 for r in im:
  p=r['refs']['CP1_input'];f=pd.read_parquet(bind(p,r['output_sha256'][p]),columns=['close','segment_id']).reindex(grid)
  valid=f.close.gt(0)&np.isfinite(f.close)&f.segment_id.notna()
  a=valid.shift(5).reindex(warm).fillna(False);b=valid.shift(60).reindex(warm).fillna(False)
  same=f.segment_id.shift(5).reindex(warm).eq(f.segment_id.shift(60).reindex(warm))
  known.append({'sector_id_static':r['series'],'endpoint_same_segment_available':int((a&b&same).sum()),'warm_dates':len(warm)})
 stock_sources=[]
 for r in sm:
  paths=[p for p in r['source_sha256']if '/prepared'in p and p.endswith('/signal.parquet')];assert len(paths)==1
  stock_sources.append({'sid':r['symbol'],'path':paths[0],'declared_sha256':r['source_sha256'][paths[0]]})
 old_kernel=bind(OLD/'compute_opportunities.py')
 output={'status':'SOURCE_READY_WAITING_ROOT_FREEZE','new_ranking_or_Rp_values_computed':0,'new_B_panels_computed':0,'new_accounts':0,
  'warm_year':2021,'warm_sessions':len(warm),'warm_first':str(warm[0].date()),'warm_last':str(warm[-1].date()),
  'first_Rp_tminus60_date':str(market.index[i-60].date()),'first_Rp_tminus5_date':str(market.index[i-5].date()),
  'B_kernel_calendar_pad29_start':str(market.index[i-29].date()),
  'industry_endpoint_availability':known,'all_90_all_2021_Rp_endpoints_same_segment_available':all(x['endpoint_same_segment_available']==len(warm)for x in known),
  'stock_sources':stock_sources,'reuse_stock_state_function':str(old_kernel)+'::stock_state',
  'old_2022_onward_panel':str((OLD/'INDUSTRY_OPPORTUNITIES_DAILY.parquet').resolve()),'old_rows':len(existing),
  'old_2022_onward_recompute_planned':False,
  'existing_2021_same_definition_B_found':False,
  'search_scope':['selection_core_v1 saved panels/schemas','INDUSTRY_DAILY_BEHAVIOR.parquet (starts2022, different breadth)','legacy dual-board B21/B63 (different formula)','new_price_trend PRICE_FEATURES starts2022 and has no industry U breadth'],
  'boundary_audit_plan':'Compare computed last5 2021 own-U breadth/N against old first5 2022 B_lag5_ownU/N_U_previous5, without rebuilding old2022 rows.',
  'initial_state_plan':['I0','I1','A0','A1','A2'],
  'initial_state_result':'NOT_COMPUTED: advance all legal initial states only after root freeze; unknown rank breaks counter but retains maturity possibility; no backfill from later states.',
  'data_limits':'2026 static pool/current classification retained; no historical full-industry membership authentication; preIPO/unavailable stocks remain unavailable, not false breadth.'}
 (O/'SOURCE_READINESS.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
 (O/'PREPARED_SOURCE_SHA256.json').write_text(json.dumps(HASH,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:v for k,v in output.items()if k not in ['industry_endpoint_availability','stock_sources']},ensure_ascii=False))

if __name__=='__main__':main()
