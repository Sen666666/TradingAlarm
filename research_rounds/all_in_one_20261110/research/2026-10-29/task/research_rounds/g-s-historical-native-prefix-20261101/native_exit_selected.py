"""Two selection seams in the original native financial fill_exit body.

No replacement pricing, fee, FillReceipt, settlement or cash implementation.
Original source is retained and exact substitutions are published for audit.
"""
import inspect,textwrap
from imports_native import T,IO
ORIGINAL=textwrap.dedent(inspect.getsource(T.SectorAccount.fill_exit))
SEAMS=[
 ('available = sum(lot.shares for lot in pos.lots if lot.sellable_at <= window.at)',
  'available = self._selected_available(sid, window)'),
 ('if lot.sellable_at <= window.at:\n            sold = min(remaining, lot.shares); lot.shares -= sold; remaining -= sold',
  'if self._selected_eligible(lot, window):\n            sold = self._selected_take(lot, remaining, window); lot.shares -= sold; remaining -= sold')]
TRANSFORMED=ORIGINAL
for old,new in SEAMS:
 assert TRANSFORMED.count(old)==1,('native selection seam changed',old)
 TRANSFORMED=TRANSFORMED.replace(old,new)
undo=TRANSFORMED
for old,new in reversed(SEAMS):undo=undo.replace(new,old)
assert undo==ORIGINAL
env=dict(T.SectorAccount.fill_exit.__globals__)
exec(compile(TRANSFORMED,__file__+'::native-selected-lot-seams','exec'),env)
fill_exit_selected=env['fill_exit']
def manifest():
 return dict(original_qualified_name=T.SectorAccount.fill_exit.__qualname__,original_source_file=inspect.getsourcefile(T.SectorAccount.fill_exit),
  original_code_sha256=IO._code_fingerprint(T.SectorAccount.fill_exit.__code__),selected_code_sha256=IO._code_fingerprint(fill_exit_selected.__code__),
  substitutions=[dict(before=a,after=b) for a,b in SEAMS],financial_body_otherwise_exact=True)
