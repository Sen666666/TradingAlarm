from pathlib import Path
from collections import Counter,defaultdict
import csv,json,hashlib
O=Path(__file__).resolve().parent;P=O.parent
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/momentum_persistence_breadth_v1/FIXED_ROSTER.csv')
M=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/current-pool-20261022/audit-snapshot/current-stock-master.industry-resolved.csv')
read=lambda p:list(csv.DictReader(Path(p).open()))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
g=json.loads((P/'SECTOR51_MAPPING_RECEIVED.json').read_text())['groups'];rev=defaultdict(list)
for k,vs in g.items():
 for v in vs:rev[v].append(k)
r=read(R);m=read(M);c=read(P/'CORE_CLASSIFICATION.csv');md={x['symbol']:x for x in m};counts=Counter();fresh={};missing=[];excluded=[];classified=[];errors=[]
for x in r:
 y=md.get(x['symbol']);leaf=y.get('industry_leaf_code','') if y else '';sector=rev.get(leaf,[None])[0];fresh[x['symbol']]=(leaf,sector);counts[sector]+=1
 row=dict(x,industry_leaf_code=leaf,sector51=sector)
 if not y or not leaf or not sector:missing.append(row)
 elif sector=='未分类':excluded.append(row)
 else:classified.append(row)
for x in c:
 if fresh.get(x['symbol'])!=(x['industry_leaf_code'],x['sector51']):errors.append(dict(sid=x['symbol'],old=[x['industry_leaf_code'],x['sector51']],new=fresh.get(x['symbol'])))
assert len(g)==51 and len(rev)==257 and all(len(v)==1 for v in rev.values())
assert len(r)==len({x['symbol'] for x in r})==1709 and len(m)==len(md)
assert len(c)==len({x['symbol'] for x in c})==217
assert not errors and not missing and len(classified)==1692 and len(excluded)==17
j=P/'joint51_candidate_v1/CLASSIFICATION_ALL1709.csv'
joint_check=None
if j.exists():
 jr=read(j);joint_check=all(fresh[x['symbol']]==(x['industry_leaf_code'],x['sector51']) and (x['eligible'].lower()=='true')==(x['sector51']!='未分类') for x in jr) and len(jr)==1709
 assert joint_check
report=dict(status='PASS',mapping_sha256=sha(P/'SECTOR51_MAPPING_RECEIVED.json'),groups=51,unique_leaf_codes=257,unclassified_codes=g['未分类'],roster_rows=1709,eligible_rows=1692,unclassified_rows=17,missing_rows=0,populated_eligible_sectors=50,core_rows=217,core_mismatches=errors,joint_mapping_matches=joint_check,sector_counts=dict(sorted(counts.items())),excluded_unclassified=excluded,missing=missing,source_hashes={str(p):sha(p) for p in [R,M,P/'SECTOR51_MAPPING_RECEIVED.json',P/'CORE_CLASSIFICATION.csv']},limitations=['Current classification and existing fixed sample are not historical point-in-time universe.','Unclassified rows are excluded, never treated as an investable sector.','N=1 and N=2 sectors cannot reach TRUE under unchanged minimum n>=3 state rule.'])
(O/'CLASSIFICATION_AUDIT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
