"""Parse preserved INI links losslessly; do not infer constituent membership."""
import json,re,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/ths-sector-cache-audit'
def parse_links(text):
 section=None;rows=[];unparsed=[]
 for number,line in enumerate(text.splitlines(),1):
  line=line.strip()
  if not line or line.startswith((';','#')):continue
  if line.startswith('[') and line.endswith(']'):section=line[1:-1];continue
  if section in ('ConfigInfo','LinkType'):continue
  if '=' not in line:unparsed.append(dict(line=number,section=section,raw=line));continue
  key,value=line.split('=',1)
  rows.append(dict(line=number,section=section,key=key,value=value))
 return rows,unparsed

def main():
 source=OUT/'stocklink-snapshot.ini';rows,unknown=parse_links(source.read_bytes().decode('gb18030'));names=json.loads((OUT/'block-names.json').read_text());links=[]
 for r in rows:
  if not r['section'].lower().endswith('_k'):continue
  for component in r['value'].split(','):
   match=re.fullmatch(r'(\d+):([A-Za-z0-9]+)',component)
   if not match:continue
   market,code=match.groups();links.append(dict(**r,target_market=market,block_code=code,candidate_name=names.get('BK'+code),name_match_basis='lexical BK+code only; target market compatibility not verified'))
 (OUT/'index-to-block-candidates.json').write_text(json.dumps(links,ensure_ascii=False,indent=2)+'\n')
 counts={}
 for r in links:
  counts.setdefault(r['section'],dict(links=0,names_matched=0));counts[r['section']]['links']+=1;counts[r['section']]['names_matched']+=r['candidate_name'] is not None
 review={'status':'link_inventory_not_membership','all_link_rows':len(rows),'unparsed_lines':unknown,'candidate_index_to_block_links':len(links),'lexical_name_matches':sum(r['candidate_name'] is not None for r in links),'sections':counts,'stock_to_industry_membership_established':False,'historical_membership_established':False,'limits':['Section/type letters are from the file; an index-to-block link is not a list of stocks in the block.','BK+code lexical name matches do not verify market248 versus255 namespaces.','Only a current snapshot observed; no start/end publication fields parsed.','Some links connect foreign securities or other instruments; do not label every section an A-share industry.'],'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'parser_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
 (OUT/'link-inventory-review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n');print({k:review[k] for k in ['all_link_rows','candidate_index_to_block_links','lexical_name_matches']});print(counts)
if __name__=='__main__':main()
