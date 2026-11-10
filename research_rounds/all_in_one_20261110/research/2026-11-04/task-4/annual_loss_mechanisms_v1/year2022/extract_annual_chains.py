"""Saved-book financial aggregation and saved-table joins only; no native imports."""
import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
import pandas as pd

OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
SHARED=OUT.parent/'shared';PAIR=ROOT/'new_price_trend_v1/funding/runs/long_OFF/pair'
MANIFEST=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
D=lambda x:Decimal(str(x));Z=D(0);START='2022-01-04';END='2022-12-30';sources={}
def bind(p):
    p=Path(p);sources[str(p.resolve())]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(p):return json.loads(bind(p).read_text())
def gz(p,lines=False):
    with gzip.open(bind(p),'rt') as f:return list(map(json.loads,f)) if lines else json.load(f)
def clean(x):
    if isinstance(x,dict):return {k:clean(v)for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v)for v in x]
    if x is pd.NA or x is pd.NaT:return 'SOURCE_NULL'
    if hasattr(x,'item'):return clean(x.item())
    if isinstance(x,Decimal):return str(x)
    if isinstance(x,float) and pd.isna(x):return 'SOURCE_NULL'
    return x
def save(n,x):(OUT/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2)+'\n')
def csvsave(n,rows):
    with (OUT/n).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(clean(rows))

b=gz(PAIR/'B.json.gz');all_daily=gz(PAIR/'daily.jsonl.gz',True)
daily={r['at'][:10]:r for r in all_daily if START<=r['at'][:10]<=END}
first,last=daily[START],daily[END]
assert not first['positions'] and D(first['nav'])==D(1000000)
mark=read(SHARED/'END2022_STOCK_INVENTORY.json');marks={r['sid']:r for r in mark['rows']}
classes=read(SHARED/'ORIGINAL_BUY_CLASSIFICATIONS.json')
cycles=read(SHARED/'ORIGINAL_POSITION_CYCLES.json')
annual=read(SHARED/'ANNUAL_LAYER_WEALTH_CHANGES.json')
mother=read(SHARED/'ANNUAL_CONTRIBUTION_SUMMARY.json')['2022']
al={r['layer']:r for r in annual if r['year']==2022}
names={r['sid']:(r['name'],r['industry'])for r in mother['stock_contributions']}
trade22=[t for t in b['trades'] if START<=t['at'][:10]<=END]
div22=[r['receivable'] for r in b['audit'] if r['kind']=='dividend_accrual' and START<=r['receivable']['ex_at'][:10]<=END]
by=defaultdict(list);divs=defaultdict(list)
for t in trade22:by[t['security_id']].append(t)
for r in div22:divs[r['security_id']].append(r)
stocks=[]
for sid,tx in by.items():
    buys=[t for t in tx if t['side']=='buy'];sells=[t for t in tx if t['side']=='sell']
    cost=sum((D(t['gross_cny'])+D(t['fees_cny'])for t in buys),Z)
    proceeds=sum((D(t['gross_cny'])-D(t['fees_cny'])for t in sells),Z)
    dividend=sum((D(x['net_local'])for x in divs[sid]),Z)
    inventory=D(marks[sid]['inventory']) if sid in marks else Z
    change=proceeds-cost+dividend+inventory
    parent_change=D(next(r['annual_change']for r in mother['stock_contributions']if r['sid']==sid))
    assert abs(change-parent_change)<D('1e-18')
    stocks.append(dict(sid=sid,name=names[sid][0],industry=names[sid][1],actual_buy_fills=len(buys),actual_sell_fills=len(sells),
                       actual_buy_cash=cost,actual_net_sale_cash=proceeds,recognized_2022_dividend=dividend,
                       trade_cash_plus_recognized_dividend=proceeds-cost+dividend,
                       year_end_qty=last['positions'].get(sid,0),year_end_inventory=inventory,
                       annual_NAV_contribution=change,parent_layer_sum_minus_direct_cash_change=parent_change-change,
                       annual_contribution_pct_initial_NAV=100*change/D(first['nav']),
                       annual_source='original 2022 trade cash+recognized dividend+shared exact same-day year-end stock anchor; start inventory0'))
stocks.sort(key=lambda r:r['annual_NAV_contribution'])
assert len(stocks)==560 and len(marks)==66
assert sum((r['year_end_inventory']for r in stocks),Z)==D(last['inventory'])
assert sum((r['annual_NAV_contribution']for r in stocks),Z)==D(last['nav'])-D(first['nav'])
csvsave('ALL560_STOCK_ANNUAL_CONTRIBUTIONS.csv',stocks);save('ALL560_STOCK_ANNUAL_CONTRIBUTIONS.json',stocks)
bottom=stocks[:5];top=sorted(stocks,key=lambda r:r['annual_NAV_contribution'],reverse=True)[:3]
selected={r['sid'] for r in bottom+top}|{'600869.SH','300718.SZ'}
assert not any(r['kind']=='split'and r.get('sid') in selected and r['at'].startswith('2022')for r in b['audit'])
sm={r['symbol']:r for r in read(MANIFEST)};facts={}
for sid in sorted(selected):
    p=bind(sm[sid]['refs']['facts'])
    facts[sid]=pd.read_parquet(p,columns=['close','raw_close','factor','e0_target','i_target','i_floor','i_buy','g_grade']).loc[START:END]

funding=defaultdict(list);opps=defaultdict(list);industries=defaultdict(list)
for n,target in [('funding',funding),('opportunities',opps),('industry',industries)]:
    with gzip.open(bind(PAIR/(n+'.jsonl.gz')),'rt')as f:
        for line in f:
            r=json.loads(line);day=r.get('day',r.get('at',''))[:10]
            if day>END:break
            if n=='industry':target[r['sector']].append(r)
            elif r['sid'] in selected:target[(r['sid'],day)].append(r)
decisions={r['at']:r for r in b['decisions']}
native_layers={r['id']:r for r in b['layers']}
fill_audit={r['receipt']['receipt_id']:r for r in b['audit']if r['kind']=='fill'}
exit_requests={r['event_id']:r for r in b['audit']if r['kind']=='exit_request'}
proposals=[r for r in b['audit']if r['kind']=='pilot_layer_exit']
buy_rows=[];sell_rows=[];chain_records={};protect_changes=[];previous_lines={}
for sid in sorted(selected):
    tx=by[sid];lids={t['layer'] for t in tx if t['side']=='buy'}
    original_layer_records=[]
    for t in tx:
        if t['side']=='buy':
            lid=t['layer'];cl=classes[str(lid)];meta=b['metadata'][str(lid)]
            intent=[i for i in decisions[t['signal_at']]['intents'] if i['sid']==sid and i['kind']==t['kind']]
            assert len(intent)==1;intent=intent[0]
            ff=[r for r in funding[(sid,t['at'][:10])]if r['result']=='reserved' and r['role']==meta['role'] and r['shares']==t['shares']]
            assert len(ff)==1
            known=[r for r in industries[meta['sector']]if r['day']<=t['signal_at'][:10]]
            industry=known[-1] if known else None
            dt=pd.Timestamp(t['at'][:10]);factor=facts[sid].loc[dt,'factor'] if dt in facts[sid].index else None
            floorraw=D(t['floor'])/D(factor) if factor is not None else 'NOT_SAVED'
            final=native_layers[lid];sales=[dict(at=s['at'],receipt_id=s['receipt_id'],part=p)for s in b['trades']if s['side']=='sell'for p in s.get('parts',[])if p['layer']==lid]
            row=dict(sid=sid,name=names[sid][0],industry_name=names[sid][1],layer=lid,cycle_id=cl['cycle_id'],
                     original_signal_CLOSE=t['signal_at'],actual_OPEN=t['at'],role=meta['role'],original_kind=t['kind'],
                     actual_quantity_before_buy=cl['actual_quantity_before_fill'],actual_entry_class=cl['classification'],
                     previous_closed_cycle_net=cl['previous_closed_cycle_net'],cycle_after_prior_closed_loss=cl['cycle_after_prior_closed_loss'],
                     shares=t['shares'],actual_buy_price=t['price'],actual_buy_gross=t['gross_cny'],actual_buy_fee=t['fees_cny'],buy_cash_cost=D(t['gross_cny'])+D(t['fees_cny']),
                     first_actual_protection_floor_adjusted=t['floor'],OPEN_saved_factor=factor,first_actual_protection_floor_raw=floorraw,
                     original_intent_budget=intent['budget'],original_intent_cap=intent['cap'],original_CORE_risk_budget=intent.get('risk_budget'),
                     original_CP1_id=intent.get('CP1_id'),original_runner_I_epoch=json.dumps(t['epoch']),
                     actual_reserved_pool=ff[0]['pool'],sector=meta['sector'],original_budget_episode=meta['episode'],original_budget_attempt=meta['attempt'],
                     last_saved_industry_event_day=industry['day'] if industry else 'NOT_SAVED_INITIAL_SEED',
                     last_saved_industry_result=industry['result'] if industry else 'NOT_SAVED_INITIAL_SEED',
                     last_saved_industry_financial_level=industry['financial_level'] if industry else 'NOT_SAVED_INITIAL_SEED',
                     industry_latest_event_episode_matches_fill=industry['episode']==meta['episode']if industry else 'NOT_SAVED_INITIAL_SEED',
                     year2022_contribution=al[lid]['annual_wealth_change'],year_end_qty=al[lid]['end_qty'],year_end_layer_inventory=al[lid]['end_inventory'],
                     final_original_closed=final['closed'],final_original_reason=final['reason'],
                     original_lifecycle_net_cash_plus_dividend=D(final['cash'])+D(final['dividend']) if final['closed'] else 'NOT_CLOSED_BY_ORIGINAL_ACCOUNT_END',
                     lifecycle_is_not_annual_contribution=True)
            buy_rows.append(row)
            original_layer_records.append(dict(classification=cl,annual_layer=al[lid],original_buy=t,original_intent=intent,original_funding=ff,
                                               last_known_industry_event=industry,original_final_layer=final,original_metadata=meta,all_actual_sale_parts=sales,
                                               original_signal_opportunity=opps[(sid,t['signal_at'][:10])]))
        else:
            fa=fill_audit[t['receipt_id']];oid=fa['order_id'];created=exit_requests[oid]
            relevant=[r for r in proposals if r['sid']==sid and created['at']<=r['at']<=t['at']]
            sell_rows.append(dict(sid=sid,name=names[sid][0],actual_OPEN=t['at'],actual_shares=t['shares'],actual_raw_open=t['raw_open'],actual_sell_price=t['price'],
                                  actual_gross=t['gross_cny'],actual_sell_fee=t['fees_cny'],actual_net_sale_cash=D(t['gross_cny'])-D(t['fees_cny']),
                                  receipt_id=t['receipt_id'],order_id=oid,aggregate_order_created_at=created['at'],
                                  actual_parts=json.dumps(t['parts'],ensure_ascii=False),original_proposal_chain=json.dumps(relevant,ensure_ascii=False),
                                  aggregate_order_creation_is_not_each_layer_trigger=True))
    chain_records[sid]=dict(annual_stock=next(r for r in stocks if r['sid']==sid),original_2022_trades=tx,original_2022_dividend_accruals=divs[sid],
                           original_layer_records=original_layer_records,
                           original_position_cycles=[c for c in cycles if c['sid']==sid and c['opened'].startswith('2022')],
                           original_all_2022_opportunities=[v for (s,day),rr in opps.items() if s==sid for v in rr],
                           original_all_2022_funding=[v for (s,day),rr in funding.items() if s==sid for v in rr],
                           original_2022_exit_proposals=[p for p in proposals if p['sid']==sid and p['at'].startswith('2022')])
for day,d in daily.items():
    for l in d['layers']:
        if l['sid'] not in selected:continue
        lid=l['id'];line=l.get('last_core_line')if l['kind']=='core'else l['floor']
        old=previous_lines.get(lid)
        if old!=line:
            protect_changes.append(dict(day=day,sid=l['sid'],layer=lid,kind=l['kind'],qty=l['qty'],
                                         prior_saved_after_CLOSE_effective_line=old or 'NO_PRIOR_SAVED_LAYER_CLOSE',
                                         current_saved_after_CLOSE_effective_line=line,source='original daily snapshot; not old-F check return log'))
        previous_lines[lid]=line
csvsave('SELECTED10_ALL_ORIGINAL_BUYS.csv',buy_rows);save('SELECTED10_ALL_ORIGINAL_BUYS.json',buy_rows)
csvsave('SELECTED10_ALL_2022_ACTUAL_SELLS.csv',sell_rows)
csvsave('SELECTED10_SAVED_PROTECTION_LINE_CHANGES.csv',protect_changes)
save('SELECTED10_FULL_ORIGINAL_CHAIN_RECORDS.json',chain_records)
buy_lookup={r['layer']:r for r in buy_rows};exit_rows=[]
for p in proposals:
    sid=p['sid'];day=p['at'][:10]
    if sid not in selected or not START<=day<=END:continue
    dt=pd.Timestamp(day)
    fact=facts[sid].loc[dt] if dt in facts[sid].index else None
    for lid in p['layers']:
        live=[l for l in daily[day]['layers']if l['id']==lid]
        assert len(live)==1
        l=live[0];line=l.get('last_core_line')if l['kind']=='core'else l['floor']
        factor=fact['factor']if fact is not None else None
        later=[dict(at=t['at'],raw_open=t['raw_open'],actual_price=t['price'],receipt_id=t['receipt_id'],part=part,
                    order_id=fill_audit[t['receipt_id']]['order_id'])
               for t in b['trades']if t['side']=='sell'and t['at']>p['at']for part in t.get('parts',[])if part['layer']==lid]
        ex=dict(sid=sid,name=names[sid][0],layer=lid,cycle_id=classes[str(lid)]['cycle_id'],kind=l['kind'],
                proposal_CLOSE=p['at'],original_reason=p['reason'],original_proposal_target_shares=p['shares'],
                original_proposal_target_layers=json.dumps(p['layers']),layer_qty_at_proposal=l['qty'],
                saved_signal_CLOSE_adjusted=fact['close']if fact is not None else 'NOT_SAVED',
                saved_signal_CLOSE_raw=fact['raw_close']if fact is not None else 'NOT_SAVED',saved_signal_factor=factor,
                saved_effective_line_at_proposal_adjusted=line,
                saved_effective_line_at_proposal_raw=D(line)/D(factor)if factor is not None else 'NOT_SAVED',
                original_i_target=fact['i_target']if fact is not None else 'NOT_SAVED',
                line_source='exact proposal-day original daily Mobile x.floor / CORE last_core_line, never final layer floor',
                CP_branch_old_line_note='Mobile CP exits check old floor and skip raise in that branch, so this unchanged daily floor is the checked line'if p['reason']=='CP1_add_protection'else 'I/ACT exit condition does not require price crossing this line',
                first_actual_later_sell_OPEN=later[0]['at']if later else 'NOT_SAVED_FILLED',
                first_actual_later_raw_OPEN=later[0]['raw_open']if later else 'NOT_SAVED_FILLED',
                first_actual_later_sell_price=later[0]['actual_price']if later else 'NOT_SAVED_FILLED',
                all_actual_later_sale_parts=json.dumps(later,ensure_ascii=False),
                link_rows_not_independent_financial_flows=True)
        exit_rows.append(ex)
csvsave('SELECTED10_EACH_EXIT_PROPOSAL_CLOSE_LINE_AND_ACTUAL_OPEN.csv',exit_rows)
save('SELECTED10_EACH_EXIT_PROPOSAL_CLOSE_LINE_AND_ACTUAL_OPEN.json',exit_rows)
mechanisms=[]
for sid in selected:
    aa=[r for r in annual if r['year']==2022 and r['sid']==sid]
    mechanisms.append(dict(sid=sid,name=names[sid][0],annual_contribution=next(r['annual_NAV_contribution']for r in stocks if r['sid']==sid),
                           role_contributions={role:sum((D(r['annual_wealth_change'])for r in aa if r['kind']==role),Z)for role in ['core','add']},
                           actual_buy_class_contributions={cls:sum((D(r['annual_wealth_change'])for r in aa if r['classification']==cls),Z)for cls in ['first_account_entry','add_to_existing','reentry']},
                           actual_stock_cycles=chain_records[sid]['original_position_cycles']))
save('SELECTED10_MECHANISM_AND_CYCLE_SUMMARIES.json',mechanisms)
summary=dict(year=2022,initial_NAV=first['nav'],year_end_NAV=last['nav'],annual_NAV_change=D(last['nav'])-D(first['nav']),
             denominator='original initial all-cash NAV1,000,000; original first CLOSE Jan4 to last CLOSE Dec30',
             return_pct=100*(D(last['nav'])-D(first['nav']))/D(first['nav']),stocks=560,year_end_flat_stocks=494,year_end_held_stocks=66,
             buy_fills=sum(t['side']=='buy'for t in trade22),sell_fills=sum(t['side']=='sell'for t in trade22),
             actual_fees=sum((D(t['fees_cny'])for t in trade22),Z),recognized_dividend=sum((D(r['net_local'])for r in div22),Z),
             stock_negative_count=sum(r['annual_NAV_contribution']<0 for r in stocks),stock_positive_count=sum(r['annual_NAV_contribution']>0 for r in stocks),
             negative_stock_sum=sum((r['annual_NAV_contribution']for r in stocks if r['annual_NAV_contribution']<0),Z),
             positive_stock_sum=sum((r['annual_NAV_contribution']for r in stocks if r['annual_NAV_contribution']>0),Z),
             worst_five=bottom,top_three=top,
             worst_five_sum=sum((r['annual_NAV_contribution']for r in bottom),Z),
             worst_five_share_of_total_net_loss_pct=100*sum((r['annual_NAV_contribution']for r in bottom),Z)/(D(last['nav'])-D(first['nav'])),
             selected_chain_stocks=sorted(selected),selected_buys=len(buy_rows),selected_sell_receipts=len(sell_rows),
             all_stock_annual_contributions_match_parent_shared_mother_within_1e_18=True,
             maximum_stock_parent_layer_sum_vs_direct_cash_rounding_difference=max(abs(r['parent_layer_sum_minus_direct_cash_change'])for r in stocks),
             inventory_anchor=mark['status'],inventory_anchor_residual=mark['residual'],
             source_classification='Reused parent ORIGINAL_BUY_CLASSIFICATIONS and ORIGINAL_POSITION_CYCLES; no second quantity replay',
             Market_Account_Runner_model_parameter_backtest_calls=0)
save('ANNUAL_SCOPE_AND_FINANCIAL_CHECK.json',summary);save('SOURCE_SHA256.json',sources)
print(json.dumps(clean(summary),ensure_ascii=False))
