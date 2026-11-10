"""Inspect actual saved CA dates against original raw/factor observations; no account."""
from pathlib import Path
from decimal import Decimal as D
import importlib.util,argparse,json,gzip
s=importlib.util.spec_from_file_location('saved_reader',Path(__file__).with_name('audit_saved_native.py'));R=importlib.util.module_from_spec(s);s.loader.exec_module(R)
a=argparse.ArgumentParser();a.add_argument('run',type=Path);a.add_argument('--out',type=Path,required=True);a=a.parse_args();a.out.mkdir(parents=True,exist_ok=False)
proof=[];fractions=[]
for arm in ['B','G10','G20','G40','NR20']:
 b=R.book(a.run/'pair'/f'{arm}.json.gz')
 for ix,e in enumerate(b['audit']):
  if e['kind']not in ('split','split_fraction_floor_proxy'):continue
  p=R.prefix(b,ix);sid=e['sid'];ratio=R.n(e['ratio']);day=R.pd.Timestamp(str(e['at'])[:10]);ids=[lid for lid,q in p['q'].items()if q and next(t['security_id']for t in b['trades']if t.get('layer')==lid)==sid]
  per=[dict(layer=lid,old_qty=p['q'][lid],exact_new_qty=str(D(p['q'][lid])*ratio),before_basis=str(p['basis'][lid]))for lid in ids]
  q=R.prefix(b,ix+1)
  for r in per:
   r['native_rule_new_qty']=q['q'][r['layer']];r['after_basis']=str(q['basis'][r['layer']]);r['after_entry']=str(q['entry'][r['layer']])
   if D(r['exact_new_qty'])!=int(D(r['exact_new_qty'])):fractions.append(dict(arm=arm,sid=sid,at=e['at'],**r))
  raw=R.raw(sid);exact=day in raw.index
  observed=bool(raw.loc[day,'observed_bar'])and not bool(raw.loc[day,'synthetic_event_bar']) if exact else False
  R.factor(sid,e['at']);f=R.factcache[sid];fact_exact=day in f.index
  proof.append(dict(arm=arm,sid=sid,at=e['at'],kind=e['kind'],ratio=str(ratio),raw_exact_current_date=exact,raw_observed_current_date=observed,factor_exact_current_date=fact_exact,raw_OPEN=str(raw.loc[day,'raw_open'])if exact else None,factor=str(R.factor(sid,e['at'])),layer_allocation=per))
x=dict(status='ACTUAL_CA_UNIT_DATE_INSPECTION',events=len(proof),actual_split_events=proof,noninteger_within_layer_before_native_distribution=fractions,all_events_have_current_observed_raw_and_current_factor_row=all(r['raw_observed_current_date']and r['factor_exact_current_date']for r in proof),limits='Checks original observed units/dates plus authoritative native allocation and admission basis convention; does not certify external corporate-action entitlement economics or exchange fills.',source_sha256=R.SRC,checker_sha256=R.sha(__file__))
(a.out/'AUDIT.json').write_text(json.dumps(x,indent=2)+'\n');print(json.dumps({k:v for k,v in x.items()if k not in ('actual_split_events','source_sha256')}))
