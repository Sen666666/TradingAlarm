"""Append only the newly approved cutoff, unchanged common month entry."""
import subprocess,sys
import month_runtime as M
def main():
 M.guard();starts={'2022':'2022-01-07','2025_26':'2025-07-04'}
 for window in ('2022','2025_26'):
  for mode in ('C10','C_BATCH20'):
   root=M.HERE/'runs'/(window+'-'+mode);progress=M.read(root/'PROGRESS.json')
   assert progress['phase']=='CLOSE' and progress['cursor'][:10]==starts[window],'unexpected already advanced cursor; no silent rerun'
   with (M.HERE/(window+'-'+mode+'-SHORT.out')).open('w') as so,(M.HERE/(window+'-'+mode+'-SHORT.err')).open('w') as se:
    result=subprocess.run([sys.executable,'-B',str(M.HERE/'run_month.py'),'--window',window,'--mode',mode,'--grant',str(M.HERE/'grants/002_short_window.json')],stdout=so,stderr=se)
   if result.returncode:raise RuntimeError('atomic stop; inspect '+str(root/'ERROR.json'))
   print('COMPLETED_SHORT',window,mode,flush=True)
if __name__=='__main__':main()
