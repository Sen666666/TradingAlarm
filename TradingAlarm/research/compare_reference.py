"""Compare authorized observed labels, never inferred proprietary labels.

Inputs: CSV date, close, temperature; JSON manifests with instrument_id,
price_basis, source, label_vintage (point_in_time / retrospective / unknown).
No real reference file is bundled. A refusal is not a measured disagreement.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd

ORDER={v:i for i,v in enumerate(['冻','寒','凉','平','温','热','沸'])}

def compare(candidate, reference, candidate_meta, reference_meta):
    for df in (candidate,reference):
        if not {'date','close','temperature'}.issubset(df):
            raise ValueError('Required columns: date, close, temperature')
        if df.date.duplicated().any(): raise ValueError('Duplicate date')
        pd.to_datetime(df.date,errors='raise')
        if not np.isfinite(df.close).all() or (df.close<=0).any():
            raise ValueError('Finite positive closes required')
        labels=df.temperature.dropna()
        if not labels.isin(ORDER).all(): raise ValueError('Unknown nonempty temperature label')
    reasons=[]
    for key in ['instrument_id','price_basis']:
        if not candidate_meta.get(key) or candidate_meta.get(key)!=reference_meta.get(key):
            reasons.append(f'Missing or mismatched {key}')
    if not reference_meta.get('source'): reasons.append('Missing reference provenance')
    merged=candidate.merge(reference,on='date',suffixes=('_candidate','_reference')).sort_values('date')
    if merged.empty: reasons.append('No common dates')
    mismatch=~np.isclose(merged.close_candidate,merged.close_reference,rtol=1e-6,atol=1e-8)
    if mismatch.any(): reasons.append('Underlying close series differs; cannot isolate algorithm difference')
    result={'status':'not_comparable' if reasons else 'comparable',
            'reasons':reasons,'common_price_dates':len(merged),
            'reference_rows':len(reference),'candidate_rows':len(candidate),
            'price_mismatch_dates':int(mismatch.sum()),
            'label_vintage':reference_meta.get('label_vintage','unknown'),
            'performance_claim':'None: label agreement does not establish profitability or superiority.'}
    if reasons: return result
    valid=merged.dropna(subset=['temperature_candidate','temperature_reference']).copy()
    result['paired_label_dates']=len(valid)
    result['coverage_of_reference_rows']=len(valid)/len(reference) if len(reference) else None
    if valid.empty:
        result['status']='insufficient_labels'; return result
    a=valid.temperature_candidate.map(ORDER); b=valid.temperature_reference.map(ORDER)
    result['exact_agreement']=float((a==b).mean())
    result['within_one_band']=float(((a-b).abs()<=1).mean())
    result['mean_absolute_band_difference']=float((a-b).abs().mean())
    result['confusion_reference_rows_candidate_columns']=pd.crosstab(
        valid.temperature_reference,valid.temperature_candidate).reindex(index=ORDER,columns=ORDER,fill_value=0).to_dict(orient='index')
    result['interpretation']=('Contemporaneous record comparison' if result['label_vintage']=='point_in_time'
                              else 'Retrospective/unknown label vintage; repainting and historical availability not verified')
    result['event_timing']='Not measured: requires a complete common trading calendar and explicit right-side event definitions.'
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('candidate'); p.add_argument('reference')
    p.add_argument('candidate_manifest'); p.add_argument('reference_manifest')
    p.add_argument('--output',required=True)
    a=p.parse_args()
    result=compare(pd.read_csv(a.candidate),pd.read_csv(a.reference),
                   json.loads(Path(a.candidate_manifest).read_text()),json.loads(Path(a.reference_manifest).read_text()))
    Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
    print(result['status'])

if __name__=='__main__': main()
