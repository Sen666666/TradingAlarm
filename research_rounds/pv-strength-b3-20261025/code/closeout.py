"""Final identity and delivery receipt. Does not recalculate any model."""
import json,re
from pathlib import Path
import numpy as np,pandas as pd
from common import ROOT,REPO,OLD,B2,NAMES,read,write,now,sha,identity

def main():
    identity();checks=read(ROOT/'validation/checks.json');audit=read(ROOT/'reviews/implementation/audit.json')
    assert checks['technical_passed'] and checks['technical_checks']==239 and audit['passed']
    raw=read(ROOT/'reviews/raw/OUTPUT_RECEIPT.json');synt=read(ROOT/'reviews/adversarial/SYNTHETIC_VIEW_RECEIPT.json')
    assert raw['plots_viewed']==22 and raw['before_raw_report_unchanged'] and synt['count']==24
    for kind,n in [('real',22),('synthetic',24)]:
        manifest=read(ROOT/'figures'/(kind+'-manifest.json'));assert len(manifest['plots'])==n
        for x in manifest['plots']:assert sha(x['path'])==x['sha256']
    assert len(audit['physical_prefixes'])==14
    f=pd.read_parquet(ROOT/'results/AU0.parquet');f=f.loc[f.valid_strength_observation];r=np.log(f.close).diff();rows=[]
    for date in ['2026-03-10','2026-03-20','2026-04-13','2026-04-30','2026-05-15','2026-06-05','2026-06-11']:
        i=f.index.get_loc(pd.Timestamp(date));hist=r.iloc[i-63:i];row=f.loc[date]
        rows.append(dict(date=date,**{k:float(row[k]) for k in ['grade','z_21','z_63','amplitude_21','amplitude_63','sigma']},
            top3_square_share=float(hist.pow(2).nlargest(3).sum()/hist.pow(2).sum()),median_absolute_return=float(hist.abs().median())))
    write(ROOT/'analysis/decline-diagnostics.json',rows)
    # Verify local references that appear in the delivered HTML, ignoring hashes/query/data/http links.
    html=(ROOT/'report/index.html').read_text();bad=[]
    for ref in re.findall(r'(?:href|src)="([^"]+)"',html):
        if ref.startswith(('http:','https:','#','data:')) or '${' in ref:continue
        p=(ROOT/'report'/ref).resolve()
        if not p.exists() and p.name!='complete.json':bad.append(str(p))
    assert not bad,bad
    receipt=dict(recorded_at=now(),status='completed_not_promoted',formal_candidates=1,
        mechanism_parameter_revisions_after_real=0,prefreeze_type_serialization_fix=1,
        account_runs=0,market_downloads=0,blank_agents=5,real_assets=7,real_figures=22,
        synthetic_figures=24,summary_figure=1,technical_checks=239,independent_rows=17605,
        independent_numerical_fields=27,real_physical_prefixes=14,old_files_preserved=400,
        registered_baseline_files_preserved=30,seen_development_only=True,
        decision='Consolidation and acute crash improvement; persistent decline/reheating/fast-start failures prevent promotion.',
        report_url='http://127.0.0.1:8787/report/',no_automatic_next_queue=True,
        ui_checks=['AU0 2025-07-31 neutral','AU0 2026-02-02 freeze','512480 2026-08-10 cold','narrow-panel select fits after CSS-only correction'],
        primary_artifacts=['CONCLUSION.md','PROTOCOL.md','report/index.html','figures/gold-summary.png'],
        artifact_sha256={str(p.relative_to(ROOT)):sha(p) for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='complete.json'},
        project_handoff_sha256={str(p.relative_to(REPO)):sha(p) for p in [REPO/'README.md',REPO/'docs/HANDOFF.md',REPO/'docs/NEXT_RESEARCH_TASKS.md',REPO/'docs/TREND_STRENGTH_STATE_B3_2026_10_25.md']})
    write(ROOT/'complete.json',receipt);identity()
    print(dict(passed=True,artifacts=len(receipt['artifact_sha256']),old_files=400,registered=30,accounts=0),flush=True)

if __name__=='__main__':main()
