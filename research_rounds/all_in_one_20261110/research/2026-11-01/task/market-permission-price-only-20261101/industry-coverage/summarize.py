"""Summarize saved all-node results. Does not import or execute F1."""
import hashlib
import json
from pathlib import Path
import pandas as pd

O=Path(__file__).resolve().parent;P=O/'run-v1';B=O.parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
nodes=json.loads((P/'ALL_NODES.json').read_text())
metrics=json.loads((P/'WINDOW_METRICS.json').read_text())
input_gate=json.loads((P/'INPUT_GATE.json').read_text())
previous_sources=json.loads((B/'input-preparation/prepared-v2/SOURCE_SHA256.json').read_text())


def save(name,x):
    (P/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


unknowns=[];catalog=[]
for n in nodes:
    rows=[r for r in metrics if r['node_id']==n['node_id']]
    cat=dict(n)
    cat['window_status']={r['window']:r['status'] for r in rows}
    cat['daily_result_path']=str(P/'daily'/(n['node_id']+'.parquet'))
    cat['source_note']='original industry index price; breadth of fixed research pool, not full index membership'
    for r in rows:
        if r['status']!='READY':
            unknowns.append(dict(node_id=n['node_id'],name=n['name'],window=r['window'],status=r['status'],
                                 fixed_identities=n.get('fixed_identities'),source_roster=n.get('source_roster'),
                                 observations=r.get('observations'),joint_ready=r.get('joint_ready_observations'),
                                 price_unknown=r.get('price_unknown'),breadth_unknown=r.get('breadth_unknown'),
                                 reason='fixed research roster has fewer than5 identities' if n.get('fixed_identities',5)<5
                                 else 'some observations have fewer than5 ready signed-m components; preserve as unknown'))
    catalog.append(cat)
save('NODE_CATALOGUE.json',catalog)
pd.DataFrame([{k:v for k,v in r.items() if not isinstance(v,(list,dict))} for r in catalog]).to_csv(P/'NODE_CATALOGUE.csv',index=False)
save('WINDOW_UNKNOWNS.json',unknowns)

focus=json.loads((P/'SHADOW_FREEZE.json').read_text())['focus_2023']
local=pd.read_parquet(P/'LOCAL_VS_GLOBAL_2023.parquet').groupby('node_id').local_while_global_withheld.sum().to_dict()
focus_rows=[]
for r in metrics:
    if r['domain']=='NATIVE1709' and r['sector'] in focus and r['window']=='year2023':
        rr=dict(r)
        rr['local_permit_global_withheld_after_Mar14']=int(local[rr['node_id']])
        focus_rows.append(rr)
save('FOCUS_2023.json',focus_rows)
pd.DataFrame([{k:v for k,v in r.items() if not isinstance(v,list)} for r in focus_rows]).to_csv(P/'FOCUS_2023.csv',index=False)

global_old=pd.read_parquet(B/'historical-shadow/run-v1/OLD407_global_daily.parquet')
old_compare=[]
for n in nodes:
    if n['domain']!='OLD407':continue
    f=pd.read_parquet(P/'daily'/(n['node_id']+'.parquet'))
    for d,r in f.loc['2024-09-24':'2024-12-31'].iterrows():
        gp=bool(global_old.loc[d,'permit_next_open'])
        old_compare.append(dict(node_id=n['node_id'],name=n['name'],day=d,industry_permit=bool(r.permit_next_open),
                                global_permit=gp,local_while_global_withheld=bool(r.permit_next_open and not gp)))
pd.DataFrame(old_compare).to_parquet(P/'LOCAL_VS_GLOBAL_OLD924.parquet',index=False)
save('OLD924_ALL_NODES.json',[r for r in metrics if r['domain']=='OLD407'])

reuse_checks=[]
for n in nodes:
    if not n['reuse']:continue
    original=B/'historical-shadow/run-v1'/(n['scope']+'_daily.parquet')
    x=pd.read_parquet(original);y=pd.read_parquet(P/'daily'/(n['node_id']+'.parquet'))
    pd.testing.assert_frame_equal(x,y[x.columns],check_exact=True)
    reuse_checks.append(dict(node_id=n['node_id'],original=str(original),original_sha256=sha(original),all_original_columns_exact=True))
save('REUSED_CONTROL_GATE.json',dict(passed=True,checks=reuse_checks))

binding={}
for path in [Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json'),
             Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json'),
             Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/tech-compound-design-20261026/proposed-pool.csv'),
             B/'input-preparation/prepared-v2/NATIVE1709/all_industry_coverage.parquet',
             B/'input-preparation/prepared-v2/OLD407/all_industry_coverage.parquet']:
    actual=sha(path)
    if str(path) in previous_sources:assert previous_sources[str(path)]==actual
    binding[str(path)]=actual
for p,h in input_gate['source_sha256'].items():assert sha(p)==h
save('SOURCE_BINDING.json',dict(manifests_and_counts=binding,all_industry_sources_still_equal=True,
                               source_timing='end-of-day source rows; next eligible open consumption; prepared retrospective current-snapshot domain, not PIT',
                               native_price_cutoff='2026-06-30',old_shadow_cutoff='2024-12-31',old_input_price_cutoff='2026-10-26'))

groups={}
for r in metrics:
    k=r['domain']+'/'+r['window'];groups.setdefault(k,{});groups[k][r['status']]=groups[k].get(r['status'],0)+1
save('RESULT_INTERPRETATION.json',dict(node_window_status=groups,
      missing_price_source_nodes=input_gate['unknown'],
      unknown_breadth_windows=len([r for r in metrics if r['status']=='UNKNOWN_BREADTH_MIN5']),
      partial_unknown_windows=len([r for r in metrics if r['status']=='PARTIAL_UNKNOWN']),
      true_false_permission_rate='UNKNOWN: no independent true-trend/no-trend labels; NO_ADVANCE_FAILURE is only a structural proxy, never account loss',
      unknown_nodes_are_not_successful_risk_off=True,scope_reuse_aliases=reuse_checks,
      all_nodes_retained=True,parameter_changes=0,account_paths=0,new_stream_calculations=99,reused_prior_streams=2))
print(json.dumps(dict(catalogue=len(catalog),unknown_windows=len(unknowns),reuse_controls_exact=len(reuse_checks)),ensure_ascii=False))
