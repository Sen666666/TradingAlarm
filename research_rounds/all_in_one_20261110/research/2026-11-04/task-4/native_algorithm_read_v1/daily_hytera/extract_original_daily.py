"""Saved native Hytera frames/actions only; no model or indicator execution."""
from pathlib import Path
from collections import defaultdict
import csv
import gzip
import hashlib
import json
import math
import time
import pandas as pd

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
BASE=ROOT/'new_price_trend_v1/funding/runs/long_OFF/pair'
SID='002583.SZ';START='2024-09-23';END='2024-11-27'
SOURCES={};NS='NOT_SAVED';SN='SOURCE_NULL';NONE='NONE'
def bind(p):
    p=Path(p);SOURCES[str(p.resolve())]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(p):return json.loads(bind(p).read_text())
def gz(p,lines=False):
    with gzip.open(bind(p),'rt')as f:return list(map(json.loads,f))if lines else json.load(f)
def stock_gz(p):
    # Keep just this stock/date slice, not the full-universe rank/opportunity
    # tables in memory. This is a read-only saved-record selection.
    result=[]
    with gzip.open(bind(p),'rt')as f:
        for line in f:
            if SID not in line:continue
            r=json.loads(line);day=r.get('day',r.get('at',''))[:10]
            if r.get('sid')==SID and '2024-09-20'<=day<=END:result.append(r)
    return result
def clean(x):
    if x is pd.NA or x is pd.NaT:return SN
    if isinstance(x,dict):return {str(k):clean(v)for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v)for v in x]
    if hasattr(x,'item'):return clean(x.item())
    if isinstance(x,float)and not math.isfinite(x):return SN
    if isinstance(x,pd.Timestamp):return str(x)
    return x
def save(n,v):(OUT/n).write_text(json.dumps(clean(v),ensure_ascii=False,indent=2)+'\n')
def jsoncell(x):return json.dumps(clean(x),ensure_ascii=False,separators=(',',':'))if x else NONE
def val(row,key):return clean(row[key])if row is not None and key in row.index else NS
def onday(f,d):return f.loc[d]if d in f.index else None
def issid(r):return r.get('sid')==SID or r.get('security_id')==SID or r.get('receipt',{}).get('security_id')==SID or r.get('receivable',{}).get('security_id')==SID
def layerlight(l):return {k:l[k]for k in ['id','kind','qty','floor','opened','signal_at','epoch','reason']if k in l}

def main():
    t0=time.monotonic();bind(__file__)
    manifest_path=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
    manifest=read(manifest_path);rec=next(x for x in manifest if x['symbol']==SID)
    paths={}
    for label,path in rec['refs'].items():
        if label in ['facts','CP1']:paths[label]=path
    for path in rec['source_sha256']:
        if path.endswith('/states.parquet'):paths['E0_states']=path
        elif path.endswith('/events.parquet'):paths['E0_events']=path
        elif path.endswith('/signal.parquet'):paths['source_signal']=path
        elif '/ix-a-share-entry-'in path:paths['IX_signal']=path
    frames={}
    for label,path in paths.items():
        p=bind(path);expected=rec.get('output_sha256',{}).get(str(p),rec.get('source_sha256',{}).get(str(p)))
        assert expected==SOURCES[str(p.resolve())],('Source hash changed',label)
        frames[label]=pd.read_parquet(p)
        assert frames[label].index.is_unique and frames[label].index.is_monotonic_increasing
    score_manifest=Path('/Users/bytedance/Documents/Codex/2026-11-04/task/ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/SCORES_MANIFEST.json')
    sm=read(score_manifest);sr=next(x for x in sm['entries']if x['symbol']==SID)
    scorepath=bind(score_manifest.parent/'scores'/f'{SID}.parquet')
    assert SOURCES[str(scorepath.resolve())]==sr['output_sha256']
    scores=pd.read_parquet(scorepath)
    bind(ROOT/'new_price_trend_v1/funding/input_loader.py')
    book=gz(BASE/'B.json.gz');daily=gz(BASE/'daily.jsonl.gz',True)
    byday={r['at'][:10]:r for r in daily};daily_order=sorted(byday)
    decisions={r['at'][:10]:r for r in book['decisions']}
    funding=stock_gz(BASE/'funding.jsonl.gz');rank=stock_gz(BASE/'rank-policy.jsonl.gz')
    opp=stock_gz(BASE/'opportunities.jsonl.gz')
    facts=frames['facts'];signal=frames['source_signal'];cp=frames['CP1']
    dates=[d for d in facts.loc[START:END].index if d in signal.index and bool(signal.loc[d,'is_observed_bar'])]
    rows=[];raw_outputs=[];crosschecks=[];identity_differences=[]
    for d in dates:
        day=str(d.date());f=facts.loc[d];ss=signal.loc[d];c=onday(cp,d)
        e=onday(frames['E0_states'],d);ev=onday(frames['E0_events'],d);ix=onday(frames['IX_signal'],d)
        a=byday[day];pi=daily_order.index(day)-1;prevday=daily_order[pi];prev=byday[prevday]
        live=[l for l in a['layers']if l['sid']==SID]
        before=[l for l in prev['layers']if l['sid']==SID]
        actual=[r for r in book['trades']if r['security_id']==SID and r['at'][:10]==day]
        buys=[r for r in actual if r['side']=='buy'];sells=[r for r in actual if r['side']=='sell']
        aud=[r for r in book['audit']if issid(r)and r.get('at','')[:10]==day]
        exits=[r for r in aud if r.get('kind')=='pilot_layer_exit']
        intents=[r for r in decisions[day]['intents']if r['sid']==SID]
        incoming=[r for r in decisions[prevday]['intents']if r['sid']==SID]
        ff=[r for r in funding if r.get('sid')==SID and r['at'][:10]==day]
        oo=[r for r in opp if r.get('sid')==SID and r['day']==day]
        rr=[r for r in rank if r.get('sid')==SID and r['day']==day]
        assert len(rr)<=1
        rp=rr[0]if rr else None
        source_score=float(scores.loc[d,'score'])if d in scores.index else NS
        if rp is not None:assert math.isclose(source_score,rp['PVR'],rel_tol=1e-12)
        qtybefore=prev['positions'].get(SID,0)
        qty_after_saved_open=qtybefore+sum(x['shares']for x in buys)-sum(x['shares']for x in sells)
        assert qty_after_saved_open==a['positions'].get(SID,0)
        # Only compare saved frames; do not regenerate E0/I or CP.
        assert bool(f.e0_target)==bool(e.target)==bool(ix.e0_target)
        assert math.isclose(float(f.g_grade),float(ix.grade),rel_tol=1e-12)
        assert bool(f.g_ready)==bool(ix.strength_ready)
        assert bool(f.g_fresh_up)==bool(ix.fresh_up)
        assert bool(f.g_acute_down)==bool(ix.acute_down)
        if bool(f.i_target)!=bool(ix.ix_target):
            identity_differences.append(dict(day=day,actual_consumed_facts_I_target=val(f,'i_target'),
                legacy_IX_target=val(ix,'ix_target'),actual_facts_I_floor=val(f,'i_floor'),
                legacy_IX_floor=val(ix,'ix_floor'),legacy_IX_exit_reason=val(ix,'ix_exit_reason'),
                note='Native actual I and legacy IX are distinct. Do not replace actual facts fields with legacy IX output.'))
        previous_floors=[layerlight(l)for l in before]
        after_floors=[layerlight(l)for l in live]
        buy_floors=[dict(layer=x['layer'],kind=x['kind'],qty=x['shares'],floor=x['floor'],at=x['at'])for x in buys]
        previous_byid={l['id']:l for l in before};buy_byid={l['layer']:l for l in buys}
        comparisons=[dict(layer=l['id'],kind=l['kind'],qty_CLOSE=l['qty'],
            previous_CLOSE_floor=previous_byid[l['id']]['floor']if l['id']in previous_byid else 'NONE_NEW_LAYER',
            actual_OPEN_initial_floor=buy_byid[l['id']]['floor']if l['id']in buy_byid else NONE,
            current_CLOSE_floor=l['floor'],intra_CLOSE_before_update_floor=NS)for l in live]
        row=dict(date=day,original_CLOSE_at=a['at'],previous_original_CLOSE=prev['at'],
            source_observed_at=val(ss,'observed_at'),source_publication_timestamp=NS,
            source_observed_bar=val(ss,'is_observed_bar'),source_segment=val(f,'segment_id'),
            raw_open=val(ss,'raw_open'),raw_high=val(ss,'raw_high'),raw_low=val(ss,'raw_low'),raw_close=val(ss,'raw_close'),
            raw_volume=val(ss,'raw_volume'),source_volume_coordinate=val(ss,'volume'),factor=val(f,'factor'),continuous_close=val(f,'close'),
            E0_target=val(f,'e0_target'),E0_floor_a=val(f,'e0_floor'),E0_ready=val(f,'e0_ready'),
            E0_entered_native_state=val(e,'entered'),E0_exited_native_state=val(e,'exited'),
            E0_entry_kind=val(e,'entry_kind'),E0_base_event=val(ev,'event'),E0_state_price_event=val(e,'price_event'),
            I_target=val(f,'i_target'),I_floor_a=val(f,'i_floor'),I_buy=val(f,'i_buy'),
            I_entered_actual_consumed_frame=NS,I_exited_actual_consumed_frame=NS,I_exit_reason_actual_consumed_frame=NS,
            G1_grade=val(f,'g_grade'),G1_ready=val(f,'g_ready'),G1_fresh_up=val(f,'g_fresh_up'),G1_acute_down=val(f,'g_acute_down'),
            G1_up_reasons_source_IX=val(ix,'up_reasons'),G1_phase_source_IX=val(ix,'phase'),
            CP_ready=val(c,'ready'),CP_phase=val(c,'phase'),CP_anchor_native=val(c,'anchor'),CP_frontier_native=val(c,'frontier'),
            CP_credit_native=val(c,'credit'),CP_scale_native=val(c,'scale'),CP_receipt=val(c,'receipt'),CP_candidate_a=val(c,'candidate'),
            CP_reset_reason=val(c,'reset_reason'),
            PVR_source_score=source_score,PVR_rank_policy=next((i['priority_policy']for i in intents if 'priority_policy'in i),NS)if rp is not None else NONE,
            PVR_original_H1_rank=rp['original_H1_rank']if rp is not None else NONE,
            PVR_priority_rank=rp['priority_rank']if rp is not None else NONE,
            PVR_original_slot=rp['original_slot']if rp is not None else NONE,
            PVR_final_slot=rp['final_slot']if rp is not None else NONE,
            PVR_actual_rank_policy_record=jsoncell(rr),
            original_qty_before_OPEN=qtybefore,original_qty_after_actual_OPEN=qty_after_saved_open,
            original_qty_CLOSE=a['positions'].get(SID,0),
            original_CORE_qty_CLOSE=sum(l['qty']for l in live if l['kind']=='core'),
            original_MOBILE_qty_CLOSE=sum(l['qty']for l in live if l['kind']=='add'),
            actual_layer_floors_previous_CLOSE=jsoncell(previous_floors),actual_new_buy_initial_floors_OPEN=jsoncell(buy_floors),
            actual_layer_floors_current_CLOSE=jsoncell(after_floors),floor_before_after_saved_comparison=jsoncell(comparisons),
            intra_CLOSE_actual_floor_update_log=NS,
            previous_CLOSE_plans_for_this_OPEN=jsoncell(incoming),OPEN_actual_funding_records=jsoncell(ff),
            OPEN_actual_buy_records=jsoncell(buys),OPEN_actual_sell_records=jsoncell(sells),
            CLOSE_original_opportunity_records=jsoncell(oo),CLOSE_actual_signal_intents=jsoncell(intents),
            CLOSE_actual_exit_proposals=jsoncell(exits),original_stock_audit_records=jsoncell(aud),
            original_account_NAV_CLOSE=a['nav'],original_ACT_on=a['on'])
        rows.append(row)
        raw_outputs.append(dict(day=day,facts=f.to_dict(),source_signal=ss.to_dict(),E0_states=e.to_dict()if e is not None else NS,
            E0_events=ev.to_dict()if ev is not None else NS,
            legacy_IX_provenance_frame_not_actual_native_I=ix.to_dict()if ix is not None else NS,
            CP1=c.to_dict()if c is not None else NS,
            PVR_score_source=source_score,rank_policy=rr,intents=intents,incoming_OPEN_intents=incoming,
            opportunities=oo,funding=ff,trades=actual,audit=aud,previous_CLOSE_stock_layers=before,current_CLOSE_stock_layers=live))
        crosschecks.append(dict(day=day,original_quantity_bridge_exact=True,
            facts_E0_equals_native_state_and_IX=True,facts_G1_equal_legacy_IX_G1_fields=True,
            actual_I_uses_consumed_facts_only=True,actual_I_equals_legacy_IX_for_this_day=bool(f.i_target)==bool(ix.ix_target),
            rank_policy_matches_source_score=rp is None or math.isclose(source_score,rp['PVR'],rel_tol=1e-12),
            no_intent_has_no_fabricated_rank=rp is not None or row['PVR_priority_rank']==NONE))
    save('HYTERA_DAILY_NATIVE_ROWS.json',rows)
    with (OUT/'HYTERA_DAILY_NATIVE.csv').open('w',newline='')as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows([clean(r)for r in rows])
    keydays=['2024-09-23','2024-10-15','2024-10-21','2024-11-04','2024-11-05','2024-11-26','2024-11-27']
    save('KEY_DAYS_ORIGINAL_OUTPUTS.json',[r for r in raw_outputs if r['day']in keydays])
    save('ALL_DAYS_ORIGINAL_STOCK_OUTPUTS.json',raw_outputs)
    save('SOURCE_IDENTITY_DIFFERENCES.json',dict(observations=len(rows),I_versus_legacy_IX_different_days=len(identity_differences),
        rows=identity_differences,actual_I_source=paths['facts'],legacy_IX_not_I_source=paths['IX_signal'],
        no_I_entered_or_exit_reason_in_actual_facts=True,no_fields_inferred=True))
    save('SOURCE_SHA256.json',SOURCES)
    save('SOURCE_REFERENCE_MAP.json',dict(stock_manifest=str(manifest_path),actual_frames=paths,
        actual_long_PVR_manifest=str(score_manifest),actual_long_PVR_scores=str(scorepath),
        original_book=str(BASE/'B.json.gz'),original_daily=str(BASE/'daily.jsonl.gz'),
        clock_note='Date-only cached frames have no saved publication instant. Actual native consuming CLOSE time comes from original account daily/decision records, not a reconstructed provider timestamp.',
        strong_cache_not_used=True,no_projected_or_regenerated_facts=True))
    selected_buys=[r for r in book['trades']if r['security_id']==SID and r['side']=='buy'and START<=r['at'][:10]<=END]
    selected_sells=[r for r in book['trades']if r['security_id']==SID and r['side']=='sell'and START<=r['at'][:10]<=END]
    assert len(selected_buys)==3 and len(selected_sells)==2
    assert rows[0]['original_qty_before_OPEN']==0 and rows[-1]['original_qty_CLOSE']==0
    save('CHECKS_AND_COST.json',dict(status='PASS_SAVED_NATIVE_STOCK_DAILY_EXTRACTION',stock=SID,observations=len(rows),
        first_day=rows[0]['date'],last_day=rows[-1]['date'],actual_buys=selected_buys,actual_sells=selected_sells,
        per_day_checks=crosschecks,E0_entered_and_event_from_saved_native_sources=True,
        floor_boundary='Actual previous/current CLOSE snapshots and actual OPEN initial floor only; intra-CLOSE before/after event log was not saved and remains NOT_SAVED.',
        source_identity_boundary='Actual I only from consumed facts.19 legacyIX/nativeI mismatch observations are expected mechanism differences, not permission to regenerate facts.',
        discovery_note='Default PVR cache did not contain2024; actual long uses pre-existing2024_full scores. Read-only schema probe hit missing2024 key; no score generation.',
        new_accounts=0,new_backtests=0,new_parameter_tests=0,new_models=0,new_market_objects=0,new_features=0,
        extraction_seconds=time.monotonic()-t0))
    print(json.dumps(dict(stock=SID,observations=len(rows),buys=3,sells=2,seconds=time.monotonic()-t0,new_accounts=0)))

if __name__=='__main__':main()
