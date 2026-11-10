"""Own-state seed for the frozen benchmark body, not a new strategy engine."""
from pathlib import Path
from decimal import Decimal as D
import copy,difflib,hashlib,importlib.util,inspect,json,sys
O=Path(__file__).resolve().parent;P=O.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
frozen=json.loads((P/'RUN_FREEZE.json').read_text())
assert sha(P/'run_benchmarks.py')==frozen['sources'][str(P/'run_benchmarks.py')]
spec=importlib.util.spec_from_file_location('frozen_2022_2023_benchmark',P/'run_benchmarks.py')
BASE=importlib.util.module_from_spec(spec);sys.modules[spec.name]=BASE;spec.loader.exec_module(BASE)
ORIGINAL=inspect.getsource(BASE.simulate)
SUBSTITUTIONS=[
 ('def simulate(history,calendar,actions,policy):','def simulate(history,calendar,actions,policy,parent):'),
 ('cash=INITIAL;shares=0;lots=[];claims=[];pending=None;previous_on=False;rows=[];fills=[];orders=[];signals=[];orderid=0',
  "cash=parent['cash'];shares=parent['shares'];lots=copy.deepcopy(parent['lots']);claims=copy.deepcopy(parent['claims']);pending=copy.deepcopy(parent['pending']);previous_on=parent['previous_on'];rows=[];fills=[];orders=[];signals=[];orderid=parent['orderid']"),
 ('previous_cash=cash;previous_shares=0;previous_claim=D(0);previous_nav=INITIAL;globalpeak=INITIAL;cumulative_fee=D(0)',
  "previous_cash=cash;previous_shares=shares;previous_claim=sum((e['amount'] for e in claims),D(0));previous_nav=parent['NAV'];globalpeak=parent['global_peak'];cumulative_fee=parent['cumulative_fee']"),
 ("if day==dates[0]:pending=create('buy',day,nav)","if day=='2022-01-04':pending=create('buy',day,nav)")]
SOURCE=ORIGINAL
for old,new in SUBSTITUTIONS:
    assert SOURCE.count(old)==1;SOURCE=SOURCE.replace(old,new)
check=SOURCE
for old,new in reversed(SUBSTITUTIONS):check=check.replace(new,old)
assert check==ORIGINAL,'non-seed trading policy changes forbidden'
env=dict(BASE.__dict__);exec(compile(SOURCE,str(O/'derived_continuation_function.py.txt'),'exec'),env);simulate=env['simulate']
def write_sources():
    files={'derived_continuation_function.py.txt':SOURCE,'CONTINUATION_SOURCE_DIFF.patch':''.join(difflib.unified_diff(ORIGINAL.splitlines(True),SOURCE.splitlines(True),fromfile='frozen_2022_2023_simulate',tofile='own_state_continuation2024_simulate'))}
    for name,value in files.items():
        p=O/name
        if p.exists():assert p.read_text()==value
        else:p.write_text(value)
def restore_parent(name):
    original=json.loads((O/'PARENT_STATE.json').read_text())[name]
    assert original['cursor']=='2023-12-29' and original['origin']=='2022-01-04'
    p=copy.deepcopy(original)
    for k in ('cash','NAV','global_peak','cumulative_fee'):p[k]=D(p[k])
    p['claims']=p.pop('receivables')
    for x in p['claims']:x['amount']=D(x['amount'])
    if p['pending']:
        for k in ('cash_budget','cumulative_gross','fee_paid'):p['pending'][k]=D(p['pending'][k])
    assert p['shares']==sum(x['quantity'] for x in p['lots']) and p['cash']>=0 and p['global_peak']>=p['NAV']
    return p
