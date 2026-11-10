"""One independent check of saved spell outputs; never imports an Account/price reader."""
from pathlib import Path
from decimal import Decimal as D, localcontext
from collections import Counter
import json,hashlib
O=Path(__file__).resolve().parent;T=O.parent;P=T/'ma63_down_replenishment_v1'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str)+'\n')
def stats(rr):
    return dict(layers=len(rr),positive_layers=sum(D(x['period_wealth'])>0 for x in rr),
        negative_layers=sum(D(x['period_wealth'])<0 for x in rr),zero_layers=sum(D(x['period_wealth'])==0 for x in rr),
        wealth=sum((D(x['period_wealth'])for x in rr),D(0)),
        positive_wealth=sum((D(x['period_wealth'])for x in rr if D(x['period_wealth'])>0),D(0)),
        negative_wealth=sum((D(x['period_wealth'])for x in rr if D(x['period_wealth'])<0),D(0)))
def match(a,b):
    for k,v in a.items():assert D(v)==D(b[k]),(k,v,b[k])
def main():
    assert not(O/'SAVED_PERIOD_WEALTH_AUDIT.json').exists(),'no repeat'
    files=[Path(__file__),O/'AXIS_RECONSTRUCTION.json',O/'PROTOCOL_AND_BOUNDARY_GATE.json',
        P/'PROTOCOL.txt',P/'ALL_SPELLS_FROZEN.json',P/'ORIGIN.json',P/'INPUT_FREEZE.json',
        P/'analyze_saved_spells.py',P/'analyze_saved_spells_v2.py',P/'analyze_saved_spells_v3.py',
        P/'ROUNDING_ADDENDUM_V2.json',P/'ROUNDING_ADDENDUM_V3.json',P/'SUMMARY.json',
        P/'ALL_SPELL_RESULTS.json',P/'ALL_LAYER_PERIOD_WEALTH.json',
        T/'risk_constraints/ma63_exposure_axis_v1/DAILY_ALIGNED.json']
    sources={str(p):sha(p)for p in files};save('SAVED_OUTPUT_REVIEW_FREEZE.json',{'source_sha256':sources})
    freeze=read(P/'INPUT_FREEZE.json');r2=read(P/'ROUNDING_ADDENDUM_V2.json');r3=read(P/'ROUNDING_ADDENDUM_V3.json')
    for p in [P/'PROTOCOL.txt',P/'ALL_SPELLS_FROZEN.json',P/'analyze_saved_spells.py']:
        assert sha(p)==freeze['source_sha256'][str(p.resolve())]
    assert sha(P/'analyze_saved_spells_v2.py')==r2['new_reporter_sha256']==r3['old_reporter_sha256']
    assert sha(P/'analyze_saved_spells_v3.py')==r3['new_reporter_sha256']
    axis={x['day']:x for x in read(T/'risk_constraints/ma63_exposure_axis_v1/DAILY_ALIGNED.json')if x['arm']=='NO60'}
    own=read(O/'AXIS_RECONSTRUCTION.json');spells=read(P/'ALL_SPELL_RESULTS.json');rr=read(P/'ALL_LAYER_PERIOD_WEALTH.json');summary=read(P/'SUMMARY.json')
    assert len(spells)==9 and len({(x['spell_id'],x['layer'])for x in rr})==len(rr)==1329
    newids=[x['layer']for x in rr if x['group']=='new_actual_fill_in_spell'];assert len(newids)==len(set(newids))==866
    checked=[]
    with localcontext()as ctx:
        ctx.prec=90
        for s,o in zip(spells,own['all_spells']):
            assert s['days']==o['days']and s['previous_close']==o['first_signal_CLOSE']
            entries=[x for x in rr if x['spell_id']==s['spell_id']];old=[x for x in entries if x['group']=='carry_at_previous_CLOSE'];new=[x for x in entries if x['group']=='new_actual_fill_in_spell']
            assert len(old)+len(new)==len(entries)
            for x in entries:
                assert D(x['end_wealth'])-D(x['boundary_wealth'])==D(x['period_wealth'])
                if x['group']=='carry_at_previous_CLOSE': assert x['opened'][:10]<=s['previous_close']and x['qty_at_boundary']>0
                else: assert s['start']<=x['opened'][:10]<=s['end']and x['qty_at_boundary']==0 and D(x['boundary_wealth'])==0
            match(stats(old),s['old']);match(stats(new),s['new'])
            for label,a in s['new_action'].items():match(stats([x for x in new if x['action']==label]),a)
            source=sum((D(axis[d]['wealth_change'])for d in s['days']),D(0));money=stats(entries)['wealth'];residual=D(s['rounding_residual'])
            assert source==D(s['original_period_wealth'])and money+residual==source and abs(residual)<=D('.000001')
            navdiff=D(axis[s['end']]['NAV'])-D(axis[s['start']]['lag_NAV'])
            assert D(s['source_minus_native_NAV_period_residual'])==source-navdiff
            assert abs(source-navdiff)<=D('.000001')
            assert D(s['NAV_begin'])==D(axis[s['start']]['lag_NAV'])and D(s['NAV_end'])==D(axis[s['end']]['NAV'])
            period=s['actual_trade_period'];cash=sum((D(axis[d]['actual_buy_cash'])for d in s['days']),D(0));fees=sum((D(axis[d]['actual_fees'])for d in s['days']),D(0))
            assert cash==D(period['actual_buy_cash'])and fees==D(period['actual_fees'])
            assert D(s['buy_cash_before_first_sell'])+D(s['buy_cash_after_first_sell'])==cash
            checked.append(dict(id=s['spell_id'],days=len(s['days']),start=s['start'],end=s['end'],source_wealth=source,
                carry_period_wealth=stats(old)['wealth'],new_period_wealth=stats(new)['wealth'],unallocated_rounding=residual,
                actual_new_buy_cash=cash,new_positive_wealth=stats(new)['positive_wealth'],new_negative_wealth=stats(new)['negative_wealth']))
        old=stats([x for x in rr if x['group']=='carry_at_previous_CLOSE']);new=stats([x for x in rr if x['group']=='new_actual_fill_in_spell'])
        match(old,summary['old']);match(new,summary['new'])
        residual=sum((x['unallocated_rounding']for x in checked),D(0))
        assert old['wealth']+new['wealth']+residual==D(own['source_wealth_sum'])==D(summary['exact_source_wealth'])
        assert residual==D(summary['rounding_residual'])
        assert Counter('positive'if x['source_wealth']>0 else'negative'if x['source_wealth']<0 else'zero'for x in checked)=={'positive':2,'negative':4,'zero':3}
        report=dict(status='PASS_WITH_SCOPE_SAVED_SOURCE_BOUNDARIES_CLOCK_AND_PERIOD_GROUP_BRIDGES',spells=9,execution_days=298,
            layer_spell_rows=1329,carry_layer_spell_rows=463,unique_new_actual_layers=866,
            carry=old,new=new,source_wealth=D(summary['exact_source_wealth']),rounding_residual=residual,
            max_abs_spell_residual=max(abs(x['unallocated_rounding'])for x in checked),
            reuse='Source reviewed original H.account/H.after924 W(t) semantics; no second financial basis/price engine',
            not_a_second_per_layer_native_rebuild=True,not_avoidable_loss_or_sale_financing=True,
            known_source_decimal_rounding_not_allocated=True,checked_spells=checked,source_sha256=sources)
        save('SAVED_PERIOD_WEALTH_AUDIT.json',report)
    for p,h in sources.items():assert sha(p)==h,p
    print('PASS',report['carry']['wealth'],report['new']['wealth'],report['source_wealth'])
if __name__=='__main__':main()
