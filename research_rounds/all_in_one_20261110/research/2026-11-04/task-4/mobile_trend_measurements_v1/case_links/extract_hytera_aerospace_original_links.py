"""Join original receipts/plans/funding/fills; no new indicators or account run."""
from pathlib import Path
from datetime import date
from collections import Counter
import csv
import gzip
import hashlib
import json
import time

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
NS='NOT_SAVED_IN_REUSED_CASE_TABLE'
SOURCES={}
CASES={
 '002583.SZ':dict(window='long',start='2024-09-23',end='2024-11-27',saved=ROOT/'native_algorithm_read_v1/daily_hytera/ALL_DAYS_ORIGINAL_STOCK_OUTPUTS.json'),
 '000547.SZ':dict(window='strong',start='2025-10-22',end='2026-01-16',saved=ROOT/'reentry_event_identity_v1/aerospace/FULL_DAILY_ORIGINAL_2025_11_20_2026_01_16.json'),
}

def bind(path):
    p=Path(path).resolve();SOURCES[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p

def read(path):return json.loads(bind(path).read_text())

def gz(path,lines=False):
    with gzip.open(bind(path),'rt')as f:return [json.loads(x)for x in f]if lines else json.load(f)

def save(name,value):(OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def csvwrite(name,rows):
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with(OUT/name).open('w',newline='')as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        w.writerows({k:json.dumps(v,ensure_ascii=False,separators=(',',':'))if isinstance(v,(dict,list))else v for k,v in r.items()}for r in rows)

def stream_stock(path,sid,start,end):
    out=[]
    with gzip.open(bind(path),'rt')as f:
        for k,line in enumerate(f):
            if sid not in line:continue
            r=json.loads(line);day=r.get('day',r.get('at',''))[:10]
            if r.get('sid')==sid and start<=day<=end:
                out.append(dict(original_stream_index=k,**r))
    return out

def main():
    t0=time.monotonic();bind(__file__)
    bind(OUT.parent/'FROZEN_DEFINITIONS.txt')
    manifest2024=read('/Users/bytedance/Documents/Codex/2026-11-04/task/ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/inputs/MANIFEST.json')
    universe=read('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
    summary={}
    for sid,case in CASES.items():
        lo,hi=case['start'],case['end']
        base=ROOT/'new_price_trend_v1/funding/runs'/f"{case['window']}_OFF"/'pair'
        book=gz(base/'B.json.gz')
        all_daily=gz(base/'daily.jsonl.gz',True)
        daily={r['at'][:10]:r for r in all_daily};all_days=list(daily)
        last_next=all_days[all_days.index(hi)+1]
        decisions={r['at'][:10]:r for r in book['decisions']}
        reused={r['day']:r for r in read(case['saved'])}
        opp=stream_stock(base/'opportunities.jsonl.gz',sid,lo,hi)
        funding=stream_stock(base/'funding.jsonl.gz',sid,lo,last_next)
        op_byday={r['day']:r for r in opp}
        assert len(opp)==len(op_byday)
        if sid=='002583.SZ':
            rm=next(r for r in manifest2024 if r['sid']==sid)
            rp=rm['output_path'];rh=rm['output_sha256']
        else:
            rm=next(r for r in universe if r['symbol']==sid)
            rp=rm['refs']['receipts'];rh=rm['output_sha256'][rp]
        receipts=read(rp);assert SOURCES[str(Path(rp).resolve())]==rh
        receipt_byday={r['confirmed_day']:r for r in receipts if lo<=r['confirmed_day']<=hi}
        assert len(receipt_byday)==sum(bool(r['CP1_id'])for r in opp)
        rows=[]
        for day,op in op_byday.items():
            a=daily[day];nextday=all_days[all_days.index(day)+1]
            next_at=nextday+' 09:30:00+08:00'
            original_intents=[r for r in decisions[day]['intents']if r['sid']==sid]
            mobile_intents=[r for r in original_intents if r['role']=='mobile']
            mob_funding=[r for r in funding if r['at']==next_at and r['role']=='mobile']
            all_next_funding=[r for r in funding if r['at']==next_at]
            mob_trades=[dict(original_book_trade_index=k,**r)for k,r in enumerate(book['trades'])if r.get('security_id')==sid and r['at']==next_at and r['side']=='buy'and r.get('kind')=='add'and r.get('signal_at','')[:10]==day]
            all_next_trades=[dict(original_book_trade_index=k,**r)for k,r in enumerate(book['trades'])if r.get('security_id')==sid and r['at'][:10]==nextday]
            hascp=bool(op['CP1_id']);rc=receipt_byday.get(day)
            assert hascp==bool(rc)
            if hascp:
                assert rc['receipt_id']==op['CP1_id']
                assert all(r['CP1_id']==op['CP1_id']for r in mobile_intents)
            if not hascp:status='NO_ORIGINAL_CP_RECEIPT'
            elif op['mobile_Q']is not True:status='CP_BUT_MOBILE_Q_NOT_TRUE'
            elif 'mobile'not in op['roles']:status='CP_AND_Q_BUT_NO_MOBILE_ROLE'
            elif not mobile_intents:status='CP_ROLE_BUT_NO_FROZEN_MOBILE_INTENT'
            elif mob_trades:status='ORIGINAL_MOBILE_FILL'
            elif any(r['result']=='reserved'for r in mob_funding):status='ORIGINAL_MOBILE_RESERVED_NO_FILL'
            elif mob_funding:status='ORIGINAL_MOBILE_OPEN_REJECTED'
            elif any(r['role']=='core'and r['result']=='reserved'for r in all_next_funding):status='MOBILE_SKIPPED_AFTER_SAME_STOCK_CORE_RESERVED'
            else:status='MOBILE_INTENT_WITH_NO_SAVED_OPEN_OUTCOME'
            old=reused.get(day)
            if old is None:
                facts=NS;market=NS;cp_cache=NS
                saved_origin='Expanded-window account/opportunity/intent/funding only; price metrics are supplied separately by parent metrics CSV.'
            elif sid=='002583.SZ':
                facts=old['facts'];market=old['source_signal'];cp_cache=old['CP1']
                assert old['opportunities']==[{k:v for k,v in op.items()if k!='original_stream_index'}]
                assert old['intents']==original_intents
                saved_origin=str(case['saved'])
            else:
                facts=old['facts'];market={'raw_close':facts['raw_close'],'continuous_close':facts['close'],'factor':facts['factor'],'raw_open_high_low':NS};cp_cache=old['CP']
                assert old['original_opportunity']==[{k:v for k,v in op.items()if k!='original_stream_index'}]
                assert old['original_frozen_intents']==original_intents
                saved_origin=str(case['saved'])
            if old is not None:assert bool(cp_cache['receipt'])==hascp
            audit=[dict(original_book_audit_index=k,**r)for k,r in enumerate(book['audit'])if r.get('sid')==sid and r.get('at','')[:10]in[day,nextday]]
            journals=[dict(original_book_journal_index=k,**r)for k,r in enumerate(book['journal'])if r.get('sid')==sid and r.get('at','')[:10]in[day,nextday]]
            live=[r for r in a['layers']if r['sid']==sid]
            nextlive=[r for r in daily[nextday]['layers']if r['sid']==sid]
            row=dict(sid=sid,day=day,date=day,original_account_window=case['window']+'_OFF',
                original_CLOSE_at=decisions[day]['at'],
                original_canonical_CP_receipt_id=op['CP1_id'],original_canonical_CP_receipt=rc,
                CP_present=hascp,original_core_Q=op['core_Q'],original_mobile_Q=op['mobile_Q'],
                original_roles=op['roles'],original_barriers=op['barriers'],
                original_opportunity=op,original_frozen_intents=original_intents,
                original_MOBILE_intent_count=len(mobile_intents),original_MOBILE_intents=mobile_intents,
                original_CLOSE_size_funding_failures=[r for r in funding if r['at']==decisions[day]['at']],
                original_CLOSE_held_qty=a['positions'].get(sid,0),original_CLOSE_layers=live,
                original_CLOSE_NAV=a['nav'],original_CLOSE_available=a['available'],
                original_CLOSE_pool_probe=a['pool_probe'],original_CLOSE_pool_confirmed=a['pool_confirmed'],
                original_CLOSE_pending_sells=a['pending_sells'],
                reused_saved_market_fields=market,reused_saved_actual_native_facts=facts,
                reused_saved_CP_numeric_fields=cp_cache,reused_source=saved_origin,
                metric_join_key={'sid':sid,'date':day},
                next_original_OPEN=next_at,next_original_trading_day=nextday,
                calendar_days_to_next_OPEN=(date.fromisoformat(nextday)-date.fromisoformat(day)).days,
                next_OPEN_original_MOBILE_funding=mob_funding,
                next_OPEN_original_all_stock_funding=all_next_funding,
                next_OPEN_original_MOBILE_fills=mob_trades,
                next_day_original_all_stock_trades=all_next_trades,
                next_CLOSE_original_stock_layers=nextlive,
                next_day_original_stock_audit=audit,next_day_original_stock_journal=journals,
                connection_status=status,
                skip_reason_evidence='Original opening source sets done after successful CORE reserve, then skips same stock; no MOBILE rejection logged.'if status=='MOBILE_SKIPPED_AFTER_SAME_STOCK_CORE_RESERVED'else None,
                original_intraday_pre_each_route_resource_snapshot='NOT_SAVED',
                execution_boundary='Original daily-bar-proxy backtest ledger; not broker or minute-level fill evidence.',
                clock_boundary='CLOSE15:10 is native consuming protocol, not a certified data vendor receipt time.',
                historical_evaluation_only=True)
            rows.append(row)
        save(sid+'.json',rows)
        csvwrite(sid+'.csv',rows)
        cp_rows=[r for r in rows if r['CP_present']]
        save(sid+'.CP_RECEIPT_ONLY.json',cp_rows)
        non_cp_intents=[r for r in rows if not r['CP_present']and r['original_MOBILE_intent_count']]
        assert not non_cp_intents
        count=dict(sid=sid,source_account=str(base),start=lo,end=hi,all_original_observations=len(rows),
            CP_receipts=len(cp_rows),CP_but_Q_not_true=sum(r['original_mobile_Q']is not True for r in cp_rows),
            CP_with_mobile_role=sum('mobile'in r['original_roles']for r in cp_rows),
            MOBILE_intents=sum(r['original_MOBILE_intent_count']for r in rows),
            CORE_intents=sum(i['role']=='core'for r in rows for i in r['original_frozen_intents']),
            CP_connection_status_counts=dict(Counter(r['connection_status']for r in cp_rows)),
            MOBILE_fills=sum(len(r['next_OPEN_original_MOBILE_fills'])for r in rows),
            CP_dates=[r['day']for r in cp_rows],
            reused_saved_price_fact_rows=sum(r['reused_saved_actual_native_facts']!=NS for r in rows),
            expanded_account_link_rows_without_case_price_recalculation=sum(r['reused_saved_actual_native_facts']==NS for r in rows),
            source_receipt_manifest=str(rp),canonical_id_exact_match_all=True)
        if sid=='002583.SZ':
            holiday=next(r for r in rows if r['day']=='2024-09-30')
            assert holiday['next_original_trading_day']=='2024-10-08'
            count['National_Day_holiday_connection']=dict(signal='2024-09-30',next_OPEN=holiday['next_original_OPEN'],calendar_gap_days=holiday['calendar_days_to_next_OPEN'],funding=holiday['next_OPEN_original_all_stock_funding'])
        summary[sid]=count
    # Copy verbatim original opening skip, clock and sizing contract source, no compile/import.
    src=bind('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py')
    ls=src.read_text().splitlines()
    (OUT/'HYTERA_AEROSPACE_OPEN_SKIP_SOURCE.txt').write_text(f'PATH {src}\nSHA256 {SOURCES[str(src)]}\nLINES302-324\n'+'\n'.join(f'{n:5d} {ls[n-1]}'for n in range(302,325))+'\n')
    save('HYTERA_AEROSPACE_COUNTS_AND_SCOPE.json',dict(cases=summary,
        added_indicators=0,new_models=0,new_accounts=0,new_backtests=0,new_resource_or_order_replay=0,
        reused_existing_case_rows=83,expanded_Aerospace_account_link_rows=21,
        chronology='Each CLOSE joins next original account trading OPEN, not calendar+1. Next CLOSE layers separately labelled; never input at prior CLOSE.',
        omitted_opportunities=0,universe_scope='Two specified original stock windows, all original stock opportunities, not only bought layers.',
        missing_price_fields='Aerospace21 early days deliberately not re-read/recomputed here; parent metrics CSV supplies original price/features separately bysid/day.',
        elapsed_read_extract_seconds=time.monotonic()-t0))
    save('HYTERA_AEROSPACE_SOURCE_SHA256.json',SOURCES)
    save('HYTERA_AEROSPACE_OUTPUT_SHA256.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in OUT.iterdir()if p.is_file()and(p.name.startswith(('002583.','000547.','HYTERA_AEROSPACE_'))or p.name==Path(__file__).name)and p.name!='HYTERA_AEROSPACE_OUTPUT_SHA256.json'})

if __name__=='__main__':main()
