"""Full saved-opportunity/rank/pair/label annex audit; no market or account replay."""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D,getcontext
import gzip,hashlib,json,math,time
getcontext().prec=65
O=Path(__file__).resolve().parent;S=O.parents[1];F=S/'mechanism_design';T=S.parent/'trend_exit_controls_v1'
BOUND={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):BOUND[str(Path(p).resolve())]=sha(p);return json.loads(Path(p).read_text())
def rows(p):
    BOUND[str(Path(p).resolve())]=sha(p)
    with gzip.open(p,'rt') as f:
        for l in f:yield json.loads(l)
def agg(a):
    return dict(layers=len(a),stocks=len({x['sid'] for x in a}),cost=sum((D(x['cost']) for x in a),D(0)),net=sum((D(x['net']) for x in a),D(0)),positive=sum((max(D(0),D(x['net'])) for x in a),D(0)),negative=sum((min(D(0),D(x['net'])) for x in a),D(0)))
def eqmoney(got,want):
    assert set(got)==set(want)
    for k,v in want.items():assert D(str(got[k]))==D(str(v)),(k,got[k],v)
def klass(a,b):
    if a['eta'] is None or b['eta'] is None:return 'pair_touches_UNKNOWN_fixed_H1_slot'
    return 'round12_tie_H1_order' if round(a['eta'],12)==round(b['eta'],12) else 'true_unequal_eta_order'
def main():
    begun=time.monotonic();allpairs=read(F/'RANK_TIE_NONTIE_NA_ANNEX.json')['summary']
    cmp=read(F/'COMPETITION_TIE_NONTIE_ANNEX.json');aff=read(F/'ACTUAL_COMPETITION_TOUCH_ANNEX.json')
    ctlsummary=read(F/'FIXED83_94_ETA_SUMMARY.json');findings={}
    for win in ['2022_2024','strong']:
        mm=list(rows(F/(win+'_PENDING_RANK_MOVES.jsonl.gz')))
        byday=defaultdict(list);lookup={}
        for x in mm:byday[x['day']].append(x);lookup[x['day'],x['sid']]=x
        c=Counter();classes={}
        kinds=['true_unequal_eta_order','round12_tie_H1_order','pair_touches_UNKNOWN_fixed_H1_slot']
        for day,rs in byday.items():
            rs.sort(key=lambda r:r['old_PVR_slot']);flags=[set() for _ in rs]
            for i,a in enumerate(rs):
                for j in range(i+1,len(rs)):
                    b=rs[j]
                    if a['new_eta_slot']>b['new_eta_slot']:
                        k=klass(a,b);c['all_inverted_pairs']+=1;c['pair_kind:'+k]+=1
                        flags[i].add(k);flags[j].add(k)
            eta=Counter(round(r['eta'],12) for r in rs if r['eta'] is not None)
            ties=[n for n in eta.values() if n>1]
            c['batches']+=1;c['pending_stock_days']+=len(rs);c['tie_rows']+=sum(ties)
            c['days_with_eta_ties']+=bool(ties);c['max_eta_tie_group']=max(c['max_eta_tie_group'],max(ties,default=0))
            for i,r in enumerate(rs):
                name='UNCHANGED_SLOT' if r['eta_minus_PVR_slot']==0 else '+'.join(k for k in kinds if k in flags[i])
                assert name
                c['row_class:'+name]+=1;classes[day,r['sid']]=name
                if r['eta'] is None:c['eta_UNKNOWN']+=1
                else:
                    c['eta_exact_plus1']+=r['eta']==1;c['eta_round12_plus1']+=round(r['eta'],12)==1;c['eta_round12_minus1']+=round(r['eta'],12)==-1
        for k in set(c)|set(allpairs[win]):assert c[k]==allpairs[win].get(k,0),(win,k,c[k],allpairs[win].get(k))
        # Source opportunities: all rows and native roles/barriers, not buys only.
        co=Counter();oppbyday=defaultdict(Counter)
        for r in rows(T/'runs/BASELINE'/win/'pair/opportunities.jsonl.gz'):
            key=(r['day'],r['sid']);co['all_original_opportunity_rows']+=1
            if r['roles']:
                co['rows_with_native_roles']+=1
                for role in r['roles']:co['role_'+role]+=1
                if not r['barriers']:co['native_barrier_free_rows']+=1
            oppbyday[r['day']]['all']+=1
        cv=read(F/'OPPORTUNITY_COVERAGE.json')[win]
        for k,v in co.items():assert cv['totals'][k]==v,(win,k)
        assert all(cv['by_day'][d]['all']==v['all'] for d,v in oppbyday.items())
        # Reconstruct all OPEN resource-crossing backgrounds from raw funding,
        # not from the producer's candidate background list.
        cal=[r['at'][:10] for r in rows(T/'runs/BASELINE'/win/'pair/daily.jsonl.gz')]
        prior={cal[i]:cal[i-1] for i in range(1,len(cal))};funded=defaultdict(set);rejected=[];close_resource=0
        reasons={'cash_or_original_reserve','pool_capital','probe_risk','sector_capital','sector_risk','stock_capital'}
        for r in rows(T/'runs/BASELINE'/win/'pair/funding.jsonl.gz'):
            resource=bool(set(r['result'].split(','))&reasons)
            if '09:30:00' not in r['at']:
                close_resource+=resource;continue
            d=prior.get(r['at'][:10]);k=(d,r['sid'])
            if k not in lookup:continue
            if r['result']=='reserved':funded[d].add(r['sid'])
            elif resource:rejected.append((d,r))
        assert close_resource==0
        pc=Counter();bg=Counter();touched=set();actual_bg=0;stockdays=set();bgdates=set()
        for day,r in rejected:
            candidate=lookup[day,r['sid']];ks=set()
            for sid in funded[day]:
                x=lookup[day,sid]
                if x['old_PVR_rank']<candidate['old_PVR_rank'] and x['new_eta_rank']>candidate['new_eta_rank']:
                    k=klass(candidate,x);pc[k]+=1;ks.add(k);touched.add((day,sid))
            if ks:actual_bg+=1;bg['+'.join(sorted(ks))]+=1;stockdays.add((day,r['sid']));bgdates.add(day)
        assert dict(pc)==cmp[win]['pair_counts'] and dict(bg)==cmp[win]['background_row_classes']
        assert len(touched)==cmp[win]['original_reserved_stock_days_crossed_by_rejected']
        cs=read(F/'RESOURCE_COMPETITION_SUMMARY.json')[win]
        assert [actual_bg,len(stockdays),len(bgdates)]==[cs['resource_reject_rows_with_order_reversal'],cs['unique_rejected_stock_days_with_order_reversal'],cs['dates']]
        # All actual layer input fields remain the original source rows.
        original=read(S/'state_semantics'/(win+'_ROWS.json'));actual=read(F/(win+'_ACTUAL_ENTRY_RANK_DIAGNOSTIC.json'))
        assert len(original)==len(actual)==(2265 if win=='2022_2024' else 1171)
        origmap={x['layer']:x for x in original};actualmap={x['layer']:x for x in actual}
        for x in actual:
            assert {k:v for k,v in x.items() if k!='eta_rank_diagnostic'}==origmap[x['layer']]
            assert x['eta_rank_diagnostic']==lookup[x['decision_at'][:10],x['sid']]
        aa=[x for x in actual if (x['decision_at'][:10],x['sid']) in touched]
        eqmoney(aff[win]['all_original_actual_entries_touched'],agg(aa))
        eqmoney(aff[win]['first'],agg([x for x in aa if x['action']=='first_actual_participation']))
        eqmoney(aff[win]['own_tail30'],agg([x for x in aa if D(x['net'])/D(x['cost'])>=D('.3')]))
        assert set(aff[win]['all_actual_by_class'])=={classes[x['decision_at'][:10],x['sid']] for x in actual}
        for k,g in aff[win]['all_actual_by_class'].items():
            eqmoney(g,agg([x for x in actual if classes[x['decision_at'][:10],x['sid']]==k]))
        controls=read(S/'state_semantics'/(win+'_FIXED_TAIL_CONTROLS.json'))
        outcontrols=read(F/(win+'_FIXED83_94_ETA_CONTROL_ROWS.json'));matched=[]
        assert len(controls)==len(outcontrols)==(83 if win=='2022_2024' else 94)
        for old,new in zip(controls,outcontrols):
            assert old['original']==new['original'] and old['unmatched']==new['unmatched']
            assert len(old['matched_No60_rows'])==len(new['matched_No60_rows'])
            for x,y in zip(old['matched_No60_rows'],new['matched_No60_rows']):
                assert {k:v for k,v in y.items() if k not in ['eta_rank_diagnostic','rank_pair_row_class','original_funding_competition_touched']}==x
                z=actualmap[y['layer']];key=(z['decision_at'][:10],z['sid'])
                assert y['eta_rank_diagnostic']==lookup[key] and y['rank_pair_row_class']==classes[key]
                assert y['original_funding_competition_touched']==(key in touched)
                matched.append(y)
        su=ctlsummary[win]
        assert [su['original_members'],su['matched_original_members'],su['matched_actual_layers']]==[len(controls),sum(bool(x['matched_No60_rows']) for x in controls),len(matched)]
        for move in ['earlier','same','later']:
            z=[x for x in matched if ('earlier' if x['eta_rank_diagnostic']['eta_minus_PVR_slot']<0 else 'later' if x['eta_rank_diagnostic']['eta_minus_PVR_slot']>0 else 'same')==move]
            eqmoney(su['movement'][move],agg(z))
        eqmoney(su['original_reserved_crossed_by_resource_reject'],agg([x for x in matched if x['original_funding_competition_touched']]))
        findings[win]=dict(all_inverted_pairs=c['all_inverted_pairs'],pair_kinds=dict(pc),resource_cross_background_rows=actual_bg,unique_rejected_stockdays=len(stockdays),background_dates=len(bgdates),actual_layers=len(actual),fixed_original_members=len(controls),fixed_matched_layers=len(matched),all_actual_entries_on_crossed_original_stockdays=agg(aa),close_resource_rows_misclocked=close_resource)
    bind=read(F/'ANNEX_SOURCE_BINDING.json')
    assert all(sha(p)==h for p,h in bind['frozen_before_hashes'].items())
    out=dict(status='PASS_ALL_NECESSARY_RANK_SCOPE_COMPETITION_AND_FIXED_TAIL_ANNEX_WITH_LIMITS',findings=findings,
             source_sha256=BOUND,script_sha256=sha(__file__),seconds=time.monotonic()-begun,
             limits=['Order crossing and a rejected-resource label do not prove legal replacement: stock/sector/role/minimum and other resource guards coexist.','Funded old winners are a selected subset; their unchanged old-path net is not eta lost profit.','No causal money attribution, no candidate financial outcome or forecast quality gate.','Producer raw matched/unmatched funding totals include CLOSE size diagnostics mapped by the prior-calendar helper. The audited resource-crossing subset is exclusively09:30 OPEN; CLOSE resource rows=0.'],
             new_accounts=0,new_financial_events=0)
    (O/'RANK_SCOPE_AND_TAIL_ANNEX_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str)+'\n')
    print(json.dumps(dict(status=out['status'],findings=findings,seconds=out['seconds']),ensure_ascii=False,default=str),flush=True)


if __name__=='__main__':main()
