"""Independent reads/arithmetic over original saved books; no tail simulation."""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D
import gzip,hashlib,json,pickle,statistics,time
import pandas as pd
O=Path(__file__).resolve().parents[1];T=O.parent.parent/'task';R=Path(__file__).resolve().parent;Z=D(0)
def read(p):return json.loads(Path(p).read_text())
def gz(p,lines=False):
    with gzip.open(p,'rt')as h:return list(map(json.loads,h))if lines else json.load(h)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def stats(v):return dict(n=len(v),minimum=min(v)if v else None,median=statistics.median(v)if v else None,maximum=max(v)if v else None)
def normalize(v):return json.loads(json.dumps(v,default=str))
def main():
    begin=time.monotonic();out=read(O/'CP_TAIL_ALL_ORIGINAL_NECESSARY_BOUNDS.json');summary=read(O/'CP_TAIL_NECESSARY_BOUND_SUMMARY.json');ss=read(O/'CP_TAIL_STATIC_SOURCE_SHA256.json')
    correction=read(O/'CP_TAIL_BOOLEAN_SERIALIZATION_CORRECTION.json')
    for p,h in ss.items():
        source=correction['original_execution_source']if p==str(O/'cp_tail_necessary_bounds.py')else p
        assert sha(source)==h
    assert sha(O/'CP_TAIL_ALL_ORIGINAL_NECESSARY_BOUNDS.pre_bool_fix.json')==correction['old_rows_sha256']
    assert sha(O/'CP_TAIL_ALL_ORIGINAL_NECESSARY_BOUNDS.json')==correction['new_rows_sha256']
    assert sha(O/'CP_TAIL_NECESSARY_BOUND_SUMMARY.pre_bool_fix.json')==sha(O/'CP_TAIL_NECESSARY_BOUND_SUMMARY.json')==correction['summary_unchanged_sha256']
    before=read(O/'CP_TAIL_ALL_ORIGINAL_NECESSARY_BOUNDS.pre_bool_fix.json');changed=0
    for a,b in zip(before,out):
        normalized=dict(a)
        for field in correction['source_boolean_fields']:
            if normalized.get(field)in ('True','False'):
                normalized[field]=normalized[field]=='True';changed+=1
        assert normalized==b
    assert changed==correction['normalized_boolean_cells']==1749
    assert len(out)==1749 and len({(r['window'],r['layer'])for r in out})==1749
    sm={r['symbol']:r for r in read('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};features=pickle.loads((O/'PRICE_FEATURES.pkl').read_bytes());facts={}
    rules=read('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json');fixed=read(O.parent/'POST_PURCHASE_ALL25_PATHS.json');ids={r['layer']for r in fixed};assert len(ids)==25
    cfg={'long':(T/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair',T/'risk_constraints/continuation2024_finance/analysis/2022_2024/PVR_NO_CONFIRMED60/LAYERS.json'),'strong':(T/'pvr_pool_feasibility/runs/2025_26/pair',T/'loss_correction/pvr_no60_2025_26/analysis/2025_26/PVR_NO60/LAYERS.json')}
    proof={};reason25=None;fixed_pass=[]
    for w,(p,lp)in cfg.items():
        b=gz(p/'B.json.gz');daily={r['at'][:10]:r for r in gz(p/'daily.jsonl.gz',True)};days=sorted(daily);native_layers={r['id']:r for r in b['layers']};layers={r['layer']:r for r in read(lp)};buy={r['layer']:r for r in b['trades']if r['side']=='buy'};first={};ix={}
        for i,e in enumerate(b['audit']):
            if e['kind']=='pilot_layer_exit':
                for lid in e['layers']:
                    if lid not in first:first[lid]=e;ix[lid]=i
        mobile={k for k,l in native_layers.items()if l['kind']=='add'};cp={k for k in mobile if k in first and first[k]['reason']=='CP1_add_protection'};rows=[r for r in out if r['window']==w];assert {r['layer']for r in rows}==cp
        assert summary['mothers'][w]['all_mobile_layers']==len(mobile);assert summary['mothers'][w]['first_exit_proposals']==sum(k in first for k in mobile);assert summary['mothers'][w]['first_exit_reason_counts']==dict(Counter(first[k]['reason']for k in mobile if k in first))
        for r in rows:
            lid=r['layer'];e=first[lid];sid=r['sid'];d=e['at'][:10];n=next(v for v in daily[d]['layers']if v['id']==lid)
            assert (r['day'],r['actual_qty'],r['original_CP_checked'],r['entry_hardfloor'])==(d,n['qty'],n['floor'],buy[lid]['floor'])
            assert r['original_actual_lifecycle_net']==layers[lid]['net']and r['original_actual_cost']==layers[lid]['cost']
            if sid not in facts:facts[sid]=pd.read_parquet(sm[sid]['refs']['facts'],columns=['close','factor','segment_id','i_target','i_floor','e0_target'])
            f=facts[sid];dt=pd.Timestamp(d);fr=f.loc[dt];pr=features[sid].loc[dt];signal=pd.Timestamp(buy[lid]['signal_at'][:10]);C=D(str(fr.close));factor=D(str(fr.factor));F=D(n['floor']);H=max(D(buy[lid]['floor']),D(str(fr.i_floor)));assert C<=F
            known=all(pd.notna(fr[k])for k in ['close','factor','segment_id','i_target','i_floor','e0_target'])and factor>0
            assert r['known_price_hardline']==known
            assert r['source_segment_survives']==bool(fr.segment_id==f.loc[signal,'segment_id'])
            hard=bool(daily[d]['on'])and bool(fr.i_target)and bool(fr.e0_target)and fr.segment_id==f.loc[signal,'segment_id']and C>H
            version=[z['rule']for z in rules['quantity_versions'][sid]if z['from']<=d and(z.get('to')is None or d<z['to'])];assert len(version)==1;step=version[0]['sell_step'];q=n['qty'];half_ceiling=(q+1)//2;trim=((half_ceiling+step-1)//step)*step;keep=max(0,q-trim);legal=0<keep<q and trim%step==0
            E=bool(pr.ema_trend_known)and bool(pr.ema_trend);B=bool(pr.bb_trend_known)and bool(pr.bb_trend)
            assert (r['SELL_step'],r['optimistic_half_tail_qty'],r['positive_partial_retention_legal'],r['hard_priorities_survive'],r['EMA_license'],r['BB_middle_license'],r['E_price_unit_upper'],r['B_price_unit_upper'])==(step,keep,legal,hard,E,B,hard and E and legal,hard and B and legal)
            values={'continuous_close':C,'factor':factor,'current_I':D(str(fr.i_floor)),'proposed_hardfloor':H,'nominal_old_CP_risk':max(Z,C-F)/factor*q,'nominal_full_quantity_risk_before_trim':max(Z,C-H)/factor*q,'nominal_tail_risk_after_assumed_trim':max(Z,C-H)/factor*keep,'tail_gross_if_trim_fills':keep*C/factor,'tail_gross_pct_NAV':keep*C/factor/D(daily[d]['nav'])*100}
            for k,v in values.items():assert D(r[k])==v,(w,lid,k)
            live={l['id']for l in daily[d]['layers']if l['sid']==sid and l['qty']}
            prior=[dict(layer=k,at=first[k]['at'],reason=first[k]['reason'])for k in live if k!=lid and k in first and ix[k]<ix[lid]]
            hard_other=[dict(layer=k,at=first[k]['at'],reason=first[k]['reason'])for k in live if k!=lid and k in first and first[k]['at'][:10]==d and first[k]['reason']!='CP1_add_protection']
            assert r['other_live_layers_with_prior_exit_requests']==prior and r['other_same_day_nonCP_hard_exit_requests']==hard_other
            assert r['exact_stock_ExitOrder_latch_reconstructed']is False
            index=days.index(d);assert r['proposal_plus5_market_CLOSE']==(days[index+5]if index+5<len(days)else None)
            assert r['fixed_2026H1_bought_25_layer']==(w=='strong'and lid in ids)
        if w=='strong':
            reason25=dict(first_reason=dict(Counter(first[k]['reason']if k in first else None for k in ids)),final_reason=dict(Counter(native_layers[k]['reason']for k in ids)),closed_mobile=sum(native_layers[k]['kind']=='add'and native_layers[k]['closed']is not None for k in ids),first_vs_final_differences=[k for k in ids if (first[k]['reason']if k in first else None)!=native_layers[k]['reason']])
            assert not reason25['first_vs_final_differences']
            assert reason25['closed_mobile']==20 and reason25['final_reason']=={'I_structure_exit':3,'CP1_add_protection':18,None:4}
            for r in summary['mothers'][w]['fixed_H1_25_all_roles']:
                assert r['layer']in ids and r['first_exit_reason']==(first[r['layer']]['reason']if r['layer']in first else None)
            fixed_pass=[{k:r[k]for k in ['layer','sid','name','day','actual_qty','optimistic_half_tail_qty','tail_gross_pct_NAV','nominal_full_quantity_risk_before_trim','nominal_tail_risk_after_assumed_trim','same_sid_contains_hard_priority_failure']}for r in rows if r['fixed_2026H1_bought_25_layer']and r['E_price_unit_upper']]
        proof[w]=dict(first_CP=len(cp),all_row_input_and_arithmetic_exact=True)
    siblings=defaultdict(list)
    for r in out:siblings[r['window'],r['day'],r['sid']].append(r)
    for r in out:
        group=siblings[r['window'],r['day'],r['sid']]
        assert r['same_sid_CP_proposal_layers']==len(group)
        assert r['same_sid_contains_hard_priority_failure']==any(v['hard_priorities_survive']is False for v in group)
    for key,s in summary['strata'].items():
        w=key.split('_',1)[0];tag=key[len(w)+1:];a=[r for r in out if r['window']==w]
        if tag.isdigit():a=[r for r in a if r['day'][:4]==tag]
        elif tag=='after_924':a=[r for r in a if r['day']>='2024-09-24']
        elif tag=='semiconductor_proposal_calendar_2026':a=[r for r in a if r['day']>='2026-01-01'and r['industry']=='半导体']
        elif tag=='fixed25_H1_bought_CP_only':a=[r for r in a if r['fixed_2026H1_bought_25_layer']]
        else:assert tag=='all'
        assert (s['proposal_layers'],s['stocks'],s['unknown'],s['hard_survives'],s['legal_half'])==(len(a),len({r['sid']for r in a}),sum(not r['known_price_hardline']for r in a),sum(r['hard_priorities_survive']is True for r in a),sum(r['positive_partial_retention_legal']for r in a))
        for label in ['E_price_unit_upper','B_price_unit_upper']:
            u=[r for r in a if r[label]];expected=dict(events=len(u),stocks=len({r['sid']for r in u}),retained_gross_pct_NAV_per_event=stats([D(r['tail_gross_pct_NAV'])for r in u]),original_contacted_layer_net=sum((D(r['original_actual_lifecycle_net'])for r in u),Z),same_sid_hard_mixed=sum(r['same_sid_contains_hard_priority_failure']for r in u),full_risk_before_trim=stats([D(r['nominal_full_quantity_risk_before_trim'])for r in u]));assert normalize(expected)==s['licenses'][label],key
    result=dict(passed=True,status='PASS_NECESSARY_BOUNDS_ONLY_NO_TAIL_ACCOUNT',rows=len(out),proofs=proof,all_summary_groups_exact=True,source_hashes=len(ss),original_compute_seconds=summary['seconds'],review_seconds=time.monotonic()-begin,reviewer_accounts=0,reviewer_projections=0,fixed25_reason_audit=reason25,fixed25_E_passing_events=fixed_pass,scope='Optimistic independent layer price/unit necessary bounds only. No exact ExitOrder/FIFO latch, shared risk grant, fees, OPEN recheck, actual trim, five-observation execution or tail profit has been validated. 20 means closed MOBILE layers: 18 CP + 2 I, not 20 CP exits. Prior/final reasons match in all fixed25 layers.')
    (R/'CP_TAIL_STATIC_RESULT_REVIEW.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
