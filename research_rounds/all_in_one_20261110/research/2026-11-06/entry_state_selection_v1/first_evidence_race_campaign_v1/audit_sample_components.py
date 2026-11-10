from campaign_engine import *
a=pd.read_csv(O/'sample/ATTEMPTS.csv',low_memory=False);a=a[a.policy_arm.eq('A')]
b=pd.read_csv(R/'cross_window_entry_mechanism_v1/BASELINE_EXISTING_CONTEXT.csv',low_memory=False).set_index('round_id')
fields={'core_return':'net_return_on_buy_cash','core_buy_fee':'entry_fee','core_dividend_net80':'dividend_net80_total','core_buy_cash':'total_buy_cash'};rows=[]
for r in a.to_dict('records'):
    q=b.loc[r['baseline_round_id']]
    if not q.evidence_usable_closed:continue
    out=dict(round_id=q.name)
    for old,new in fields.items():
        diff=r[new]-q[old];assert abs(diff)<1e-7,(q.name,old,diff);out[old+'_delta']=diff
    diff=r['all_fees']-r['entry_fee']-q.core_sell_fee;assert abs(diff)<1e-7;out['core_sell_fee_delta']=diff;rows.append(out)
pd.DataFrame(rows).to_csv(O/'SAMPLE_COMPONENT_RECONCILIATION.csv',index=False)
(O/'SAMPLE_COMPONENT_QA.json').write_text(json.dumps(dict(usable_A_rows=len(rows),all_components_match=True,source_hashes={str(p):sha(p) for p in [O/'sample/ATTEMPTS.csv',R/'cross_window_entry_mechanism_v1/BASELINE_EXISTING_CONTEXT.csv',Path(__file__)]}),indent=2)+'\n')
print('PASS',len(rows))
