from pathlib import Path
import json
import pandas as pd
from engine import O,E,AS,sha,save
ro=pd.read_csv(O/'CLASSIFICATION_ALL1709.csv',keep_default_na=False);events=json.loads((E/'cash_dividend_2024_coverage_v1/EVENT_ADAPTER_CANDIDATES.json').read_text())+json.loads((O.parent/'continuous_candidate_v1/EXTRA_REVIEWED_EQUITY_EVENTS_V2.json').read_text());known={(x['sid'],x['ex_date']) for x in events};rows=[]
for _,s in ro[ro.eligible].iterrows():
 p=AS/'inputs-v1/actions'/(s.symbol+'.json')
 for a in json.loads(p.read_text())['events']:
  dt=a['effective_date']
  if '2024-09-02'<=dt<='2024-10-31' and (s.symbol,dt) not in known:
   caches=[str(E/d/(s.symbol+'.json')) for d in ['cash_dividend_source_feasibility_v1/raw','cash_dividend_2024_coverage_v1/raw'] if (E/d/(s.symbol+'.json')).exists()]
   rows.append(dict(sid=s.symbol,name=s['name'],sector51=s.sector51,ex_date=dt,cash_per_old_share=a['cash_per_old_share'],split_ratio=a['split_ratio'],action_path=str(p),action_sha256=sha(p),existing_fact_cache=';'.join(caches),status='UNADMITTED_INVENTORY_NOT_ACTUAL_EXPOSURE'))
rows=sorted(rows,key=lambda x:(x['ex_date'],x['sid']));save(O/'UNADMITTED_ACTION_INVENTORY.json',rows);pd.DataFrame(rows).to_csv(O/'UNADMITTED_ACTION_INVENTORY.csv',index=False)
run=O/'full_20241031_once';ledger=json.loads((run/'DAY_LEDGER.json').read_text());save(O/'RUN_STATUS.json',dict(planned_start='2024-09-02',planned_end='2024-10-31',completed_horizon=False,certified_through=ledger[-1]['day'],complete_days=len(ledger),orders=len(json.loads((run/'ORDERS.json').read_text())),blockers=json.loads((run/'BLOCKERS.json').read_text()),checkpoint_20240923_created=False,classification_total=1709,eligible=1692,excluded=17,populated_named_sectors=50,unadmitted_inventory=len(rows),warning='Inventory is not exposure. Do not skip unsupported events or infer no economic effect. Original frozen run preserved.'))
print(len(rows),'inventory rows; run status saved')
