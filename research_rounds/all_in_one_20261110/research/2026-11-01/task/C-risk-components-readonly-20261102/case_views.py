"""Summarize already extracted components; no portfolio optimization."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import json,hashlib
O=Path(__file__).resolve().parent;Z=D(0);TOL=D('1e-16')
def read(n):return json.loads((O/n).read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,default=str,indent=2)+'\n')
dt=read('LAYER_COMPONENTS.json');dec=read('ORIGINAL_DECISIONS.json');su=read('SUMMARY.json')
causal=Path('/tmp/August-four-arm-independent-20261102/C20_Aug25_CAUSAL_CASE.json')
c=json.loads(causal.read_text())
dec.append(dict(cell='C20',day='2025-08-22',donors={'rows':c['donors']}))
for v in dt.values():
    assert all(D(r['profit_giveback'])==0 for r in v['layers'] if D(r['unrealized'])<=0)

donors=[]
for x in dec:
    rows={r['layer']:r for r in dt[x['cell']+'|'+x['day']+'|CLOSE']['layers']}
    out=[]
    for z in x['donors']['rows']:
        r=rows[z['layer']];q=D(z['q']);fraction=q/D(r['qty'])
        out.append(dict(layer=z['layer'],sid=r['sid'],qty=q,capital=q*D(r['mark']),
            principal=fraction*D(r['principal']),profit_giveback=fraction*D(r['profit_giveback']),
            original_projection_risk_release=z['risk_release'],planned_net=z['net']))
    total={k:sum((D(r[k]) for r in out),Z) for k in ['capital','principal','profit_giveback','original_projection_risk_release','planned_net']}
    donors.append(dict(cell=x['cell'],day=x['day'],rows=out,total=total))

new=[]
for k,v in dt.items():
    cell,day,phase=k.split('|')
    if phase!='OPEN':continue
    rr=[r for r in v['layers'] if r['opened'].startswith(day)]
    new.append(dict(cell=cell,day=day,actual_new_layers=len(rr),
        actual_new_principal=sum((D(r['principal']) for r in rr),Z),actual_new_profit=sum((D(r['profit_giveback']) for r in rr),Z),
        rows=rr))

before={r['layer']:r for r in dt['C20|2025-08-22|CLOSE']['layers']}
after={r['layer']:r for r in dt['C20|2025-08-25|OPEN']['layers']}
bridge=[]
for lid,b in after.items():
    a=before[lid];q=D(b['qty']);ratio=q/D(a['qty']);assert q<=D(a['qty'])
    assert a['raw_floor']==b['raw_floor']
    assert abs(D(a['cost_including_allocated_buy_fees'])-D(b['cost_including_allocated_buy_fees']))<TOL
    bridge.append(dict(layer=lid,sid=b['sid'],qty=q,
        close_principal_same_remaining_qty=D(a['principal'])*ratio,
        close_profit_same_remaining_qty=D(a['profit_giveback'])*ratio,
        open_principal=D(b['principal']),open_profit=D(b['profit_giveback']),
        principal_increase=D(b['principal'])-D(a['principal'])*ratio,
        profit_increase=D(b['profit_giveback'])-D(a['profit_giveback'])*ratio))
total={k:sum((r[k] for r in bridge),Z) for k in ['close_principal_same_remaining_qty','close_profit_same_remaining_qty','open_principal','open_profit','principal_increase','profit_increase']}
assert abs(total['close_principal_same_remaining_qty']+total['close_profit_same_remaining_qty']-D(c['close_conditional_existing_risk_after_all_D']))<TOL
assert abs(total['principal_increase']+total['profit_increase']-D(c['open_vs_close_after_D_risk_increase']))<TOL
save('CASE_VIEWS.json',dict(healthy_donors=donors,actual_new_capital=new,Aug25_same_inventory_price_bridge=dict(totals=total,layers=bridge),
    important='Donor base components describe remaining exposure if retained; no action is cancelled and no freed cash is invented.'))

ch=[r for r in su if r['cell']=='C10' and r['day'].startswith('2025-08')]
assert len(ch)==9
save('CHUNZHONG_RISK_SUMMARY.json',dict(rows=ch,all_nine_have_positive_profit_risk=all(D(r['profit_giveback'])>0 for r in ch),
    majority_profit_days=sum(D(r['profit_share'])>D('.5') for r in ch),
    minimum_profit_share=min(D(r['profit_share']) for r in ch),maximum_profit_share=max(D(r['profit_share']) for r in ch),
    inference_limit='End-of-close balances are not each serial conditional candidate preview; no removal-of-budget feasibility or counterfactual fill computed.'))
daily_path=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/g-s-C-August-continuation-v1-20261102/analysis/C10-DAILY.json')
daily={r['day']:r for r in json.loads(daily_path.read_text())}
for r in ch:
    assert abs(D(daily[r['day']]['risk'])-D(r['original_risk']))<TOL
    assert daily[r['day']]['Q'].get('603516.SH',0)==0

save('RECOVERY_NOTES.json',dict(financial_events=0,
    initial_export_denial='Both Jan13 OPEN restores rejected stale Jan13 registry SHA before loading checkpoint.',
    new_evidence='Existing audited January-end CONTINUATION_CHECKPOINTS records the current append-only registry SHA and original Jan13 registry archive.',
    resolution='Used that explicit trusted index; original restore/clock/source/certificate guards unchanged; exports verify full state unchanged.',
    transport='First attempt failed to create process: exec-server transport disconnected; pwd confirmed transport recovery before retry.'))
sources=read('SOURCE_SHA256.json')
for p in [causal,daily_path,O/'2022-C10-EXPORT-PROOF.json',O/'2022-C_BATCH20-EXPORT-PROOF.json',
 Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/g-s-historical-native-prefix-20261101/native_capital.py'),
 Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/g-broad-s-concentrated-native-r2-20261101/policy.py')]:
    sources[str(p)]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
save('SOURCE_SHA256.json',sources)
print('Aug25 bridge',json.dumps(total,default=str))
print('nine days profit shares',[(r['day'],str(round(D(r['profit_share'])*100,2))) for r in ch])
print('donor totals',json.dumps([{k:v for k,v in r.items() if k!='rows'} for r in donors],default=str))
