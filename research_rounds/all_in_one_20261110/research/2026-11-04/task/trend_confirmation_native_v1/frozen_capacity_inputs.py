"""Compose the already-audited annual inputs; no indicator recalculation."""
from pathlib import Path
import ast, hashlib, json, math, time
from types import MappingProxyType
import pandas as pd
import capacity_adapter as C
A,N,J,L,IO=C.A,C.N,C.J,C.L,C.IO
W=A.W; O=Path(__file__).resolve().parent
YEARS = {
    '2022': (W/'2022-normal-reference-20261031/adapter.py','2022-01-01','2022-12-30'),
    '2023': (W/'recovery-2023-readiness-20261101/continuation_2023.py','2023-01-01','2023-12-29'),
    '2024': (O.parent/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/loader_2024.py','2024-01-01','2024-12-31'),
}
SCORE_PATHS = {
    '2022': W/'pvr-slot1-native-readiness-20261101/SCORES_MANIFEST.json',
    '2023': W/'pvr-slot1-native-readiness-20261101/continuation-2023-readiness/SCORES_MANIFEST.json',
    '2024': O.parent/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/SCORES_MANIFEST.json',
    'strong': W/'pvr-slot1-native-readiness-20261101/SCORES_MANIFEST.json',
}


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def one_year(year, out):
    source,start,end=YEARS[year]
    J.START,J.END=start,end
    def save(path,value): IO.write_json(Path(out)/'input-readiness'/year/Path(path).name,J.W.canon(value))
    if year == '2024':
        module=J.W.load('capacity_existing_2024_inputs',source)
        return module.inputs()
    node=next(v for v in ast.parse(source.read_text()).body if isinstance(v,ast.FunctionDef) and v.name=='inputs')
    env=dict(J=J,L=L,pd=pd,O=source.parent,START=start,END=end,time=time,save=save)
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'),env)
    return env['inputs']()


def load_long(out):
    begun=time.monotonic(); combined_receipts={};combined_ir={};ids=[];shared=cp=states=None
    for year in ('2022','2023','2024'):
        value=one_year(year,out)
        shared,receipts,cp,states,ir,identity=value
        for sid,rows in receipts.items():
            dest=combined_receipts.setdefault(sid,{})
            for day,row in rows.items():
                assert day not in dest or dest[day]==row,('receipt overlap mismatch',sid,day)
                dest[day]=row
        for key,row in ir.items():
            assert key not in combined_ir or combined_ir[key]==row,('industry receipt overlap',key)
            combined_ir[key]=row
        ids.append(dict(year=year,identity=identity,loader=str(YEARS[year][0]),loader_sha256=sha(YEARS[year][0]),
                        stock_receipts=sum(len(v)for v in receipts.values()),industry_receipts=len(ir)))
    J.START,J.END='2022-01-01','2024-12-31'
    days=[str(v.date())for v in shared[1].cutoffs if '2022-01-04'<=str(v.date())<='2024-12-31']
    assert len(days)==726 and len(set(days))==726
    cp_count=sum(int(f.loc['2022-01-04':'2024-12-31','receipt'].eq(True).sum())for f in cp.values())
    assert sum(len(v)for v in combined_receipts.values())==cp_count, 'union omitted historical CP1 receipts'
    sector_days={sid:{v['day']for v in rows} for sid,rows in states.items()}
    assert all(set(days)<=rows for rows in sector_days.values()), 'superset industry history omitted an old year'
    identity=dict(window=['2022-01-04','2024-12-31'],annual_source_identities=ids,
                  own_state_annual_reset=False,new_numeric_models=0,seconds=time.monotonic()-begun)
    identity.update(final_fact_CP1_state_source='audited2024 fullwarm superset, not 2024-only slice',
                    calendar_days=len(days),calendar_first=min(days),calendar_last=max(days),
                    calendar_by_year={y:sum(v.startswith(y)for v in days)for y in ('2022','2023','2024')},
                    all_stock_CP1_receipts_exact_count=cp_count,all90industry_states_cover_all726_dates=True,
                    immutable_numeric_source_overlap='each audited annual loader checks same original manifest output SHA before reading; no numeric recomputation',
                    score_overlap='separately byte-value checked by CombinedScores')
    IO.write_json(Path(out)/'LONG_INPUT_COMPOSITION.json',J.W.canon(identity))
    return shared,combined_receipts,cp,states,combined_ir,identity


def load_strong(out):
    old=A.S.O
    try:
        A.S.O=Path(out)/'input-readiness'
        return A.S.inputs('2025_26')
    finally:A.S.O=old


class CombinedScores:
    def __init__(self, paths, out, years=None):
        self.values={}; overlap=0;counts={}
        history_overlap=dict(finite_exact=0,both_unavailable=0,finite_differences=0,availability_differences=0,samples=[])
        assert years is None or len(years)==len(paths)
        for n,path in enumerate(paths):
            old=N.FrozenScores(path)
            selected=0
            for sid, rows in old.values.items():
                dest=self.values.setdefault(sid,{})
                for day,value in rows.items():
                    if years is not None and day in dest:
                        before=dest[day];bf,vf=math.isfinite(before),math.isfinite(value)
                        if not bf and not vf:history_overlap['both_unavailable']+=1
                        elif bf and vf and before==value:history_overlap['finite_exact']+=1
                        else:
                            key='finite_differences' if bf and vf else 'availability_differences'
                            history_overlap[key]+=1
                            if len(history_overlap['samples'])<20:
                                history_overlap['samples'].append(dict(sid=sid,day=day,original=before if bf else None,
                                    unused_later_history=value if vf else None,source=str(path)))
                    # Match the original real annual continuation exactly.
                    # Later exports may contain historical float roundoff;
                    # they never replace a prior year's live ranking source.
                    if years is not None and not day.startswith(years[n]):
                        continue
                    if day in dest:
                        assert dest[day]==value or(not math.isfinite(dest[day])and not math.isfinite(value)),('PVR source prefix changed',sid,day)
                        overlap+=1
                    dest[day]=value
                    selected+=1
            counts[str(path)]=selected
        record=dict(source_paths=[str(p.resolve()) for p in paths],
                    source_sha256={str(p.resolve()):sha(p) for p in paths},overlapping_values_exact=overlap,
                    per_original_year_manifest_dispatch=list(years) if years is not None else None,selected_values_by_source=counts,
                    unused_historical_overlap_diagnostic=history_overlap,
                    unused_export_history_never_overwrites_old_year=True,new_score_calculations=0)
        self.path=str((Path(out)/'COMBINED_SCORE_BINDING.json').resolve())
        target=Path(self.path)
        if target.exists():
            assert json.loads(target.read_text())==record, 'immutable score binding changed'
        else:
            IO.write_json(self.path,record)
        self.manifest_sha256=sha(self.path)
        self.values=MappingProxyType({sid:MappingProxyType(rows) for sid,rows in self.values.items()})
    def at(self,sid,day):
        value=self.values.get(sid,{}).get(day)
        return value if value is not None and math.isfinite(value) else None


def configure_scores(window,out):
    paths=[SCORE_PATHS[y] for y in ('2022','2023','2024')] if window=='long' else [SCORE_PATHS['strong']]
    # Keep the previous strong binding stable; its single source requires no
    # annual dispatch. Long is a new explicit original-year binding.
    folder=O/'bindings'/('long-year-dispatch-v2' if window=='long' else 'strong-single-source-v2')
    N.SCORES=CombinedScores(paths,folder,years=('2022','2023','2024')if window=='long' else None)
    IO.write_json(Path(out)/'SCORE_BINDING_REFERENCE.json',dict(path=N.SCORES.path,sha256=N.SCORES.manifest_sha256))
    return N.SCORES
