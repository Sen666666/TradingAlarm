from pathlib import Path
import json,gzip,hashlib,collections
import pandas as pd
O=Path(__file__).resolve().parent;D=json.loads((O/'FROZEN_DATES.json').read_text());DATES=set(D['root_frozen_dates']);EARLY=set(D['first_delivery_dates']);sha=json.loads((O/'SOURCE_SHA256.json').read_text());decisions=[];intents=[];daily=[]
def read(p):
 p=Path(p);b=p.read_bytes();sha[str(p.resolve())]=hashlib.sha256(b).hexdigest();return json.loads(b)
for run in ['long_OFF','strong_OFF']:
 p=Path('new_price_trend_v1/funding/runs')/run/'pair/B.json.gz';sha[str(p.resolve())]=hashlib.sha256(p.read_bytes()).hexdigest()
 with gzip.open(p,'rt') as f:b=json.load(f)
 for r in b['decisions']:
  day=r['at'][:10]
  if day not in DATES:continue
  decisions.append(dict(source=str(p.resolve()),source_window=run,**r))
  for i in r['intents']:intents.append(dict(signal_date=day,signal_at=r['at'],ACT_on=r['on'],signal_NAV=r['nav'],source=str(p.resolve()),**i))
 q=p.parent/'daily.jsonl.gz';sha[str(q.resolve())]=hashlib.sha256(q.read_bytes()).hexdigest()
 with gzip.open(q,'rt') as f:
  for line in f:
   atkey='"at": "';n=line.find(atkey)
   if n<0 or line[n+len(atkey):n+len(atkey)+10] not in DATES:continue
   r=json.loads(line);daily.append(dict(source=str(q.resolve()),**{k:v for k,v in r.items() if k!='layers'}))
(O/'ORIGINAL_SAVED_DECISION_SNAPSHOTS.json').write_text(json.dumps(decisions,ensure_ascii=False,indent=2)+'\n');pd.DataFrame(intents).to_csv(O/'ORIGINAL_PENDING_INTENTS.csv',index=False);(O/'ORIGINAL_DAILY_ACCOUNT_STATE.json').write_text(json.dumps(daily,ensure_ascii=False,indent=2)+'\n')
selection=read('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/selection.json');disp=read(selection['all_roster_dispositions']['path']);sm=read('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json');ids={x['symbol'] for x in sm};meta=read('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json')
sel={x['security_id']:x for x in selection['lines']};pd.DataFrame([{**meta[sid],**sel[sid],'sid':sid} for sid in sorted(ids)]).to_csv(O/'CURRENT_STATIC_STOCK_POOL.csv',index=False)
p=Path('/Users/bytedance/repos/my-quant/data/processed/security_memberships/security_memberships.parquet');hist=pd.read_parquet(p);sha[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
scope={'static_stock_count':len(ids),'true_industry_count':len({meta[s]['sector_id'] for s in ids}),'current_2026_roster_dispositions_count':len(disp),'current_roster_disposition_counts':dict(collections.Counter(x['disposition'] for x in disp)),'selection_metadata':{k:v for k,v in selection.items() if k!='lines'},'selection_rows_not_in_original_1709':[x for x in selection['lines'] if x['security_id'] not in ids],'hist_membership_dataset':str(p),'hist_membership_rows':len(hist),'hist_taxonomy_counts':dict(collections.Counter(hist.taxonomy)),'hist_current_1709_stock_coverage':int(hist[hist.symbol.isin(ids)].symbol.nunique()),'hist_effective_end_missing_rows':int(hist.effective_end_date.isna().sum()),'hist_observed_at_values':hist.observed_at.astype(str).value_counts().to_dict(),'formal_THS881_historical_membership_verified':False,'hist_limitation':'Existing historical SW rows are a different taxonomy; open-ended overlaps/2026 observation provenance do not prove contemporaneously known THS881 membership. No bridge or current-member custom historical index made.','full_historical_market_rank_or_eligibility_available':False,'no_new_CP_I_E0_H1_PVR_or_eligibility_computation':True,'no_accounts_instantiated_or_advanced':True}
(O/'STATIC_UNIVERSE_AND_MEMBERSHIP_AUDIT.json').write_text(json.dumps(scope,ensure_ascii=False,indent=2,default=str)+'\n');(O/'SOURCE_SHA256.json').write_text(json.dumps(sha,ensure_ascii=False,indent=2)+'\n')
print('decision snapshots',len(decisions),'intents',len(intents),'daily',len(daily));print('SCOPE',json.dumps({k:v for k,v in scope.items() if k not in ['selection_metadata','selection_rows_not_in_original_1709']},ensure_ascii=False,default=str));print('ACT',{r['at'][:10]:r['on'] for r in decisions if r['at'][:10] in EARLY})
