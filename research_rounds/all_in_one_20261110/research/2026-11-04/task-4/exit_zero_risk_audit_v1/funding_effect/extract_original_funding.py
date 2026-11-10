"""Original saved No60 JSON selection only; never instantiate a market/account."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import csv
import gzip
import hashlib
import json
import time

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
BASE=ROOT/'new_price_trend_v1/funding/runs/long_OFF/pair'
SID='000620.SZ';SECTOR='URFI881153';NS='NOT_SAVED'
START='2022-01-27 15:10:00+08:00';END='2022-02-08 09:30:00+08:00'
HASH={}

def bind(path):
    p=Path(path).resolve();HASH[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p

def read(path):return json.loads(bind(path).read_text())

def gz(path,lines=False):
    with gzip.open(bind(path),'rt')as f:return [json.loads(s)for s in f]if lines else json.load(f)

def save(name,x):(OUT/name).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')

def csvwrite(name,rows):
    if not rows:return
    with (OUT/name).open('w',newline='')as f:
        names=list(dict.fromkeys(k for r in rows for k in r))
        w=csv.DictWriter(f,fieldnames=names);w.writeheader()
        w.writerows({k:json.dumps(v,ensure_ascii=False,separators=(',',':'))if isinstance(v,(dict,list))else v for k,v in r.items()}for r in rows)

def main():
    t0=time.monotonic();bind(__file__)
    yingxin=read(ROOT/'mobile_allocation_audit_v1/yingxin/ORIGINAL_ONLY_DAILY_INPUTS.json')
    ys={r['original_CLOSE_clock'][:10]:r for r in yingxin}
    book=gz(BASE/'B.json.gz')
    all_daily=gz(BASE/'daily.jsonl.gz',True)
    daily={r['at'][:10]:r for r in all_daily}
    ordered=list(daily)
    balances=gz(BASE/'balances.jsonl.gz',True)
    fund=[dict(original_stream_index=k,**r)for k,r in enumerate(gz(BASE/'funding.jsonl.gz',True))if START<=r['at']<=END]
    industry=[dict(original_stream_index=k,**r)for k,r in enumerate(gz(BASE/'industry.jsonl.gz',True))if '2022-01-26'<=r['day']<='2022-02-08']
    decisions={r['at'][:10]:r for r in book['decisions']}
    exit_trade=next(r for r in book['trades']if r['security_id']==SID and r['side']=='sell'and r['at']==END)
    assert exit_trade['shares']==9900
    # Source trade and journal order, plus original opening code, establish sells first.
    journal=[dict(original_journal_index=k,**r)for k,r in enumerate(book['journal'])if START<=r.get('at','')<=END]
    exit_jindex=next(r['original_journal_index']for r in journal if r['kind']=='real_sell_fill'and r.get('sid')==SID)
    same_open_reserves=[r for r in journal if r.get('at')==END and r['kind']=='real_reserve']
    assert same_open_reserves and all(exit_jindex<r['original_journal_index']for r in same_open_reserves)
    origintents={}
    for row in fund:
        day=row['at'][:10]
        signalday=ordered[ordered.index(day)-1]if '09:30' in row['at']else day
        row['signal_day']=signalday
        candidates=[i for i in decisions[signalday]['intents']if i['sid']==row['sid']and i['role']==row['role']]
        row['original_intent']=candidates[0]if len(candidates)==1 else NS
        row['original_intent_match_count']=len(candidates)
        origintents[(signalday,row['sid'])]=None
    # Only select already saved opportunities, not new signals; preserve original sector identity.
    opportunities=[];lookup={}
    with gzip.open(bind(BASE/'opportunities.jsonl.gz'),'rt')as f:
        for k,line in enumerate(f):
            r=json.loads(line)
            if r['day']>'2022-02-08':break
            if r['day']<'2022-01-27':continue
            if (r['day'],r['sid'])in origintents or r['sector']==SECTOR:
                tagged=dict(original_stream_index=k,**r);opportunities.append(tagged)
                lookup[(r['day'],r['sid'])]=tagged
    for row in fund:
        original_opp=lookup.get((row['signal_day'],row['sid']))
        assert original_opp is not None
        row['original_opportunity']=original_opp
        row['original_sector']=original_opp['sector']
        row['same_real_estate_sector_as_Yingxin']=original_opp['sector']==SECTOR
        row['phase']='after_actual_Yingxin_sale_same_OPEN'if row['at']==END else ('before_actual_exit_OPEN'if '09:30'in row['at']else'original_CLOSE_size_failure')
        if row['result']=='reserved':
            row['pool_evidence']='explicit_original_reserved_pool'
        elif row['role']=='core' and row['result']!='industry_invalidated' and '09:30'in row['at']:
            row['pool_evidence']='original_CORE_route_is_probe_only; no successful_pool'
        elif 'probe_risk' in row['result']:
            row['pool_evidence']='probe_test_evidenced_by_failure_union; other route pools NOT_SAVED'
        elif row['result']=='industry_invalidated':
            row['pool_evidence']='industry_rejects_before_pool_route'
        else:row['pool_evidence']=NS
        row['instant_before_route_resources']=NS
        row['caused_or_enabled_by_Yingxin_clipped_risk_zero']='NOT_ESTABLISHED'
    save('ALL_ORIGINAL_FUNDING_ROWS_WITH_PRIOR_CLOSE_SECTOR.json',fund)
    csvwrite('ALL_ORIGINAL_FUNDING_ROWS.csv',fund)
    pre=[r for r in fund if r['phase']=='before_actual_exit_OPEN']
    after=[r for r in fund if r['phase']=='after_actual_Yingxin_sale_same_OPEN']
    closefails=[r for r in fund if r['phase']=='original_CLOSE_size_failure']
    save('PRE_EXIT_ORIGINAL_OPEN_FUNDING_19_ROWS.json',pre)
    save('ORIGINAL_CLOSE_SIZE_FAILURES.json',closefails)
    save('SAME_REAL_ESTATE_ORIGINAL_FUNDING_ROWS.json',[r for r in fund if r['same_real_estate_sector_as_Yingxin']])
    real_estate_industry=[r for r in industry if r['sector']==SECTOR]
    save('ORIGINAL_REALESTATE_OPPORTUNITIES_AND_ALL_INDUSTRY_EVENTS.json',dict(
        industry_original=industry,
        real_estate_opportunities=[r for r in opportunities if r['sector']==SECTOR],
        relevant_funding_stock_opportunity_rows=opportunities,
        original_close_intents=[decisions[d]for d in ['2022-01-27','2022-01-28','2022-02-07']],
        note='Original industry.jsonl contains change/result events, not a full sector-state snapshot at each route. Same-sector opportunities can exist without a planned/funded order.',
        real_estate_industry_original_rows=real_estate_industry,
        observed_real_estate_episode_ids=sorted({r['episode']for r in real_estate_industry}),
        observed_real_estate_attempt_ids=sorted({r['attempt']for r in real_estate_industry if r.get('attempt')}),
        original_journal_explicit_migration_events=[r for r in journal if 'migrat'in r['kind'].lower()],
        migration_boundary='Three saved pre-exit CLOSE snapshots all confirmed. No explicit migration event in this original journal slice; it does not log every migrate call, so no claim that no intraday reassignment occurred.'))

    close_rows=[];originals=[]
    for day in ['2022-01-27','2022-01-28','2022-02-07','2022-02-08']:
        r=ys[day];a=daily[day];layers=[l for l in a['layers']if l['sid']==SID]
        for l in layers:
            assert l['pool']=='confirmed'
        M=[l for l in r['original_live_layers']if l['saved_native_layer']['id']in[113,122]]
        assert all(D(l['native_mark_to_guard_before_check'])==D(0)and D(l['native_mark_to_guard_after_checks'])==D(0)for l in M)
        qty=sum(l['saved_native_layer']['qty']for l in M)
        close_rows.append(dict(day=day,actual_proxy_stock_qty=a['positions'].get(SID,0),
            M113_M122_qty=qty,pool_of_all_live_Yingxin_layers='confirmed'if layers else'NO_LIVE_LAYER',
            source_raw_close=r['original_bar']['raw_close'],
            saved_total_stock_mark=r['original_stock_mark'],
            M113_M122_static_mark_from_saved_raw_close=str(D(qty)*D(str(r['original_bar']['raw_close']))),
            saved_remaining_stock_fee_aware_basis=r['original_stock_remaining_basis'],
            original_total_stock_clipped_risk=r['original_mark_to_guard_after_CLOSE'],
            M113_M122_clipped_risk='0',
            stock_is_still_on_original_pending_exit_list=SID in a['pending_sells'],
            original_available=a['available'],original_inventory=a['inventory'],original_NAV=a['nav'],
            original_pool_probe=a['pool_probe'],original_pool_confirmed=a['pool_confirmed'],
            original_order_reserved=a['order_reserved'],
            stock_cash_is_released=not bool(layers),
            source_mark_risk_origin='Existing saved original per-stock diagnostic; verified native layer equality, not new risk-model replay.'))
        assert [l['saved_native_layer']for l in r['original_live_layers']]==layers
        originals.append(dict(day=day,original_full_account=a,
            original_stock_saved_diagnostic=r,
            original_balance_check=next(b for b in balances if b['at'][:10]==day)))
    save('FOUR_ORIGINAL_CLOSE_ACCOUNT_AND_YINGXIN_INPUTS.json',originals)
    csvwrite('CAPITAL_CASH_GUARD_RISK_AND_POOL.csv',close_rows)

    reserve_rows=[dict(original_audit_index=k,**r)for k,r in enumerate(book['audit'])if r.get('kind')=='reserve'and START<=r.get('at','')<=END]
    trades=[dict(original_trade_index=k,**r)for k,r in enumerate(book['trades'])if START<=r['at']<=END]
    audit_y=[dict(original_audit_index=k,**r)for k,r in enumerate(book['audit'])if r.get('sid')==SID and START<=r.get('at','')<=END]
    reserve_fill_rows=[]
    for f in fund:
        if f['result']!='reserved':continue
        reserve=next(r for r in reserve_rows if r['at']==f['at']and r['sid']==f['sid'])
        tr=next(r for r in trades if r['at']==f['at']and r['security_id']==f['sid']and r['side']=='buy')
        jr=next(r for r in journal if r['at']==f['at']and r.get('sid')==f['sid']and r['kind']=='real_buy_fill')
        order=book['budget']['orders'][jr['budget_order']]
        reserve_fill_rows.append(dict(funding=f,original_reserve=reserve,original_trade=tr,
            original_fill_journal=jr,original_frozen_entry_order=order,
            original_cash_spent=str(D(tr['gross_cny'])+D(tr['fees_cny'])),
            own_entry_order_route_risk_scalar_excluding_fee=str(D(tr['shares'])*max(D(0),D(tr['price'])-D(str(order['floor'])))),
            original_created_order_note='Preserved filled order qty is terminal0; entry limit/floor retained, not a later layer floor.',
            phase=f['phase']))
    save('ACTUAL_RESERVED_AND_FILLED_BUYS.json',reserve_fill_rows)
    save('ORIGINAL_GLOBAL_JOURNAL_RESERVES_TRADES_AND_EXIT.json',dict(
        reserves=reserve_rows,trades=trades,journal=journal,Yingxin_audit=audit_y,
        original_Yingxin_exit=exit_trade,
        original_Yingxin_exit_journal_index=exit_jindex,
        Feb8_all_reserve_journal_indexes_are_later_than_original_Yingxin_sell=True,
        same_clock_warning='All record09:30; ordering comes from original source opening and preserved journal sequence, not distinct minute timestamps.'))

    probe=[r for r in fund if r['result']=='reserved'and r['pool']=='probe' or r['role']=='core'and '09:30'in r['at']or'probe_risk'in r['result']]
    save('ALL_PROBE_EVIDENCED_OR_PROBE_ONLY_CORE_ATTEMPTS.json',dict(rows=probe,
        rule='Explicit reserved probe, CORE OPEN intentions (route only probe if industry active), or probe_risk in original failure union. Rejected MOBILE with only sector failures cannot be assigned an exact route pool from this log.',
        completeness='ALL_ORIGINAL_FUNDING_ROWS also retains every other MOBILE attempt; no unknown pool silently labelled confirmed/probe.'))

    source_ranges={
      '/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/account-risk-ablation-20261031/route_without_account_check.py':[(1,29)],
      '/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/component.py':[(14,35)],
      '/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/native_adapter.py':[(10,20),(28,39)],
      '/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py':[(36,61),(302,324)],
    }
    snippets=[]
    for path,ranges in source_ranges.items():
        p=bind(path);lines=p.read_text().splitlines()
        for lo,hi in ranges:
            snippets.append(f'PATH {p}\nSHA256 {HASH[str(p)]}\nLINES {lo}-{hi}\n'+'\n'.join(f'{n:5d} {lines[n-1]}'for n in range(lo,hi+1)))
    (OUT/'ORIGINAL_POOL_AND_OPEN_ORDERING_SOURCE.txt').write_text('\n\n'.join(snippets)+'\n')
    read(BASE.parent/'ORIGINAL_IDENTITY.json')
    stats=dict(interval_start=START,actual_exit_END=END,
        pre_exit_OPEN_days=['2022-01-28','2022-02-07'],
        before_exit_OPEN_funding_records=len(pre),
        before_exit_OPEN_outcome_counts=dict(Counter(r['result']for r in pre)),
        before_exit_OPEN_reserved_count=sum(r['result']=='reserved'for r in pre),
        before_exit_actual_reserves=[r for r in reserve_fill_rows if r['phase']=='before_actual_exit_OPEN'],
        same_real_estate_actual_funding_count=sum(r['same_real_estate_sector_as_Yingxin']for r in fund),
        close_size_failure_count=len(closefails),after_exit_same_OPEN_funding_count=len(after),
        after_exit_same_OPEN_reserved_count=sum(r['result']=='reserved'for r in after),
        original_Yingxin_exit_net_cash=str(D(exit_trade['gross_cny'])-D(exit_trade['fees_cny'])),
        directly_established=['M113/122 are confirmed and individually clipped risk0 on all3 saved pre-exit CLOSE snapshots; no claim about all intraday instants','Their qty/marked capital and original unrecouped cash basis did not disappear','No same-real-estate funding row in the observed interval','1/28 no original buy fill,2/7 two other-sector probe CORE fills','2/8 new reserves follow original actual sale in journal and source opening order'],
        causal_boundary='No per-route original before-state resource certificate or counterfactual: do not attribute the2 grants to zero clipping. Structurally confirmed guard-risk is not probe-risk; No60 source removes account-risk admission and confirmed60-capital admission. Invalidated real-estate prevents same-sector funding.',
        missing=['original whole-account pre-each-route pool/sector risk,mark and pending-fee snapshots','numeric per-quantity failed predicates','hypothetical unclipped risk rule and its counterfactual allocations'],
        no_new_market_or_account_instances=True,new_financial_models=0,new_indicators=0,new_backtests=0,new_orders_or_resource_replay=0,
        elapsed_read_extract_seconds=time.monotonic()-t0)
    save('SUMMARY_AND_EVIDENCE_BOUNDARY.json',stats)
    save('SOURCE_SHA256.json',HASH)
    save('OUTPUT_SHA256.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in OUT.iterdir()if p.is_file()and p.name!='OUTPUT_SHA256.json'})

if __name__=='__main__':main()
