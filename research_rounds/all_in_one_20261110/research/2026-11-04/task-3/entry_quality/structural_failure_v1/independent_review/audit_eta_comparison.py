"""Thin completed-book/derived-table checks; no account/indicator recomputation."""
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D,getcontext
import gzip,hashlib,json
getcontext().prec=65
O=Path(__file__).resolve().parent;S=O.parent;F=S/'eta_account_comparison/results_v1';T=S.parent/'trend_exit_controls_v1';BIND={};C=Counter()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
    BIND[str(Path(p).resolve())]=sha(p)
    with (gzip.open(p,'rt') if str(p).endswith('.gz') else open(p)) as f:
        return [json.loads(l) for l in f] if '.jsonl' in str(p) else json.load(f)
def num(v):return D(str(v))
def near(a,b,k):assert abs(num(a)-num(b))<D('1e-7'),(k,a,b);C[k]+=1
DATA={};LAYERS={};DETAIL={}
def data(arm,win):
    k=arm,win
    if k not in DATA:
        p=(T/'runs/BASELINE'/win) if arm=='BASELINE' else S/'pvr_eta_v1/runs'/win
        b=read(p/'pair/B.json.gz');d=read(p/'pair/daily.jsonl.gz');w=read(F/(arm+'_'+win+'_DAILY_WEALTH_SPLIT.json'))
        assert len(d)==len(w)==(726 if win=='2022_2024' else 242)
        for x,y in zip(d,w):
            assert x['at']==y['at'] and x['on']==y['ACT_on']
            for a,z in [('nav','NAV'),('inventory','inventory'),('available','available'),('dividend_receivable','AR')]:near(x[a],y[z],'all_exported_daily_source_fields')
            near(num(y['strict_realized'])+num(y['open_unrealized'])+num(y['AR']),num(y['NAV'])-1000000,'all_daily_wealth_parts')
        DATA[k]=b,d,w
    return DATA[k]
def layerdata(arm,win):
    k=arm,win
    if k not in LAYERS:
        b,d,w=data(*k);rs=read(F/(arm+'_'+win+'_LAYERS.json'));bs={x['id']:x for x in b['layers']};buys={x['layer']:x for x in b['trades'] if x['side']=='buy'}
        assert len(rs)==len(bs);assert len({x['key'] for x in rs})==len(rs)
        for r in rs:
            x=bs[r['layer_in_this_book']];buy=buys[x['id']]
            assert r['sid']==x['sid'] and r['qty']==x['qty'] and r['initial_qty']==x['initial_qty']
            near(r['cost'],num(buy['gross_cny'])+num(buy['fees_cny']),'all_layer_cost_source')
            near(r['AR'],x['dividend'],'all_layer_AR_source');near(r['net'],num(x['cash'])+num(x['dividend'])+num(r['value']),'all_layer_lifecycle_source')
            near(r['net'],num(r['strict_realized'])+num(r['open_unrealized'])+num(r['AR']),'all_layer_wealth_parts')
            near(r['legacy_actual_trade_pvr_H1_value'],buy['pvr'],'all_trade_H1_alias_source')
        near(sum((num(r['value']) for r in rs),D(0)),d[-1]['inventory'],'all_layer_value_sum')
        near(sum((num(r['net']) for r in rs),D(0)),num(b['ending_NAV'])-1000000,'all_layer_net_sum')
        LAYERS[k]={r['key']:r for r in rs}
    return LAYERS[k]
def period(r,stage=False):
    arm,win=r['arm'],r['window'];b,d,w=data(arm,win);ii=[i for i,x in enumerate(d) if r['start']<=x['at'][:10]<=r['end']];assert ii
    lo,hi=ii[0],ii[-1];start=num(d[lo-1]['nav']) if lo else D(1000000);end=num(d[hi]['nav'])
    assert r['observations']==len(ii) and r['first_observed']==d[lo]['at'][:10] and r['last_observed']==d[hi]['at'][:10]
    exp={'NAV_begin':start,'NAV_end':end,'net_wealth_change':end-start,'return_fraction':end/start-1}
    peak=start;dd=D(0);globalpeak=D(1000000);globaldd=[]
    for j,x in enumerate(d):
        nv=num(x['nav']);globalpeak=max(globalpeak,nv);globaldd.append(1-nv/globalpeak)
    for j in ii:
        peak=max(peak,num(d[j]['nav']));dd=max(dd,1-num(d[j]['nav'])/peak)
    exp['period_rebased_max_DD']=dd;exp['maximum_account_DD_from_entire_account_path_peak']=max(globaldd[j] for j in ii)
    for label,prev in [('CLOSE',False),('previous_CLOSE',True)]:
        ns=[];vs=[];es=[]
        for j in ii:
            q=d[j-1] if prev and j else (dict(nav=1000000,inventory=0) if prev else d[j]);nv=num(q['nav']);v=num(q['inventory']);ns.append(nv);vs.append(v);es.append(v/nv)
        exp['mean_'+label+'_NAV']=sum(ns)/len(ii);exp['mean_'+label+'_inventory']=sum(vs)/len(ii);exp['mean_'+label+'_exposure']=sum(es)/len(ii)
    exp['fees']=num(d[hi]['fees_cny'])-(num(d[lo-1]['fees_cny']) if lo else D(0))
    ts=[x for x in b['trades'] if r['start']<=x['at'][:10]<=r['end']]
    exp['buy_gross']=sum((num(x['gross_cny']) for x in ts if x['side']=='buy'),D(0));exp['sell_gross']=sum((num(x['gross_cny']) for x in ts if x['side']=='sell'),D(0));exp['buy_plus_sell_gross']=exp['buy_gross']+exp['sell_gross']
    for key,v in exp.items():near(r[key],v,'all56_period_'+key)
    for source,dest in [('strict_realized','strict_realized_change'),('open_unrealized','open_unrealized_change'),('AR','AR_change')]:
        near(r[dest],num(w[hi][source])-(num(w[lo-1][source]) if lo else D(0)),'all56_period_'+dest)
    f=F/(arm+'_'+r['period']+('_STAGE_DETAIL.json' if stage else '_DETAIL.json'));detail=read(f)
    for label,key in [('wealth','net_wealth_change'),('real','strict_realized_change'),('unreal','open_unrealized_change'),('AR','AR_change')]:near(sum((num(x[label]) for x in detail['layer_rows']),D(0)),r[key],'all56_detail_'+label)
    DETAIL[arm,win,r['period']]=detail
def main():
    mainrows=read(F/'FIXED18_PERIODS_TWO_CONFIGURATIONS.json');stages=read(F/'TEN_DISJOINT_STAGES_TWO_CONFIGURATIONS.json');assert len(mainrows)==36 and len(stages)==20
    for r in mainrows:period(r)
    for r in stages:period(r,True)
    grouped=read(F/'FULL_STOCK_MONTH_SECTOR_CONTRIBUTION_DIFFERENCES.json');summary=read(F/'FULL_PATH_DIFFERENCE_SUMMARY.json')
    for win in ['2022_2024','strong']:
        maps={a:layerdata(a,win) for a in ['BASELINE','ETA']};base,new=maps['BASELINE'],maps['ETA'];delta=sum((num(x['net']) for x in new.values()),D(0))-sum((num(x['net']) for x in base.values()),D(0))
        near(summary[win]['account_net_delta'],delta,'full_account_delta')
        diff=read(F/('ETA_'+win+'_FULL_ENTRY_AND_ACT_DIFFERENCES.json'));assert diff['summary']==summary[win]
        assert len(diff['matched'])==len(set(base)&set(new))==summary[win]['matched_entries']
        assert len(diff['removed'])==len(set(base)-set(new))==summary[win]['removed_baseline_entries'];assert len(diff['new'])==len(set(new)-set(base))==summary[win]['new_candidate_entries']
        for x in diff['matched']:
            b,n=base[x['key']],new[x['key']]
            for k,y in [('baseline_cost',b['cost']),('candidate_cost',n['cost']),('baseline_net',b['net']),('candidate_net',n['net']),('net_delta',num(n['net'])-num(b['net']))]:near(x[k],y,'all_matched_entry_money')
        near(summary[win]['matched_entry_net_delta']-D(0) if isinstance(summary[win]['matched_entry_net_delta'],D) else summary[win]['matched_entry_net_delta'],sum((num(new[k]['net'])-num(base[k]['net']) for k in set(base)&set(new)),D(0)),'matched_delta_sum')
        for field,ks,mp in [('removed_baseline',set(base)-set(new),base),('new_candidate',set(new)-set(base),new)]:
            near(summary[win][field]['net'],sum((num(mp[k]['net']) for k in ks),D(0)),'new_removed_net_sum')
        near(num(summary[win]['matched_entry_net_delta'])-num(summary[win]['removed_baseline']['net'])+num(summary[win]['new_candidate']['net']),delta,'full_matched_new_removed_identity')
        d0=data('BASELINE',win)[1];d1=data('ETA',win)[1];acts=[(a,b) for a,b in zip(d0,d1) if a['on']!=b['on']]
        assert len(acts)==len(diff['ACT_changes'])==summary[win]['ACT_changed_closes']
        for (a,b),x in zip(acts,diff['ACT_changes']):assert x['at']==a['at']==b['at'] and x['baseline_ACT_on']==a['on'] and x['candidate_ACT_on']==b['on']
        for label,col in [('stock','sid'),('month','opened'),('sector','sector')]:
            amounts={a:defaultdict(D) for a in maps}
            for a,mp in maps.items():
                if label=='month':
                    previous=D(1000000)
                    for x in data(a,win)[1]:
                        current=num(x['nav']);amounts[a][x['at'][:7]]+=current-previous;previous=current
                else:
                    for x in mp.values():
                        group=data(a,win)[0]['metadata'][str(x['layer_in_this_book'])]['sector'] if label=='sector' else x[col]
                        amounts[a][group]+=num(x['net'])
            rr=grouped[win][label]['all_rows'];assert {x['group'] for x in rr}==set(amounts['BASELINE'])|set(amounts['ETA'])
            for x in rr:
                k=x['group'];b,n=amounts['BASELINE'][k],amounts['ETA'][k]
                near(x['BASE_true_period_contribution'],b,'all_full_group_source');near(x['ETA_true_period_contribution'],n,'all_full_group_source');near(x['delta'],n-b,'all_full_group_delta')
            near(sum((num(x['delta']) for x in rr),D(0)),delta,'all_full_group_sum')
    mark=read(F/'NATIVE_CLOSE_MARK_DOMAIN.json');audit=read(O/'PVR_ETA_2022_2024_ACCOUNT_AUDIT.json')
    want=audit['cold_mark_scope']['stale_action_reference_differences_from_facts_carry'];got=mark['stale_action_differences_from_old_facts_carry']
    assert [{k:v for k,v in x.items() if k!='is_tradable_quote'} for x in got]==want and all(x['is_tradable_quote'] is False for x in got)
    for p,h in read(F/'DELIVERABLE_SHA256.json').items():assert sha(p)==h
    r=dict(status='PASS_ALL36_PERIOD20_STAGE_FINANCIAL_TABLES_FULL_STOCK_MONTH_SECTOR_ACT_AND_MARK_DOMAIN_WITH_LIMITS',checks=dict(C),source_sha256=BIND,script_sha256=sha(__file__),
           remaining=['Separate fixed83/94 whole-stock and primary10+3 identity annex audit.'],scope='Direct source completed books/daily for aggregate period NAV/DD/exposure/gross/fees; period wealth-component/detail sums from exported daily wealth basis whose endpoint source identity is checked. No repeated financial/quote engine.',technical_note='Initial group assertion treated calendar-month wealth as entry-month lifecycle cohorts; source output correctly means actual calendar-month NAV change. Audit now independently differences native daily NAV for that view; producer/books unchanged.',new_accounts=0,new_financial_events=0)
    (O/'PVR_ETA_COMPARISON_MAIN_AUDIT.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(r['status'],dict(C),flush=True)
if __name__=='__main__':main()
