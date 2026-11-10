def run_prepared(self,out,max_seconds,resume_after=None,end=None):
 # Original M.Pilot.run event construction/order. The only clock difference
 # is a strict skip of already completed checkpoint events on explicit resume.
 from datetime import datetime,time as dt
 end=end or J.END
 start=J.M.N.iso(J.START+'T15:10:00+08:00');finish=J.M.N.iso(end+'T15:10:00+08:00')
 cutoffs={x for x in self.market.cutoffs if start<=x<=finish};opens={x for x in self.market.sessions['A'] if start<=x<=finish}
 acts={datetime.combine(datetime.fromisoformat(d).date(),dt.min,J.M.N.TZ) for d in self.actions_by_date}
 events=sorted(cutoffs|opens|{x for x in acts if start<=x<=finish});assert finish in cutoffs
 J.M.E.risk_policy.RECOVERY=pd.read_csv(J.M.O/'recovery.csv',index_col=0,parse_dates=True).loc[:end]
 t=time.monotonic();last=resume_after
 for at in events:
  if resume_after is not None and at<=resume_after:continue
  if time.monotonic()-t>max_seconds:
   if last is not None:self.checkpoint(out,last)
   self.dump_joint(Path(out)/'partial');return False
  for a in self.accounts.values():a.settle_due(at)
  self._actions(at)
  for a in self.accounts.values():self._payments(a,at)
  if at in opens:
   for a in self.accounts.values():self.opening(a,at)
  if at in cutoffs:self.planning(at)
  last=at
  # Monthly data checkpoint, never a cash/position/ACT reset.
  if at in cutoffs and ((pd.Timestamp(at.date())+pd.offsets.BDay()).month!=at.month or str(at.date()) in {'2023-03-31','2023-06-30','2023-09-28','2023-12-29'}):self.checkpoint(out,last)
 self.run_seconds=time.monotonic()-t;self.checkpoint(out,last);self.dump_joint(Path(out)/'pair')
 save(Path(out)/'DONE.json',dict(completed=True,run_seconds=self.run_seconds,ending_NAV={k:str(a.current_nav) for k,a in self.accounts.items()}))
 return True
