from pathlib import Path
import importlib.util,sys
O=Path(__file__).resolve().parent;W=O.parent
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
w=load('rb1_current_original_setup',W/'entry-loss-budget-full-account-20261031/wire.py')
port=load('rb1_frozen_minimal_sizing',W/'rb1-act-port-preflight-20261031/sizing_adapter.py')
def setup(sector,root,enabled,cutoff=None):
 R,E,core,prep,mode=w.setup(sector,root,False,cutoff)
 R.Account=port.account_class(R.Account);Base=R.Runner
 class Runner(Base):
  def run_tech(self):
   for a in self.accounts.values():a.rb1_sizing=enabled
   return super().run_tech()
 R.Runner=Runner
 return R,E,core,prep,mode
