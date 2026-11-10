"""Independent original-state census audit. No strategy/Account import."""
from pathlib import Path
from collections import Counter,defaultdict
import gzip,hashlib,json,pickle,time
import pandas as pd
O=Path(__file__).resolve().parents[1];T=O.parent.parent/'task';R=Path(__file__).resolve().parent
def j(p):return json.loads(Path(p).read_text())
def gz(p):
    with gzip.open(p,'rt')as h:return json.load(h)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    start=time.monotonic();summary=j(O/'I_AUTHORIZATION_CENSUS_SUMMARY.json');rows=j(O/'ALL_FIRST_I_EXIT_E0_STATES.json');events=j(O/'RAW_I_AUTH_GAP_PRICE_EVENTS.json');sources=j(O/'I_AUTH_CENSUS_SOURCE_SHA256.json');assert all(sha(p)==h for p,h in sources.items())
    root={'long':T/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair/B.json.gz','strong':T/'pvr_pool_feasibility/runs/2025_26/pair/B.json.gz'}
    expected_exits={};mother={};by_sid=defaultdict(list)
    for w,p in root.items():
        b=gz(p);first={}
        for e in b['audit']:
            if e['kind']=='pilot_layer_exit':
                for k in e['layers']:first.setdefault(k,e)
        layers={e['id']:e for e in b['layers']};mother[w]=dict(layers=len(layers),first_exit_reasons=dict(Counter(e['reason']for e in first.values())))
        for k,e in first.items():
            if e['reason']=='I_structure_exit':
                z=dict(window=w,layer=k,sid=e['sid'],day=e['at'][:10],role=layers[k]['kind']);expected_exits[w,k]=z;by_sid[z['sid']].append(z)
    assert {(r['window'],r['layer'])for r in rows}==set(expected_exits)
    saved={(r['window'],r['layer']):r for r in rows};saved_events={(r['window'],r['sid'],r['day']):r for r in events};assert len(saved_events)==len(events)
    features=pickle.loads((O/'PRICE_FEATURES.pkl').read_bytes());sm=j('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json');counts=defaultdict(Counter);seen=set();missing_cp=Counter()
    for rec in sm:
        sid=rec['symbol'];f=pd.read_parquet(rec['refs']['facts'],columns=['close','segment_id','e0_target','e0_floor','i_target','i_floor']);p=features[sid]
        for e in by_sid[sid]:
            r=saved[e['window'],e['layer']];d=pd.Timestamp(e['day']);fr=f.loc[d]
            for k,v in e.items():assert r[k]==v
            assert r['exact_price_state_known']is True
            assert r['e0_target']==bool(fr.e0_target)and r['i_target']==bool(fr.i_target)
            assert r['close']==float(fr.close)
            for k in ['e0_floor','i_floor']:assert r[k]==(float(fr[k])if pd.notna(fr[k])else None)
        g=f.reindex(p.index);known=g.e0_target.notna()&g.i_target.notna();gap=known&g.e0_target.eq(1)&g.i_target.eq(0)
        same_source=p.source_segment.eq(p.source_segment.shift())
        previous_known=p.ema20.shift().notna()&p.ema60.shift().notna()
        ema_cross=p.ema_trend_known&same_source&previous_known&p.ema20.gt(p.ema60)&p.ema20.shift().le(p.ema60.shift())
        cp=pd.read_parquet(rec['refs']['CP1'],columns=['receipt']).receipt.reindex(p.index)
        for w,lo,hi in [('long','2022-01-01','2024-12-31'),('strong','2025-07-01','2026-06-30')]:
            within=(p.index>=lo)&(p.index<=hi);m=gap&within;c=counts[w]
            c['known_E0_I_stock_CLOSEs']+=int((known&within).sum());c['raw_E0_on_I_off_stock_CLOSEs']+=int(m.sum());c['raw_gap_BB_cross_events']+=int((m&p.bb20_cross).sum());c['raw_gap_EMA_cross_events']+=int((m&ema_cross).sum());c['raw_gap_original_CP_receipts']+=int((m&cp.eq(True)).sum());missing_cp[w]+=int((m&cp.isna()).sum())
            for d in p.index[m&(p.bb20_cross|ema_cross)]:
                key=(w,sid,str(d.date()));r=saved_events[key];seen.add(key)
                assert r['original_e0_target']is True and r['original_i_target']is False and r['raw_price_evidence_only']is True
                assert r['BB_cross']==bool(p.at[d,'bb20_cross'])and r['EMA20_60_cross']==bool(ema_cross.loc[d])
                assert r['original_CP_receipt']==(bool(cp.loc[d])if pd.notna(cp.loc[d])else None)
    assert seen==set(saved_events)
    for w in root:
        a=[r for r in rows if r['window']==w];d=dict(layers=len(a),unique_stock_CLOSEs=len({(r['sid'],r['day'])for r in a}),known=len(a),unknown=0,E0_still_on=sum(r['e0_target']for r in a),E0_off=sum(not r['e0_target']for r in a),I_still_on=sum(r['i_target']for r in a));assert d==summary['mother'][w]['first_I_exit_diagnostic']
        assert mother[w]['layers']==summary['mother'][w]['layers']and mother[w]['first_exit_reasons']==summary['mother'][w]['first_exit_reasons'];assert dict(counts[w])==summary['raw_gap_summary'][w]
    result=dict(passed=True,status='PASS_ORIGINAL_I_CENSUS_ONLY',all_first_I_exit_rows_exact=True,first_I_exit_layers={w:summary['mother'][w]['first_I_exit_diagnostic']for w in root},all_1709_gap_counts_and_saved_event_keys_exact=True,raw_gap_summary={w:dict(c)for w,c in counts.items()},raw_gap_CP_unknown=dict(missing_cp),raw_price_event_union=len(events),source_hashes=len(sources),seconds=time.monotonic()-start,account_runs=0,projection_runs=0,caveats=['No active I exit with E0 still on is observed in these original accounts. EMA preservation through actual I exits would therefore cross an E0 boundary in this sample.','Original stock CP1 uses e0_valid=i_target, so zero CP receipts while I is off is mechanically expected from the upstream contract. It is not evidence that these price segments lack potential structure or progress.','Raw E0-on/I-off BB/EMA events are not S0/Q/ACT/industry/funding permission or returns. First saved 2022 EMA prior ordering stays unknown; no new indicator or supplementary strategy is tested.'])
    (R/'I_AUTHORIZATION_CENSUS_REVIEW.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
