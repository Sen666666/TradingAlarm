"""Thin ACT-transition/source-identity supplement, no financial replay."""
from pathlib import Path
from collections import Counter
from decimal import Decimal as D
import ast,gzip,hashlib,json
import pandas as pd
O=Path(__file__).resolve().parent;P=O.parent/'pvr_eta_v1'
SM=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
RISK=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/actual-risk-recovery-20261027/code/risk_policy.py')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
    with (gzip.open(p,'rt') if str(p).endswith('.gz') else open(p)) as f:
        return [json.loads(x) for x in f] if '.jsonl' in str(p) else json.load(f)
src=RISK.read_text();fn=next(n for n in ast.parse(src).body if isinstance(n,ast.FunctionDef) and n.name=='advance')
exec(compile(ast.Module(body=[fn],type_ignores=[]),str(RISK)+':pureadvance','exec'),globals())
known={p:h for m in read(SM) for p,h in m['output_sha256'].items()}
for window in ['2022_2024','strong']:
    receipt=O/('PVR_ETA_'+window+'_ACCOUNT_AUDIT.json');dst=O/('PVR_ETA_'+window+'_ACT_SOURCE_SUPPLEMENT.json')
    if not receipt.exists() or dst.exists():continue
    audited=read(receipt);out=P/'runs'/window;meta=read(out/'RUN_METADATA.json');identity=meta['original_shared_input_identity'];extra=identity.get('receipt_union_sources',{})
    assert identity['stock_manifest_sha256']==sha(SM)
    counts=Counter()
    for p,h in audited['raw_price_source_sha256'].items():
        if p in extra:assert extra[p]==h;counts['annual_union_receipt_hash_identity']+=1
        elif p in known:assert known[p]==h;counts['original_manifest_fact_receipt_hash_identity']+=1
        else:assert p.endswith('execution-rules-v2.json');counts['original_fee_rule_file_already_independently_used']+=1
    candidates=[Path(z) for z,h in meta['source_freeze'].items() if h==identity['ACT_external_sha256'] and Path(z).name=='recovery.csv'];assert len(candidates)==1;recovery=candidates[0];assert sha(recovery)==identity['ACT_external_sha256']
    rec=pd.read_csv(recovery,index_col=0,parse_dates=True)
    book=read(out/'pair/B.json.gz');daily=read(out/'pair/daily.jsonl.gz');byat={d['at']:d for d in daily}
    cps=[a for a in book['audit'] if a['kind']=='risk_checkpoint'];assert len(cps)==len(daily)
    state=dict(on=True,peak=D(1000000),saw_off=False,previous_fast=False,episode=0);events=[]
    for c in cps:
        d=byat[c['at']];day=pd.Timestamp(c['at'][:10]);j=rec.index.searchsorted(day,side='right')-1
        fast=bool(rec.iloc[j].fast_on) if j>=0 else False;br=bool(rec.iloc[j].breakout) if j>=0 and rec.index[j]==day else False
        assert c['fast']==fast and c['breakout']==br and c['policy']=='ACT20_BREAK'
        # Normal one-session buys expire before the CLOSE ACT checkpoint.
        flat=not d['positions'] and not d['pending_sells'];assert c['flat']==flat
        assert D(c['nav'])==D(d['nav'])
        state,dd,event=advance(state,D(c['nav']),flat,fast,br,'ACT20_BREAK')
        assert all((D(str(c[k]))==v if isinstance(v,D) else c[k]==v) for k,v in state.items())
        assert c['event']==event and abs(D(c['episode_drawdown'])-dd)<D('1e-24')
        assert c['on']==d['on'];counts['all_actual_ACT_checkpoints_and_native_external_flags']+=1
        if event:events.append(dict(at=c['at'],event=event,NAV=c['nav'],peak=str(state['peak'])))
    result=dict(status='PASS_ALL_ACT_TRANSITIONS_AND_ORIGINAL_RECEIPT_SOURCE_IDENTITIES',window=window,checks=dict(counts),events=events,
                source_sha256={str(receipt):sha(receipt),str(RISK):sha(RISK),str(SM):sha(SM),str(recovery):sha(recovery)},script_sha256=sha(__file__),
                limits=['Saved actual flat/NAV flags tested against original pure ACT advance, not a candidate economic replay.','Raw quote/receipt bytes were already read and hashed by the completed-account auditor; this supplement compares those hashes to original manifests/annual union rather than re-reading all files.'],new_accounts=0,new_financial_events=0)
    dst.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(window,result['status'],len(cps),events,flush=True)
