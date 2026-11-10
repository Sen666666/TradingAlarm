"""Export the saved 242-session original ATT only; no new indicators/ranks/labels."""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,collections,shutil
O=Path(__file__).resolve().parent;B=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/market-mainline-measurement-20261031');P=B/'FEATURE_MATRIX_90.parquet';U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031');M=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json')
def h(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
freeze=json.loads((B/'FEATURE_FREEZE.json').read_text());assert h(P)==freeze['sha256']
d=pd.read_parquet(P,columns=['day','sector','attention_ratio','attention_known','attention_members','member_count','denominator_complete_window_members']);assert len(d)==21780 and d.day.nunique()==242 and d.sector.nunique()==90
A=np.load(B/'AMOUNT_INPUT.npz');L=np.load(B/'STOCK_PRICE_LABELS.npz');sid=A['symbols'].astype(str);lsid=L['symbols'].astype(str);lsector=L['sector'].astype(str)
sm=json.loads((U/'STOCK_MANIFEST.json').read_text());im=json.loads((U/'INDUSTRY_MANIFEST.json').read_text());meta=json.loads(M.read_text());ids={x['symbol']for x in sm};gids={x['series']for x in im}
assert set(sid)==set(lsid)==ids;assert set(d.sector)==gids;assert all(meta[s]['sector_id']==g for s,g in zip(lsid,lsector));assert d.drop_duplicates('sector').set_index('sector').member_count.to_dict()==dict(collections.Counter(lsector))
z=d.rename(columns={'day':'date','sector':'sector_id_static','attention_ratio':'ATT_original','attention_known':'ATT_known','attention_members':'ATT_member_known_count','member_count':'ATT_static_member_count','denominator_complete_window_members':'ATT_global_complete26_stock_count'}).sort_values(['date','sector_id_static']).reset_index(drop=True)
assert np.isfinite(z.ATT_original).all() and z.ATT_known.eq(True).all();assert not z.duplicated(['date','sector_id_static']).any()
z.to_parquet(O/'ATT_ORIGINAL_SAVED_DAILY.parquet',index=False);z.to_csv(O/'ATT_ORIGINAL_SAVED_DAILY.csv',index=False)
sha={str(p):h(p)for p in [P,B/'FEATURE_FREEZE.json',B/'AMOUNT_INPUT.npz',B/'STOCK_PRICE_LABELS.npz',U/'STOCK_MANIFEST.json',U/'INDUSTRY_MANIFEST.json',M,Path(__file__)]}
audit={'ATT_source_path':str(P),'ATT_source_SHA256':h(P),'ATT_feature_freeze_SHA_matches':True,'export_path':str(O/'ATT_ORIGINAL_SAVED_DAILY.parquet'),'columns':list(z.columns),'rows':len(z),'sessions':z.date.nunique(),'industries':z.sector_id_static.nunique(),'start':z.date.min(),'end':z.date.max(),'known_ATT_cells':int(z.ATT_known.sum()),'all_values_copied_without_new_formula_or_rank':True,'requires_no_ATT_gt1_gate':True,'target_total_sessions_2022_to2026H1':1085,'missing_earlier_target_sessions':843,'missing_intervals':['2022-01-04..2023-12-29','2024-01-02..2024-12-31','2025-01-02..2025-06-30'],'old_amount_cache_start':str(pd.Timestamp(A['dates'][0]).date()),'old_amount_cache_end':str(pd.Timestamp(A['dates'][-1]).date()),'old_amount_cache_shape':list(A['amount'].shape),'pool_stock_ids_exact_current1709':True,'industry_ids_exact_current90':True,'per_stock_sector_bridge_exact_current_metadata':True,'per_industry_member_counts_exact':True,'bridge_proof_only_archive_metadata_arrays_read':['symbols','sector'],'future_label_arrays_read':False,'new_A_rank_read':False,'new_accounts_or_models':0,'PIT_verified':False,'comparison_limitation':'Only the 242 saved sessions can be directly reused. No fill/ffill/new earlier ATT. Pool and bridge exact does not by itself certify all amount-source vintages identical to a newer feature pipeline. Original ATT complete26 cohort is part of its definition, not the newer liquidity U_t.'}
(O/'ATT_ORIGINAL_SOURCE_COVERAGE.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n');(O/'ATT_ORIGINAL_BRIDGE_EVIDENCE_SHA256.json').write_text(json.dumps(sha,ensure_ascii=False,indent=2)+'\n')
old=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-4/continuous_rank_v3/original_baselines')
for p in old.iterdir():
 if p.is_file():
  target=O/p.name
  if target.exists():assert h(p)==h(target),('conflicting existing mirror',str(target))
  else:shutil.copy2(p,target)
print(json.dumps(audit,ensure_ascii=False))
