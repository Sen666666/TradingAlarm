import os
from dataclasses import replace
from run_first10 import first10_specs as original
def first10_specs():
 modes=os.environ.get('ABCD_MODES','A,B,C,D').split(',');stresses=os.environ.get('ABCD_STRESSES','base,cost2,delay1').split(',')
 assert set(modes)<=set('ABCD')
 return tuple(replace(s,account_id=mode+'__'+s.account_id) for mode in modes for s in original() if s.variant=='S0' and s.stress.name in stresses)
