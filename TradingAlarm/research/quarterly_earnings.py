"""Derive standalone-quarter profits from compatible, publication-dated YTD statements."""
from datetime import date
from decimal import Decimal

def quarter_growth(current,previous,signal_date):
 """Each statement has current and prior-year comparative YTD attributable profit.

 Both rows must have verified field provenance and an explicitly checked shared
 accounting-basis identifier. A row unavailable at the signal date yields None.
 Nonpositive comparison-quarter profit returns no conventional percentage growth.
 """
 dt=date.fromisoformat(signal_date);end=date.fromisoformat(current['period_end']);q=(end.month-1)//3+1
 if (end.month,end.day) not in [(3,31),(6,30),(9,30),(12,31)]:raise ValueError('not fiscal calendar quarter end')
 required=[current] if q==1 else [current,previous]
 if any(r is None for r in required):return None
 for r in required:
  if not r.get('verified') or not r.get('evidence_url') or not r.get('basis_id'):return None
  available=date.fromisoformat(r['available_date'])
  if available<date.fromisoformat(r['period_end']):raise ValueError('publication before period end')
  if available>=dt:return None
  if r.get('metric')!='attributable_net_profit' or r.get('period_basis')!='year_to_date':raise ValueError('wrong earnings metric or flow basis')
 if q==1 and previous is not None:raise ValueError('Q1 must not subtract prior year annual profit')
 if q>1:
  pe=date.fromisoformat(previous['period_end'])
  if pe.year!=end.year or (pe.month,pe.day)!=[(3,31),(6,30),(9,30)][q-2]:raise ValueError('missing preceding quarter')
  for key in ['symbol','currency','basis_id','metric']:
   if current[key]!=previous[key]:raise ValueError('incompatible statements:'+key)
 def number(row,key):
  x=Decimal(row[key])
  if not x.is_finite():raise ValueError('nonfinite earnings')
  return x
 now=number(current,'current_ytd')-(number(previous,'current_ytd') if previous else 0)
 prior=number(current,'comparative_ytd')-(number(previous,'comparative_ytd') if previous else 0)
 return dict(symbol=current['symbol'],period_end=current['period_end'],current_quarter=str(now),prior_quarter=str(prior),yoy=str(now/prior-1) if prior>0 else None,comparison_status='positive_base' if prior>0 else 'nonpositive_base_requires_separate_feature',available_after=max(r['available_date'] for r in required),sources=[r['evidence_url'] for r in required])
