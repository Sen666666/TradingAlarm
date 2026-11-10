"""Unchanged native mark function over read-only source carriers.
No Market/Runner/Account is instantiated. Preserve stale ex-reference semantics.
"""
from pathlib import Path
from types import SimpleNamespace,MethodType
from datetime import datetime
import hashlib,inspect,json,sys

O=Path(__file__).resolve().parent
sys.path.insert(0,str(O/'funding'))
import entry_adapter as E
F=E.J.M.E.FastMarket.__mro__[1]
native=sys.modules[F.__module__]
sources={};views={};mark_cache={};derived_marks={}
def bind(p):p=Path(p);sources[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(p):return json.loads(bind(p).read_text())
records={r['series_id']:r for r in read(E.J.M.P/'manifest.json')['series']}
protocol=read(E.J.BP.C.OLD/'inputs-v2/economic-protocol.json')
rules=read(E.J.M.RR/'pvr-act-comparison-20261027/execution-rules-v2.json')
sessions={k:tuple(datetime.fromisoformat(t)for t in vs)for k,vs in rules['calendars'].items()}
for function in [F.latest_mark,F.source_available,F.rate,native.read_raw,native.read_actions,native.eligible_prices]:
 bind(inspect.getsourcefile(function))
bind(__file__)

def price(sid,day):
 key=(sid,day)
 if key in mark_cache:return mark_cache[key]
 if sid not in views:
  rec=records[sid];assert rec['currency']=='CNY'
  rawpath=native.checked_ref(rec['raw'],E.J.M.P);bind(rawpath)
  f=native.read_raw(rawpath,rec);f['valid_price']=f.index.isin(native.eligible_prices(f).index)
  f['observed_bar']=native.boolean_column(f,'observed_bar',True)
  events,_=native.read_actions(rec,E.J.M.P);bind(rec['adjustment']['actions']['path'])
  view=SimpleNamespace(raw={sid:f},bundle=SimpleNamespace(series={sid:SimpleNamespace(record=rec)}),
   lines={sid:SimpleNamespace(market='A')},sessions=sessions,actions={sid:events},protocol=protocol)
  view.source_available=MethodType(F.source_available,view);view.rate=MethodType(F.rate,view);views[sid]=view
 at=datetime.fromisoformat(day+'T15:10:00+08:00')
 mark=F.latest_mark(views[sid],sid,at);value=mark.cny_price(at);mark_cache[key]=value
 if ':derived_ex_reference:'in mark.source_id:
  derived_marks[sid+'|'+day]=dict(sid=sid,day=day,mark=str(value),known_at=str(mark.known_at),source_id=mark.source_id,
   valuation_reference_not_executable_quote=True)
 return value
