"""Offline S0 screening snapshot. Imports frozen logic; never runs an account."""
from __future__ import annotations
import csv, hashlib, json, math, sys, time, traceback
from pathlib import Path
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'research_rounds/current-pool-20261022'
OUT=Path(__file__).resolve().parent
CUT='2026-10-22'
for p in [BASE/'audit-a',BASE/'code',ROOT/'TradingAlarm/research']:
    sys.path.insert(0,str(p))
import finalize_a as fa
import current_pool_bridge as bridge
from stock_actions import parse_ths_rights
fa.LEGACY_RIGHTS=ROOT/'TradingAlarm/research/data/ths-refresh-20261018/rights'
A=bridge.admission

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
def clean(x):
    if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if x is pd.NA or x is pd.NaT:return None
    if isinstance(x,(float,np.floating)):return float(x) if math.isfinite(x) else None
    if isinstance(x,np.integer):return int(x)
    if isinstance(x,np.bool_):return bool(x)
    return x
def writecsv(name,rows):
    pd.DataFrame(rows).to_csv(OUT/name,index=False,encoding='utf-8-sig')

def stock_job(arg):
    row,paths,batches,units=arg
    symbol,native=row['current_symbol'],row['ths_symbol']
    result={'symbol':symbol,'calculated':False,'source_evidence':[],'input_refs':[],'stock_status':'未知'}
    old=BASE/'audit-a/prepared-current-master-v1/bars'/(symbol+'.parquet')
    try:
        merged=fa.annotate_observations(pd.read_parquet(old),symbol=symbol) if old.exists() else None
        if old.exists():result['input_refs'].append({'path':str(old),'sha256':sha(old)})
        for p in sorted(map(Path,paths),key=fa.history_source_order):
            e={'path':str(p),'sha256':sha(p),'accepted':False}
            try:
                frame,x,cp,item,seen=fa.verified_raw_frame(p)
                e.update(history_status=cp['history_status'],requested_end=x['requested_end'],requested_earliest=x['requested_earliest'],observed_at=seen,stop_reason=cp.get('stop_reason'))
                if cp['history_status']=='quarantined':raise ValueError('collector quarantined')
                if native[:4] not in units:raise ValueError('market volume units unverified')
                frame=fa.annotate_observations(frame,symbol,p,seen)
                frame=frame.loc[frame.trade_date.between('2013-01-01',CUT)]
                if frame.empty:raise ValueError('empty source')
                e.update(first=str(frame.trade_date.min().date()),last=str(frame.trade_date.max().date()))
                merged,conflicts,check=fa.merge_observations(merged,frame,symbol)
                e.update(check,conflict_cells=len(conflicts))
            except (ValueError,KeyError,FileNotFoundError,TypeError) as exc:e['reason']=str(exc)
            result['source_evidence'].append(e)
        result['unresolved_sources']=fa.source_dispositions(result['source_evidence'])
        if merged is None or merged.empty:
            result['data_reason']='无本地行情';return result
        merged=merged.loc[merged.trade_date.le(CUT)].set_index('trade_date')
        merged.index.name='date'
        result.update(raw_rows=len(merged),raw_start=str(merged.index[0].date()),raw_asof=str(merged.index[-1].date()),close_raw=float(merged.close.iloc[-1]))
        rights=fa.rights_sources(symbol,native,list(map(Path,batches)),parse_ths_rights)
        result.update(action_status=rights['status'],action_unparsed=len(rights['unparsed']),action_issues=len(rights['issues']))
        if rights['source_path']:result['input_refs'].append({'path':rights['source_path'],'sha256':rights['source_sha256']})
        unresolved_in_window=[r for r in rights['unparsed'] if str(merged.index[0].date()).replace('-','') <=str(r['row'].get('1','99999999'))<=CUT.replace('-','')]
        if rights['status']=='missing' or unresolved_in_window:
            result['data_reason']='除权资料缺失或区间内存在未解析事件';return result
        events=[]
        for e in rights['events']:
            events.append(dict(effective_date=e['effective_date'],cash_per_old_share=str(e['gross_cash_per_old_share']),split_ratio=str(1+e['bonus_shares_per_old_share']+e['capitalization_shares_per_old_share']),source_id=rights['source_sha256']))
        if len({e['effective_date'] for e in events})!=len(events):
            result['data_reason']='同日除权事件未聚合';return result
        rec={'adjustment':{'method':'theoretical_ex_price'}}
        signal=bridge.prepare_signal(merged,rec,events,cutoff=CUT)
        eligible,ev,state,memories=bridge.state_frame(signal)
        prefix_checks=[]
        if symbol in ('000823.SZ','300839.SZ','600825.SH','601988.SH'):
            for end in (eligible.index[-2],eligible.index[-5]):
                ps=bridge.prepare_signal(merged,rec,events,cutoff=end)
                pe,pev,pst,pm=bridge.state_frame(ps)
                pd.testing.assert_frame_equal(pst,state.loc[:end],check_exact=True)
                prefix_checks.append(str(end.date()))
        last=state.iloc[-1];asof=str(state.index[-1].date())
        factor=float(signal.loc[state.index[-1],'adjustment_factor'])
        ready=bool(last.ready)
        result.update(calculated=True,asof=asof,ready=ready,up=bool(last.target) if ready else None,
                      stock_status=('上行结构' if last.target else '未建立上行结构') if ready else '预热不足',
                      rs=clean(last.rs),floor_signal=clean(last.floor),adjustment_factor=factor,
                      floor_raw=float(last.floor)/factor if ready and last.target else None,
                      pending=bool(last.pending),pending_reclaim_raw=clean(last.pending_reclaim/factor),
                      pending_lower_raw=clean(last.pending_lower/factor),volume_ratio=clean(last.volume_ratio),
                      signal_observations=len(state),fresh=asof==CUT,close_raw=clean(signal.loc[state.index[-1],'raw_close']))
        result['prefix_checks']=prefix_checks
        result['rs_reference_closes']=[float(eligible.close.iloc[-1-k]) for k in (0,63,126,189,252)] if len(eligible)>=253 else None
        entries=state.loc[state.entered.eq(1)]
        if len(entries):result.update(last_entry_date=str(entries.index[-1].date()),last_entry_kind=str(entries.entry_kind.iloc[-1]))
        reasons=[]
        if asof!=CUT:reasons.append('行情止于'+asof+'，不推断停牌或退市')
        if result['unresolved_sources']:reasons.append('行情源有未决冲突或缺口')
        if rights['status']!='received_current':reasons.append('除权资料仅旧缓存，最新覆盖未认证')
        if not ready:reasons.append('趋势预热不足')
        result['data_reason']='；'.join(reasons) or '本地最新行情与已解析除权研究口径'
        # Research signal sufficiency only; precise shareholder ledger not certified.
        result['technical_current']=bool(ready and asof==CUT and not result['unresolved_sources'] and rights['status']=='received_current')
        if row['industry_index_symbol'] in ('URFI881270','URFI881180','URFI881164','URFI881155'):
            (OUT/'tails').mkdir(exist_ok=True)
            pd.concat([state.tail(8),signal[['raw_close','adjustment_factor']].reindex(state.tail(8).index)],axis=1).to_csv(OUT/'tails'/(symbol+'.csv'))
        return clean(result)
    except Exception as exc:
        result.update(data_reason=str(exc),error_type=type(exc).__name__)
        return clean(result)

def main():
    OUT.mkdir(exist_ok=True)
    selection=BASE/'audit-snapshot/cap-join-hk-cachedfx-check-03/current-snapshot-selection.csv'
    roster=pd.read_csv(selection,dtype=str).fillna('').to_dict('records')
    assert len(roster)==8372 and len({r['current_symbol'] for r in roster})==8372
    frozen={str(p):sha(p) for p in bridge.UPSTREAM.values()}
    pm=BASE/'sector-trajectories-v1/prepared/manifest.json'
    manifest=json.loads(pm.read_text())
    assert manifest['bridge_sha256']==sha(BASE/'code/current_pool_bridge.py')
    summaries=pd.read_csv(BASE/'sector-trajectories-v1/trajectory-summary.csv').set_index('symbol')
    sectors=[];refs=[{'path':str(selection),'sha256':sha(selection)},{'path':str(pm),'sha256':sha(pm)}]
    for entry in manifest['series']:
        sid=entry['series_id'];s=summaries.loc[sid]
        frames={}
        for k in ('states','signal'):
            ref=entry['files'][k];p=pm.parent/ref['path'];assert sha(p)==ref['sha256'];frames[k]=pd.read_parquet(p);refs.append({'path':str(p),'sha256':ref['sha256']})
        f=frames['states'];last=f.iloc[-1];signal=frames['signal'];ready=bool(last.ready) and str(f.index[-1].date())==CUT
        sectors.append(dict(symbol=sid,market=s.market,name=s['name'],asof=str(f.index[-1].date()),ready=ready,
            up=bool(last.target) if ready else None,status=('上行结构' if last.target else '未建立上行结构') if ready else '未知（最新分段预热不足）',
            rs=clean(last.rs) if ready else None,floor=clean(last.floor) if ready and last.target else None,close=clean(signal.close.iloc[-1]),
            pending=bool(last.pending),observations=len(f)))
    ups=sorted([s for s in sectors if s['up'] is True],key=lambda s:(-round(s['rs'],12),s['symbol']))
    for rank,s in enumerate(ups,1):s['up_rank']=rank
    smap={s['symbol']:s for s in sectors}
    todo=[r for r in roster if r['industry_index_symbol'] in {s['symbol'] for s in ups}]
    batches=fa.discover_history_batches(BASE/'downloads')
    native={r['ths_symbol']:r['current_symbol'] for r in roster if not r['current_symbol'].endswith('.HK')}
    paths=[p for b in batches for p in (b/'history').glob('*.json') if p.stem in native]
    grouped={}
    for p in paths:grouped.setdefault(p.stem,[]).append(str(p))
    prepared=BASE/'audit-a/prepared-current-master-v1'
    units=fa.unit_evidence(prepared,paths,native)
    protocol=dict(created_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),cutoff=CUT,scope='2026-10-22 current surviving fixed snapshot; selection bias retained',
        variant='S0',algorithm_changes=0,account_runs=0,network_requests=0,initial_occupancy='empty screening bootstrap; does not assert actual holdings',
        screening='101 industry states reused with hashes; stock signals calculated for all 1441 names in the 24 confirmed-up A sectors; other roster rows retained and explicitly not calculated',
        cap_policy='Never promote unknown company-cap evidence to pass; numeric HK cached FX value is not certified',
        ranking='frozen 4x63 RS; current, up, research-data-ready observations only, before cap qualification; not an official S0 candidate queue',
        protection='floor / latest causal adjustment factor, in last raw CNY price coordinates; daily close <= floor invalidates structure, next available session execution; not guaranteed fill',
        hashes=frozen,unit_evidence=units,inputs=refs,batches=[str(p) for p in batches],planned_stocks=len(todo))
    dump(OUT/'protocol.json',clean(protocol))
    results=[];started=time.time()
    with ProcessPoolExecutor(max_workers=8,mp_context=multiprocessing.get_context('spawn')) as pool:
        futures=[pool.submit(stock_job,(r,grouped.get(r['ths_symbol'],[]),[str(p) for p in batches],units)) for r in todo]
        for f in as_completed(futures):
            results.append(f.result())
            if len(results)%100==0:print(json.dumps({'finished':len(results),'total':len(todo),'seconds':round(time.time()-started)}),flush=True)
    dump(OUT/'stock-signals.json',clean(results))
    finalize(roster,sectors,results,protocol)

def finalize(roster,sectors,results,protocol):
    smap={s['symbol']:s for s in sectors};rmap={r['symbol']:r for r in results}
    observed=[]
    for s in sectors:
        group=[dict(rmap[r['current_symbol']],sector_id=s['symbol']) for r in roster if r['industry_index_symbol']==s['symbol'] and r['current_symbol'] in rmap and rmap[r['current_symbol']].get('technical_current') and rmap[r['current_symbol']].get('up')]
        if not group:continue
        fallback=any(g.get('rs') is None for g in group)
        if fallback:group.sort(key=lambda g:g['symbol'])
        else:group.sort(key=lambda g:(-round(g['rs'],12),g['symbol']))
        for i,g in enumerate(group,1):
            g['stock_rank']=i;g['sector_rank']=s['up_rank'];g['ranking_mode']='代码顺序（组内有RS缺失）' if fallback else 'RS降序';observed.append(g)
    omap={r['symbol']:r for r in observed}
    # Actual frozen admission, with original unknown qualifications preserved.
    tz=ZoneInfo('Asia/Shanghai');now=datetime.now(tz)
    decision=max(now,datetime(2026,10,23,7,tzinfo=tz))
    clock=A.Clock(decision,decision+timedelta(seconds=1),date.fromisoformat(CUT))
    def fact(v):return A.Fact(v,decision,decision,source_id='offline_snapshot')
    sec=[A.Sector(s['symbol'],fact(s['up']),A.Rank(s['rs'],datetime(2026,10,22,15,5,tzinfo=tz),decision)) for s in sectors]
    securities=[];rows=[]
    for r in roster:
        symbol=r['current_symbol'];s=smap.get(r['industry_index_symbol']);v=rmap.get(symbol,{})
        cap=None
        if r['size_filter_status'] in ('pass','fail') and r['company_market_cap_cny']:
            cap=float(r['company_market_cap_cny'])
        buy=None if r['strategy_snapshot_filter_status']=='unknown' else r['strategy_snapshot_filter_status']=='pass'
        # Size is separate; A common stock / H southbound status can be known even with unknown size.
        if r['southbound_filter_status'] in ('pass','not_required_A') and r['security_type_filter_status']=='pass':buy=True
        elif r['southbound_filter_status']=='fail' or r['security_type_filter_status']=='fail':buy=False
        issuer=r.get('company_a_symbol') or symbol
        rank=A.Rank(v.get('rs') if v.get('technical_current') else None,datetime(2026,10,22,15,5,tzinfo=tz),decision)
        securities.append(A.Security(symbol,fact(issuer),fact(s['symbol'] if s else None),fact(None),fact(buy),fact(cap),fact(v.get('up') if v.get('technical_current') else None),rank))
        reasons=['100亿元市值资格未知' if cap is None else ('市值通过' if cap>1e10 else '市值未过100亿元')]
        if buy is False:reasons.append('当前证券类型或港股通条件不通过')
        elif buy is None:reasons.append('当前买入资格未知')
        if not s or s['up'] is None:reasons.append('板块趋势未知')
        elif not s['up']:reasons.append('板块未建立上行结构，S0不新开仓')
        if v:
            if not v.get('technical_current'):reasons.append(v.get('data_reason','个股资料未知'))
            elif not v.get('up'):reasons.append('个股未建立上行结构'+('，等待跨日收复或原通道确认' if v.get('pending') else '，等待确认事件'))
            else:reasons.append('板块与个股量价结构均上行；等待市值资格核实')
        else:reasons.append('板块未通过，本次未计算个股状态')
        o=omap.get(symbol,{})
        status='量价观察／资格待核' if o else '资料等待' if v and not v.get('technical_current') else '信号等待' if v else '板块等待'
        rows.append(dict(symbol=symbol,name=r['name'],market='H' if symbol.endswith('.HK') else 'A',sector_id=r['industry_index_symbol'],sector_name=r['industry_name'],
            sector_status=s['status'] if s else '未匹配',sector_rank=s.get('up_rank') if s else None,sector_rs=s.get('rs') if s else None,
            stock_status=v.get('stock_status','未计算（板块未通过）'),stock_rank=o.get('stock_rank'),ranking_mode=o.get('ranking_mode'),stock_rs=v.get('rs'),
            close_raw=v.get('close_raw'),floor_raw=v.get('floor_raw'),pending_reclaim_raw=v.get('pending_reclaim_raw'),pending_lower_raw=v.get('pending_lower_raw'),
            price_asof=v.get('asof') or v.get('raw_asof'),raw_start=v.get('raw_start'),status=status,reason='；'.join(reasons),
            cap_filter=r['size_filter_status'],company_market_cap_cny=r['company_market_cap_cny'],southbound_filter=r['southbound_filter_status'],
            action_status=v.get('action_status'),data_reason=v.get('data_reason'),last_entry_date=v.get('last_entry_date'),last_entry_kind=v.get('last_entry_kind'),
            technical_current=v.get('technical_current',False),volume_ratio=v.get('volume_ratio')))
    actual=A.decide(clock=clock,variant='S0',securities=securities,sectors=sec,bootstrap=True)
    assert not actual.selected and not actual.waiting
    emap={e.security_id:e for e in actual.eligibility}
    for r in rows:r.update(strict_eligible=emap[r['symbol']].q,strict_reasons=';'.join(emap[r['symbol']].reasons))
    order=lambda r:(r['sector_rank'] or 999,r['stock_rank'] or 99999,r['symbol'])
    candidates=sorted([r for r in rows if r['symbol'] in omap],key=order)
    sectors=sorted(sectors,key=lambda s:(0 if s['up'] else 1 if s['up'] is False else 2,s.get('up_rank',999),-(s['rs'] or 0),s['symbol']))
    writecsv('candidates.csv',candidates);writecsv('sectors.csv',sectors);writecsv('full-roster.csv',rows)
    hashes_after={p:sha(p) for p in protocol['hashes']};assert hashes_after==protocol['hashes']
    summary=dict(cutoff=CUT,roster=len(rows),sector_count=len(sectors),up_sectors=sum(s['up'] is True for s in sectors),unknown_sectors=sum(s['up'] is None for s in sectors),
        calculated=sum(r.get('calculated',False) for r in results),attempted=len(results),technical_current=sum(r.get('technical_current',False) for r in results),observation_candidates=len(candidates),
        strict_selected=list(actual.selected),strict_waiting=list(actual.waiting),all_caps_unknown=all(r['cap_filter']=='unknown' for r in rows),
        algorithm_unchanged=hashes_after==protocol['hashes'],account_runs=0,network_requests=0,common_ready='unknown: full pool/head history closeout not certified',
        prefix_checks={r['symbol']:r['prefix_checks'] for r in results if r.get('prefix_checks')},
        ranking_fallback_sectors=sorted({r['sector_name'] for r in candidates if r['ranking_mode'].startswith('代码')}),
        errors=[{k:r.get(k) for k in ('symbol','error_type','data_reason')} for r in results if 'error_type' in r],
        top_per_sector=[r for r in candidates if r['stock_rank']<=2])
    dump(OUT/'summary.json',clean(summary))
    dump(OUT/'workbook-data.json',clean(dict(summary=summary,candidates=candidates,sectors=sectors,roster=rows)))
    dump(OUT/'input-evidence.json',clean([{'symbol':r['symbol'],'inputs':r.get('input_refs',[]),'new_sources':r.get('source_evidence',[])} for r in results]))
    print(json.dumps({k:v for k,v in summary.items() if k not in ('errors','top_per_sector')},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
