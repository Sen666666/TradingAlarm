"""Reuse final L0 without ADD; only calendar interval changes."""
from pathlib import Path
import importlib.util,sys,inspect
O=Path(__file__).resolve().parent;W=O.parent
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
C=load('frozen_current_l0_final',W/'lr1-cp1-add-preflight-20261031/adapter.py')
RR,BP,LR,N,E,R,D=C.RR,C.BP,C.LR,C.N,C.E,C.R,C.D
save,read,sha,dump=C.save,C.read,C.sha,C.dump
source=inspect.getsource(BP.Pilot.run)
assert source.count('2023-12-29T15:10:00+08:00')==1
source=source.replace('2023-12-29T15:10:00+08:00','2018-12-28T15:10:00+08:00')
env=dict(BP.__dict__);exec(source.strip(),env);run_interval=env['run']
class Pilot(C.Pilot):
 run=run_interval
