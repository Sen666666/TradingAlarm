"""Thin all-fixed-tail/whole-stock/13 frozen-case audit over audited exports."""
from pathlib import Path
from collections import Counter
from decimal import Decimal as D,getcontext
import hashlib,json
import pandas as pd
getcontext().prec=65
O=Path(__file__).resolve().parent;S=O.parent;F=S/'eta_account_comparison/results_v1';BIND={};C=Counter()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):BIND[str(Path(p).resolve())]=sha(p);return json.loads(Path(p).read_text())
def n(v):return D(str(v))
def eq(a,b,k):assert abs(n(a)-n(b))<D('1e-7'),(k,a,b);C[k]+=1
def time(v):return pd.Timestamp(v) if v is not None else None
def overlap(x,start,end):return time(x['opened'])<end and (x['closed'] is None or time(x['closed'])>start)
def main():
    assert read(O/'PVR_ETA_COMPARISON_MAIN_AUDIT.json')['status'].startswith('PASS')
    maps={(a,w):{x['key']:x for x in read(F/(a+'_'+w+'_LAYERS.json'))} for a in ['BASELINE','ETA'] for w in ['2022_2024','strong']}
    summaries=read(F/'FIXED_TAIL_SUMMARY.json');stocks=read(F/'FIXED_TAIL_ALL_ENTRY_STOCK_COVERAGE.json');tailrows=0
    for win,total in [('2022_2024',83),('strong',94)]:
        base=maps['BASELINE',win];originals=None
        last=time(read(F/('BASELINE_'+win+'_DAILY_WEALTH_SPLIT.json'))[-1]['at'])
        for arm in ['BASELINE','ETA']:
            cur=maps[arm,win];doc=read(F/(arm+'_'+win+'_FIXED_ORIGINAL83_94.json'));rr=doc['rows'];su=doc['summary'];assert len(rr)==total and su==summaries[arm+'|'+win]
            if originals is None:originals=[r['original_fixed_member'] for r in rr]
            else:assert originals==[r['original_fixed_member'] for r in rr]
            for r in rr:
                k=r['entry_key'];b=base.get(k);a=cur.get(k);assert r['baseline_current_exact_match']==b and r['candidate_exact_entry_match']==a
                orig=r['original_fixed_member'];start=time(orig['opened']);end=time(orig['closed']) if orig['closed'] else last
                hit=[x['key'] for x in cur.values() if x['sid']==orig['sid'] and overlap(x,start,end)]
                assert hit==r['candidate_holding_overlap_original_tail_interval_keys']
                assert r['candidate_no_actual_holding_during_original_tail_interval']==(not hit)
                status='matched_baseline_and_candidate' if b and a else 'same_entry_not_participated_candidate' if b else 'baseline_unmatched_candidate_entry_present' if a else 'baseline_unmatched_both_absent'
                assert r['status']==status
                if b:eq(r['raw_contribution_delta'],(n(a['net']) if a else D(0))-n(b['net']),'all_fixed_raw_delta')
                else:assert r['raw_contribution_delta'] is None
                early=bool(b and a and a['closed'] and time(a['closed'])<(time(b['closed']) if b['closed'] else last))
                assert r['matched_entry_exited_earlier']==early
                later=[x['key'] for x in cur.values() if x['sid']==a['sid'] and x['key']!=k and overlap(x,time(a['closed']),time(b['closed']) if b['closed'] else last)] if early else []
                assert later==r['candidate_other_holding_after_exact_layer_exit_before_baseline_end_keys']
                assert r['candidate_no_further_holding_after_early_exit']==((not later) if early else None)
                tailrows+=1
            assert su['statuses']==dict(Counter(r['status'] for r in rr))
            for key,val in [('original_frozen_members',len(rr)),('baseline_current_matches',sum(r['baseline_current_exact_match'] is not None for r in rr)),('candidate_exact_matches',sum(r['candidate_exact_entry_match'] is not None for r in rr)),('completely_no_holding_in_original_tail_interval',sum(r['candidate_no_actual_holding_during_original_tail_interval'] for r in rr)),('baseline_matched_cohort_completely_no_holding_in_original_tail_interval',sum(r['candidate_no_actual_holding_during_original_tail_interval'] for r in rr if r['baseline_current_exact_match'] is not None))]:assert su[key]==val
            eq(su['baseline_matched_cohort_net'],sum((n(r['baseline_current_exact_match']['net']) for r in rr if r['baseline_current_exact_match']),D(0)),'fixed_baseline_net')
            eq(su['candidate_same_entry_contribution_for_baseline_matched_cohort'],sum((n(r['candidate_exact_entry_match']['net']) for r in rr if r['baseline_current_exact_match'] and r['candidate_exact_entry_match']),D(0)),'fixed_candidate_net')
            for label,ids in [('all_original83_94_stocks',{x['sid'] for x in originals}),('current_No60_matched45_67_stocks',{x['original_fixed_member']['sid'] for x in rr if x['baseline_current_exact_match']})]:
                g=stocks[arm+'|'+win][label];bs=[x for x in base.values() if x['sid'] in ids];cs=[x for x in cur.values() if x['sid'] in ids]
                assert g['stocks']==len(ids) and g['candidate_entries']==len(cs)
                assert g['candidate_never_traded_stocks']==sorted(ids-{x['sid'] for x in cs})
                eq(g['baseline_all_entry_contribution'],sum((n(x['net']) for x in bs),D(0)),'all_tail_whole_stock_base')
                eq(g['candidate_all_entry_contribution'],sum((n(x['net']) for x in cs),D(0)),'all_tail_whole_stock_candidate')
    source=read(S/'chains/COMPLETE_ORIGINAL_CHAINS.json');cases=read(F/'ETA_PRIMARY_TEN_CAMPAIGNS_PLUS_THREE_CONTROLS.json');assert len(source)==len(cases)==13
    assert sum(x['attached_control'] for x in cases)==3
    detail={}
    for old,x in zip(source,cases):
        assert x['selection']==old['selection'] and x['attached_control']==old['attached_control'] and x['original_complete_campaign']==old['campaign']
        c=x['original_complete_campaign'];cur=maps['ETA',c['window']];bs=maps['BASELINE',c['window']];ks=set(c['entry_keys']);got=ks&set(cur)
        assert got==set(x['ETA_exact_original_keys_participating'])
        eq(sum((n(bs[k]['net']) for k in ks),D(0)),c['endpoint_net'],'all13_original_campaign_endpoint')
        eq(x['ETA_exact_original_keys_endpoint_contribution'],sum((n(cur[k]['net']) for k in got),D(0)),'all13_same_key_endpoint')
        own=[v for v in cur.values() if v['sid']==c['sid']]
        eq(x['ETA_all_stock_all_entries_endpoint_contribution'],sum((n(v['net']) for v in own),D(0)),'all13_whole_stock_endpoint')
        assert set(v['key'] for v in x['ETA_all_stock_actual_entries'])==set(v['key'] for v in own)
        assert x['ETA_roles']==dict(Counter(v['role'] for v in own)) and x['ETA_entry_actions']==dict(Counter(v['actual_entry_action'] for v in own))
        for field,subset in [('ETA_same_original_campaign_keys_true_stage_wealth',lambda r:r['key'] in got),('ETA_all_stock_true_stage_wealth',lambda r:r['sid']==c['sid'])]:
            for period,values in x[field].items():
                if period not in detail:detail[period]=read(F/('ETA_'+period+'_STAGE_DETAIL.json'))['layer_rows']
                z=[r for r in detail[period] if subset(r)]
                for k in ['wealth','real','unreal','AR']:eq(values[k],sum((n(r[k]) for r in z),D(0)),'all13_stage_subset_'+k)
    result=dict(status='PASS_ALL354_FIXED_TAIL_ROWS_WHOLE_STOCK_AND13_FROZEN_CASE_IDENTITIES_AND_BRIDGES',tail_rows=tailrows,frozen_primary_cases=10,attached_controls=3,checks=dict(C),source_sha256=BIND,script_sha256=sha(__file__),limits=['All original fixed-mother rows, exact-key objects, interval holding and complete-stock monetary views checked against already audited source exports; no candidate causal lost-profit claim.','All13 source selections/campaign objects preserved; whole-account and same-original-key endpoint and stage wealth views remain distinct. No old signal or state model recomputed.'],new_accounts=0,new_financial_events=0)
    (O/'PVR_ETA_TAIL_CASE_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(result['status'],dict(C),flush=True)
if __name__=='__main__':main()
