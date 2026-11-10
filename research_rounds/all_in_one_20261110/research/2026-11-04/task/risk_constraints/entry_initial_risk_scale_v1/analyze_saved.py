"""One existing .25% nominal reference, saved entry fields only. No engine."""
from pathlib import Path
from decimal import Decimal as D,getcontext
from collections import Counter
import json,hashlib
getcontext().prec=50
H=Path(__file__).resolve().parent;T=H.parent.parent;P=T/'loss_correction/entry_risk_commitment_review';R=T/'risk_constraints';Z=D(0);REF=D('.25')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def agg(xs):
    pos=[r for r in xs if D(r['net'])>0];neg=[r for r in xs if D(r['net'])<0];opened=[r for r in xs if D(r['qty'])>0]
    return dict(layers=len(xs),stocks=len({r['sid']for r in xs}),actual_buy_cash=sum((D(r['cost'])for r in xs),Z),original_cutoff_net=sum((D(r['net'])for r in xs),Z),
        positive_original_net=sum((D(r['net'])for r in pos),Z),negative_original_net=sum((D(r['net'])for r in neg),Z),negative_layers_actual_buy_cash=sum((D(r['cost'])for r in neg),Z),
        open_layers=len(opened),open_layers_original_cutoff_net=sum((D(r['net'])for r in opened),Z),old_reference_unknown_flags=Counter(z for r in xs for z in r['reference_unknown_reasons']))
def dist(xs,key):
    a=sorted(D(r[key])for r in xs);return dict(observations=len(a),minimum=a[0],maximum=a[-1],quantiles={str(p):a[int((len(a)-1)*float(p))]for p in ['.10','.25','.50','.75','.90','.95','.99']},method='fixed empirical lower order-statistics; descriptive only, no performance-selected bins')
def main():
    files=[P/'2022_2024_ENTRIES.json',P/'strong_ENTRIES.json',R/'no60_continuation2023_finance/analysis/2022_2023/PVR_NO_CONFIRMED60/LAYERS.json',R/'ma63_information_diagnostic_v1/POST_OCT8_303_ACTUAL_FILLS.json',P/'FINAL_REVIEW_BINDING.json',P/'FINAL_DISPOSITION_STOP.txt',H/'analyze_saved.py']
    hashes={str(p):sha(p)for p in files};save(H/'INPUT_FREEZE.json',dict(scope='One existing .25%NAV nominal initial-risk reference; no new sizing/cap/grid/ledger/account',source_sha256=hashes))
    base=read(files[0]);strong=read(files[1]);cut=read(files[2]);mp={r['layer']:r for r in cut};two=[dict(r)for r in base if r['opened'][:4]in ['2022','2023']]
    assert len(two)==len(cut)==1557 and {r['layer']for r in two}==set(mp)
    for r in two:
        old=mp[r['layer']];assert (r['sid'],r['role'],r['opened'])==(old['sid'],old['role'],old['opened'])
        for k in ['cost','net','qty','value']:assert D(str(r[k]))==D(str(old[k]));r[k]=old[k]
        assert D(r['qty'])==0
    ids={r['layer']for r in read(files[3])['fills']};post=[r for r in base if r['layer']in ids];assert len(post)==303
    populations={'2022_2023_at_2023_cutoff':two,'post_Oct8_new303_at_2024_cutoff':post,'strong_at_2026Jun30_cutoff':strong};results={};thin=[]
    for label,rs in populations.items():
        for r in rs:
            p=D(r['actual_execution_price']);f=D(r['initial_raw_floor']);r['positive_initial_protection_distance_pct']=max(Z,(p-f)/p)*100
        groups={'mobile_above_reference':[r for r in rs if r['role']=='mobile'and D(r['actual_initial_risk_pct_decisionNAV'])>REF],
                'mobile_at_or_below_reference':[r for r in rs if r['role']=='mobile'and D(r['actual_initial_risk_pct_decisionNAV'])<=REF],
                'core_separate_original_contract':[r for r in rs if r['role']=='core']}
        mobile=[r for r in rs if r['role']=='mobile'];hi=groups['mobile_above_reference'];total=agg(rs)
        results[label]=dict(total=total,groups={k:agg(v)for k,v in groups.items()},
            mobile_continuous=dict(initial_nominal_risk_pct_NAV=dist(mobile,'actual_initial_risk_pct_decisionNAV'),positive_initial_protection_distance_pct=dist(mobile,'positive_initial_protection_distance_pct')),
            core_continuous_initial_nominal_risk_pct_NAV=dist(groups['core_separate_original_contract'],'actual_initial_risk_pct_decisionNAV'),
            absolute_reference_cross_old_R0_related_labels=dict(Counter(r['risk_reference_class']for r in hi)),
            above_reference_mobile_fraction=D(len(hi))/len(mobile),above_reference_buycash_fraction_of_all=agg(hi)['actual_buy_cash']/total['actual_buy_cash'],
            above_reference_negative_magnitude_fraction_of_all=agg(hi)['negative_original_net']/total['negative_original_net'],
            economic_scope='Original entry-cohort contributions through named saved cutoff. No deleted/resized-trade counterfactual or capital reinvestment. .25 is nominal reference, not original core all-in risk contract.')
        for r in rs:
            thin.append(dict(population=label,**{k:r[k]for k in ['layer','sid','name','role','opened','decision_at','budget_order','decision_NAV','actual_fill_quantity','actual_execution_price','initial_raw_floor','actual_initial_nominal_risk','actual_initial_risk_pct_decisionNAV','positive_initial_protection_distance_pct','cost','net','qty','risk_reference_class','reference_unknown_reasons']},above_nominal_reference=r['role']=='mobile'and D(r['actual_initial_risk_pct_decisionNAV'])>REF))
    save(H/'RESULTS.json',results);save(H/'THIN_ENTRIES.json',thin)
    examples=[]
    for label,rs in populations.items():
        hi=[r for r in rs if r['role']=='mobile'and D(r['actual_initial_risk_pct_decisionNAV'])>REF]
        examples.extend(dict(population=label,selection=kind,**{k:r[k]for k in ['layer','sid','name','decision_at','actual_initial_risk_pct_decisionNAV','positive_initial_protection_distance_pct','cost','net','qty']})for kind,r in [('largest_original_positive_associated',max(hi,key=lambda r:D(r['net']))),('largest_original_negative_associated',min(hi,key=lambda r:D(r['net'])))])
    save(H/'ASSOCIATED_POSITIVE_NEGATIVE_EXAMPLES.json',examples);assert all(sha(p)==h for p,h in hashes.items())
    save(H/'CUTOFF_IDENTITY.json',dict(original_2023_layer_source=str(files[2]),source_sha256=sha(files[2]),layers=1557,mobile=1199,core=358,net_cost_qty_value_exact_per_layer_to_saved_enriched_entry_subset=True,all_qty_zero=True,net=sum((D(r['net'])for r in cut),Z),actual_money_uses_2023_source_not_2024=True))
    save(H/'COMPLETED.json',dict(status='SAVED_INITIAL_RISK_ASSOCIATION_STOP_NOT_MAIN_DRIVER',new_models=0,new_accounts=0,new_ledgers=0,new_sizing_rules=0,new_reference_parameters=0,reference_pct_NAV='.25',source_post_exact=True))
    print('INITIAL_RISK_SCALE_READY')
if __name__=='__main__':main()
