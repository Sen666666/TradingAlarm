"""Strict publication-aware quarterly financial lookup; unknown vintages excluded."""
from datetime import date
from decimal import Decimal,InvalidOperation

def available_snapshot(rows,signal_date,field):
 """Latest reported period, latest verified version known strictly before signal date.

 Vintage confirmation must be field-specific. Date-only publication uses a full-day
 delay because intraday publication time is unknown. Later restatements never
 overwrite earlier snapshots. Ambiguous same-date versions fail closed.
 """
 dt=date.fromisoformat(str(signal_date)[:10]);eligible=[]
 for row in rows:
  stat=date.fromisoformat(row['statDate']);pub=date.fromisoformat(row['pubDate'])
  if pub<stat:raise ValueError('publication precedes financial period end')
  if field not in row.get('verified_original_fields',[]) or not row.get('evidence_url'):continue
  # The evidence may only establish availability later than the vendor date.
  known=date.fromisoformat(row['evidence_available_date']);available=max(pub,known)
  if available>=dt:continue
  if row.get(field) in ['',None]:continue
  try:value=Decimal(str(row[field]))
  except InvalidOperation:raise ValueError('invalid financial number')
  if not value.is_finite():raise ValueError('nonfinite financial number')
  eligible.append((stat,available,value,row))
 if not eligible:return None
 latest=max((stat,available) for stat,available,_,_ in eligible)
 same=[x for x in eligible if x[:2]==latest]
 if len({x[2] for x in same})>1:raise ValueError('ambiguous financial vintage')
 stat,available,value,row=same[0]
 return dict(statDate=str(stat),available_after=str(available),value=str(value),evidence_url=row['evidence_url'])
