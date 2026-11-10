"""Read parent's frozen R and original action links, never calculate a new ratio."""
from pathlib import Path
from collections import Counter
import csv
import hashlib
import json

OUT=Path(__file__).resolve().parent
BASE=OUT.parent
HASH={}
def bind(path):
    p=Path(path).resolve();HASH[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(path):return json.loads(bind(path).read_text())
def save(name,value):(OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def csvwrite(name,rows):
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with(OUT/name).open('w',newline='')as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        w.writerows({k:json.dumps(v,ensure_ascii=False,separators=(',',':'))if isinstance(v,(dict,list))else v for k,v in r.items()}for r in rows)

def main():
    bind(__file__);bind(BASE/'FROZEN_DIAGNOSTIC.txt')
    originals=read(OUT/'ORIGINAL_CLASSIFICATION_59.json')
    original_bykey={(r['sid'],r['date']):r for r in originals}
    with bind(BASE/'all59.csv').open()as f:ratios=list(csv.DictReader(f))
    assert len(ratios)==59
    merged=[]
    keep=['date','sid','name','close_deviation_ema20_pct','ema20_five_observation_slope_pct_per_observation',
          'deviation_time_ratio','signed_ratio','ratio_definition_status','slope_abs_bps_per_observation',
          'slope_below_1bp_display_alert','slope_machine_near_zero_alert','small_slope_economic_cutoff',
          'R_if_denominator_plus_1bp','R_if_denominator_minus_1bp',
          'max_relative_R_change_for_1bp_slope_perturbation_pct']
    for ratio in ratios:
        key=(ratio['sid'],ratio['date']);o=original_bykey[key]
        assert o['original_status']==ratio['original_mobile_next_OPEN_status']
        assert o['original_rejection_union']==ratio['original_mobile_next_OPEN_funding_results']
        assert int(o['original_mobile_filled_shares'])==int(ratio['original_mobile_filled_shares'])
        r={k:ratio[k]for k in keep};r.update(o)
        if r['original_status']=='ORIGINAL_MOBILE_OPEN_REJECTED':
            reasons=set(r['original_rejection_union'].split(','))
            if reasons=={'industry_invalidated'}:kind='INDUSTRY_INVALIDATED_NOT_RESOURCE_REJECTION'
            elif reasons&{'cash_or_original_reserve','probe_risk','sector_capital','sector_risk','pool_capital','stock_capital','account_risk'}:kind='ORIGINAL_RESOURCE_FAILURE_UNION'
            else:kind='OTHER_ORIGINAL_REJECTION'
        elif r['original_status']=='MOBILE_SKIPPED_AFTER_SAME_STOCK_CORE_RESERVED':kind='CORE_PRIORITY_SKIP_NOT_REJECTION'
        else:kind='ACTUAL_ORIGINAL_MOBILE_FILL'
        r['original_reason_kind']=kind
        r['refused_hypothetical_outcome']='NOT_DEFINED_OR_ESTIMATED'if r['original_status']!='ORIGINAL_MOBILE_FILL'else'Original saved layer net only'
        merged.append(r)
    assert len({(r['sid'],r['date'])for r in merged})==59
    filled=[r for r in merged if r['original_status']=='ORIGINAL_MOBILE_FILL']
    refused=[r for r in merged if r['original_status']=='ORIGINAL_MOBILE_OPEN_REJECTED']
    skipped=[r for r in merged if r['original_status']=='MOBILE_SKIPPED_AFTER_SAME_STOCK_CORE_RESERVED']
    assert(len(filled),len(refused),len(skipped))==(19,38,2)
    R=lambda r:float(r['deviation_time_ratio'])
    perstock=[];pairs=[]
    for sid in sorted({r['sid']for r in merged}):
        ff=[r for r in filled if r['sid']==sid];rr=[r for r in refused if r['sid']==sid]
        losses=[r for r in ff if r['original_saved_layer_net_sign']=='negative']
        for r in rr:
            r['same_stock_actual_filled_R_min']=min(map(R,ff))
            r['same_stock_actual_filled_R_max']=max(map(R,ff))
            r['R_below_every_actual_filled_layer_of_same_stock']=R(r)<min(map(R,ff))
            r['R_above_every_saved_loss_layer_of_same_stock']=R(r)>max(map(R,losses))if losses else None
            r['relative_range_flags_are_descriptive_not_screening_thresholds']=True
            for f in ff:
                pairs.append(dict(sid=sid,rejected_signal_day=r['date'],rejected_R=r['deviation_time_ratio'],
                    original_rejection_union=r['original_rejection_union'],original_reason_kind=r['original_reason_kind'],
                    filled_signal_day=f['date'],filled_R=f['deviation_time_ratio'],
                    original_filled_layer=f['original_saved_layer_outcome_evaluation_only']['layer'],
                    filled_saved_net_sign_evaluation_only=f['original_saved_layer_net_sign'],
                    rejected_R_minus_filled_R=R(r)-R(f),
                    comparison='less'if R(r)<R(f)else'greater'if R(r)>R(f)else'equal',
                    rejected_counterfactual_return='NOT_DEFINED_OR_ESTIMATED'))
        def light(r):return dict(date=r['date'],R=r['deviation_time_ratio'],original_rejection_union=r['original_rejection_union'],reason_kind=r['original_reason_kind'])
        perstock.append(dict(sid=sid,actual_filled_count=len(ff),rejected_count=len(rr),
            actual_filled_R_range=[min(map(R,ff)),max(map(R,ff))],
            rejected_R_range=[min(map(R,rr)),max(map(R,rr))],
            actual_filled_saved_negative_R_range=[min(map(R,losses)),max(map(R,losses))]if losses else None,
            rejected_below_every_same_stock_fill=[light(r)for r in rr if r['R_below_every_actual_filled_layer_of_same_stock']],
            resource_rejected_below_every_same_stock_fill=[light(r)for r in rr if r['R_below_every_actual_filled_layer_of_same_stock']and r['original_reason_kind']=='ORIGINAL_RESOURCE_FAILURE_UNION'],
            resource_rejected_above_every_same_stock_saved_negative_fill=[light(r)for r in rr if r['R_above_every_saved_loss_layer_of_same_stock']and r['original_reason_kind']=='ORIGINAL_RESOURCE_FAILURE_UNION']))
    save('ALL38_ORIGINAL_REJECTIONS_WITH_FROZEN_R.json',refused)
    csvwrite('ALL38_ORIGINAL_REJECTIONS_WITH_FROZEN_R.csv',refused)
    save('CORE_PRIORITY_SKIP2_WITH_FROZEN_R.json',skipped)
    csvwrite('CORE_PRIORITY_SKIP2_WITH_FROZEN_R.csv',skipped)
    save('ORIGINAL_FILLED19_REFERENCE_R_AND_SAVED_NET.json',filled)
    csvwrite('ORIGINAL_FILLED19_REFERENCE_R_AND_SAVED_NET.csv',filled)
    save('ALL_SAME_STOCK_REJECTED_VS_FILLED_PAIRWISE_COMPARISONS.json',pairs)
    save('PER_STOCK_DESCRIPTIVE_CROSSINGS.json',perstock)
    minrow=min(merged,key=lambda r:float(r['ema20_five_observation_slope_pct_per_observation']))
    counts=dict(total=59,original_fills=19,original_OPEN_rejections=38,CORE_priority_skips_not_rejections=2,
        original_rejection_reason_kinds=dict(Counter(r['original_reason_kind']for r in refused)),
        all59_ratio_definition_status=dict(Counter(r['ratio_definition_status']for r in merged)),
        all59_slope_below_1bp_display_alert_count=sum(r['slope_below_1bp_display_alert']=='True'for r in merged),
        all59_machine_near_zero_alert_count=sum(r['slope_machine_near_zero_alert']=='True'for r in merged),
        minimum_original_slope=dict(sid=minrow['sid'],date=minrow['date'],slope_pct_per_observation=minrow['ema20_five_observation_slope_pct_per_observation']),
        same_stock_rejections_below_all_fills=sum(r['R_below_every_actual_filled_layer_of_same_stock']for r in refused),
        same_stock_resource_rejections_below_all_fills=sum(r['R_below_every_actual_filled_layer_of_same_stock']and r['original_reason_kind']=='ORIGINAL_RESOURCE_FAILURE_UNION'for r in refused),
        same_stock_resource_rejections_above_all_saved_loss_fills=sum(bool(r['R_above_every_saved_loss_layer_of_same_stock'])and r['original_reason_kind']=='ORIGINAL_RESOURCE_FAILURE_UNION'for r in refused),
        ratio_and_slope_recomputed_here=False,new_thresholds_defined=0,new_accounts=0,new_counterfactual_return_estimates=0,
        causal_limit='Original refusal outcomes describe resource/industry rules, not an R filter or rejected-trade future returns. Relative extrema are descriptive comparisons only; not proposed cutoffs.',
        CORE_priority_skip_rows=[dict(sid=r['sid'],date=r['date'],R=r['deviation_time_ratio'],original_status=r['original_status'])for r in skipped])
    assert counts['original_rejection_reason_kinds']=={'ORIGINAL_RESOURCE_FAILURE_UNION':32,'INDUSTRY_INVALIDATED_NOT_RESOURCE_REJECTION':6}
    save('R_REJECTION_COVERAGE_AND_CLASSIFICATION_REVIEW.json',counts)
    save('R_REVIEW_SOURCE_SHA256.json',HASH)
    save('OUTPUT_SHA256.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in OUT.iterdir()if p.is_file()and p.name!='OUTPUT_SHA256.json'})

if __name__=='__main__':main()
