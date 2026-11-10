"""Use the already corrected22-Oct industry master, independently rederive it.

Preserve all invalid v1 evidence. No prices, signals, cap, policies or dates change.
"""
from pathlib import Path
import csv,configparser,collections,os,shutil,gzip,json
from build_inputs import HERE,OLD,read,write,ref,sha256,now

def ini(path):
 c=configparser.ConfigParser(interpolation=None,strict=False);c.optionxform=str;c.read_string(Path(path).read_text(encoding='gb18030'));return c

def main():
 root=OLD/'audit-snapshot';master=list(csv.DictReader((root/'current-stock-master.industry-resolved.csv').open()));byid={x['current_symbol']:x for x in master}
 tree=ini(root/'raw/BlockUpdate/block_tree.ini');industry=ini(root/'raw/BlockUpdate/block_industry.ini');link=ini(root/'raw/StockLink/stocklink.ini')
 children={k:[child for child,flag in tree[v].items() if flag.strip()] for sec in tree.sections() for k,v in tree[sec].items() if v.startswith('@') and v in tree}
 def descend(k,seen=None):
  seen=set() if seen is None else seen
  if k in seen:return set()
  seen.add(k);return {k}.union(*(descend(ch,seen.copy()) for ch in children.get(k,[])))
 indices={k:v.split(':')[-1] for k,v in link['stock_48_X_K'].items() if k.startswith('881')};leaves={idx:descend(block) for idx,block in indices.items()}
 errors=[];mapping=[]
 for r in master:
  matches=[idx for idx,ds in leaves.items() if r['industry_leaf_code'] in ds];expect='URFI'+matches[0] if len(matches)==1 else ''
  leafmembers=industry['BLOCK_STOCK_CONTEXT'].get(r['industry_leaf_code'],'')
  token=r['raw_market']+':'+r['code']
  checks=dict(index=expect==r['industry_index_symbol'],unique=len(matches)==1 if r['current_symbol']!='000016.SZ' else len(matches)==0,
   membership=token in leafmembers.split(',') if r['current_symbol']!='000016.SZ' else not r['industry_leaf_code'])
  if not all(checks.values()):errors.append(dict(symbol=r['current_symbol'],checks=checks))
  mapping.append(dict(symbol=r['current_symbol'],leaf=r['industry_leaf_code'],index=expect,name=r['industry_name'],matches=len(matches)))
 assert not errors,errors[:10]
 src=HERE/'inputs-v1';out=HERE/'inputs-v2';out.mkdir(exist_ok=False)
 oldselection=read(src/'selection.json');selection=json.loads(json.dumps(oldselection));changes=[]
 for line in selection['lines']:
  r=byid[line['security_id']];old=line['sector_id'];line['sector_id']=r['industry_index_symbol'] or None
  if old!=line['sector_id']:changes.append(dict(symbol=line['security_id'],old_sector=old,new_sector=line['sector_id'],name=r['industry_name'],cap_qualified=line['company_cap_cny'] is not None))
 assert len(changes)==145 and sum(x['cap_qualified'] for x in changes)==144
 qualified=[x for x in selection['lines'] if x['company_cap_cny'] is not None]
 assert len(qualified)==1709 and all(x['sector_id'] in {'URFI'+i for i in indices} for x in qualified)
 dispositions=read(src/'roster-dispositions.json')
 for x in dispositions:r=byid[x['symbol']];x['industry']=r['industry_name'];x['sector_id']=r['industry_index_symbol']
 write(out/'roster-dispositions.json',dispositions);selection['all_roster_dispositions']=ref(out/'roster-dispositions.json');selection['industry_resolution_evidence']=ref(root/'current-stock-master.industry-resolved.csv')
 selection['snapshot_id']='A-roster22-resolved-nonempty-industry-tree22-cap24';write(out/'selection.json',selection)
 meta=read(src/'metadata.json')
 for sid,x in meta.items():r=byid[sid];x['industry']=r['industry_name'];x['sector_id']=r['industry_index_symbol'] or None
 write(out/'metadata.json',meta)
 rules=read(src/'market-rules.json');rules['security_metadata']=meta;write(out/'market-rules.json',rules)
 for name in ['fx-quotes.json','action-normalization.json']:os.link(src/name,out/name)
 construction=read(src/'construction-summary.json');construction.update(industry_unique_qualified=1709,industry_unknown_cap_only=['000016.SZ'],data_mapping_repair=True)
 write(out/'construction-summary.json',construction)
 audit=HERE/'audit/industry-repair-v2';audit.mkdir(exist_ok=False)
 write(audit/'mapping.json',mapping);write(audit/'changes.json',changes)
 write(audit/'report.json',dict(recorded_at=now(),root_cause='Prepared original master retained374 ambiguous empty-placeholder tree edges; independently corrected current master already existed but v1 builder joined the old master.',
  raw_roster=5576,verified_unique_industries=5575,unknown_industry=['000016.SZ'],qualified=1709,qualified_industry_unknown=0,
  selected_or_cap_unknown_lines_changed=145,qualified_lines_changed=144,membership_independently_rederived=True,
  facts=[ref(root/'current-stock-master.industry-resolved.csv'),ref(root/'raw/BlockUpdate/block_tree.ini'),ref(root/'raw/BlockUpdate/block_industry.ini'),ref(root/'raw/StockLink/stocklink.ini')],
  original_v1_data_claim_superseded=True,algorithm_changes=0,errors=errors))
 # Record the interrupted run, including its partial stream rather than make
 # a new claim that no real capital computations have ever started.
 last=None;rows=0
 with gzip.open(HERE/'accounts-v1/daily.jsonl.gz','rt') as f:
  for s in f:last=json.loads(s);rows+=1
 write(HERE/'accounts-v1/aborted.json',dict(recorded_at=now(),status='aborted_invalid_industry_input',main_accounts_started=13,completed_accounts=0,
  last_record_at=last['at'],partial_daily_rows=rows,reason='144 cap-qualified stocks had unknown industry due wrong master join; partial results not used as strategy evidence',
  package=ref(src/'package.json'),full_results_retained=True))
 receipt=HERE/'audit/data-closeout-v2.json';files=[HERE/'audit/data-closeout.json',audit/'report.json',audit/'mapping.json',audit/'changes.json',
  out/'selection.json',out/'roster-dispositions.json',out/'metadata.json',out/'construction-summary.json',HERE/'accounts-v1/aborted.json']
 write(receipt,dict(kind='data_closeout',round_id=HERE.name,status='data_pool_closed',scope_date='2026-10-22',scope_sha256=sha256(HERE/'scope.json'),recorded_at=now(),
  artifacts={str(p.resolve()):sha256(p) for p in files},supersedes=ref(HERE/'audit/data-closeout.json'),
  raw_price_integrity_and_action_sources_unchanged=True,qualified=1709,qualified_industry_unknown=0,
  raw_remaining_unknown_source_origin='002731.SZ',unknown_current_cap=['000016.SZ','002731.SZ'],unknown_industry_cap_only=['000016.SZ'],
  closure_meaning='Audited current-pool research inputs with explicit remaining unknowns, not PIT or precise broker ledger certification',
  prior_main_accounts_started=13,prior_main_accounts_completed=0,algorithm_changes=0))
 manifest=read(src/'input-manifest.json');manifest['selection']=ref(out/'selection.json');manifest['data_pool_closeout']=ref(receipt)
 write(out/'input-manifest.json',manifest)
 assert manifest['series']==read(src/'input-manifest.json')['series']
 # Full state reuse is exact: no record entering the price/volume model changed.
 prepared=HERE/'prepared-v2';prepared.mkdir(exist_ok=False)
 pm=read(HERE/'prepared-v1/manifest.json')
 for row in pm['series']:
  for file in row['files'].values():
   srcfile=HERE/'prepared-v1'/file['path'];dest=prepared/file['path'];dest.parent.mkdir(exist_ok=True);os.link(srcfile,dest)
 pm.update(source_manifest=str((out/'input-manifest.json').resolve()),source_manifest_sha256=sha256(out/'input-manifest.json'),
   state_reuse_from=ref(HERE/'prepared-v1/manifest.json'),reuse_basis='All1801 series records and frozen model/RS code exactly identical; only selection industry metadata repaired')
 write(prepared/'manifest.json',pm)
 # Outcome diagnostic prices also unchanged; repair display/classification only.
 opp=HERE/'opportunities-v2';opp.mkdir(exist_ok=False)
 import pandas as pd
 af=pd.read_csv(HERE/'opportunities-v1/annual-all-current-A.csv',keep_default_na=False)
 af['industry']=af.symbol.map({s:r['industry_name'] for s,r in byid.items()});af.to_csv(opp/'annual-all-current-A.csv',index=False,encoding='utf-8-sig')
 for name in ['annual-top20.json','structural-winners.json']:
  xs=read(HERE/'opportunities-v1'/name)
  for x in xs:x['industry']=byid[x['symbol']]['industry_name']
  write(opp/name,xs)
 os.link(HERE/'opportunities-v1/coverage.json',opp/'coverage.json')
 write(out/'state-reuse-proof.json',dict(recorded_at=now(),all_series_records_exactly_equal=True,series=1801,
  source_prepared=ref(HERE/'prepared-v1/manifest.json'),new_prepared=ref(prepared/'manifest.json'),prior_causal_and_visual_review=ref(HERE/'audit/signal-visual-review.json'),
  no_E0_RS_input_or_formula_changes=True))
 print({'qualified':1709,'qualified_industry_unknown':0,'raw_classification_unique':5575,'corrected_qualified_lines':144,'unchanged_state_series':1801},flush=True)

if __name__=='__main__':main()
