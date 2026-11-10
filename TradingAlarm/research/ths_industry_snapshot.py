"""Preserve observed THS industry membership caches, never backdate to ConfigVer."""
import configparser,datetime,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/ths-industry-snapshot'
SOURCE=Path('/Users/bytedance/Library/Containers/cn.com.10jqka.macstockPro/Data/Documents/BlockUpdate')
def decode(data):
 p=configparser.ConfigParser(interpolation=None,strict=True);p.optionxform=str;p.read_string(data.decode('gb18030'))
 names=dict(p['BLOCK_NAME_MAP_TABLE']);rows=[]
 for block,value in p['BLOCK_STOCK_CONTEXT'].items():
  for member in value.split(','):
   if not member.strip():continue
   m=re.fullmatch(r'(-?\d+):([A-Za-z0-9]+)',member.strip())
   if not m:raise ValueError('Unknown member encoding')
   rows.append(dict(block_code=block,block_name=names.get(block),raw_market=int(m[1]),raw_code=m[2]))
 return p['ConfigInfo'].get('ConfigVer'),names,rows

def main():
 OUT.mkdir(exist_ok=True);observed=datetime.datetime.now(datetime.timezone.utc).isoformat();reports=[];allrows=[]
 for name in ['block_industry.ini','block_hk_industry.ini']:
  b=(SOURCE/name).read_bytes();version,names,rows=decode(b);(OUT/name).write_bytes(b)
  for row in rows:row.update(source_file=name,source_version=version,observed_at=observed,effective_from=None,effective_to=None)
  allrows.extend(rows);reports.append(dict(file=name,sha256=hashlib.sha256(b).hexdigest(),version=version,block_names=len(names),blocks_with_members=len({r['block_code'] for r in rows}),membership_edges=len(rows),unique_raw_instruments=len({(r['raw_market'],r['raw_code']) for r in rows}),raw_market_ids=sorted({r['raw_market'] for r in rows})))
 (OUT/'memberships.json').write_text(json.dumps(allrows,ensure_ascii=False,indent=2)+'\n')
 review={'status':'observed_cache_memberships_recovered_not_historical','observed_at':observed,'files':reports,'interpretation':['BLOCK_STOCK_CONTEXT directly contains block-to-instrument membership entries; unlike stocklink identifier associations.','ConfigVer is file version, not a per-stock effective start; HK cache version predates observation by months, freshness unverified.','No publication or membership add/remove timestamps are present in this parsed schema.','Raw market namespaces retained; exchange normalization and hierarchical duplicate memberships need validation before trading use.','Industry taxonomy can be used as grouping metadata without adding fundamentals to the price-volume signal.'],'historical_backtest_allowed':False,'next':'Validate raw market identifiers, hierarchy and source freshness; preserve observation-time snapshots for forward research. Native history API remains unknown.'}
 (OUT/'review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n');print(json.dumps(reports,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
