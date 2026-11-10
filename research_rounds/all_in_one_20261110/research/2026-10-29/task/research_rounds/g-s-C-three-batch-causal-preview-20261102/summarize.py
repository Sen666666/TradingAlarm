"""Summarize fixed local planning evidence; never execute account events."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import sys, json, hashlib
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import run as R
M=R.M;J=R.J;Z=D(0)
ENG=HERE.parent/'g-s-C-engineering-causal-readonly-20261102'

def read(p):return json.loads(Path(p).read_text())
def money(x):return f'{D(x):,.2f}'
def classes(v):return sorted({x.rsplit(':',1)[-1] for x in v['validation']['violations']})
def reserve(v,sid):return {c['constraint']:{k:c[k] for k in ('value','limit','residual')} for c in v['validation']['checks'] if c['stage']=='reserve:'+sid}
def totals(v,ds):
    return dict(new_buy_gross=sum((D(v['Q'].get(d['sid'],0))*D(d['mark'])*(1+J.SLIP) for d in ds),Z),
        planned_sale_mark=sum((D(z['capital']) for z in v['donors']['rows']),Z),
        planned_sale_net=sum((D(z['net']) for z in v['donors']['rows']),Z),
        projected_old_risk_release=v['validation']['projected_risk_released'],terminal=v['validation']['terminal'],
        actual_cash_released=0,actual_risk_released=0)
def remaining_old_risk(s,Dmap,costs,plan):
    sold={z['layer']:z['q'] for z in plan['donors']['rows']};out=defaultdict(lambda:Z)
    for z in s['lots']:
        q=D(z['qty']-sold.get(z['id'],0));mark=D(z['mark']);floor=D(z['floor']);cost=costs[z['id']]
        out['principal']+=q*max(Z,min(mark,cost)-floor)
        out['profit_giveback']+=q*max(Z,mark-max(cost,floor))
        out['execution_lock_excess']+=(D(z['risk'])-D(z['qty'])*max(Z,mark-floor))*q/D(z['qty'])
    return dict(out)
def main():
    M.guard();r=R.load('C10');costs={lid:D(v['unit_cost']) for lid,v in r.account.capital_meta.items()}
    facts=r.inputs.table('facts').set_index(['sid','day'])
    meta=read(R.R/'inputs/2025_26/metadata.json');eng=read(ENG/'ENGINEERING_DAILY.json')['2025_26-C10'];ctx=read(ENG/'DAILY_RESOURCE_CONTEXT.json')['2025_26-C10']
    month_contribution={z['sid']:z for z in read(R.R/'july_end_analysis/ALL_STOCKS.json')['2025_26-C10']}
    source_index=read(ENG/'ARTIFACT_SHA256.json');assert all(R.sha(ENG/n)==h for n,h in source_index.items())
    rows=[];units=[];controls=[]
    for day in R.DATES:
        label='C10-'+day;b=read(HERE/('BASELINE-'+label+'.json'));ds=b['sorted_complete_demands'];s=b['transformed_snapshot'];orig=b['result'];comp=read(HERE/('COMPARATIVE_RANK-'+label+'.json'));que=read(HERE/('QUEUE_ONLY-'+label+'.json'))
        assert que['result']['Q']==orig['Q'] and que['result']['D']==orig['D']
        assert comp['result']['validation']['ok'] and comp['rank_only_recovery_exact']
        context=next(x for x in ctx if x['day']==day)
        rows.append(dict(day=day,candidates=len(ds),complete_prefixes=len(b['prefixes']),baseline=totals(orig,ds),queue_only=totals(que['result'],ds),
            comparative_rank=totals(comp['result'],ds),all_Q_changes=comp['all_Q_changes'],all_D_changes=comp['all_D_changes'],
            industry_F1=context['industry_F1'],industry_H1=context['industry_H1'],industry_rank_all90=context['industry_rank_all90_1based'],actual_C_queue=context['industry_C_queue_1based'],
            prebatch_old_nominal_risk=sum((D(z['risk']) for z in s['lots']),Z),decision_nav=s['decision_nav'],cash=s['available']))
        for p in read(HERE/('FIXED_PREFIX_UNITS-'+label+'.json')):
            x=dict(day=day,sid=p['sid'],name=meta[p['sid']]['name'],original_plan_q=p['original_accepted_q'],raw_max=p['original_max'],legal_min=p['original_initial_min'],
                initial_violations=classes(p['base_exact']),initial_reserve_checks=reserve(p['base_exact'],p['sid']),
                first_legal_D=p['first_legal_with_original_donor_path']['D'] if p['first_legal_with_original_donor_path'] else None,
                last_path_violations=classes(p['last_original_path_test']),last_path_reserve_checks=reserve(p['last_original_path_test'],p['sid']),
                tests=p['tests'],original_weaker_donor_path=p['admissible_weaker_donor_stocks'],prebatch_risk_decomposition=p['prefix_breakdown']['old'],
                prefix_new_reserve_risk=p['prefix_breakdown']['prefix_new_reserve_risk'],projected_prefix_old_risk_release=p['prefix_breakdown']['projected_old_risk_release'],
                projected_prefix_remaining_old_risk=remaining_old_risk(s,p['base_exact']['D'],costs,p['base_exact']))
            n=p.get('next_increment')
            if isinstance(n,dict):x['next_unit']=dict(q=n['tested_total_quantity'],first_legal=bool(n['first_legal_with_original_donor_path']),last_reserve_checks=reserve(n['last_original_path_test'],p['sid']),last_violations=classes(n['last_original_path_test']),tests=n['tests'])
            else:x['next_unit']=n
            units.append(x)
        # Deterministic old-risk controls plus ALL changed hypothetical donors and original positive recipients.
        chosen={z['sid'] for z in sorted(s['lots'],key=lambda z:-D(z['risk']))[:3]}|set(orig['D'])|{z['sid'] for z in comp['all_D_changes']}|{sid for sid,q in orig['Q'].items() if q}
        for sid in sorted(chosen):
            lots=[z for z in s['lots'] if z['sid']==sid];fr=facts.loc[(sid,day)].to_dict() if (sid,day) in facts.index else None
            controls.append(dict(day=day,sid=sid,name=meta[sid]['name'],source_facts=fr,full_month_actual_contribution_hindsight_only=month_contribution.get(sid),
                original_new_Q=orig['Q'].get(sid,0),diagnostic_new_Q=comp['result']['Q'].get(sid,0),
                original_D=orig['D'].get(sid,0),diagnostic_D=comp['result']['D'].get(sid,0),
                lots=[dict(id=z['id'],role=z['role'],pool=z['pool'],purpose=z['purpose'],holding_S=z.get('holding_S'),B_donor_eligible=z.get('B_donor_eligible'),qty=z['qty'],sellable_qty=z['sellable_qty'],mark=z['mark'],floor=z['floor'],risk=z['risk'],original_C_rank=z['rank_key'],
                    gross_unit_cost=costs[z['id']],gross_mark_PNL_before_fees=D(z['qty'])*(D(z['mark'])-costs[z['id']])) for z in lots]))
    R.save('COMPACT_NUMERICAL_EVIDENCE.json',dict(batches=rows,exact_prefix_unit_tests=units,incumbent_controls=controls,financial_events=0,scope='fixed original-prefix / original donor-path local feasibility, never achievable PnL'))
    # Precisely preserve as-of evidence/identity for all engineering case candidates.
    selected=[x for x in eng if x['day'] in R.DATES and x['fresh_CP1'] and x['stock_Q'] is True]
    R.save('ASOF_CASE_EVIDENCE.json',selected)
    old_checks={n:dict(expected=h,actual=R.sha(ENG/n)) for n,h in source_index.items()}
    assert all(x['expected']==x['actual'] for x in old_checks.values())
    checkpoint_reads=read(HERE/'SOURCE_INPUT_CHECKS.json')['source_reads']
    assert len(checkpoint_reads)==2 and all(R.sha(p)==h for p,h in checkpoint_reads.items())
    complete=[]
    for mode in ('C10','C_BATCH20'):
        for day in R.DATES:
            label=mode+'-'+day;b=read(HERE/('BASELINE-'+label+'.json'));v=read(HERE/('INPUT-'+label+'.json'))
            assert J.digest(b['result'])==v['saved_certificate']['projection_hash']
            complete.append(dict(label=label,complete_result_digest=J.digest(b['result']),expected=v['saved_certificate']['projection_hash'],candidate_prefixes=len(b['prefixes'])))
    R.save('FINAL_READONLY_VERIFICATION.json',dict(passed=True,all_original_six_complete_projection_digests=True,
        complete_digest_checks=complete,
        all_original_candidate_prefixes_exact=True,queue_original_key_mode_no_Q_D_changes_all_three=True,
        comparative_rank_only_recovery_exact=True,unchanged_joint_hard_guards_all_three=True,
        original_engineering_package_unchanged=old_checks,old_checkpoint_reads=checkpoint_reads,
        financial_events=0,new_indicators=0,price_labels_read_for_rank_intervention=False,order_submission=False))
    print('SUMMARY_READY',len(rows),'batches',len(units),'original-prefix unit probes',len(controls),'control rows',flush=True)

if __name__=='__main__':main()
