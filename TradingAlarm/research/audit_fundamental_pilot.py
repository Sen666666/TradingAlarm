"""Field-level vintage evidence, never certify an entire vendor from one spot check."""
import json
from decimal import Decimal
from pathlib import Path
from fundamental_asof import available_snapshot
ROOT=Path(__file__).resolve().parent;DATA=ROOT/'data/fundamental-vintage-pilot';OUT=ROOT/'results/fundamental-vintage-pilot'
def main():
 OUT.mkdir(exist_ok=True);summary=[]
 for p in sorted(DATA.glob('*query*.json')):
  d=json.loads(p.read_text());assert d['error_code']=='0';assert len(d['rows'])==1
  r=d['rows'][0];assert r['code']==d['code'];assert r['pubDate']>r['statDate']
  summary.append(dict(file=p.name,code=r['code'],pubDate=r['pubDate'],statDate=r['statDate'],has_version_identifier=False,verified_fields=[]))
 row=json.loads((DATA/'sh.600518-2017Q4-query_growth_data.json').read_text())['rows'][0]
 current=Decimal('4100926148.57');prior=Decimal('3340403640.26');growth=current/prior-1
 assert abs(Decimal(row['YOYPNI'])-growth)<Decimal('.000001')
 source='https://static.cninfo.com.cn/finalpage/2018-04-26/1204793691.PDF'
 verified=dict(row,verified_original_fields=['YOYPNI'],evidence_url=source,evidence_available_date='2018-04-26')
 assert available_snapshot([verified],'2018-04-26','YOYPNI') is None
 assert available_snapshot([verified],'2018-04-27','YOYPNI') is not None
 (OUT/'verified-fields.json').write_text(json.dumps([verified],indent=2))
 report=dict(requests=len(summary),records=len(summary),stock_count=4,records_detail=summary,spotcheck=dict(symbol='600518.SH',period='2017-12-31',field='YOYPNI',issuer_current_attributable_profit=str(current),issuer_prior_attributable_profit=str(prior),calculated_growth=str(growth),vendor_growth=row['YOYPNI'],source=source,first_allowed_signal_date='2018-04-27'),limitations=['Only one field andonevintage verified,notcompletefundamentaldata','No revisionidentifier fromAPI;appendhistoricalfilings as separateversions','netProfit is consolidatedincome;YOYPNI is attributablegrowth;do not conflate','epsTTM isnot reportedannualbasicEPS;profitabilityROE definitions requireseparatechecks','Historicalfraud laterdiscovered cannotbe retroactivelyfiltered unless known atsignaldate','Growth isnot earningssurprise;notPEAD replication','No performance claim fromfourstocks'])
 (OUT/'audit.json').write_text(json.dumps(report,indent=2));print('8 APIrecords saved;1 field/vintage independently checked;date-only availability delayed')
if __name__=='__main__':main()
