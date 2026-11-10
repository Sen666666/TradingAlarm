import json, pathlib, hashlib
import pandas as pd
O=pathlib.Path(__file__).parent
U=pathlib.Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
sha=lambda p: hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
old=json.loads((O/'SOURCE_HASHES.json').read_text())
assert all(sha(p)==h for p,h in old.items())
mm={r.get('series',r.get('symbol')):r for fn in ['INDUSTRY_MANIFEST.json','STOCK_MANIFEST.json'] for r in json.loads((U/fn).read_text())}
ids=['URFI881272','URFI881121','URFI881157','300085.SZ','300059.SZ','688256.SH','688981.SH','300308.SZ','000158.SZ','300339.SZ']
names=['软件开发','半导体','证券','银之杰','东方财富','寒武纪','中芯国际','中际旭创','常山北明','润和软件']
rows=[]
for sid,name in zip(ids,names):
 ps=[(p,h) for p,h in mm[sid]['source_sha256'].items() if p.endswith('/signal.parquet') and '/a-share-selection-e0-' in p]
 assert len(ps)==1
 p,h=ps[0];assert sha(p)==h;d=pd.read_parquet(p)
 dates=['2024-09-23','2024-09-27','2024-09-30','2024-10-08','2024-11-08','2024-12-31'];q=d.loc[dates]
 assert q.observed_bar.astype(bool).all() and q.price_eligible.astype(bool).all() and not q.source_invalid.astype(bool).any() and not q.synthetic_event_bar.astype(bool).any()
 c=q.close
 rows.append(dict(sid=sid,name=name,emergence_0923C_to_0927C_pct=100*(c['2024-09-27']/c['2024-09-23']-1),acceleration_0927C_to_1008C_pct=100*(c['2024-10-08']/c['2024-09-27']-1),differentiation_1008C_to_1108C_pct=100*(c['2024-11-08']/c['2024-10-08']-1),late_1108C_to_1231C_pct=100*(c['2024-12-31']/c['2024-11-08']-1),raw_gap_1008O_from_0930C_pct=100*(q.loc['2024-10-08','raw_open']/q.loc['2024-09-30','raw_close']-1),raw_1008C_from_1008O_pct=100*(q.loc['2024-10-08','raw_close']/q.loc['2024-10-08','raw_open']-1),source=p,source_sha256=h))
a=pd.DataFrame(rows);a.to_csv(O/'924_SUBPHASES.csv',index=False);(O/'924_SUBPHASES.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
assert all(sha(p)==h for p,h in old.items())
print(a.drop(columns=['source','source_sha256']).round(4).to_string(index=False))
