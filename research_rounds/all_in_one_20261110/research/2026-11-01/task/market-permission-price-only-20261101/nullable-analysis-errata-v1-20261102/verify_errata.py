"""Verify corrected market-only artifacts against frozen full-domain sources."""
from pathlib import Path
from collections import Counter
import ast,hashlib,json,math
import pandas as pd
O=Path(__file__).resolve().parent;B=O.parent;W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 tests=[]
 def check(name,ok,detail=None):
  tests.append(dict(check=name,passed=bool(ok),detail=detail));assert ok,(name,detail)
 src=read(O/'SOURCE_SHA256.json');ps=read(O/'PUBLISH_SOURCE_SHA256.json');old=read(O/'OLD_FROZEN_SNAPSHOT.json');f=read(O/'FREEZE.json')
 check('all calculation source files unchanged',all(sha(p)==h for p,h in src.items()),len(src))
 check('all report/map source files unchanged',all(sha(p)==h for p,h in ps.items()),len(ps))
 check('all old drafts/outputs and artifact manifests retained',all(sha(p)==h for g in old.values() for p,h in g.items()),{k:len(v) for k,v in old.items()})
 check('frozen helper source/protocol/calculation exact',sha(O/'PROTOCOL.txt')==f['protocol_sha256'] and sha(O/'nullable_analysis.py')==f['normalizer_sha256'] and sha(O/'rebuild_market_views.py')==f['analysis_sha256'])
 sr=read(O/'SYNTHETIC_RESULTS.json');stderr=(O/'TEST_STDERR.txt').read_text()
 check('16 nullable/unknown guard tests passed',sr['passed'] and sr['tests']==16 and 'Ran 16 tests' in stderr and '\nOK\n' in stderr and sha(O/'TEST_STDERR.txt')==sr['stderr_sha256'])
 changed=read(O/'STATE_CHANGES.json');sc=read(O/'NORMALIZED_SCOPE_STATES.json')
 expected={('2026-04-30','URFI881123'),('2026-04-30','URFI881267'),('2026-05-07','URFI881123'),('2026-05-07','URFI881162'),('2026-05-07','URFI881267')}
 check('exact five state observations across three industries', {(r['day'],r['sector']) for r in changed}==expected and len(changed)==5)
 check('all changed fields are absent NaN and ACTIVE',all(r['pending_kind']=='ABSENT' and r['pending_original_repr']=='nan' and r['mode']=='ACTIVE' and r['legacy_support'] is False and r['support'] is True for r in changed))
 check('91 scope records per date including unchanged global',all(len(v)==91 and v['G']['mode']=='ENDED' and not v['G']['support'] and not v['G']['permit'] for v in sc.values()))
 e=pd.read_parquet(B/'industry-advance-gate-coverage-readonly-v1/STOCK_CANONICAL_EVENTS.parquet');rankchanges=read(O/'ALL_STOCK_RANK_CHANGES.json');summary=read(O/'CORRECTED_MARKET_SUMMARY.json')
 for day,total,raw in [('2026-04-30',14,129),('2026-05-07',62,218)]:
  disp=read(O/'static'/(day+'-ALL1709_DISPOSITIONS.json'));br=read(O/'static'/(day+'-ALL_SECTOR_FRESH_COMPETITION.json'));cr=read(O/'C-market-2026'/(day+'-STOCK_ORDER.json'));ir=read(O/'C-market-2026'/(day+'-INDUSTRIES.json'));secs=read(O/'static'/(day+'-SECTOR_OPPORTUNITY.json'))
  check(day+' all1709 identities/canonical completeness',len(disp)==1709 and len({x['sid'] for x in disp})==1709 and sum(x['canonical'] for x in disp)==raw)
  expected_e=e[e.day.eq(day)&e.F1_MATURE]
  check(day+' corrected candidates exactly equal existing complete-domain qualification',len(br)==total and {x['sid'] for x in br}==set(expected_e.sid)=={x['sid'] for x in cr})
  check(day+' canonical receipt IDs exact', {(r['sid'],r['details']['fresh_receipt_id']) for r in br}==set(zip(expected_e.sid,expected_e.receipt)))
  check(day+' all90 sectors retain zero/unknown nodes',len(ir)==len(secs)==90 and len({r['sector'] for r in ir})==90)
  check(day+' all included protection factor and qualification guards passed',all(r['details']['input_guard']['eligible'] and r['details']['stock_Q'] is True and r['details']['input_guard']['raw_floor']>0 for r in br))
  check(day+' positive close/protection/minimum inputs remain known',all(float(r['details']['close_buy_proxy'])>float(r['details']['fresh_raw_floor'])>0 and r['details']['minimum_quantity']>0 and float(r['details']['minimum_fee'])>0 for r in br))
  check(day+' complete B/C ranks unique and consecutive',sorted(r['competition_rank'] for r in br)==list(range(1,total+1)) and sorted(r['C_market_only_rank'] for r in cr)==list(range(1,total+1)))
  check(day+' original C industry-first then B order unchanged',[(r['industry_H1_rank'],r['original_B_rank']) for r in cr]==sorted((r['industry_H1_rank'],r['original_B_rank']) for r in cr))
  check(day+' full90 industry H1 ranks preserve descending rounded score and code tie',[(r['industry_H1_rank'],r['sector']) for r in ir]==[(j+1,r['sector']) for j,r in enumerate(sorted(ir,key=lambda r:(-round(r['industry_H1'],12),r['sector'])))])
  check(day+' sector and stock counts reconcile',sum(r['fresh_names'] for r in secs.values())==total and sum(r['frozen_market_expansion_list_count'] for r in ir)==total)
  check(day+' rank-change map complete',len([r for r in rankchanges if r['day']==day])==total)
 apr=summary['2026-04-30'];may=summary['2026-05-07']
 check('Apr30 C1..6 strict energy metals and C7..10 chemicals',all(r['sector']=='URFI881267' for r in apr['C_all'][:6]) and all(r['sector']=='URFI881172' for r in apr['C_all'][6:10]))
 check('Apr30 no advance accompanies any of14',apr['same_day_advance_fresh']==0)
 check('May7 Liyuan B19/C31 and semiconductor first B6/C32',any(r['sid']=='300184.SZ' and r['original_B_rank']==19 and r['C_market_only_rank']==31 for r in may['C_all']) and may['first_strict_semiconductor_B']==6 and may['first_strict_semiconductor_C']==32)
 check('May7 strict semiconductor remains21 and Btop20 now5',may['strict_semiconductor_count']==21 and may['strict_semiconductor_B_top20']==5)
 check('May7 true PVR NA preserves original slot, B7/C24',any(r['sid']=='920045.BJ' and r['PVR'] is None and r['PVR_ready'] is False and r['original_B_rank']==7 and r['C_market_only_rank']==24 for r in may['C_all']))
 # Isolate only the frozen pure priority function, with original NA/tie controls.
 path=W/'pvr-slot1-native-readiness-20261101/native_rank.py';tree=ast.parse(path.read_text());fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='priority_plan');ns={'math':math}
 exec(compile(ast.Module(body=[fn],type_ignores=[]),str(path)+'::rank_only_test','exec'),ns);priority=ns['priority_plan']
 _,log=priority([dict(sid=s,rank=h,role='mobile') for s,h in [('a',10),('b',77),('c',108)]],lambda s,d:{'a':5.,'b':None,'c':8.}[s],'fixed-close');order=sorted(log,key=lambda r:r['priority_rank'])
 check('original PVR NA control retains slot77', [r['sid'] for r in order]==['c','b','a'] and order[1]['priority_rank']==77)
 _,log=priority([dict(sid=s,rank=h,role='mobile') for s,h in [('a',10),('b',77)]],lambda s,d:{'a':1.0000000000001,'b':1.0000000000002}[s],'fixed-close')
 check('original PVR 12decimal tie control unchanged',[r['sid'] for r in sorted(log,key=lambda r:r['priority_rank'])]==['a','b'])
 market=read(O/'attribution/MAY7_ALL90_MARKET_DIRECTIONS.json');ms=read(O/'attribution/MAY7_SUMMARY.json')
 check('May7 all90 direction table and counts conserved',len(market)==90 and sum(r['frozen_expansion_list_count'] for r in market)==62 and sum(r['frozen_expansion_list_count'] for r in market if r['price_advance_today'])==55 and ms['without_advance']==7)
 check('May7 exact advance decomposition',ms['with_advance_industries']=={'半导体':21,'其他电子':1,'消费电子':10,'电子化学品':9,'元件':14} and ms['without_advance_industries']=={'通信设备':6,'电池':1})
 oldmarket=read(W/'g-s-B-C-native-advance-attribution-readonly-20261102/MAY7_MARKET_DIRECTIONS.json');mb={r['sector']:r for r in market};eq=True
 for r in oldmarket:
  for k in ['market_context_started','context_first_advance','last_current_context_advance','current_context_advance_count','events','price_advance_today','permit','support','mature','canonical_CP1_Q']:
   eq &= r[k]==mb[r['sector']][k]
 check('May7 source event/context attribution fields unchanged; only opportunity list corrected',eq)
 oldsummary=read(B/'g-s-static-capital-competition-v1/SUMMARY.json');newsummary=read(O/'static/SUMMARY.json')
 check('Jan6/Jul3 static account facts and old posthoc preserved byte-value exact',oldsummary['account_cases']==newsummary['account_cases'] and oldsummary['posthoc']==newsummary['posthoc'])
 preserved=read(O/'UNCHANGED_FINANCIAL_AND_ATTRIBUTION.json');check('original target B73/C62 and receiving28/groups15 preserved',preserved['original_B_files']==73 and preserved['original_C_files']==62 and preserved['receiving_rows']==28 and preserved['receiving_industry_policy_groups']==15 and preserved['all_receiving_same_day_advance_false'])
 check('F1 frozen core/contract unchanged',sha(B/'v2-frozen/signal_core.py')=='962275bd41b5c7bbc062a1191780a6b6a9c616f8d3097ea669b602eabbc9ac59' and sha(B/'v2-frozen/CONTRACT.md')=='c3914aed1896563253961ea40d6065614a115cef21e13a93e1e74ad71779c54a')
 extracts=read(O/'PURE_AST_EXTRACTION.json');selected={n for names in extracts.values() for n in names}
 check('pure AST whitelist excludes financial loader/account/solver',not selected.intersection({'Account','Runner','account_case','main','solve_B','solve_C','load','restore'}))
 imports=[]
 for file in ['nullable_analysis.py','rebuild_market_views.py','publish_errata.py','verify_errata.py']:
  t=ast.parse((O/file).read_text())
  imports += [a.name for n in ast.walk(t) if isinstance(n,ast.Import) for a in n.names]
  imports += [n.module or '' for n in ast.walk(t) if isinstance(n,ast.ImportFrom)]
 check('analysis scripts import no financial loader/native/selector modules',not any(any(z in m for z in ['loader','native_rank','selector','sector_account','gs_native']) for m in imports),imports)
 complete=read(O/'COMPLETION.json');check('all unauthorized execution counters zero',all(complete[k]==0 for k in ['financial_loader_calls','accounts','target_solves','financial_events','orders','indicator_runs','F1_runs','downloads']))
 mapping=read(O/'ORIGINAL_FILE_REPLACEMENTS.json')
 check('31 original-file replacements preserve original hashes',len(mapping)==31 and all(sha(r['original'])==r['original_sha256'] for r in mapping))
 check('all non-selfreferential replacement paths exist',all(Path(r['replacement']).exists() or Path(r['replacement']).name in ['VERIFICATION.json','PACKAGE_SHA256.json','REPORT.txt'] for r in mapping))
 out=dict(passed=all(t['passed'] for t in tests),checks=len(tests),tests=tests,scope='market analysis only, no financial execution')
 (O/'VERIFICATION.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print('ERRATA_VERIFIED',len(tests),'checks')
if __name__=='__main__':main()
