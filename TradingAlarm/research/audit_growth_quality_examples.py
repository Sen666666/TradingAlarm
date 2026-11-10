"""Issuer audit of growth arithmetic and nonrecurring profit; no return-based exclusions."""
import json,hashlib
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parent;DATA=ROOT/'data/candidate-fundamentals';OUT=ROOT/'results/fundamental-calendar-pilot'
def main():
 cases=[dict(symbol='000036.SZ',period='2016-06-30',pub='2016-08-31',file='000036-2016H1-original',current='432119794.01',prior='-15629827.41',adjusted_current='-18096855.29',adjusted_prior='-15283493.07',cache='000036.SZ-2016Q2.json',source='https://static.cninfo.com.cn/finalpage/2016-08-31/1202657667.PDF'),dict(symbol='000007.SZ',period='2025-03-31',pub='2025-04-30',file='000007-2025Q1-original',current='1772378.55',prior='640801.15',adjusted_current='950928.07',adjusted_prior='579980.30',cache='000007.SZ-2025Q1.json',source='https://disc.static.szse.cn/disc/disk03/finalpage/2025-04-30/b53dadd9-01a4-4125-a4b6-cc4fb74902d2.PDF')]
 result=[]
 for c in cases:
  t=(DATA/(c['file']+'.txt')).read_text()
  for k in ['current','prior','adjusted_current','adjusted_prior']:assert format(Decimal(c[k]),',.2f') in t
  row=json.loads((DATA/c['cache']).read_text())['rows'][0];assert row['pubDate']==c['pub'] and row['statDate']==c['period']
  now=Decimal(c['current']);prior=Decimal(c['prior']);adjusted=Decimal(c['adjusted_current']);adjusted_prior=Decimal(c['adjusted_prior']);growth=(now-prior)/abs(prior);adjusted_growth=(adjusted-adjusted_prior)/abs(adjusted_prior)
  assert abs(growth-Decimal(row['YOYPNI']))<Decimal('.000001')
  result.append(dict(**c,calculated_vendor_growth=str(growth),vendor_growth=row['YOYPNI'],adjusted_growth=str(adjusted_growth),current_nonrecurring_share=str((now-adjusted)/now),negative_comparison_base=prior<0,sha256=hashlib.sha256((DATA/(c['file']+'.pdf')).read_bytes()).hexdigest(),excluded_from_strategy=False))
 report=dict(status='Two field/definition examples,not complete data certification',cases=result,conclusion='Positive normalizedprofit growth doesnot implypositive recurringprofit or recurringgrowth. Keepfrozenbookprofit screen; do not posthoc removeexamples. Need separatelyverified recurringprofit data forqualityhypothesis.')
 (OUT/'growth-quality-examples.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
