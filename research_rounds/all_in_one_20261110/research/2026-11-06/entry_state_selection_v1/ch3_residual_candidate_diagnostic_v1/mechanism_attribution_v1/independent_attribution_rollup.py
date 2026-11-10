"""Final read-only summary and source-integrity checks. Writes audit outputs only."""
from pathlib import Path
import hashlib,json
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;L=O.parent/'lifecycle_comparison_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def csv(p):return pd.read_csv(p,float_precision='round_trip',low_memory=False)
def eq(a,b):assert np.isclose(a,b,rtol=1e-11,atol=1e-7,equal_nan=True),(a,b)
audits=['INDEPENDENT_EXANTE_AUDIT.json','INDEPENDENT_CASH_AUDIT.json','INDEPENDENT_PAIR_FEATURE_AUDIT.json']
for n in audits:
    q=json.loads((O/n).read_text());assert q['status'].startswith('PASS')
    for name,h in q.get('inputs',q.get('audited_input_hashes',q.get('source_hashes',{}))).items():assert sha(O/name)==h,name
source=json.loads((O/'cash_source_manifest.json').read_text())['files']
for n,h in source.items():assert sha(L/n)==h,n
exante_sources=json.loads((O/'EXANTE_SOURCE_HASHES.json').read_text())
for n,h in exante_sources.items():assert sha(n)==h,n
z=csv(L/'report/CORE_AND_FULL_ROUNDS.csv');z['window']=z.window.astype(str)
m=csv(O/'cash_arm_metrics.csv');c=csv(O/'cash_stock_comparison.csv');c['window']=c.window.astype(str)
classes=csv(O/'cash_path_class_summary.csv')
fields={'core':{'net':'core_net','raw':'core_gross_raw_open_pnl','slippage':'core_slippage_drag','gross':'core_gross_after_slippage_pnl','fees':'core_fees','net80':'core_dividend_net80','buy_cash':'core_buy_cash','return':'core_return'},'full':{'net':'net_pnl','raw':'full_gross_raw_open_pnl','slippage':'full_slippage_drag','gross':'full_gross_after_slippage_pnl','fees':'full_fees','net80':'full_dividend_net80','buy_cash':'total_buy_cash','return':'net_return_on_buy_cash'}}
for r in m.itertuples():
    allr=z[z.window.eq(str(r.window))&z.arm.eq(r.arm)];g=allr[allr.evidence_usable_closed];f=fields[r.layer];v=g[f['net']];pos=v[v>0];neg=v[v<0]
    assert r.permissions==len(allr) and r.confirmed_entries==allr.entry_day.notna().sum() and r.usable_closed==len(g)
    assert r.execution_unknown==allr.status.str.contains('UNKNOWN').sum()
    assert r.closed_financial_unknown==(allr.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')&~allr.evidence_usable_closed).sum()
    assert r.nofill==allr.status.str.contains('NOFILL').sum()
    assert r.winners==len(pos) and r.losers==len(neg) and r.zeros==v.eq(0).sum()
    for k,col in f.items():eq(getattr(r,'observed_'+k),g[col].sum())
    for k,value in {'winner_net':pos.sum(),'loser_net':neg.sum(),'mean_win':pos.mean(),'mean_loss':neg.mean(),'mean_net':v.mean(),'mean_return':g[f['return']].mean(),'win_rate':len(pos)/len(g)}.items():eq(getattr(r,k),value)
for r in c.itertuples():
    ca,ra=r.comparison.split('_MINUS_');a=z[z.window.eq(r.window)&z.arm.eq(ca)&z.sid.eq(r.sid)];b=z[z.window.eq(r.window)&z.arm.eq(ra)&z.sid.eq(r.sid)]
    if len(a)==len(b)==0:kind='BOTH_NO_PERMISSION'
    elif not len(a):kind='C_NO_PERMISSION_R_ACTUAL_OR_UNRESOLVED'
    elif not len(b):kind='R_NO_PERMISSION_C_ACTUAL_OR_UNRESOLVED'
    elif a.status.str.contains('NOFILL').all() or b.status.str.contains('NOFILL').all():kind='ONE_OR_BOTH_ONLY_NOFILL'
    elif set(a.event_id)==set(b.event_id):kind='SAME_EVENT_SET'
    elif a.entry_day.notna().any() and b.entry_day.notna().any():kind='BOTH_ACTUAL_DIFFERENT_EVENT_SETS'
    else:kind='PARTICIPATION_UNKNOWN'
    assert r.path_class==kind
for r in classes.itertuples():
    g=c[c.window.eq(str(r.window))&c.comparison.eq(r.comparison)&c.path_class.eq(r.path_class)]
    assert r.stocks==len(g) and r.complete_stocks==g.complete_known.sum() and r.unknown_stocks==(~g.complete_known).sum()
    assert r.c_observed_n==g.c_usable_closed.sum() and r.r_observed_n==g.r_usable_closed.sum()
    eq(r.observed_subtotal_bridge,g[r.layer+'_observed_subtotal_bridge_net'].sum())
    eq(r.known_complete_stock_net_delta,g.loc[g.complete_known,r.layer+'_complete_delta_net'].sum())
for n,h in source.items():assert sha(L/n)==h,n
out=dict(status='PASS_READ_ONLY_MECHANISM_ATTRIBUTION',independent_audit_hashes={n:sha(O/n) for n in audits},cash_arm_metric_rows_verified=len(m),stock_path_classifications_reconstructed=len(c),path_class_summary_rows_verified=len(classes),sealed_lifecycle_source_files_unchanged=len(source),exante_sources_unchanged=len(exante_sources),new_economic_runs=0,new_consumers=0,new_filters=0,scope='Post-result descriptive and arithmetic audit, not causal/PIT/OOS or trading validation',limitations=['RAW_MOM11 controls the formation month window but does not isolate normalization, intercept removal and risk-factor removal effects.','Native industry beta is total static-industry sensitivity; it is not market-neutral, leave-one-stock-out industry alpha or a validated future elasticity measure.','Prior-month date support is verified, but current revision factor, adjustment and static mapping vintages remain unknown.','Same-exit pairs condition on realized exits. Contributions and leave-one-out deletion cannot justify a deployable filter.','Cash aggregates are independent stock-round path sums rather than a shared, capital-constrained account.','Small or unchanged loser averages are not an improvement claim; execution and financial UNKNOWN stay in coverage and propagate to complete stock deltas.'],review_notes=['Decimal concentration ranks were checked from original CSV strings. A float-only near-tie audit assertion was replaced; production files were not changed.','Known-complete class totals can be zero for an empty known subset. Always read complete/unknown counts, not this sum as a zero outcome for unknown stocks.'])
(O/'INDEPENDENT_ATTRIBUTION_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(out,ensure_ascii=False,indent=2))
