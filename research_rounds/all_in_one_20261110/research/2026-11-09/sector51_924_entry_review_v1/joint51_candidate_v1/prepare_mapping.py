from pathlib import Path
import json,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;P=O.parent;R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');M=Path('/Users/bytedance/Documents/ChatGPT/money')
mp=P/'SECTOR51_MAPPING_RECEIVED.json';masterp=M/'research_rounds/current-pool-20261022/audit-snapshot/current-stock-master.industry-resolved.csv';rp=R/'momentum_persistence_breadth_v1/FIXED_ROSTER.csv'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(mp)=='86144c2c9791a53d76d2b64c493f610569ca57a57ff0db0618b5b4d994557049'
m=json.loads(mp.read_text());flat={c:g for g,cs in m['groups'].items() for c in cs};assert flat==m['code_to_sector51'] and sum(map(len,m['groups'].values()))==len(flat) and len(m['groups'])==51
ro=pd.read_csv(rp);master=pd.read_csv(masterp);assert len(ro)==1709 and ro.symbol.is_unique
ro=ro.merge(master[['symbol','industry_leaf_code','industry_leaf_name']],on='symbol',how='left',validate='1:1');ro['sourcecode']=ro.industry_leaf_code;ro['sector51']=ro.sourcecode.map(flat);ro['eligible']=ro.sector51.notna()&~ro.sector51.eq('未分类');ro['exclusion_reason']='';ro.loc[ro.sector51.isna(),'exclusion_reason']='LEAF_CODE_NOT_IN_SUPPLIED_MAP';ro.loc[ro.sector51.eq('未分类'),'exclusion_reason']='EXPLICIT_UNCLASSIFIED';ro['sector51']=ro.sector51.fillna('未映射')
core=pd.read_csv(P/'CORE_CLASSIFICATION.csv');now=ro.set_index('symbol').loc[core.symbol];assert list(now.sector51)==list(core.sector51);assert list(now.industry_leaf_code)==list(core.industry_leaf_code)
ro.to_csv(O/'CLASSIFICATION_ALL1709.csv',index=False);ro[~ro.eligible].to_csv(O/'EXCLUDED_UNCLASSIFIED.csv',index=False)
hashes={str(p):sha(p) for p in [mp,masterp,rp,P/'CORE_CLASSIFICATION.csv',O/'prepare_mapping.py']};(O/'MAPPING_SOURCE_HASHES.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2)+'\n')
summary=dict(total=1709,eligible=int(ro.eligible.sum()),excluded=int((~ro.eligible).sum()),taxonomy_groups=51,populated_named_sectors=int(ro[ro.eligible].sector51.nunique()),counts=ro.groupby('sector51').size().to_dict(),core217_exact_match=True,current_membership_not_PIT=True)
(O/'MAPPING_QA.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False))
