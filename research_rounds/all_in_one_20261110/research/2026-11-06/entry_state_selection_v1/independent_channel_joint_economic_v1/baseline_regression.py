"""G1 only: immutable original AB consumers, PRICE disabled, strict baseline replay.
Never imports or executes old run.py/report.py entry points. No broker interface.
"""
from pathlib import Path
import argparse, ast, csv, hashlib, importlib.util, io, json, math, re, sys
from decimal import Decimal
ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent / 'm3_stock_birth_during_sector_v1'
PROTOCOL_SHA = '94965590a1d5ba5fd28e88a6cf6c09188f747663590d2ffa0e3f7858e2265687'
CONFIG = {
 '2022': ('relative_priority_equity_run_2022_v1', 'dynamic', '77a5d6345a7f35cbfaffedc08320512140adc2cd853fc8fef560de6a1a1a303c', '00b841b1da11e0f7e0f44856bf9e699dce709a091ed72b94f8482e4e2cd8d518'),
 '2024': ('cash_equity_baseline_2024_v1', 'economic', '3c4fc71504bf1d6aa534387ede86008828e7d21a03b4a89a74d364c1a97a5c09', '74315e1d9e78605aca46abe58779a2339ad444ea2a8cd19c407b3d7b68cd7ce0'),
}
TABLES = ['ROUNDS','ACTIONS','DECISIONS','RANKING_AUDIT','END_STATES','REGISTRATIONS','CLAIM_LEDGER','PROFIT_GATES']
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text())
def save(p, value):
 with Path(p).open('x') as f: json.dump(value, f, indent=2, ensure_ascii=False, default=str); f.write('\n')
def arm_rows(rows):
 return [r for r in rows if r.get('arm') == 'A_UNION_B' or ('arm' not in r and '|A_UNION_B|' in r.get('round_id',r.get('owner_round_id','')))]
def csv_rows(path):
 with path.open(newline='') as f:
  r=csv.DictReader(f); return r.fieldnames,list(r)
def canonical_hash(rows):
 return hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def exact_cell(a,b):
 # Empty CSV fields are the frozen NaN representation. Never coerce missing to 0.
 if a == '' or b == '': return a == b
 if a == b: return True
 # Decimal equality is exact: permits only lossless 1 versus 1.0 serialization.
 # No floating tolerance, rounding, date truncation or missing-value fill.
 try: return Decimal(a).is_finite() and Decimal(b).is_finite() and Decimal(a)==Decimal(b)
 except Exception: return False
def compare_csv(actual, expected, selected=True):
 ac,aa=csv_rows(actual); bc,bb=csv_rows(expected)
 if selected: bb=arm_rows(bb)
 assert ac==bc,(actual.name,'column order/schema',ac,bc)
 assert len(aa)==len(bb),(actual.name,'rows',len(aa),len(bb))
 for i,(a,b) in enumerate(zip(aa,bb)):
  for c in bc:
   assert (a[c]=='')==(b[c]==''),(actual.name,i,c,'NaN mask mismatch')
   assert exact_cell(a[c],b[c]),(actual.name,i,c,a[c],b[c])
 return dict(rows=len(aa),columns=len(ac),all_columns_exact=True,nan_mask_exact=True,row_order_exact=True,actual_file_sha256=sha(actual),reference_file_sha256=sha(expected),reference_filtered_sha256=canonical_hash(bb),actual_serialized_rows_sha256=canonical_hash(aa))
def load_engine(window):
 folder,_,engine_sha,_=CONFIG[window]; path=BASE/folder/'engine.py'
 assert sha(path)==engine_sha,'frozen original engine changed'
 # Reviewed top-level work loads facts, checks hashes and builds the finite rights
 # registry. No top-level consumer, dump, old runner or report execution exists.
 tree=ast.parse(path.read_text()); forbidden={'run_window','run_fixed','dump','entry_open','held_open','held_close'}
 for node in tree.body:
  if isinstance(node,(ast.FunctionDef,ast.ClassDef)): continue
  for call in ast.walk(node):
   if isinstance(call,ast.Call) and isinstance(call.func,ast.Name): assert call.func.id not in forbidden
 spec=importlib.util.spec_from_file_location('frozen_ab_'+window,path)
 s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
 assert not s.rounds and not s.actions and not s.claims,'import executed a consumer'
 return s

def run_price_off(window, *, price_enabled=False):
 """Only admissible adapter branch. Original methods and global O unchanged."""
 if price_enabled is not False: raise ValueError('G1 forbids PRICE economics')
 s=load_engine(window)
 s.reset(True)
 s.run_window('A_UNION_B')
 assert {x['arm'] for x in s.rounds}=={'A_UNION_B'}
 return s

def baseline_report(s,window,dest,output=None):
 if output is None: output=dest
 """AST-selected read-only original report calculation; no runner or write body."""
 folder,_,_,report_sha=CONFIG[window];path=BASE/folder/'report.py';txt=path.read_text()
 assert sha(path)==report_sha
 start=txt.index("closed='COMPLETE_CONDITIONAL_STOCK_ROUND'")
 # 2024 starts closed on a line after bridge read. Start exactly at assignment.
 end=txt.index('\ndef metric(') if window=='2024' else txt.index('\nmetrics=[]')
 segment=txt[start:end]
 if window=='2022':
  extra=next(n for n in ast.parse(txt).body if isinstance(n,ast.Assign) and ast.get_source_segment(txt,n).startswith("z['duration_bucket']"))
  segment+='\n'+ast.get_source_segment(txt,extra)+'\n'
 for node in ast.walk(ast.parse(segment)):
  if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute): assert node.func.attr not in {'to_csv','mkdir','write_text','run_window','run_fixed','save','dump'}
 ns=dict(s=s,pd=s.pd,np=s.np,D=s.D,Path=Path,re=re,math=math,
  z=s.pd.read_csv(dest/'ROUNDS.csv',float_precision='round_trip',low_memory=False),
  a=s.pd.read_csv(dest/'ACTIONS.csv',float_precision='round_trip',low_memory=False),
  d=s.pd.read_csv(dest/'DECISIONS.csv',float_precision='round_trip',low_memory=False),
  claims=read(dest/'CLAIMS.json'),bridges=read(dest/'BRIDGES.json'))
 exec(compile(segment,str(path)+':read_only_report_calculation','exec'),ns)
 ns['z'].to_csv(output/'CORE_AND_FULL_ROUNDS.csv',index=False)
 coverage=ns['cov'] if window=='2024' else ns['coverage']
 coverage.to_csv(output/'FINANCIAL_COVERAGE.csv',index=False)
 return hashlib.sha256(segment.encode()).hexdigest()

def main():
 p=argparse.ArgumentParser();p.add_argument('--window',required=True,choices=list(CONFIG));p.add_argument('--confirmed-protocol-sha256',required=True);p.add_argument('--verify-existing',action='store_true')
 args=p.parse_args();assert args.confirmed_protocol_sha256==PROTOCOL_SHA==sha(ROOT/'PROTOCOL_DRAFT.md')
 audit=read(ROOT/'INDEPENDENT_CONTRACT_AUDIT.json')
 assert audit['contract_specification_passed'] is True and audit['protocol_sha256']==PROTOCOL_SHA and audit['economic_run_permitted'] is False
 folder,sub,_,_=CONFIG[args.window];reference=BASE/folder/sub;dest=ROOT/('baseline_regression_'+args.window)
 assert dest.exists() if args.verify_existing else not dest.exists(),'never overwrite a regression'
 # Seal every original output before replay; do not ignore provenance files.
 oldpaths=[p for d in [reference,BASE/folder/'report'] for p in d.iterdir() if p.is_file()]
 before={str(p):sha(p) for p in oldpaths+[BASE/folder/'engine.py',BASE/folder/'run.py',BASE/folder/'report.py']}
 for name,h in read(reference/'OUTPUT_HASHES.json').items(): assert sha(reference/name)==h
 if args.verify_existing:
  started=read(ROOT/('BASELINE_REGRESSION_STARTED_'+args.window+'.json'))
  assert started['protocol_sha256']==PROTOCOL_SHA and started['price_enabled'] is False
  for path,h in started['old_files'].items(): assert sha(path)==h
  s=load_engine(args.window) # read-only import, absolutely no run_window
 else:
  save(ROOT/('BASELINE_REGRESSION_STARTED_'+args.window+'.json'),dict(window=args.window,price_enabled=False,protocol_sha256=PROTOCOL_SHA,audit_sha256=sha(ROOT/'INDEPENDENT_CONTRACT_AUDIT.json'),driver_sha256=sha(__file__),old_files=before))
  s=run_price_off(args.window,price_enabled=False)
  s.dump(dest)
 checks={name:compare_csv(dest/(name+'.csv'),reference/(name+'.csv')) for name in TABLES}
 for name in ['CLAIMS','BRIDGES','LEDGER_QA']:
  a=read(dest/(name+'.json'));b=arm_rows(read(reference/(name+'.json')))
  assert a==b,(name,'strict nested JSON mismatch')
  checks[name]=dict(rows=len(a),exact=True,actual_file_sha256=sha(dest/(name+'.json')),reference_file_sha256=sha(reference/(name+'.json')),filtered_sha256=canonical_hash(b))
 report_dest=dest
 if args.verify_existing:
  report_dest=dest/'postprocess_completion';report_dest.mkdir(exist_ok=False)
 report_segment_sha=baseline_report(s,args.window,dest,report_dest)
 checks['CORE_AND_FULL_ROUNDS']=compare_csv(report_dest/'CORE_AND_FULL_ROUNDS.csv',BASE/folder/'report/CORE_AND_FULL_ROUNDS.csv')
 # Coverage can lack arm. Filter by known original AB round IDs.
 ca,aa=csv_rows(report_dest/'FINANCIAL_COVERAGE.csv');cb,bb=csv_rows(BASE/folder/'report/FINANCIAL_COVERAGE.csv')
 ids={r['round_id'] for r in csv_rows(dest/'ROUNDS.csv')[1]};bb=[r for r in bb if r['round_id'] in ids]
 assert ca==cb and len(aa)==len(bb)
 for i,(a,b) in enumerate(zip(aa,bb)):
  for c in ca: assert exact_cell(a[c],b[c]),('FINANCIAL_COVERAGE',i,c,a[c],b[c])
 checks['FINANCIAL_COVERAGE']=dict(rows=len(aa),columns=len(ca),exact=True,actual_file_sha256=sha(report_dest/'FINANCIAL_COVERAGE.csv'),reference_file_sha256=sha(BASE/folder/'report/FINANCIAL_COVERAGE.csv'))
 original_sources=read(reference/'SOURCE_HASHES.json');current_sources=read(dest/'SOURCE_HASHES.json')
 for path,h in current_sources.items(): assert original_sources.get(path)==h and sha(path)==h,(path,'source mismatch')
 for path,h in before.items(): assert sha(path)==h,(path,'legacy output modified')
 z=s.pd.read_csv(dest/'ROUNDS.csv',float_precision='round_trip',low_memory=False)
 save(dest/'EXACT_REGRESSION_QA.json',dict(result='PASS_PRICE_OFF_EXACT',window=args.window,arm='A_UNION_B',price_enabled=False,new_price_economic_runs=0,real_orders=0,real_fills=0,real_ACKs=0,protocol_sha256=PROTOCOL_SHA,driver_sha256=sha(__file__),audit_sha256=sha(ROOT/'INDEPENDENT_CONTRACT_AUDIT.json'),original_engine_sha256=sha(BASE/folder/'engine.py'),original_report_calculation_sha256=report_segment_sha,checks=checks,status_counts=z.status.value_counts().to_dict(),original_source_entries=len(original_sources),current_source_entries=len(current_sources),unused_original_source_entries=len(set(original_sources)-set(current_sources)),source_hashes_verified=True,all_legacy_files_unchanged=True,adapter_semantics='Unmodified frozen engine; original reset(True), run_window(A_UNION_B), dump(new directory); PRICE branch rejected. Does not certify any future PRICE-on joint adapter.',comparison='Ordered original columns, exact NaN masks and numeric equality without tolerances; original full engine/report hashes pinned. Provenance hashes verified separately rather than comparing run-specific manifests.'))
 save(dest/'REGRESSION_OUTPUT_HASHES.json',{str(p.relative_to(dest)):sha(p) for p in dest.rglob('*') if p.is_file()})
 print('PASS_PRICE_OFF_EXACT',args.window,{k:v['rows'] for k,v in checks.items()},flush=True)
if __name__=='__main__': main()
