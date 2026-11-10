"""Verify frozen evidence and presentation exports; never rerun economic accounts."""
from pathlib import Path
import json,hashlib,re,datetime
from urllib.parse import unquote
import numpy as np,pandas as pd
R=Path(__file__).resolve().parent;O=R/'results/v0';P=R.parent/'strategy-switching-20261024'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
counts={}
for directory in [R,P,R.parent/'gold-e0-r-diagnosis-20261024']:
    m=json.loads((directory/'freeze.json').read_text())['sha256']
    bad=[n for n,h in m.items() if sha(directory/n)!=h]
    assert not bad,(directory,bad)
    counts[directory.name]=len(m)
s=pd.read_csv(O/'comparison.csv');refs=pd.read_csv(O/'cash-reference.csv');assert len(s)==270 and len(refs)==54
data=json.loads((R/'report-data.json').read_text());assert len(data['summary'])==270 and len(data['reference'])==54
assert len(data['cases'])==18 and len(data['scenarios'])==3
paths=0
for c in data['cases']:
    for sc in data['scenarios']:
        d=json.loads((R/'series'/f"{c['id']}__{sc}.json").read_text());assert d['dates']==sorted(d['dates']) and len(set(d['dates']))==len(d['dates'])
        for p,a in d['paths'].items():
            assert len(a['nav'])==len(a['drawdown'])==len(d['dates']);assert np.isfinite(a['nav']).all()
            source=refs if p=='HALF_E0' else s
            row=source[(source.case==c['id'])&(source.scenario==sc)&(source.policy==p)].iloc[0]
            assert abs(a['nav'][-1]-1-row.net_return)<5.1e-10
            assert abs(min(a['drawdown'])+row.max_drawdown)<5.1e-10
            paths+=1
assert paths==324
# Every statically linked local evidence/image exists. Dynamic paths are covered above.
html=(R/'index.html').read_text();checked=[]
for href in re.findall(r'(?:href|src)="([^"]+)"',html):
    if href.startswith(('http','#')):continue
    if href=='artifact-manifest.json':
        assert (R/'ui-qa.json').exists(),'UI record is required to generate final manifest'
        checked.append(href)
        continue
    assert (R/unquote(href)).is_file(),href
    checked.append(href)
for c in data['cases']:
    assert (R/'charts'/f"{c['id']}.png").is_file()
    for sc in data['scenarios']:assert (O/'accounts'/f"{c['id']}__R1__{sc}/trades.csv").is_file()
assert len(list((O/'accounts').glob('*')))==54
assert json.loads((O/'audit.json').read_text())['passed']

# Actual order evidence for the one delayed-execution decomposition exception.
traces=[]
for policy,root in [('R',P),('R1',R)]:
    o=pd.read_csv(root/'results/v0/accounts'/f'continuous_USHJ510300__{policy}__delay1/orders.csv')
    z=o[o.date.between('2023-05-08','2023-05-19')|o.date.between('2025-08-20','2025-09-11')].copy();z.insert(0,'policy',policy);traces.append(z)
pd.concat(traces).to_csv(O/'delayed-entry-exception-orders.csv',index=False)
result={'passed':True,'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'frozen_sources_unchanged':counts,'new_R1_accounts':54,'reused_controls':216,'separate_cash_reference_paths':54,'exported_paths_checked':paths,'static_local_links_checked':len(checked),'post_result_rule_changes':0,'market_downloads':0,'wechat_operations':0,'economic_reruns':0,'notes':['UI checks recorded separately; presentation fixes do not modify frozen policy, state or economics.','Full raw PV/state review occurred before account admission; final economic plots for gold, semi YTD, semi bull, continuous semi and fixed-suite matrix were inspected after the run.']}
(R/'final-checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False,indent=2))
if (R/'ui-qa.json').exists():
    files=[p for p in R.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='artifact-manifest.json']
    manifest={str(p.relative_to(R)):sha(p) for p in files}
    (R/'artifact-manifest.json').write_text(json.dumps({'generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sha256':manifest},ensure_ascii=False,indent=2));assert (R/'artifact-manifest.json').is_file();print('Final artifact manifest',len(manifest))
