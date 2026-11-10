"""Physical-prefix seed and synthetic receipt consumption tests, no economic paths."""
import copy,json,traceback
from pathlib import Path
from decimal import Decimal as D
import pandas as pd
import numpy as np
import inputs as I
import conditional_engine as E
J=I.J

def crop(args,day):
 (b,m,f),rec,cp,states,ir=args;t=pd.Timestamp(day)
 # Replace original view behind ClockFacts and all raw market arrays, leaving only common calendar future times.
 b.series={k:copy.copy(v)for k,v in b.series.items()}
 for v in b.series.values():v.states=v.states.loc[:day]
 dd,cols,score=b._h1_cache;mask=dd<=t;b._h1_cache=(dd[mask],cols,score[mask].copy())
 f.original.f={k:v.loc[:day].copy()for k,v in f.original.f.items()};f.original.b=b;f.original.cache={};f.original.day=None
 m._raw_source={k:v.loc[:day].copy()for k,v in m._raw_source.items()};m.raw=m._raw_source;m.arr={}
 for sid,raw in m._raw_source.items():
  # Reconstruct the native arrays by taking the physical index prefix.
  old=args[0][1]._saved_arrays[sid];n=len(raw)
  m.arr[sid]={k:(v[v<n].copy()if k in ('good','positive')else v[:n].copy()if isinstance(v,np.ndarray)else v)for k,v in old.items()}
 m.actions={k:[e for e in vv if e['effective_date']<=day]for k,vv in m.actions.items()}
 return (b,m,f),{k:{d:v for d,v in rr.items()if d<=day}for k,rr in rec.items()},{k:v.loc[:day]for k,v in cp.items()},{k:[r for r in rr if r['day']<=day]for k,rr in states.items()},{k:v for k,v in ir.items()if v['confirmed_day']<=day}

def main():
 data=I.load();out=[]
 for c in data['cases']:
  args=I.single(data,c['sid']);r=E.Runner(*args,c,E.ARMS[0]);r.warm(data['calendar']);full=I.canon(E.seed_plan(r))
  args=I.single(data,c['sid']);args[0][1]._saved_arrays=args[0][1].arr;trunc=crop(args,c['signal_day']);q=E.Runner(*trunc,c,E.ARMS[0]);q.warm(data['calendar']);short=I.canon(E.seed_plan(q));assert full==short,('physical prefix differs',c['round_id'])
  out.append(dict(round_id=c['round_id'],physical_prefix=c['signal_day'],seed_state_exact=True))
 # Synthetic original budget evidence validity/consumption, no ledger/path.
 b=A=I.A.NoConfirmed60Budget(True);b.cash=1200000.;sector='S';stock='X';b.start(sector,'e',0);s=b.sectors[sector];s.active=True;s.attempt='a';s.started=1;s.level=0
 tok=J.V.Evidence('cp1',sector,'stock_cp1','21',1,2,2,'e',stock,'a')
 result=b.request('one',stock,sector,100,10.,9.,tok,2,.05,probe_request=True,role='mobile',order_expiry_bar=2);assert result=='reserved'and 'cp1'in b.consumed
 b.cancel('one');b.cancel_ack('one');assert b.request('dup',stock,sector,100,10.,9.,tok,2,.05,probe_request=True,role='mobile',order_expiry_bar=2)=='no_fresh_stock_signal'
 # An unused old receipt cannot pass on a later bar even though broad validity allows a prefix.
 old=J.V.Evidence('unused_old',sector,'stock_cp1','21',1,2,2,'e',stock,'a');assert b.request('old_late',stock,sector,100,10.,9.,old,3,.05,probe_request=True,role='mobile',order_expiry_bar=3)=='no_fresh_stock_signal';assert 'unused_old'not in b.consumed
 fresh=J.V.Evidence('cp2',sector,'stock_cp1','21',2,3,3,'e',stock,'a');assert b.request('new',stock,sector,100,10.,9.,fresh,3,.05,probe_request=True,role='mobile',order_expiry_bar=3)=='reserved'
 b.cancel('new');b.cancel_ack('new');assert b.request('corelock',stock,sector,100,10.,9.,None,4,.05,probe_request=True,role='core',order_expiry_bar=4,core_epoch_locked=True)=='core_epoch_locked'
 # Seed-only role condition exact: its direct predicate is false on every later date.
 assert "str(at.date())==self.case['signal_day'] and role=='core'" in E.DIFFS['planning']['derived_source']
 I.save('PHYSICAL_PREFIX_AND_RECEIPTS.json',dict(passed=True,physical_seed_rows=out,source_fields_physically_cropped=['facts','CP','receipts','industry states','industry receipts','raw bars','raw arrays and masks','H1 score future rows','company actions'],synthetic_receipt_tests=['consumed CP rejects reuse','unused old CP cannot revive on later bar','new fresh CP can reserve','CORE epoch lock rejects','seed-only branch ends after seed'],economic_paths=0))
 print('PHYSICAL_PREFIX_AND_RECEIPTS_PASS')
if __name__=='__main__':
 try:main()
 except BaseException:
  (I.O/('PREFIX_FAILURE_'+str(__import__('time').time_ns())+'.txt')).write_text(traceback.format_exc());raise
