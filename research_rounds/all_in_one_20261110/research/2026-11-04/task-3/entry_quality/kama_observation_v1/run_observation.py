"""Five fullsource indicators and six fixed original anchor contracts only."""
from pathlib import Path
import sys,json,hashlib,time
HERE=Path(__file__).resolve().parent;SHARED=HERE.parent/'channel_atr_fsm_v1'
sys.path.insert(0,str(SHARED))
import engine,runner
import kama

ANCHORS={'000620.SZ':['2022-01-07'],'002583.SZ':['2024-09-20'],
 '300085.SZ':['2024-09-12','2024-10-09'],'603061.SH':['2025-12-04'],'300623.SZ':['2026-01-09']}
KEYDAYS={'000620.SZ':['2022-01-17','2022-01-18','2022-01-19'],
 '002583.SZ':['2024-10-31','2024-11-01','2024-11-04'],
 '300085.SZ':['2024-09-12','2024-09-19','2024-09-20','2024-10-09','2024-10-10'],
 '603061.SH':['2025-12-04','2026-02-11'],'300623.SZ':['2026-01-09','2026-02-02']}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(engine.clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def main():
    out=HERE/'run_v1';out.mkdir(exist_ok=False);started=time.monotonic()
    sources={str(p):sha(p) for p in [HERE/'kama.py',Path(__file__),SHARED/'engine.py',SHARED/'runner.py',runner.MANIFEST]}
    metas={x['symbol']:x for x in json.loads(runner.MANIFEST.read_text())};allrows=[];key=[]
    for sid,anchors in ANCHORS.items():
        data,bind=runner.read_symbol(metas[sid]);sources.update(bind);price=data['price'];features=engine.features(price)
        indicators=kama.calculate(price,features);indicators.insert(0,'sid',sid)
        indicators.to_parquet(out/(sid.replace('.','_')+'_INDICATORS.parquet'))
        pairfile=SHARED/'smoke_v1'/sid.replace('.','_')/'CP_ANCHOR_PAIRS.json';sources[str(pairfile)]=sha(pairfile)
        pairs=json.loads(pairfile.read_text())
        for anchor in anchors:
            pair=next(x for x in pairs if x['anchor_day']==anchor);assert pair['status']=='PAIRED_SHADOWS'
            for label in ['KAMA','EMA20']:
                result=kama.shadow(pair,price,features,data['facts'],indicators,label);allrows.append(result)
                byday={x['day']:x for x in result['steps']}
                for day in KEYDAYS[sid]:
                    key.append(dict(sid=sid,anchor=anchor,label=label,day=day,
                        indicator=indicators.loc[day].to_dict(),shadow=byday.get(day),
                        shadow_status='RECORDED_STEP' if day in byday else 'NOT_ACTIVE_AT_THIS_DAY_NOT_REUSED'))
    save(out/'ANCHOR_SHADOWS.json',allrows);save(out/'KEY_DAYS.json',key)
    summary=[{k:x[k] for k in ['sid','anchor_day','label','anchor_seed_weight','outcome','exit_day','exit_reason','next_source_OPEN_reference','ever_unknown']} for x in allrows]
    save(out/'SUMMARY.json',summary)
    assert all(sha(p)==v for p,v in sources.items())
    save(out/'RUN_RECEIPT.json',dict(status='FIVE_SOURCE_SIX_FIXED_ANCHOR_OBSERVATIONS_COMPLETE',source_sha256=sources,
        seed='Both KAMA and EMA20 first ten completed close mean at j9; j10 first update',
        fixed_parameters=dict(ER_length=10,KAMA_fast=2/3,KAMA_slow=2/31,EMA20alpha=2/21,sigma_prior=63,band_sigma=1),
        sources=5,anchors=6,protection_shadows=12,new_accounts=0,new_orders=0,new_quantities=0,new_returns=0,
        original_E0_I_CP_model_runs=0,full_calendar_gap_check='NOT_VERIFIED',elapsed_seconds=time.monotonic()-started))
    print(json.dumps(engine.clean(summary),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
