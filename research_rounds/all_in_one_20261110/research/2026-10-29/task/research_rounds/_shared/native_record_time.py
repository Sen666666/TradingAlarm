"""Report-only event time, reusing audited native-identity extraction.

No recursive timestamp search. Recognize outer at/day or the native fill
receipt schema; unsupported records fail. Canonicalization may serialize a
real FillReceipt, but never chooses which timestamp field to read.
"""
from pathlib import Path
import ast, hashlib

SOURCE=Path(__file__).resolve().parents[1]/'migration-admission-native-readiness-20261101/check_identity.py'
SOURCE_SHA256=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
assert SOURCE_SHA256=='87d5a7eed423a7e003576eab1f1a58ec06a57b23774a233f8807ad49ab006f34', 'audited event-time source drift'
tree=ast.parse(SOURCE.read_text())
function=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='event_day')
env={}
exec(compile(ast.Module(body=[function],type_ignores=[]),str(SOURCE)+'::audited_event_day','exec'),env)
_audited_event_day=env['event_day']

def event_day(record, *, canonicalize=lambda value:value):
    assert isinstance(record,dict),'unsupported native record timestamp schema: non-record'
    value=record.get('at') or record.get('day')
    canonical=canonicalize(record)
    if value is None:
        receipt=canonical.get('receipt')
        required={'at','security_id','side','shares','gross_cny','fees_cny'}
        assert record.get('kind')=='fill' and isinstance(receipt,dict) and required<=receipt.keys(), \
            'unsupported native record timestamp schema: expected native fill receipt'
    return _audited_event_day(canonical)
