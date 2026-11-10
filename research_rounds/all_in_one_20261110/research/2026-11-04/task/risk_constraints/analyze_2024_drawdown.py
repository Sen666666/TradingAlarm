"""Strict saved CLOSE drawdowns and continuation/source identity, zero accounts."""
from pathlib import Path
from decimal import Decimal as D
import json,gzip,hashlib

HERE=Path(__file__).resolve().parent;OUT=HERE/'continuation2024_drawdown'
BASE=HERE.parent/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full'
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
OLD=W/'pvr-slot1-native-readiness-20261101';SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):SRC[str(p)]=sha(p);return json.loads(p.read_text())
def book(p):
    SRC[str(p)]=sha(p)
    with gzip.open(p,'rt') as f:return json.load(f)
def rows(p):
    SRC[str(p)]=sha(p)
    with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def dd(seq):
    peak=seq[0];worst=None
    for x in seq:
        if x[1]>peak[1]:peak=x
        ratio=1-x[1]/peak[1]
        if worst is None or ratio>worst['fraction']:
            worst=dict(fraction=ratio,percent=ratio*100,peak_at=peak[0],peak_NAV=peak[1],trough_at=x[0],trough_NAV=x[1],drawdown_yuan=peak[1]-x[1])
    return worst
def main():
    OUT.mkdir(exist_ok=False);result={};sm=read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json');im=read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')
    ids={x['symbol'] for x in sm};sectors={x['series'] for x in im};assert len(ids)==1709 and len(sectors)==90
    gate=read(BASE/'DATA_GATE.json');lg=read(BASE/'LOADER_GATE.json');assert gate['passed'] and lg['passed'] and lg['same1709stocks90industries']
    assert gate['old_canonical_controls_exact_series']==gate['physical_canonical_prefix_exact_series']==1799
    for side,parent in [('original',OLD/'continuation-2023-readiness/run-2023'),('no60',HERE.parent/'pvr_pool_feasibility/continuation2023/run-2023')]:
        root=BASE/'cycle2024'/side/'run-2024';ds=rows(root/'pair/daily.jsonl.gz');b=book(root/'pair/B.json.gz');done=read(root/'DONE.json');freeze=read(root/'EXECUTION_FREEZE.json');timing=read(root/'TIMING.json')
        pd=rows(parent/'pair/daily.jsonl.gz');pb=book(parent/'pair/B.json.gz')
        assert done['completed'] and timing['completed'] and not timing['automatic_exception_retry']
        assert len(ds)==726 and len(pd)==484 and ds[:484]==pd
        assert b['trades'][:len(pb['trades'])]==pb['trades'] and b['audit'][:len(pb['audit'])]==pb['audit']
        assert len({x['at'] for x in ds})==726 and all(sum(x['at'].startswith(y) for x in ds)==242 for y in ['2022','2023','2024'])
        assert ds[-1]['at']=='2024-12-31 15:10:00+08:00'
        fy=freeze['identity'];assert set(fy['fixed_ids'])==ids and set(fy['sectors'])==sectors
        assert fy['stock_manifest_sha256']==sha(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
        assert fy['industry_manifest_sha256']==sha(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')
        assert fy['canonical_manifest_sha256']==gate['canonical_manifest_sha256'] and fy['score_manifest_sha256']==gate['score_manifest_sha256']
        frozen={**freeze['checkpoint_source_freeze_preserved'],**freeze['entry_sources']}
        for p,expected in frozen.items():assert sha(p)==expected,('changed execution source',p)
        for k in ['canonical_manifest_sha256','score_manifest_sha256','ACT_external_sha256','H1_sha256']:assert fy[k] in frozen.values(),('identity not source-bound',k)
        ys=[x for x in ds if x['at'].startswith('2024')];initial=D(str(pd[-1]['nav']));end=D(str(ds[-1]['nav']))
        assert ys[0]['at']=='2024-01-02 15:10:00+08:00' and D(str(ys[0]['nav']))==initial
        assert end==D(str(b['ending_NAV']))==D(str(done['ending_NAV']['B']))
        seq=[(r['at'],D(str(r['nav']))) for r in ds];full=[('2022-01-04 initial capital before first CLOSE',D(1000000))]+seq
        result[side]=dict(year2024_own_start_NAV=initial,terminal_NAV=end,year2024_return_pct=(end/initial-1)*100,year2024_wealth_change=end-initial,
            year2024_CLOSE_maxDD=dd([(pd[-1]['at'],initial)]+[(r['at'],D(str(r['nav']))) for r in ys]),
            cumulative2022_2024_CLOSE_maxDD=dd(full),terminal_original_principal_loss_pct=(1-end/D(1000000))*100,
            own_parent484_daily_trade_audit_prefix_exact=True,Jan2_unique=True,full_closes=726,year_closes=242,
            exact_same1709stocks90industries=True,current_execution_source_SHA_checks=len(frozen),canonical_score_manifest_identity_bound=True,
            ACT_peak_not_used=True,intraday_joint_drawdown='unverified: no synchronized whole-account intraday marks; no composite OHLC high/low curve constructed')
        save(OUT/(side+'_CLOSE_CURVE.json'),[dict(at=at,NAV=nav) for at,nav in seq])
    save(OUT/'DRAWDOWN_COMPARISON.json',result);SRC[str(Path(__file__))]=sha(__file__)
    save(OUT/'SOURCE_MANIFEST.json',dict(sources=SRC,account_events=0,
        verified='same fixed stocks/industries, execution source SHA, own484daily/trade/audit prefix, completed726CLOSE curve, no reset or ACT peak substituted',
        not_claimed='No raw-price finance reconstruction here; no strategy signal fidelity certification; ar6 owner/reviewer separately audit inputs/signals/restores. MaxDD only on original CLOSE sampling, not actual intraday extrema.'))
    print(json.dumps(result,ensure_ascii=False,default=str),flush=True)
if __name__=='__main__':main()
