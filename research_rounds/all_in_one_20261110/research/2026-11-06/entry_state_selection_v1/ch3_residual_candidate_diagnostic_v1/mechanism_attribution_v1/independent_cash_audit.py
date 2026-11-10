"""Read-only complete-stock, unknown-propagation, matching and cash-identity audit."""
from pathlib import Path
import hashlib,json,csv as csvlib
from decimal import Decimal, localcontext
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;L=O.parent/'lifecycle_comparison_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def csv(p):return pd.read_csv(p,float_precision='round_trip',low_memory=False)
def eq(a,b):assert np.allclose(a,b,rtol=1e-11,atol=1e-7,equal_nan=True),(a,b)
source=json.loads((O/'cash_source_manifest.json').read_text())
for n,h in source['files'].items():assert sha(L/n)==h,(n,'source drift')
qa=json.loads((O/'cash_qa.json').read_text());assert sha(O/'cash_compute.py')==qa['script_sha256'] and sha(O/'cash_contract.json')==qa['contract_sha256']
z=csv(L/'report/CORE_AND_FULL_ROUNDS.csv');z['window']=z.window.astype(str);index=z.set_index('round_id')
stock=csv(O/'cash_arm_stock_totals.csv');stock['window']=stock.window.astype(str)
comp=csv(O/'cash_stock_comparison.csv');comp['window']=comp.window.astype(str)
pairs=csv(O/'cash_unique_same_exit_decomposition.csv');pairs['window']=pairs.window.astype(str)
coverage=csv(O/'cash_round_coverage.csv');coverage['window']=coverage.window.astype(str)
common=csv(O/'cash_common_event_qa.csv');common['window']=common.window.astype(str)
fields={'core':{'net':'core_net','raw':'core_gross_raw_open_pnl','slippage':'core_slippage_drag','gross':'core_gross_after_slippage_pnl','fees':'core_fees','net80':'core_dividend_net80','buy_cash':'core_buy_cash','return':'core_return'},'full':{'net':'net_pnl','raw':'full_gross_raw_open_pnl','slippage':'full_slippage_drag','gross':'full_gross_after_slippage_pnl','fees':'full_fees','net80':'full_dividend_net80','buy_cash':'total_buy_cash','return':'net_return_on_buy_cash'}}
universes={};all_actions={};all_claims={};all_ledgers={}
for window in ['2022','2024_924']:
    for arm in ['A_UNION_B','RAW_MOM11','CH3_RM']:
        base=L/window/arm;d=csv(base/'DECISIONS.csv')
        universe=set(d.sid)
        if window in universes:assert universe==universes[window]
        else:universes[window]=universe
        assert set(stock.loc[stock.window.eq(window)&stock.arm.eq(arm),'sid'])==universe
        assert set(d.loc[d.selected,'round_id'])==set(z.loc[z.window.eq(window)&z.arm.eq(arm),'round_id'])
        all_actions[(window,arm)]=csv(base/'ACTIONS.csv');all_ledgers[(window,arm)]=csv(base/'CLAIM_LEDGER.csv')
        all_claims[(window,arm)]=json.loads((base/'CLAIMS.json').read_text())
for r in stock.itertuples():
    rr=z[z.window.eq(r.window)&z.arm.eq(r.arm)&z.sid.eq(r.sid)];usable=rr[rr.evidence_usable_closed]
    nofill=rr.status.str.contains('NOFILL');unresolved=rr[~(rr.evidence_usable_closed|nofill)]
    assert r.permissions==len(rr) and r.confirmed_entries==rr.entry_day.notna().sum() and r.usable_closed==len(usable)
    assert r.complete_known==(len(unresolved)==0)
    reported=set(str(r.unresolved_round_ids).split(';')) if pd.notna(r.unresolved_round_ids) else set()
    assert reported==set(unresolved.round_id)
    for layer,cols in fields.items():
        for k,col in cols.items():
            observed=getattr(r,layer+'_observed_'+k)
            if len(usable):eq(observed,usable[col].sum())
            else:assert pd.isna(observed)
            if k!='return':
                complete=getattr(r,layer+'_complete_'+k)
                if len(unresolved):assert pd.isna(complete)
                else:eq(complete,usable[col].sum())
        net=usable[cols['net']]
        assert getattr(r,layer+'_wins')==net.gt(0).sum() and getattr(r,layer+'_losses')==net.lt(0).sum() and getattr(r,layer+'_zeros')==net.eq(0).sum()
        assert getattr(r,layer+'_tail50')==usable[cols['return']].ge(.5).sum()
sindex=stock.set_index(['window','arm','sid'])
for r in comp.itertuples():
    c_arm,r_arm=r.comparison.split('_MINUS_');c=sindex.loc[(r.window,c_arm,r.sid)];base=sindex.loc[(r.window,r_arm,r.sid)]
    complete=c.complete_known and base.complete_known
    assert r.complete_known==complete
    for layer in fields:
        for k in ['net','raw','slippage','gross','fees','net80','buy_cash']:
            a=c[layer+'_observed_'+k];b=base[layer+'_observed_'+k]
            eq(getattr(r,'c_'+layer+'_observed_'+k),a);eq(getattr(r,'r_'+layer+'_observed_'+k),b)
            eq(getattr(r,layer+'_observed_subtotal_bridge_'+k),(0 if pd.isna(a) else a)-(0 if pd.isna(b) else b))
            if complete:eq(getattr(r,layer+'_complete_delta_'+k),c[layer+'_complete_'+k]-base[layer+'_complete_'+k])
            else:assert pd.isna(getattr(r,layer+'_complete_delta_'+k))
assert not coverage.duplicated(['comparison','round_id']).any()
expected_pair_ids=set();expected_common_ids=set();common_count=0
for window in ['2022','2024_924']:
    for c_arm,r_arm in [('CH3_RM','RAW_MOM11'),('CH3_RM','A_UNION_B')]:
        contrast=c_arm+'_MINUS_'+r_arm;cz=z[z.window.eq(window)&z.arm.eq(c_arm)];rz=z[z.window.eq(window)&z.arm.eq(r_arm)]
        sub=coverage[coverage.window.eq(window)&coverage.comparison.eq(contrast)]
        assert set(sub.round_id)==set(cz.round_id)|set(rz.round_id)
        for r in sub.itertuples():
            original=index.loc[r.round_id]
            assert original.event_id==r.event_id and original.arm==r.arm and original.sid==r.sid
            assert original.evidence_usable_closed==r.evidence_usable_closed
            for layer in fields:
                if original.evidence_usable_closed:eq(getattr(r,layer+'_net_observed'),original[fields[layer]['net']])
                else:assert pd.isna(getattr(r,layer+'_net_observed'))
        for sid in universes[window]:
            a=cz[cz.sid.eq(sid)];b=rz[rz.sid.eq(sid)];same=set(a.event_id)&set(b.event_id)
            for eid in same:
                ca=a[a.event_id.eq(eid)].iloc[0];ra=b[b.event_id.eq(eid)].iloc[0]
                expected_common_ids.add((window,contrast,eid));common_count+=1
                for col in ['status','entry_day','exit_day','evidence_usable_closed','financial_coverage_status']:
                    assert ca[col]==ra[col] or pd.isna(ca[col]) and pd.isna(ra[col])
                for col in ['core_net','net_pnl','entry_q','entry_price','exit_price','core_dividend_net80','dividend_net80_total']:eq(ca[col],ra[col])
                aa=all_actions[(window,c_arm)];bb=all_actions[(window,r_arm)]
                cols=['day','side','q','price','fee','reason']
                pd.testing.assert_frame_equal(aa[aa.round_id.eq(ca.round_id)][cols].reset_index(drop=True),bb[bb.round_id.eq(ra.round_id)][cols].reset_index(drop=True),check_dtype=False,check_exact=False,atol=1e-7,rtol=1e-12)
                aa=all_ledgers[(window,c_arm)];bb=all_ledgers[(window,r_arm)]
                cols=['economic_event_id','evidence_version','day','event','cash_delta','receivable_delta','amount','record_q','core_record_q','available_from']
                pd.testing.assert_frame_equal(aa[aa.round_id.eq(ca.round_id)][cols].reset_index(drop=True),bb[bb.round_id.eq(ra.round_id)][cols].reset_index(drop=True),check_dtype=False,check_exact=False,atol=1e-7,rtol=1e-12)
                keys=['economic_event_id','record_q','core_record_q','amount','core_amount','recognized','settled']
                ac=[{k:x[k] for k in keys} for x in all_claims[(window,c_arm)] if x['owner_round_id']==ca.round_id]
                bc=[{k:x[k] for k in keys} for x in all_claims[(window,r_arm)] if x['owner_round_id']==ra.round_id]
                assert ac==bc
            a=a[~a.event_id.isin(same)];b=b[~b.event_id.isin(same)]
            for day in set(a.exit_day.dropna())&set(b.exit_day.dropna()):
                ac=a[a.exit_day.eq(day)];bc=b[b.exit_day.eq(day)]
                if len(ac)==len(bc)==1 and ac.iloc[0].evidence_usable_closed and bc.iloc[0].evidence_usable_closed:
                    expected_pair_ids.add((window,contrast,ac.iloc[0].round_id,bc.iloc[0].round_id))
assert set(zip(common.window,common.comparison,common.event_id))==expected_common_ids
assert set(zip(pairs.window,pairs.comparison,pairs.c_round_id,pairs.r_round_id))==expected_pair_ids
assert not pairs.duplicated(['comparison','c_round_id']).any() and not pairs.duplicated(['comparison','r_round_id']).any()
for r in pairs.itertuples():
    c=index.loc[r.c_round_id];b=index.loc[r.r_round_id]
    assert c.sid==b.sid==r.sid and c.exit_day==b.exit_day==r.exit_day and c.entry_day!=b.entry_day and c.event_id!=b.event_id
    assert c.evidence_usable_closed and b.evidence_usable_closed
    qC,qR=c.entry_q,b.entry_q;pC,pR=c.core_net/qC,b.core_net/qR
    eq(r.core_quantity_component,(qC-qR)*(pC+pR)/2);eq(r.core_per_share_component,(pC-pR)*(qC+qR)/2)
    eq(r.core_delta_net,c.core_net-b.core_net);eq(r.core_quantity_component+r.core_per_share_component,r.core_delta_net)
    for layer,cols in fields.items():
        for k,col in cols.items():eq(getattr(r,'c_'+layer+'_'+k),c[col]);eq(getattr(r,'r_'+layer+'_'+k),b[col]);eq(getattr(r,layer+'_delta_'+k),c[col]-b[col])
        eq(getattr(r,layer+'_delta_net'),getattr(r,layer+'_delta_raw')-getattr(r,layer+'_delta_slippage')-getattr(r,layer+'_delta_fees')+getattr(r,layer+'_delta_net80'))
summary=csv(O/'cash_summary.csv');means=csv(O/'cash_mean_decomposition.csv')
for r in summary.itertuples():
    c_arm,r_arm=r.comparison.split('_MINUS_');cols=fields[r.layer];c=z[z.window.eq(str(r.window))&z.arm.eq(c_arm)&z.evidence_usable_closed];b=z[z.window.eq(str(r.window))&z.arm.eq(r_arm)&z.evidence_usable_closed]
    sc=c[cols['net']].sum();sr=b[cols['net']].sum();sub=comp[comp.window.eq(str(r.window))&comp.comparison.eq(r.comparison)]
    assert r.all_market_stocks==len(sub) and r.complete_stocks==sub.complete_known.sum() and r.unknown_stocks==(~sub.complete_known).sum()
    assert r.c_usable_n==len(c) and r.r_usable_n==len(b);eq(r.observed_subtotal_delta,sc-sr)
    eq(r.complete_stock_net_delta,sub[r.layer+'_complete_delta_net'].sum());eq(r.unknown_stock_observed_subtotal_bridge,sub.loc[~sub.complete_known,r.layer+'_observed_subtotal_bridge_net'].sum())
    eq(r.complete_stock_net_delta+r.unknown_stock_observed_subtotal_bridge,r.observed_subtotal_delta)
for r in means.itertuples():
    w=str(r.window);p=pairs[pairs.window.eq(w)&pairs.comparison.eq(r.comparison)];scale=(1/r.c_usable_n+1/r.r_usable_n)/2
    eq(r.mean_delta,r.c_sum/r.c_usable_n-r.r_sum/r.r_usable_n);eq(r.mean_sum_coefficient,scale)
    eq(r.same_exit_sum_delta,p[r.layer+'_delta_net'].sum());eq(r.unmatched_observed_sum_delta,r.observed_sum_delta-r.same_exit_sum_delta)
    eq(r.observed_count_mean_component,(1/r.c_usable_n-1/r.r_usable_n)*(r.c_sum+r.r_sum)/2)
    eq(r.mean_delta,r.same_exit_total_mean_component+r.unmatched_mean_component+r.observed_count_mean_component)
    if r.layer=='core':eq(r.same_exit_quantity_sum,p.core_quantity_component.sum());eq(r.same_exit_per_share_sum,p.core_per_share_component.sum());eq(r.same_exit_quantity_mean_component+r.same_exit_per_share_mean_component,r.same_exit_total_mean_component)
ranked=csv(O/'cash_ranked_stock_deltas.csv');concentration=csv(O/'cash_concentration.csv');deletion=csv(O/'cash_leave_one_stock_out.csv')
exact_rank_groups={}
with (O/'cash_ranked_stock_deltas.csv').open() as f:
    for row in csvlib.DictReader(f):exact_rank_groups.setdefault(tuple(row[k] for k in ['window','comparison','layer','scope']),[]).append(row)
with localcontext() as ctx:
    ctx.prec=60
    for key,rows in exact_rank_groups.items():
        actual=sorted(rows,key=lambda r:int(r['rank_abs']))
        expected=sorted(rows,key=lambda r:(-abs(Decimal(r['contribution'])),r['sid']))
        assert [r['sid'] for r in actual]==[r['sid'] for r in expected],key
        assert [int(r['rank_abs']) for r in actual]==list(range(1,len(actual)+1))
        for r in rows:assert abs(Decimal(r['contribution']))==Decimal(r['absolute_contribution'])
for (window,comparison,layer,scope),g in ranked.groupby(['window','comparison','layer','scope']):
    sub=comp[comp.window.eq(str(window))&comp.comparison.eq(comparison)]
    if scope=='COMPLETE_STOCK_DELTA':expected=dict(zip(sub[sub.complete_known].sid,sub.loc[sub.complete_known,layer+'_complete_delta_net']))
    elif scope=='OBSERVED_SUBTOTAL_BRIDGE_NOT_FULL_STOCK_DELTA':expected=dict(zip(sub.sid,sub[layer+'_observed_subtotal_bridge_net']))
    elif scope=='OBSERVED_MEAN_GAP_ADDITIVE_CONTRIBUTION':
        ss=summary[summary.window.astype(str).eq(str(window))&summary.comparison.eq(comparison)&summary.layer.eq(layer)].iloc[0]
        expected={r.sid:(0 if pd.isna(getattr(r,'c_'+layer+'_observed_net')) else getattr(r,'c_'+layer+'_observed_net'))/ss.c_usable_n-(0 if pd.isna(getattr(r,'r_'+layer+'_observed_net')) else getattr(r,'r_'+layer+'_observed_net'))/ss.r_usable_n for r in sub.itertuples()}
    elif scope.startswith('SAME_EXIT_PAIR_'):
        pp=pairs[pairs.window.eq(str(window))&pairs.comparison.eq(comparison)];field=scope[len('SAME_EXIT_PAIR_'):]
        expected={r.c_round_id+' vs '+r.r_round_id:getattr(r,field) for r in pp.itertuples()}
    else:raise AssertionError(scope)
    assert set(g.sid)==set(expected) and g.sid.is_unique
    for r in g.itertuples():eq(r.contribution,expected[r.sid])
for r in concentration.itertuples():
    x=ranked[ranked.window.astype(str).eq(str(r.window))&ranked.comparison.eq(r.comparison)&ranked.layer.eq(r.layer)&ranked.scope.eq(r.scope)].sort_values('rank_abs');v=x.contribution.to_numpy();n=min(r.top_k,len(x))
    assert len(x)==r.population and r.top_actual==n and r.positive==(v>0).sum() and r.negative==(v<0).sum() and r.zero==(v==0).sum()
    eq(r.total_signed,v.sum());eq(r.total_absolute,np.abs(v).sum());eq(r.top_signed,v[:n].sum());eq(r.top_absolute,np.abs(v[:n]).sum())
    if np.abs(v).sum():eq(r.share_absolute,np.abs(v[:n]).sum()/np.abs(v).sum())
    eq(r.delete_one_min,np.min(v.sum()-v));eq(r.delete_one_max,np.max(v.sum()-v))
    assert r.top_ids==';'.join(x.sid.tolist()[:n])
for r in deletion.itertuples():
    w=str(r.window);s=summary[summary.window.astype(str).eq(w)&summary.comparison.eq(r.comparison)&summary.layer.eq(r.layer)].iloc[0]
    row=comp[comp.window.eq(w)&comp.comparison.eq(r.comparison)&comp.sid.eq(r.sid)].iloc[0]
    c=row['c_'+r.layer+'_observed_net'];b=row['r_'+r.layer+'_observed_net'];c=0 if pd.isna(c) else c;b=0 if pd.isna(b) else b
    cn=s.c_usable_n-row.c_usable_closed;bn=s.r_usable_n-row.r_usable_closed
    assert r.c_n_after==cn and r.r_n_after==bn
    eq(r.observed_subtotal_delta_after_deletion,s.observed_subtotal_delta-c+b)
    eq(r.observed_mean_gap_after_deletion,(s.c_observed_net-c)/cn-(s.r_observed_net-b)/bn)
    if row.complete_known:eq(r.complete_stock_delta_after_deletion,s.complete_stock_net_delta-row[r.layer+'_complete_delta_net'])
    else:assert pd.isna(r.complete_stock_delta_after_deletion)
report=dict(status='PASS_READ_ONLY_CASH_ATTRIBUTION_AUDIT',source_rounds=len(z),all_arm_stock_rows=len(stock),all_comparison_stock_rows=len(comp),all_round_comparison_rows=len(coverage),common_events_reconstructed=common_count,unique_same_exit_pairs_independently_reconstructed=len(expected_pair_ids),
            complete_stock_unknowns_propagated=True,empty_observed_subtotals_remain_null=True,only_no_permission_or_explicit_nofill_can_be_known_zero=True,
            pair_selection_no_winner_filter=True,symmetric_quantity_per_share_and_gross_net_identities=True,mean_count_identity=True,concentration_and_leave_one_stock_out_verified=True,new_economic_runs=0,
            exact_decimal_rank_groups_verified=len(exact_rank_groups),fixed_original_denominator_contribution_removal_distinct_from_recomputed_leave_one_out_means=True,
            limitations=['Observed subtotal bridges are partial arithmetic, not complete-stock gains when any path is UNKNOWN.','Same-exit matching and quantity/per-share splitting are post-outcome identities, not causal entry-price or position-sizing interventions.','Concentration and deleting a stock describe this same sample, not out-of-sample robustness or an executable beta filter.'],
            audited_input_hashes={n:sha(O/n) for n in ['cash_contract.json','cash_compute.py','cash_arm_stock_totals.csv','cash_stock_comparison.csv','cash_unique_same_exit_decomposition.csv','cash_mean_decomposition.csv','cash_concentration.csv','cash_leave_one_stock_out.csv']})
(O/'INDEPENDENT_CASH_AUDIT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
