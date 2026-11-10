
"""Three completed arms, identical 78-day estimands. No engine/strategy execution."""
from pathlib import Path
from decimal import Decimal as D
import json,gzip,hashlib,importlib.util,collections,csv
import pandas as pd
HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'growth_continuous_78_v1'
SPEC=importlib.util.spec_from_file_location('sealed_performance_metrics',OLD/'performance_metrics_execution_v1.py')
M=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(M)
START,END='2023-01-03','2023-04-28';Z=D(0)
RUNS={'original':OLD/'baseline/run','growth_capped':OLD/'growth/run','growth_no_qcap':HERE/'growth/run'}
def enc(x):return str(x) if isinstance(x,D) else str(x)
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=enc)+'\n')
def lines(p):return [json.loads(l) for l in gzip.open(p,'rt')]
def load(p):return json.load(gzip.open(p,'rt'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def inwindow(x):return START<=x['at'][:10]<=END
def main():
    assert all(json.loads((r/'DONE.json').read_text())['completed'] for r in RUNS.values())
    out=HERE/'comparison';assert not out.exists(),'No report overwrite';out.mkdir()
    manifest_path=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/manifest.json')
    manifest={x['series_id']:x for x in json.loads(manifest_path.read_text())['series']}
    prices={};sourcepaths=[Path(__file__),HERE/'METRICS_CONTRACT.md',OLD/'performance_metrics_execution_v1.py',manifest_path]
    def close(sid):
        if sid not in prices:
            p=Path(manifest[sid]['raw']['path']);f=pd.read_parquet(p)
            if 'trade_date' in f:f=f.set_index('trade_date')
            elif 'date' in f:f=f.set_index('date')
            f.index=pd.DatetimeIndex(pd.to_datetime(f.index));v=f.loc[pd.Timestamp(END),'close']
            assert pd.notna(v) and v>0,('end mark needs audit',sid)
            prices[sid]=D(str(v));sourcepaths.append(p)
        return prices[sid]
    summary={};case={};bridges={};fillrows=[];stockrows=[];all_rounds={};closed_by_arm={}
    for label,run in RUNS.items():
        a=load(run/'pair/PVR.json.gz');daily=[x for x in lines(run/'pair/daily.jsonl.gz') if inwindow(x)]
        result,closed,rounds=M.arm(run);all_rounds[label]=rounds;closed_by_arm[label]=closed
        for key in ('exit_cohort','exit_cohort_inherited','exit_cohort_new'):
            if not result[key]['wins'] or not result[key]['losses']:result[key]['profit_factor']=None
        q=collections.Counter();fills=[];fee=Z;seedcash=Z;addcash=Z;seedn=addn=0
        allbuys={};trueadded={}
        for j in a['journal']:
            sid=j.get('sid');kind=j['kind']
            if kind=='real_buy_fill':
                before=q[sid];q[sid]+=j['shares'];cash=D(j['price'])*j['shares']+D(j['fees'])
                trueadded[j['layer']]=before>0;allbuys[j['layer']]=dict(cash=cash,qty=j['shares'],sid=sid)
                if inwindow(j):
                    row=dict(arm=label,at=j['at'],sid=sid,qty=j['shares'],before_qty=before,classification='held_add' if before else 'flat_trial',cash=cash,fee=D(j['fees']),layer=j['layer'])
                    fills.append(row);fillrows.append(row)
                    if before:addn+=1;addcash+=cash
                    else:seedn+=1;seedcash+=cash
                    fee+=D(j['fees'])
            elif kind=='real_sell_fill':
                q[sid]-=j['shares'];assert q[sid]>=0
                if inwindow(j):fee+=D(j['fees'])
            elif kind=='actual_split':q[sid]=int(D(q[sid])*D(j['ratio']))
        assert {k:v for k,v in q.items() if v}==daily[-1]['positions']
        marks={sid:qty*close(sid) for sid,qty in q.items() if qty}
        assert sum(marks.values(),Z)==D(daily[-1]['inventory'])
        seedmark=sum(x['qty']*close(x['sid']) for x in daily[-1]['layers'] if not trueadded[x['id']])
        addmark=sum(x['qty']*close(x['sid']) for x in daily[-1]['layers'] if trueadded[x['id']])
        assert seedmark+addmark==D(daily[-1]['inventory'])
        openrounds=[r for r in rounds if not r['exited']]
        closedtotal=sum(r['pnl_including_dividend'] for r in rounds if r['exited'])
        opentotal=sum(r['sell_net']+r['dividend']+marks.get(r['sid'],Z)-r['buy_cash'] for r in openrounds)
        assert abs(closedtotal+opentotal-(D(daily[-1]['nav'])-D(1200000)))<D('0.000001'),('NAV round bridge',label,closedtotal,opentotal)
        result.update(buy_fills=len(fills),flat_trial_fills=seedn,held_add_fills=addn,flat_trial_cash=seedcash,held_add_cash=addcash,total_buy_cash=seedcash+addcash,window_actual_fees=fee,end_cash=D(daily[-1]['available']),mean_close_cash=sum(D(d['available']) for d in daily)/len(daily),end_stocks=len(daily[-1]['positions']),mean_close_stocks=D(sum(len(d['positions']) for d in daily))/len(daily),end_seed_layer_mark=seedmark,end_true_added_layer_mark=addmark,end_seed_mark_over_nav=seedmark/D(daily[-1]['nav']),round_closed_total_all_history=closedtotal,end_open_round_book_pnl=opentotal)
        if label!='original':
            sourcepaths.append(run/'GROWTH_CANDIDATES.jsonl.gz')
            cand=[c for c in lines(run/'GROWTH_CANDIDATES.jsonl.gz') if not c['flat']]
            selected=[c for c in cand if c['selected_qty']]
            for c in selected:
                v=c['selected_values']
                assert D(c['U_avg'])>0 and D(c['U_layer'])>0 and D(v['U_post'])>0
                assert D(c['H'])+D(c['L'])+D(c['P'])+D(v['Dnew'])<=D('.25')*D(c['R0'])+D(v['U_post'])
                if label=='growth_capped':assert c['selected_qty']<=c['qty']
            result['selected_adds_larger_than_preheld']=sum(c['selected_qty']>c['qty'] for c in selected)
            result['selected_add_budget_checks']=len(selected)
            parts=[x for x in lines(run/'REALIZED_LAYER_PARTS.jsonl.gz') if inwindow(x)]
            states=json.loads((run/'GROWTH_STATES.json').read_text())['PVR']
            result['growth_diagnostics']=dict(held_candidates=len(cand),H_positive_candidates=sum(D(c['H'])>0 for c in cand),H_positive_selected=sum(D(c['H'])>0 and c['selected_qty']>0 for c in cand),P_positive_candidates=sum(D(c['P'])>0 for c in cand),delta_positive_candidates=sum(D(c['delta'])>D('1e-12') for c in cand),delta_negative_candidates=sum(D(c['delta'])<D('-1e-12') for c in cand),avg_positive_layer_nonpositive=sum(D(c['U_avg'])>0 and D(c['U_layer'])<=0 for c in cand),avg_nonpositive_layer_positive=sum(D(c['U_avg'])<=0 and D(c['U_layer'])>0 for c in cand),unknown_candidates=sum(bool(c['unknown']) for c in cand),window_negative_add_parts_loss=sum((max(Z,-D(x['realized'])) for x in parts if x['added']),Z),window_negative_seed_parts_loss=sum((max(Z,-D(x['realized'])) for x in parts if not x['added']),Z),window_layer_realized_net=sum((D(x['realized']) for x in parts),Z),end_live_H=sum((D(x['H']) for x in states.values() if x['qty']),Z),end_live_H_all=sum((D(x['H_all']) for x in states.values() if x['qty']),Z))
            sourcepaths.extend([run/'REALIZED_LAYER_PARTS.jsonl.gz',run/'GROWTH_STATES.json'])
        summary[label]=result
        case[label]={}
        for sid in ['601019.SH','601298.SH']:
            relevant=[r for r in rounds if r['sid']==sid and (not r['exited'] or r['exited'][:10]>=START)]
            ev=[j for j in a['journal'] if j.get('sid')==sid and inwindow(j) and j['kind'] in ['real_buy_fill','real_sell_fill']]
            case[label][sid]=dict(window_events=ev,rounds_active_or_closed_in_window=relevant,end_qty=q[sid],end_mark=marks.get(sid,Z),scope='Window ends 2023-04-28. May Qingdao additions and exits are excluded.')
        for sid in sorted({r['sid'] for r in rounds}):
            rs=[r for r in rounds if r['sid']==sid]
            realized=sum(r['pnl_including_dividend'] for r in rs if r['exited'])
            opened=sum(r['sell_net']+r['dividend']+marks.get(sid,Z)-r['buy_cash'] for r in rs if not r['exited'])
            stockrows.append(dict(arm=label,sid=sid,closed_pnl_all_history=realized,end_open_pnl=opened,total_contribution=realized+opened,end_qty=q[sid],end_mark=marks.get(sid,Z)))
        save(out/(label.upper()+'_CLOSED_ROUNDS.json'),closed);save(out/(label.upper()+'_ALL_ROUNDS.json'),rounds)
        sourcepaths.extend([run/'DONE.json',run/'pair/PVR.json.gz',run/'pair/daily.jsonl.gz'])
    for old in ['original','growth_capped']:
        a=summary['growth_no_qcap'];b=summary[old]
        nav=a['end_nav']-b['end_nav'];closed=a['exit_cohort']['net_pnl']-b['exit_cohort']['net_pnl'];opened=a['end_open_round_book_pnl']-b['end_open_round_book_pnl']
        assert abs(nav-closed-opened)<D('0.000001')
        bridges[old]=dict(new_minus_old_end_NAV=nav,window_closed_round_pnl_difference=closed,end_open_book_pnl_difference=opened,residual=nav-closed-opened)
    result=dict(scope=[START,END],sessions=78,arms=summary,nav_bridges=bridges,nav_bridge_note='Exit cohort values are full-lifecycle PnL of rounds closing in-window; open and stock values also include inherited history. Only same-checkpoint arm differences attribute the window NAV difference.',only_economic_change='Remove q<=current_qty in growth predicate; all original policies preserved',outside_window_note='Qingdao May losses are not included',validation='Native accounting and closed/open bridge; not a return optimization proof')
    before=json.loads((RUNS['growth_capped']/'INITIAL_GROWTH_STATES.json').read_text())
    after=json.loads((RUNS['growth_no_qcap']/'INITIAL_GROWTH_STATES.json').read_text())
    assert before==after,'Different inherited growth state'
    left=lines(RUNS['growth_capped']/'GROWTH_CANDIDATES.jsonl.gz');right=lines(RUNS['growth_no_qcap']/'GROWTH_CANDIDATES.jsonl.gz')
    first=None
    for k,(a,b) in enumerate(zip(left,right)):
        if a!=b:
            keys=('at','sid','role','flat','qty','C_layer','C_avg','R0','H','L','P','U_layer','U_avg','maxq','available','decision_nav','native_pending_cash','candidate_floor','buy_price')
            assert all(a.get(n)==b.get(n) for n in keys),('first divergence not identical decision state',k)
            assert b['selected_qty']>a['selected_qty'] and b['selected_qty']>b['qty']
            first=dict(index=k,at=b['at'],sid=b['sid'],before_qty=b['qty'],old_selected_qty=a['selected_qty'],new_selected_qty=b['selected_qty'],old_values=a.get('selected_values'),new_values=b.get('selected_values'))
            break
    result['initial_growth_states_exact']=True;result['first_growth_candidate_divergence']=first
    sourcepaths.extend([RUNS['growth_capped']/'INITIAL_GROWTH_STATES.json',RUNS['growth_no_qcap']/'INITIAL_GROWTH_STATES.json'])
    save(out/'SUMMARY.json',result);save(out/'SPECIFIED_STOCK_PATHS.json',case)
    top=sorted(closed_by_arm['original'],key=lambda r:r['pnl_including_dividend'],reverse=True)[:5]
    tails=[dict(original_reference=r,arms={label:[x for x in rounds if x['sid']==r['sid'] and (not x['exited'] or x['exited'][:10]>=START)] for label,rounds in all_rounds.items()}) for r in top]
    save(out/'ORIGINAL_TOP5_PROFIT_STOCK_PATHS.json',tails)
    for name,rs in [('FILLS.csv',fillrows),('STOCK_CONTRIBUTIONS.csv',stockrows)]:
        with (out/name).open('w') as f:w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
    by={(r['arm'],r['sid']):r for r in stockrows};deltas=[]
    for sid in sorted({r['sid'] for r in stockrows}):
        n=by.get(('growth_no_qcap',sid),{});c=by.get(('growth_capped',sid),{});b=by.get(('original',sid),{})
        deltas.append(dict(sid=sid,new_minus_capped=n.get('total_contribution',Z)-c.get('total_contribution',Z),new_minus_original=n.get('total_contribution',Z)-b.get('total_contribution',Z)))
    assert abs(sum(r['new_minus_capped'] for r in deltas)-bridges['growth_capped']['new_minus_old_end_NAV'])<D('0.000001')
    assert abs(sum(r['new_minus_original'] for r in deltas)-bridges['original']['new_minus_old_end_NAV'])<D('0.000001')
    with (out/'STOCK_CONTRIBUTION_DIFFERENCES.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(deltas[0]));w.writeheader();w.writerows(sorted(deltas,key=lambda r:r['new_minus_capped']))
    save(out/'SOURCE_HASHES.json',{str(p):sha(p) for p in sorted(set(sourcepaths))})
    print(json.dumps(result,ensure_ascii=False,default=enc))
if __name__=='__main__':main()
