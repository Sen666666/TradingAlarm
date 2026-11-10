"""Verify the entire planned 1709 source closure before G2, never any economics."""
from pathlib import Path
import json
import hashlib
import re

O=Path(__file__).resolve().parent;R=O.parent;E=R/'m3_stock_birth_during_sector_v1'
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
AS=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024')


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        while chunk:=f.read(8*1024*1024):h.update(chunk)
    return h.hexdigest()


def main():
    out=O/'planned_inputs_v1'
    if out.exists():raise RuntimeError('Do not overwrite a completed/planned input verification')
    hashes={};origins={};absent=[]
    def add(p,h=None,origin='direct source'):
        p=Path(p).resolve();h=sha(p) if h is None else h
        if str(p) in hashes:assert hashes[str(p)]==h,('CONFLICTING_SEALED_VERSIONS',str(p),origins[str(p)],origin)
        else:hashes[str(p)]=h;origins[str(p)]=origin
    maps=[R/'independent_channel_full1709_preflight_v1/SOURCE_HASHES.json',
          R/'independent_channel_full1709_preflight_v1/overlap/OLD_NATIVE_Q_SOURCE_HASHES.json',
          E/'relative_priority_equity_run_2022_v1/dynamic/SOURCE_HASHES.json',
          E/'cash_equity_baseline_2024_v1/economic/SOURCE_HASHES.json']
    for m in maps:
        add(m)
        for p,h in json.loads(m.read_text()).items():add(p,h,str(m))
    for m in [U/'STOCK_MANIFEST.json',U/'INDUSTRY_MANIFEST.json']:
        add(m)
        entries=json.loads(m.read_text())
        for entry in entries:
            for field in ('source_sha256','output_sha256'):
                for p,h in entry.get(field,{}).items():add(p,h,str(m)+':'+field)
    stocks=json.loads((U/'STOCK_MANIFEST.json').read_text())
    for item in stocks:
        p=AS/'inputs-v1/actions'/(item['symbol']+'.json')
        if not p.exists():absent.append(str(p));continue
        add(p)
        x=json.loads(p.read_text())
        for ev in x.get('coverage_evidence',[]):add(ev['path'],ev['sha256'],str(p)+':rights evidence')
    direct=[R/'independent_channel_full1709_preflight_v1/FINAL_MARKET_SEAL.json',
        R/'independent_channel_full1709_preflight_v1/INDEPENDENT_FULL_AUDIT.json',
        R/'independent_channel_full1709_preflight_v1/overlap/RECEIPT_CONDITIONAL_OVERLAP.parquet',
        R/'independent_channel_full1709_preflight_v1/overlap/OLD_NATIVE_Q_EXTENDED.parquet',
        R/'independent_channel_full1709_preflight_v1/overlap/WINNER_FULL_HOLD_FIXED_COHORT.csv',
        R/'independent_channel_full1709_preflight_v1/overlap/SUPPLEMENT_OUTPUT_HASHES.json',
        R/'fast_entry_equity_2022_v1/ALL_MARKET_INPUTS_2022.parquet',
        R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet',
        R/'pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv']
    for p in direct:add(p)
    full=R/'independent_channel_full1709_preflight_v1'
    for name,h in json.loads((full/'FINAL_MARKET_SEAL.json').read_text())['files'].items():add(full/name,h,'FINAL_MARKET_SEAL')
    for base,leaf in [(E/'relative_priority_equity_run_2022_v1','dynamic'),(E/'cash_equity_baseline_2024_v1','economic')]:
        for p in (base/leaf).iterdir():
            if p.is_file() and p.suffix in ('.csv','.json'):add(p)
        for name in ('report.py','PROTOCOL.md','report/CORE_AND_FULL_ROUNDS.csv','report/FINANCIAL_COVERAGE.csv'):
            p=base/name
            if p.exists():add(p)
    total_bytes=0
    for i,(p,h) in enumerate(sorted(hashes.items()),1):
        assert sha(p)==h,('INPUT_SEAL_DRIFT',p,origins[p])
        total_bytes+=Path(p).stat().st_size
        if i%3000==0:print('VERIFIED_INPUTS',i,len(hashes),flush=True)
    out.mkdir()
    def write(name,x):
        (out/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
    write('PLANNED_INPUT_SHA256.json',hashes)
    write('ABSENT_ACTION_SOURCES.json',absent)
    write('INPUT_ORIGINS.json',origins)
    write('QA.json',dict(scope='FULL_PLANNED_SOURCE_CLOSURE_NOT_LAZY_TOUCHED_ONLY',stocks=len(stocks),
        files=len(hashes),bytes_verified=total_bytes,absent_action_sources=len(absent),all_expected_hashes_exact=True,
        script_sha256=sha(__file__),new_price_economic_runs=0))
    print('PLANNED_INPUT_SEAL_DONE',len(hashes),total_bytes,flush=True)


if __name__=='__main__':main()
