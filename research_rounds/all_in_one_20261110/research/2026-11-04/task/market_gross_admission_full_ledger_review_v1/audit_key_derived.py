"""Final bounded D-only derived reporting audit; no account, indicator or B replay."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict, Counter
import importlib.util,json,csv
O=Path(__file__).resolve().parent;T=O.parent;AN=T/'market_gross_admission_outcome_analysis_v1';Z=D(0)
s=importlib.util.spec_from_file_location('existing_pure_saved_native_reader',T/'independent_review/trend_confirmation_full_ledger_v1/generic_saved_finance_reader.py');R=importlib.util.module_from_spec(s);s.loader.exec_module(R)
def day(v):return str(v)[:10]
def csvrows(p):R.SRC[str(p.resolve())]=R.sha(p);return list(csv.DictReader(p.open()))

report={};longdata=None
for win,n in [('long',726),('strong',242)]:
    root=T/'market_gross_admission_native_v1'/('full-'+win+'-v1');out=AN/('full_'+win+'_v1')
    ds=R.rows(root/'pair/daily.jsonl.gz');assert len(ds)==n and {d['account']for d in ds}=={'D_GROSS10'}
    book=R.book(root/'pair/D_GROSS10.json.gz');index={day(d['at']):i for i,d in enumerate(ds)}
    info=R.read(T/'market_gross_admission_native_v1/prepared'/win/'MARKET_INFO_FULL_CLOCKS.json')['all_scheduled_OPEN_CLOSE']
    opens={day(x['at']):x for x in info if x['at'][11:16]=='09:30'}
    lag=[Z]+[D(d['inventory'])/D(d['nav'])*100 for d in ds[:-1]]
    h_open=[True]+[bool(d['on'])for d in ds[:-1]]
    trade_byday=defaultdict(list)
    for t in book['trades']:trade_byday[day(t['at'])].append(t)
    div_byday=defaultdict(lambda:Z)
    for e in book['audit']:
        if e['kind']=='dividend_accrual':div_byday[day(e['receivable']['ex_at'])]+=D(e['receivable']['net_local'])
    def stats(lo,hi):
        ids=[i for i,d in enumerate(ds)if lo<=day(d['at'])<=hi];assert ids
        begin=D(ds[ids[0]-1]['nav'])if ids[0]else D(1000000);end=D(ds[ids[-1]]['nav']);tx=[t for i in ids for t in trade_byday[day(ds[i]['at'])]]
        buys=[t for t in tx if t['side']=='buy'];sells=[t for t in tx if t['side']=='sell']
        return dict(start=day(ds[ids[0]]['at']),end=day(ds[ids[-1]]['at']),days=len(ids),initial_own_NAV=begin,end_NAV=end,return_pct=(end/begin-1)*100,wealth_change=end-begin,mean_lag_exposure_pct=sum((lag[i]for i in ids),Z)/D(len(ids)),paused_OPEN_days=sum(not h_open[i]for i in ids),actual_buy_cash=sum((D(t['gross_cny'])+D(t['fees_cny'])for t in buys),Z),actual_sell_net=sum((D(t['gross_cny'])-D(t['fees_cny'])for t in sells),Z),actual_fees=sum((D(t['fees_cny'])for t in tx),Z),recognized_dividend=sum((div_byday[day(ds[i]['at'])]for i in ids),Z),buy_fills=len(buys),sell_fills=len(sells))
    def match(actual,expected):
        for k,v in actual.items():
            if k in ('start','end','days','paused_OPEN_days','buy_fills','sell_fills'):assert str(v)==str(expected[k]),(win,k,v,expected[k])
            else:R.near(v,expected[k],('derived D reporting',win,k))
    months=csvrows(out/'ALL_MONTHS.csv');assert len(months)==(36 if win=='long' else 12)
    # B monthly fields are referenced only from a previously independently audited report.
    oldpath=T/'trend_confirmation_outcome_analysis_v1'/('full_'+win+'_v1')/'ALL_MONTHS.csv';old=csvrows(oldpath);oldB={x['period']:x for x in old if x['arm']=='B'}
    for r in months:
        ss=stats(r['period']+'-01',r['period']+'-31')
        for k,field in [('wealth_change','D_wealth'),('return_pct','D_return_pct'),('end_NAV','D_own_end_NAV'),('mean_lag_exposure_pct','D_mean_lag_exposure_pct'),('actual_fees','D_fees')]:R.near(ss[k],r[field],('monthly',win,r['period'],field))
        oldrow=oldB[r['period']]
        for k,field in [('wealth_change','B_wealth'),('return_pct','B_return_pct'),('end_NAV','B_own_end_NAV'),('mean_lag_exposure_pct','B_mean_lag_exposure_pct'),('actual_fees','B_fees')]:R.near(oldrow[k],r[field],'quoted already-reviewed B monthly field')
    R.near(sum((D(r['D_wealth'])for r in months),Z),D(ds[-1]['nav'])-D(1000000),'full monthly telescope')
    segments=R.read(out/'ALL_PREDECLARED_OPEN_SEGMENTS_VS_ARCHIVED_B.json');covered=[];segment_money=defaultdict(lambda:Z);segment_count=Counter()
    for seg in segments:
        definition=seg['definition'];days=definition['days'];assert len(days)==definition['observations']
        assert days==[day(d['at'])for d in ds if definition['start']<=day(d['at'])<=definition['end']]
        for d in days:assert opens[d]['state']==definition['state']
        for row in definition['source_information_clocks']:
            x=opens[day(row['at'])];assert row['information_day']==x['day']and R.ts(row['available_at'])==R.ts(x['available_at'])
        actual=stats(definition['start'],definition['end']);match(actual,seg['D_GROSS10']);covered.extend(days);segment_count[definition['state']]+=1;segment_money[definition['state']]+=actual['wealth_change']
    assert covered==[day(d['at'])for d in ds]and len(set(covered))==n
    R.near(sum(segment_money.values(),Z),D(ds[-1]['nav'])-D(1000000),'complete D/ND segment telescope')
    report[win]=dict(monthly_rows=len(months),segments=len(segments),segment_counts=dict(segment_count),segment_D_actual_wealth={k:str(v)for k,v in segment_money.items()},months_and_all_predeclared_segment_wealth_own_denominators_fees_actualcounts_PASS=True,archived_B_month_fields_referenced_from_already_reviewed_report=True,archived_B_segment_values_not_recomputed=True)
    if win=='long':longdata=dict(ds=ds,book=book,index=index,opens=opens,h_open=h_open,lag=lag,trade_byday=trade_byday,stats=stats,match=match)
# The closures above are rebound by the strong iteration; reconstruct long-only reporting arrays once.
root=T/'market_gross_admission_native_v1/full-long-v1';out=AN/'full_long_v1';ds=longdata['ds'];book=longdata['book'];index=longdata['index'];opens=longdata['opens'];h_open=longdata['h_open'];lag=longdata['lag'];trade_byday=longdata['trade_byday'];div_byday=defaultdict(lambda:Z)
for e in book['audit']:
    if e['kind']=='dividend_accrual':div_byday[day(e['receivable']['ex_at'])]+=D(e['receivable']['net_local'])
ph=R.read(out/'FIXED_PHASE_WEALTH.json');six=stats('2024-09-24','2024-10-08');post=stats('2024-10-09','2024-12-31');match(six,ph['924_six_closes']['own_NAV_account_period']);match(post,ph['post924']['own_NAV_account_period']);sixids=[i for i,d in enumerate(ds)if '2024-09-24'<=day(d['at'])<='2024-10-08'];assert len(sixids)==6 and [h_open[i]for i in sixids]==[False,False,False,False,True,True]
assert not any(trade_byday[day(ds[i]['at'])]for i in sixids[:4])
bound=ds[index['2024-10-08']];active={l['id']:l for l in bound['layers']};groups=defaultdict(lambda:dict(layers=0,wealth=Z));new_roles=defaultdict(lambda:dict(layers=0,actual_buy_cash=Z,original_path_contribution=Z,positive_layer_contribution=Z,negative_layer_contribution=Z));buys={t['layer']:t for t in book['trades']if t['side']=='buy'}
for l in book['layers']:
    net=D(l['cash'])+D(l['dividend'])+(D(l['qty'])*R.mark(l['sid'],ds[-1]['at'])if l['qty']else Z)
    if day(l['opened'])>'2024-10-08':
        group='new_fill_after_boundary';before=Z;role=book['metadata'][str(l['id'])]['budget_order'].split('|')[-1];z=new_roles[role];z['layers']+=1;z['actual_buy_cash']+=D(buys[l['id']]['gross_cny'])+D(buys[l['id']]['fees_cny']);z['original_path_contribution']+=net
        z['positive_layer_contribution'if net>0 else'negative_layer_contribution']+=net
    elif l['id']in active:
        group='actually_held_at_boundary';x=active[l['id']];before=D(x['cash'])+D(x['dividend'])+D(x['qty'])*R.mark(l['sid'],bound['at'])
    else:group='already_closed_at_boundary';before=net
    groups[group]['layers']+=1;groups[group]['wealth']+=net-before
for k,v in groups.items():assert v['layers']==ph['post924_old_new_D']['groups'][k]['layers'];R.near(v['wealth'],ph['post924_old_new_D']['groups'][k]['wealth'],'post924 existing/new period bridge')
R.near(sum((v['wealth']for v in groups.values()),Z),post['wealth_change'],'post924 complete cohort telescope')
role_report=R.read(out/'POST924_NEW_ROLE_CONTRIBUTION.json')
for r in role_report['rows']:
    actual=new_roles[r['role']]
    for k,v in actual.items():R.near(v,r[k],('post924 new actual role',r['role'],k))
mobile_share=new_roles['mobile']['original_path_contribution']/post['wealth_change']*100
# Only D first-buy observations are newly checked. B rows remain archived references.
contexts=R.read(out/'FIRST_BUY_RECOVERY_CONTEXT.json');chosen={'June22_ND','Feb24_ND','Sep24_ACT_resume'};checked=[];risk_events=[e for e in book['audit']if e['kind']=='risk_checkpoint'and e.get('event')];first_pause=next(e for e in risk_events if e['event']=='pause');assert day(first_pause['at'])=='2024-06-11';resume=next(e for e in risk_events if e['event']=='resume');assert day(resume['at'])=='2024-09-27'
for r in contexts['rows']:
    if r['arm']!='D_GROSS10'or r['context']not in chosen:continue
    candidates=[t for t in book['trades']if t['side']=='buy'and r['lo']<=day(t['at'])<=r['hi']];assert candidates
    first=min(day(t['at'])for t in candidates);assert first==r['first_actual_buy_day'];tx=[t for t in candidates if day(t['at'])==first];i=index[first];prev=ds[i-1]
    assert len(tx)==int(r['buy_fills'])and bool(h_open[i])==r['own_ACT_at_OPEN'];R.near(sum((D(t['gross_cny'])+D(t['fees_cny'])for t in tx),Z),r['actual_buy_cash'],'first actual buy DAY cash, not entire context')
    R.near(lag[i],r['lag_market_exposure_pct'],'first buy day prior close exposure');R.near(D(ds[i]['inventory'])/D(ds[i]['nav'])*100,r['close_market_exposure_pct'],'first buy day closing exposure')
    if r['context']in('June22_ND','Feb24_ND'):
        assert opens[day(prev['at'])]['state']=='DOWN'and opens[first]['state']=='NOT_DOWN';assert h_open[i]and first<day(first_pause['at']);meaning='market D-to-ND extra cap removed; own ACT was already ON, not an ACT recovery event'
    else:
        assert first=='2024-09-30'and day(resume['at'])=='2024-09-27'and h_open[i];meaning='original own ACT resumes at Sep27 CLOSE; Sep30 is next actual legal buy OPEN'
    checked.append(dict(context=r['context'],first_buy_day=first,first_buy_at=tx[0]['at'],first_day_buy_fills=len(tx),first_day_actual_buy_cash=r['actual_buy_cash'],previous_close_available_cash=prev['available'],previous_close_inventory=prev['inventory'],previous_close_held_stocks=len(prev['positions']),first_buy_day_close_available_cash=ds[i]['available'],first_buy_day_close_inventory=ds[i]['inventory'],first_buy_day_close_held_stocks=len(ds[i]['positions']),gate_semantics=meaning))
assert len(checked)==3
final=dict(status='PASS_FINAL_BOUNDED_D_DERIVED_PERIODS_924_AND_RECOVERY_CONTEXT',windows=report,period_924={k:str(v)if isinstance(v,D)else v for k,v in six.items()},period_post924={k:str(v)if isinstance(v,D)else v for k,v in post.items()},post924_old_new_period_wealth={k:{n:str(z)if isinstance(z,D)else z for n,z in v.items()}for k,v in groups.items()},post924_new_actual_roles={k:{n:str(z)if isinstance(z,D)else z for n,z in v.items()}for k,v in new_roles.items()},mobile_net_loss_share_percent=str(mobile_share),mobile_share_denominator='entire post924 account net wealth loss186615.497058490701, not only new311 cohort or gross negative trades',first_buy_recovery_context_D_only=checked,archived_B_first_buy_context_rows='Quoted only; no new B book/financial reconstruction',new_accounts_indicators_or_financial_events=0,scope='Period and actual-entry-role association only. No request-before/after attribution, no deleted-order/avoided-loss profit claim, no new recovery mechanism. First-day buy cash/counts belong to that DAY, not the entire context interval.',source_sha256=R.SRC,checker_sha256=R.sha(__file__))
p=O/'DERIVED_KEY_REVIEW.json';assert not p.exists();p.write_text(json.dumps(final,indent=2)+'\n');print(json.dumps({k:v for k,v in final.items()if k not in ['source_sha256','post924_new_actual_roles','post924_old_new_period_wealth']}));print('RECEIPT_SHA',R.sha(p))
