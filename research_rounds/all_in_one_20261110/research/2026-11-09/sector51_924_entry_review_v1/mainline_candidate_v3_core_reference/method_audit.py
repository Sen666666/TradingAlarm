import engine as e
import inspect,ast,textwrap
names=['info_open','info_close','decorate','sell_quantity','attribute','order','exit_open','net','cpvalid','accrue','register_pay','economic_preflight','refresh_tickets','pause_ticket','reverify_gap','scan_restored_targets']
checks={n:getattr(e.Engine,n) is getattr(e.m2.Engine,n) for n in names};assert all(checks.values())
def norm(s):return ast.dump(ast.parse(textwrap.dedent(s)),include_attributes=False)
c=inspect.getsource(e.v1.Engine.close).replace('min(int(cap),self.quantity(a))','int(cap)');n=inspect.getsource(e.v1.Engine.noncash).replace("min(r['planned_q'],r['capacity'],self.quantity(a))","min(r['planned_q'],r['capacity'])")
assert norm(c)==norm(inspect.getsource(e.Engine.close));assert norm(n)==norm(inspect.getsource(e.Engine.noncash))
e.save(e.O/'METHOD_IDENTITY_QA.json',dict(result='PASS',unchanged_method_objects=checks,close_ast_only_change='remove progressive quantity ceiling',noncash_ast_only_change='remove progressive quantity ceiling',allocation_changes=['remove progressive ceiling','add reference cap and frozen close quantity/rank','reference-only retention keys','explicit UNKNOWN ticket pause'],new_methods=['classify_reference','plan_requests','reference_cap','plan_transfers','execute_transfers','demand'],state_changes=['reference','reference_log','capital_lots','reference_requests','_ref_spent'],engine_sha256=e.sha(e.O/'engine.py'),combined_not_single_factor=True))
print('METHOD_IDENTITY_PASS',len(checks))
