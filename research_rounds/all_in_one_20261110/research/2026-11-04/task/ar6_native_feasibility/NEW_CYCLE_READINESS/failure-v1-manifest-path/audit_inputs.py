"""Read-only cycle inventory and six-series pure input checks; no engine imports."""
from pathlib import Path
from collections import Counter
import ast, collections, hashlib, json, math, time
import numpy as np
import pandas as pd

O = Path(__file__).resolve().parent
W = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
P = W / 'pvr-slot1-native-readiness-20261101'
U = W / 'universe-cp1-inputs-20261031'
START, END, CUT = '2024-01-01', '2024-12-31', '2024-06-28'

def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''): h.update(block)
    return h.hexdigest()

def read(p): return json.loads(Path(p).read_text())
def save(name, value):
    (O / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n')

def main():
    begun = time.monotonic()
    sm, im = read(U/'STOCK_MANIFEST.json'), read(U/'INDUSTRY_MANIFEST.json')
    old = read(P/'SCORES_MANIFEST.json')
    scoremeta = {r['symbol']: r for r in old['entries']}
    assert len(sm) == len(scoremeta) == 1709 and len(im) == 90
    assert [r['symbol'] for r in sm] == old['fixed_stock_ids']
    hpath = Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
    h = np.load(hpath)
    hd = pd.DatetimeIndex(h['dates'])
    calendar = hd[(hd >= START) & (hd <= END)]
    assert len(calendar) == 242 and calendar.is_unique
    allsymbols = set(str(s) for s in h['symbols'])
    assert set(old['fixed_stock_ids']) | {r['series'] for r in im} <= allsymbols
    recovery_path = W/'mainline-absolute-Q4-20261031/recovery.csv'
    recovery = pd.read_csv(recovery_path, index_col=0, parse_dates=True)
    assert recovery.loc[START:END].index.equals(calendar)

    coverage, receipt_windows = [], Counter()
    missing_paths = []
    for r in sm:
        sid = r['symbol']
        for key, path in r['refs'].items():
            if not Path(path).is_file(): missing_paths.append([sid, key, path])
        # Read only cached indices and one boolean receipt column, no models.
        f = pd.read_parquet(r['refs']['facts'], columns=[])
        z = pd.read_parquet(r['refs']['CP1'], columns=['receipt'])
        assert f.index.equals(z.index)
        days = f.index[(f.index >= START) & (f.index <= END)]
        original_rr = read(r['refs']['receipts'])
        for x in original_rr: receipt_windows[x['confirmed_day'][:4]] += 1
        coverage.append(dict(sid=sid, observations_2024=len(days),
                             missing_vs_market_2024=len(calendar.difference(days)),
                             numeric_CP1_receipts_2024=int(z.loc[START:END].receipt.eq(True).sum()),
                             first=str(f.index.min()) if len(f) else None,
                             last=str(f.index.max()) if len(f) else None))
    industries = []
    for r in im:
        for key, path in r['refs'].items():
            if not Path(path).is_file(): missing_paths.append([r['series'], key, path])
        f = pd.read_parquet(r['refs']['state'], columns=['day','receipt'])
        q = f[(f.day >= START) & (f.day <= END)]
        industries.append(dict(sid=r['series'], rows_2024=len(q),
                               missing_vs_market_2024=len(set(str(x.date()) for x in calendar)-set(q.day)),
                               numeric_CP1_receipts_2024=int(q.receipt.eq(True).sum())))

    formula = W/'pvr-current-v3-information-capital-20261101/original_score_function.py'
    assert sha(formula) == old['formula_sha256']
    env = dict(np=np, pd=pd)
    exec(compile(formula.read_text(), str(formula), 'exec'), env)
    score = env['score']
    tracepath = W/'cp1-evidence-trace-20261031/trace.py'
    nodes = [n for n in ast.parse(tracepath.read_text()).body if isinstance(n,ast.FunctionDef) and n.name in {'ident','norm','trace'}]
    assert {n.name for n in nodes} == {'ident','norm','trace'}
    model = Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/continuous-protection-lines-20261028/code/model.py')
    tenv = dict(np=np, pd=pd, math=math, json=json, hashlib=hashlib, collections=collections,
                SCALE='CP1-original:'+sha(model)[:16], BEGIN=START, END=END)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(tracepath), 'exec'), tenv)
    keynode = next(n for n in ast.parse((W/'2022-normal-reference-20261031/export_receipts.py').read_text()).body
                   if isinstance(n,ast.Assign) and any(isinstance(k,ast.Name) and k.id=='KEYS' for k in n.targets))
    keys = ast.literal_eval(keynode.value)
    compact = lambda rows: [{k:r[k] for k in keys} for r in rows]
    samples = []
    for r in sorted(sm,key=lambda x:x['symbol'])[:3] + sorted(im,key=lambda x:x['series'])[:3]:
        industry = 'series' in r
        sid = r['series' if industry else 'symbol']
        for path, expected in {**r['source_sha256'], **r['output_sha256']}.items(): assert sha(path)==expected
        qfull = pd.read_parquet(r['refs']['CP1_input'])
        zfull = pd.read_parquet(r['refs']['CP1'])
        q, z = qfull.loc[:END], zfull.loc[:END]
        episodefull = qfull.e0_valid if industry else pd.read_parquet(r['refs']['facts'],columns=['e0_target']).e0_target.reindex(qfull.index).astype(bool)
        events = pd.read_parquet(next(p for p in r['source_sha256'] if p.endswith('/events.parquet'))).reindex(qfull.index)
        tenv.update(BEGIN=START,END=END)
        rr, _, _ = tenv['trace'](sid,q,z,events.loc[:END],episodefull.loc[:END])
        assert [x['confirmed_day'] for x in rr] == [str(d.date()) for d in z.loc[START:END].index[z.loc[START:END].receipt.eq(True)]]
        assert not any(x['trace_unknown'] for x in rr)
        prefix, _, _ = tenv['trace'](sid,q.loc[:CUT],z.loc[:CUT],events.loc[:CUT],episodefull.loc[:CUT])
        assert compact(prefix) == compact([x for x in rr if x['confirmed_day'] <= CUT])
        previous = []
        for year,end,root in [('2022','2022-12-30',W/'2022-normal-reference-20261031'),
                              ('2023','2023-12-29',W/'recovery-2023-readiness-20261101')]:
            tenv.update(BEGIN=year+'-01-01',END=end)
            past,_,_=tenv['trace'](sid,qfull.loc[:end],zfull.loc[:end],events.loc[:end],episodefull.loc[:end])
            cached = root/'inputs'/('industry-receipts' if industry else 'stock-receipts')/(sid+'.json')
            assert compact(past)==read(cached)
            previous.append(dict(year=year,receipts=len(past),canonical_complete_body_exact=True))
        row = dict(sid=sid,industry=industry,canonical_receipts_2024=len(rr),trace_unknown=0,
                   original_CP1_numeric_receipt_dates_exact=True,physical_June28_canonical_prefix_exact=True,
                   old_export_checks=previous)
        if industry:
            state=pd.read_parquet(r['refs']['state']); by={x['day']:x for x in state.to_dict('records')}
            assert all(by[x['confirmed_day']]['receipt_id']==x['receipt_id'] for x in rr)
            row['original_industry_state_receipt_IDs_exact']=True
        else:
            src=Path(scoremeta[sid]['source']); assert sha(src)==scoremeta[sid]['source_sha256']
            f=pd.read_parquet(src).loc[:END]; full=score(f)
            pastscore=pd.read_parquet(P/'scores'/(sid+'.parquet')).loc[old['decision_calendars']['2022']['dates']]
            pd.testing.assert_frame_equal(full[['score']].reindex(pastscore.index),pastscore,check_exact=True,check_freq=False)
            pd.testing.assert_frame_equal(score(f.loc[:CUT]),full.loc[:CUT],check_exact=True,check_freq=False)
            altered=f.copy();altered.loc[altered.index>CUT,'close']*=7;altered.loc[altered.index>CUT,'amount']*=.013
            pd.testing.assert_frame_equal(score(altered).loc[:CUT],full.loc[:CUT],check_exact=True,check_freq=False)
            ready=full[['score']].reindex(calendar).score.notna()
            row.update(PVR_ready_2024=int(ready.sum()),PVR_NA_2024=int((~ready).sum()),
                       old2022_score_cells_exact=len(pastscore),physical_and_future_poison_score_prefix_exact=True)
        save('SAMPLE-'+sid+'.json',dict(checks=row,canonical_2024=compact(rr)))
        samples.append(row)
    assert not missing_paths
    result=dict(account_events=0,new_model_I_CP1_stage_calculations=0,downloaded=0,
        window=[START,END],market_dates_2024=len(calendar),first_market_day=str(calendar[0].date()),last_market_day=str(calendar[-1].date()),
        market_days=[str(d.date()) for d in calendar],fixed_stocks=1709,industries=90,
        stocks_no_2024_observations=sum(x['observations_2024']==0 for x in coverage),
        stocks_all242_observations=sum(x['observations_2024']==242 for x in coverage),
        stock_observations_2024=sum(x['observations_2024'] for x in coverage),
        missing_stock_date_cells=sum(x['missing_vs_market_2024'] for x in coverage),
        numeric_stock_CP1_receipts_2024=sum(x['numeric_CP1_receipts_2024'] for x in coverage),
        numeric_industry_CP1_receipts_2024=sum(x['numeric_CP1_receipts_2024'] for x in industries),
        industries_complete242=sum(x['rows_2024']==242 and x['missing_vs_market_2024']==0 for x in industries),
        existing_universe_stock_receipt_years=dict(receipt_windows),
        existing_PVR_score_windows=old['windows'],existing_PVR_2024_export=False,
        all_ref_files_present=True,full_domain_file_hash_reaudit=False,six_sample_all_source_and_output_hashes_exact=True,
        sample_checks=samples,coverage_file='STOCK_COVERAGE_2024.json',industry_coverage_file='INDUSTRY_COVERAGE_2024.json',
        source_hashes={str(p):sha(p) for p in [Path(__file__),U/'STOCK_MANIFEST.json',U/'INDUSTRY_MANIFEST.json',P/'SCORES_MANIFEST.json',formula,tracepath,recovery_path,hpath]},
        interpretation='Inventory counts and six deterministic input checks only; all-domain2024 scores/canonical receipts and economic paths NOT exported/run. Missing observations retain original NA and are not classified as halts or delistings.',
        seconds=time.monotonic()-begun)
    save('STOCK_COVERAGE_2024.json',coverage);save('INDUSTRY_COVERAGE_2024.json',industries);save('INPUT_AUDIT.json',result)
    print(json.dumps({k:result[k] for k in ['account_events','fixed_stocks','industries','market_dates_2024','stocks_no_2024_observations','stocks_all242_observations','numeric_stock_CP1_receipts_2024','numeric_industry_CP1_receipts_2024','industries_complete242','seconds']}))

if __name__=='__main__': main()
