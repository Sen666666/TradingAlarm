"""Fixed original-layer cohorts and saved sell-part grouping, no engine."""
from pathlib import Path
from decimal import Decimal as D,getcontext
import json,gzip,hashlib
import pandas as pd
getcontext().prec=50
H=Path(__file__).resolve().parent;T=H.parents[2];R=T/'risk_constraints';W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');Z=D(0);EPS=D('.00000001')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def category(reason):
    if reason=='I_structure_exit':return'I_structure'
    if reason=='CP1_add_protection':return'CP1_structure'
    if reason=='ACT_pause':return'old_ACT20_force'
    if 'fund'in str(reason).lower()or'筹资'in str(reason):return'funding_sale'
    return'other'
def main():
    sp=T/'ar6_native_feasibility/market_recovery_three_state/structural_walk_daily_support_v2/DAILY.json';smp=W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json'
    refs={'two_year':dict(book=T/'pvr_pool_feasibility/continuation2023/run-2023/pair/B.json.gz',qty=[R/'pvr_pool_results_2022/PVR_NO_CONFIRMED60_DAILY.json',R/'no60_continuation2023_finance/PVR_NO_CONFIRMED60_2023_DAILY.json']),
          'strong':dict(book=T/'pvr_pool_feasibility/runs/2025_26/pair/B.json.gz',qty=[R/'pvr_pool_results_2025_26/PVR_NO_CONFIRMED60_DAILY.json'])}
    sources=[sp,smp,H/'PROTOCOL.txt',H/'associate_original_exits.py']+[p for r in refs.values()for p in [r['book'],*r['qty']]];pre={str(p):sha(p)for p in sources};save(H/'INPUT_FREEZE.json',dict(before_association=True,source_sha256=pre,scope='all v2 D transitions only fixed old actual layers/sell parts; plus explicit L02 carry-inD'))
    st=read(sp);sm={r['symbol']:r for r in read(smp)};facts={};results=[];flows=[]
    def price(sid,day):
        if sid not in facts:
            p=Path(sm[sid]['refs']['facts']);assert sha(p)==sm[sid]['output_sha256'][str(p)];sources.append(p);facts[sid]=pd.read_parquet(p,columns=['raw_close'])
        x=facts[sid].loc[:day].tail(1);assert not x.empty,(sid,day,'original quote unknown');return D(str(x.raw_close.iloc[0]))
    def phase_end(day,window):
        if window=='strong':return'2026-06-30'
        for end in ['2022-04-26','2022-07-04','2022-10-31','2023-01-30','2023-12-29']:
            if day<=end:return end
        raise AssertionError('unsupported window')
    for window,ref in refs.items():
        snaps={str(r['at'])[:10]:r for p in ref['qty']for r in read(p)};calendar=sorted(snaps)
        with gzip.open(ref['book'],'rt')as f:b=json.load(f)
        sells=[t for t in b['trades']if t['side']=='sell'];buys=[t for t in b['trades']if t['side']=='buy'];splits=[a for a in b['audit']if a['kind']=='split']
        cases=[r for r in st if r['event']=='support_break_D'and r['day']in snaps]
        if window=='two_year':
            carry=next(r for r in st if r['day']=='2022-04-27');assert carry['requested_state']=='D';cases.append(dict(carry,carry_in_case=True))
        for event in sorted(cases,key=lambda r:r['day']):
            day=event['day'];stop=phase_end(day,window);ps=[r['day']for r in st if r['day']>day and r['event']=='D_to_P'];pday=ps[0]if ps else None
            end=min(stop,pday)if pday else stop;assert end in snaps
            a,z=snaps[day],snaps[end];initial={l['id']:l for l in a['layers']if D(l['qty'])>0};end_layers={l['id']:l for l in z['layers']if D(l['qty'])>0}
            dvalue={i:D(l['qty'])*price(l['sid'],day)for i,l in initial.items()};total=sum(dvalue.values(),Z);assert abs(total-D(a['inventory']))<EPS
            def ratio(sid,at):
                f=D(1)
                for ca in splits:
                    if ca['sid']==sid and day+' 15:10:00+08:00'<str(ca['at'])<=at:f*=D(ca['ratio'])
                return f
            sold={i:Z for i in initial};groups={k:dict(sell_parts=0,actual_net_sale_cash=Z,D_mark_equivalent_shares_sold=Z,layers=set(),first_fill=None,last_fill=None)for k in ['I_structure','CP1_structure','funding_sale','old_ACT20_force','other']};all_original_exits={k:dict(sell_parts=0,actual_net_sale_cash=Z,initial_cohort_parts=0,later_layer_parts=0)for k in groups};case_flows=[]
            for t in sells:
                tday=str(t['at'])[:10]
                if not(day<tday<=end):continue
                for part in t['parts']:
                    i=part['layer']
                    k=category(part.get('reason',t.get('reason')));gall=all_original_exits[k];gall['sell_parts']+=1;gall['actual_net_sale_cash']+=D(part['net_cash']);gall['initial_cohort_parts']+=int(i in initial);gall['later_layer_parts']+=int(i not in initial)
                    if i not in initial:continue
                    l=initial[i];normal=D(part['shares'])/ratio(l['sid'],str(t['at']));sold[i]+=normal;assert sold[i]<=D(l['qty'])+EPS
                    value=normal*price(l['sid'],day);k=category(part.get('reason',t.get('reason')));g=groups[k];g['sell_parts']+=1;g['actual_net_sale_cash']+=D(part['net_cash']);g['D_mark_equivalent_shares_sold']+=value;g['layers'].add(i);g['first_fill']=g['first_fill']or t['at'];g['last_fill']=t['at']
                    row=dict(window=window,D_day=day,layer=i,sid=l['sid'],fill_at=t['at'],reason=part.get('reason',t.get('reason')),category=k,actual_shares=part['shares'],D_equivalent_shares=normal,D_mark_equivalent=value,actual_net_sale_cash=part['net_cash']);case_flows.append(row);flows.append(row)
            remaining_mark=Z;remaining_D=Z
            for i,l in initial.items():
                left=D(end_layers.get(i,{}).get('qty',0));normal_left=left/ratio(l['sid'],end+' 15:10:00+08:00');assert abs(D(l['qty'])-sold[i]-normal_left)<EPS,(day,i,'original cohort share bridge')
                remaining_D+=normal_left*price(l['sid'],day);remaining_mark+=left*price(l['sid'],end)
            assert abs(sum(g['D_mark_equivalent_shares_sold']for g in groups.values())+remaining_D-total)<EPS
            new_mark=sum((D(l['qty'])*price(l['sid'],end)for i,l in end_layers.items()if i not in initial),Z);assert abs(remaining_mark+new_mark-D(z['inventory']))<EPS
            for g in groups.values():g['distinct_layers']=len(g.pop('layers'))
            new=[t for t in buys if day<str(t['at'])[:10]<=end];assert all(t['layer']not in initial for t in new),'later buy must not enlarge an initial layer';cash=sum((D(t['gross_cny'])+D(t['fees_cny'])for t in new),Z)
            milestones={}
            for label,accepted in [('structure_only',{'I_structure','CP1_structure'}),('all_original_reasons',set(groups))]:
                acc=Z;points={}
                for flow in case_flows:
                    if flow['category']not in accepted:continue
                    acc+=flow['D_mark_equivalent']
                    for frac in [D('.5'),D('.8'),D(1)]:
                        key=str(frac)
                        if total and key not in points and acc+EPS>=frac*total:
                            fd=flow['fill_at'][:10];points[key]=dict(day=fd,original_trading_sessions_after_D=sum(day<d<=fd for d in calendar))
                milestones[label]=points
            results.append(dict(window=window,D_day=day,case_kind='L02_carry_in_D_not_new_request'if event.get('carry_in_case')else'v2_support_break_D',end=end,end_basis='first_P_CLOSE'if end==pday else'fixed_original_phase_end',first_subsequent_P=pday,
                initial_original_inventory=total,initial_layers=len(initial),initial_stocks=len(a['positions']),initial_pending_original_exits=len(a['pending_sells']),
                D_day_bought_layers=sum(str(l['opened'])[:10]==day for l in initial.values()),D_day_bought_marked_value=sum((dvalue[i]for i,l in initial.items()if str(l['opened'])[:10]==day),Z),
                original_exit_groups=groups,all_original_exits_including_later_buys=all_original_exits,share_depletion_milestones=milestones,
                initial_cohort_remaining_D_mark_equivalent=remaining_D,initial_cohort_remaining_actual_end_marketvalue=remaining_mark,initial_cohort_remaining_layers=sum(i in end_layers for i in initial),
                original_following_new_buy_fills=len(new),original_following_new_layer_buy_cash=cash,new_original_layers_still_held_at_end=len(set(end_layers)-set(initial)),new_original_layers_actual_end_marketvalue=new_mark,
                original_end_total_inventory=z['inventory'],original_end_NAV=z['nav'],original_end_exposure_pct=D(z['inventory'])/D(z['nav'])*100,
                limits='Historical fills only. D-mark-equivalent is share depletion, not cash/NAV/risk release. New buys and old ACT/funding cannot be frozen into a no-buy candidate; proceeds may await settlement.'))
    save(H/'ALL_CASES.json',results);save(H/'INITIAL_LAYER_SELL_PARTS.json',flows);assert all(sha(p)==h for p,h in pre.items());save(H/'SOURCE_MANIFEST.json',{str(p):sha(p)for p in sources})
    save(H/'COMPLETED.json',dict(status='ORIGINAL_LAYER_COHORT_EXIT_CHRONOLOGY_ONLY',cases=len(results),actual_initial_layer_sell_parts=len(flows),all_initial_inventory_and_cohort_share_and_end_inventory_bridges=True,new_models=0,new_accounts=0,new_shadowBooks=0,new_cash_or_basis_ledgers=0,source_post_exact=True))
    print('ORIGINAL_NATURAL_EXIT_FOOTPRINTS_READY',len(results),len(flows))
if __name__=='__main__':main()
