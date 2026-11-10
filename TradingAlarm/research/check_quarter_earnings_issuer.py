"""Independent issuer H1 subtraction versus directly disclosed Q3 profit."""
import hashlib,json
from pathlib import Path
from decimal import Decimal
from quarterly_earnings import quarter_growth
ROOT=Path(__file__).resolve().parent;DATA=ROOT/'data/candidate-fundamentals';OUT=ROOT/'results/candidate-fundamentals'
def main():
 base=dict(symbol='002541.SZ',currency='CNY',metric='attributable_net_profit',period_basis='year_to_date',verified=True,basis_id='002541-2019-original-H1-Q3-unrestated-comparatives')
 h1=dict(base,period_end='2019-06-30',current_ytd='169619647.87',comparative_ytd='161841970.33',available_date='2019-08-28',evidence_url='https://crm.htsc.com.cn/pdf_finchina/CNSESZ_STOCK/2019/2019-8/2019-08-28/5595834.pdf')
 q3=dict(base,period_end='2019-09-30',current_ytd='338063615.35',comparative_ytd='332789830.57',available_date='2019-10-22',evidence_url='https://static.cninfo.com.cn/finalpage/2019-10-22/1206997852.PDF')
 for name,values in [('002541-2019H1-original',['169,619,647.87','161,841,970.33']),('002541-2019Q3-original',['338,063,615.35','332,789,830.57','168,443,967.48','170,947,860.24'])]:
  t=(DATA/f'{name}.txt').read_text();assert all(v in t for v in values)
 result=quarter_growth(q3,h1,'2019-10-23');assert result['current_quarter']=='168443967.48';assert result['prior_quarter']=='170947860.24';assert abs(Decimal(result['yoy'])-Decimal('-.0146'))<Decimal('.00005');assert quarter_growth(q3,h1,'2019-10-22') is None
 record=dict(statements=[h1,q3],derived=result,direct_issuer_current='168443967.48',direct_issuer_comparative='170947860.24',direct_reported_yoy='-.0146',all_matched=True,files={name:hashlib.sha256((DATA/name).read_bytes()).hexdigest() for name in ['002541-2019H1-original.pdf','002541-2019Q3-original.pdf']},limitations=['Oneissuerexample,notfulluniverseverification','H1issuerPDFhostedbybrokerarchive;publicationdatefromdatedfilingrecord/path','Historicalaccountingbasis assessedfor thispair only;laterrevisions requireseparatebasischecks','Confirmedgrowth isnot earningssurprise or proof ofpredictivereturns'])
 (OUT/'quarter-reconstruction-check.json').write_text(json.dumps(record,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
