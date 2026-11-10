"""Target only reported boundary keys; never change or run a native account."""
from pathlib import Path
from fractions import Fraction as Q
import argparse,bisect,gzip,hashlib,importlib.util,json
import pandas as pd
import numpy as np

O=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('independent_actual_key_reader',O/'audit_actual_modifier.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('audit',type=Path);args=ap.parse_args()
    audit=json.loads(args.audit.read_text());run=Path(audit['run']);end=audit['fixed_end'];cases=[]
    wanted={(x['sid'],x['day'])for x in audit['classification_mismatches']if'differences'in x}
    manifest={x['symbol']:x for x in M.read(M.MANIFEST)}
    for sid,d in sorted(wanted):
        r=manifest[sid];fp=M.checked(r['refs']['facts'],r['output_sha256'][r['refs']['facts']])
        sp=next(Path(x)for x in r['source_sha256']if x.endswith('/signal.parquet'));M.checked(sp,r['source_sha256'][str(sp)])
        f=pd.read_parquet(fp,columns=['close','raw_close','factor','segment_id']).loc[:d]
        s=pd.read_parquet(sp,columns=['close','segment_id','price_eligible','observed_bar','synthetic_event_bar']).loc[:d]
        data=M.independent_features(f,s);i=f.index.get_loc(pd.Timestamp(d));start=i-int(data['run'][i])+1
        a=pd.Series(data['c'][start:i+1]);ma=a.rolling(60,min_periods=60).mean();upper=a.rolling(20,min_periods=20).mean()+2*a.rolling(20,min_periods=20).std(ddof=0)
        ema=a.ewm(span=10,adjust=False,min_periods=10).mean()
        pa=bool(a.iloc[-1]>=ma.iloc[-1]and ma.iloc[-1]>ma.iloc[-6])
        pb=bool(a.iloc[-1]>upper.iloc[-1]and a.iloc[-2]<=upper.iloc[-2]and ema.iloc[-1]>ema.iloc[-4])
        canonical,_=M.actual_at(data,d)
        dif=next(x['differences']for x in audit['classification_mismatches']if x['sid']==sid and x['day']==d and'differences'in x)
        logged={k:v['logged']for k,v in dif.items()if k in('A','B')}
        assert all(logged[k]==dict(A=pa,B=pb)[k]for k in logged),('logged flags not reproduced by frozen pandas arithmetic',sid,d)
        c=data['c'];delta=sum((Q.from_float(float(x))for x in c[i-4:i+1]),Q(0))-sum((Q.from_float(float(x))for x in c[i-64:i-59]),Q(0))
        cases.append(dict(sid=sid,day=d,physical_source_end=d,known_run_start=str(f.index[start].date()),
            logged_flags=logged,independent_original_pandas_physical_prefix_flags=dict(A=pa,B=pb),exact_card_flags={k:canonical[k]for k in('A','B')},
            exact_MA_entered5_minus_left5=str(delta),exact_MA_delta_float=float(delta),
            pandas_MA_slope5=float(ma.iloc[-1]-ma.iloc[-6]),numpy_MA_slope5=float(data['ma'][i]-data['ma'][i-5]),
            pandas_price_minus_upper=float(a.iloc[-1]-upper.iloc[-1]),pandas_previous_price_minus_upper=float(a.iloc[-2]-upper.iloc[-2]),
            numpy_price_minus_upper=float(c[i]-data['up'][i]),numpy_previous_price_minus_upper=float(c[i-1]-data['up'][i-1])))
    # Log actual (not counterfactual) funding responses to the affected m intents.
    changes={(x['account'],x['day'],x['sid'],x['role'])for x in audit['classification_mismatches']if'multiplier_logged'in x}
    rules=M.read(M.RULES);calendar=rules['calendars']['A'];follow={}
    for arm,d,sid,role in changes:
        close=pd.Timestamp(d+'T15:10:00+08:00').isoformat();i=bisect.bisect_right(calendar,close)
        follow[arm,calendar[i][:10],sid,role]=dict(account=arm,signal_day=d,open_day=calendar[i][:10],sid=sid,role=role,funding_rows=[])
    for row in M.rows(run/'pair/funding.jsonl.gz'):
        k=(row['account'],str(row.get('at',''))[:10],row.get('sid'),row.get('role'))
        if k in follow:follow[k]['funding_rows'].append(row)
    output=args.audit.parent/'BOUNDARY_METHOD_AND_ACTUAL_FUNDING_SCOPE.json';assert not output.exists()
    result=dict(passed_implementation_reproduction_only=True,formula_exact_classification_pass=False,
        reported_feature_key_differences=len(cases),all_logged_boundary_flags_reproduced_by_independent_pandas_on_actual_physical_source_prefix=True,
        actual_reserved_or_filled_orders_hit=len(audit['classification_differences_touching_actual_orders']),
        cases=cases,affected_intents_actual_funding=list(follow.values()),
        economic_scope='Zero existing affected fills does not prove counterfactual whole-account identity. A different cap can admit an originally blocked intent and alter later serial funding. No corrected account path was run.',
        action='Preserve frozen producer and original FAIL; do not use these numeric boundaries to replace strategy economic evaluation.',
        source_SHA256=M.SRC,audit_SHA256=hashlib.sha256(args.audit.read_bytes()).hexdigest(),checker_SHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(output=str(output),SHA256=hashlib.sha256(output.read_bytes()).hexdigest(),boundary_keys=len(cases),all_logged_reproduced=True,actual_order_hit=result['actual_reserved_or_filled_orders_hit']),indent=2))

if __name__=='__main__':main()
