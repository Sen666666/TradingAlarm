def stats(win,rs,h):
 good=[];cens=collections.Counter()
 for r in rs:
  z=labels[win,r['sid'],r['day'],r['receipt']][str(h)]
  if z['valid']:good.append((r,z))
  else:cens[z['reason']]+=1
 result=dict(events=len(rs),unique_stocks=len({r['sid'] for r in rs}),candidate_dates=len({r['day'] for r in rs}),labelled_events=len(good),labelled_dates=len({r['day'] for r,z in good}),censored=dict(cens))
 if not good:return dict(result,event_mean_pct=None,event_median_pct=None,positive_fraction=None,mean_positive_pct=None,mean_negative_pct=None,MAE_mean_pct=None,MFE_mean_pct=None,right_tail_fraction=None,date_equal_mean_pct=None,daily={})
 a=np.array([z['return_pct'] for r,z in good]);daily=collections.defaultdict(list)
 for r,z in good:daily[r['day']].append(z)
 dm={d:dict(mean_pct=float(np.mean([z['return_pct'] for z in zs])),positive_fraction=float(np.mean([z['return_pct']>0 for z in zs])),right_tail_fraction=float(np.mean([z['right_tail_MFE30'] for z in zs])),events=len(zs)) for d,zs in daily.items()}
 return dict(result,event_mean_pct=float(a.mean()),event_median_pct=float(np.median(a)),positive_fraction=float(np.mean(a>0)),mean_positive_pct=float(a[a>0].mean()) if (a>0).any() else None,mean_negative_pct=float(a[a<0].mean()) if (a<0).any() else None,MAE_mean_pct=float(np.mean([z['MAE_pct'] for r,z in good])),MFE_mean_pct=float(np.mean([z['MFE_pct'] for r,z in good])),right_tail_fraction=float(np.mean([z['right_tail_MFE30'] for r,z in good])),date_equal_mean_pct=float(np.mean([z['mean_pct'] for z in dm.values()])),date_equal_positive_fraction=float(np.mean([z['positive_fraction'] for z in dm.values()])),date_equal_right_tail_fraction=float(np.mean([z['right_tail_fraction'] for z in dm.values()])),mean_calendar_days=float(np.mean([z['calendar_days'] for r,z in good])),daily=dm)
