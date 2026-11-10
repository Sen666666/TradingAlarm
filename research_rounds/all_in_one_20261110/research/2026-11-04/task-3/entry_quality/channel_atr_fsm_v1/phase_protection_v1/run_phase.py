"""Fixed five-stock/291-anchor protection shadows only; no market FSM/account call."""
from pathlib import Path
import sys,json,hashlib,time
from collections import Counter

HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(ROOT))
import engine,runner
import phase

SIDS=['000620.SZ','002583.SZ','300085.SZ','603061.SH','300623.SZ']
LAUNCH={'000620.SZ':'2022-01-06','002583.SZ':'2024-09-19','300085.SZ':'2024-08-30','603061.SH':'2025-11-06','300623.SZ':'2025-12-16'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(engine.clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def main():
    out=HERE/'run_v1';out.mkdir(exist_ok=False);start=time.monotonic()
    sources={str(p):sha(p) for p in [HERE/'FREEZE.md',HERE/'phase.py',Path(__file__),ROOT/'engine.py',ROOT/'runner.py',runner.MANIFEST]}
    version='PHASE_2S_TREND4_V1:'+engine.key(sources)[:20]
    metas={r['symbol']:r for r in json.loads(runner.MANIFEST.read_text())};allrows=[];cases=[]
    for sid in SIDS:
        original=ROOT/'smoke_v1'/sid.replace('.','_')/'CP_ANCHOR_PAIRS.json';sources[str(original)]=sha(original)
        pairs=json.loads(original.read_text());data,bindings=runner.read_symbol(metas[sid]);sources.update(bindings)
        # Original market FSM and CP formula are NOT called. Only immutable OHLC feature arithmetic.
        features=engine.features(data['price'])
        result=phase.simulate(sid,data['price'],features,data['facts'],data['CP1'],pairs,version)
        assert len(result)==len(pairs)
        save(out/(sid.replace('.','_')+'_ANCHOR_SHADOWS.json'),result);allrows.extend(result)
        candidates=[r for r in result if r['anchor_day']>=LAUNCH[sid]]
        if candidates:cases.append(candidates[0])
    assert len(allrows)==291 and sum(r['original_pair_status']=='PAIRED_SHADOWS' for r in allrows)==290
    steps=[s for r in allrows for s in r.get('steps',[])];switch=[s for s in steps if s['phase_switch']]
    summary=dict(anchors=len(allrows),outcomes=dict(Counter(r['outcome'] for r in allrows)),
        comparison_both_exit=dict(Counter(r.get('relation_to_saved_CP') for r in allrows if r.get('relation_to_saved_CP'))),
        first_2S_reached_anchors=sum(r.get('reached_2S',False) for r in allrows),switched_anchors=sum(r.get('phase_switch_day') is not None for r in allrows),
        EARLY_exit_anchors=sum(r['outcome']=='EXIT_SIGNAL' and r.get('phase_at_end')=='EARLY' for r in allrows),
        TREND4_exit_anchors=sum(r['outcome']=='EXIT_SIGNAL' and r.get('phase_at_end')=='TREND4' for r in allrows),
        switch_same_close_raw_CP=sum(s['CP_receipt_state'] is True for s in switch),
        TREND4_line_driver_steps=dict(Counter(s['line_driver'] for s in steps if s['phase_after']=='TREND4' and s['Q'] is not None)),
        unknown_step_reasons=dict(Counter(s['unknown_reason'] for s in steps if s['unknown_reason'])),
        first_bar_peak_uses_close_only=True,new_original_E0_I_CP_FSM_runs=0,
        new_phase_protection_shadow_runs=291,new_phase_shadows_with_steps=sum(bool(r.get('steps')) for r in allrows),
        ever_unknown_anchors=sum(r.get('ever_unknown',False) for r in allrows),
        new_accounts=0,new_quantities=0,new_returns=0)
    save(out/'SUMMARY.json',summary);save(out/'FIVE_FIXED_EARLIEST_CASES.json',cases)
    assert all(sha(p)==v for p,v in sources.items())
    save(out/'RUN_RECEIPT.json',dict(status='FIXED_291_PHASE_SHADOWS_COMPLETE',version=version,source_sha256=sources,
        economic_parameters=dict(reached_multiple=2,trend_ATR_multiple=4),original_CP_control='REUSED_SAVED_PAIR',
        anchor_count=291,new_original_E0_I_CP_FSM_runs=0,new_phase_protection_shadow_runs=291,
        new_accounts=0,new_quantities=0,new_returns=0,elapsed_seconds=time.monotonic()-start))
    print(json.dumps(summary),flush=True)
    for c in cases:print(json.dumps({k:c.get(k) for k in ['sid','anchor_day','E','S','P0','first_reached_2S_day','phase_switch_day','exit_day','exit_reason','relation_to_saved_CP','original_CP_control','exit_next_OPEN_reference']},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
