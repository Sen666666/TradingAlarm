import os
from dataclasses import replace
from run_first10 import first10_specs as original

def first10_specs():
 modes=os.environ.get('IX_ENTRY_MODES','IX,W23,W2H,C3').split(',');stresses=os.environ.get('IX_ENTRY_STRESSES','base,cost2,delay1').split(',')
 assert set(modes)<=set(['IX','W23','W2H','C3','E0'])
 return tuple(replace(s,account_id=mode+'__'+s.account_id) for mode in modes for s in original() if s.stress.name in stresses)
