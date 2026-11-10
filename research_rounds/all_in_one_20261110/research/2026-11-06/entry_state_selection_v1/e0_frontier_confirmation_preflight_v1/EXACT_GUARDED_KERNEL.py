def guarded_events(bars, multiplier=1.5):
    """Pure event portion extracted from numeric.event_frame_numeric.

    Every retained scalar operation, local fsum, median window, branch and
    extreme update matches the source.  The source's active/floor/target and
    entered/exited calculations have never been executed in this function.
    An empty C/V-valid segment is a B5 extension: events remain unprepared.
    """
    raw = bars[["close", "volume"]]
    d = raw.loc[raw.gt(0).all(axis=1) & np.isfinite(raw).all(axis=1)]
    numeric_columns = [column for column in EVENT_COLUMNS if column not in EVENT_DATE_COLUMNS]
    blank = pd.DataFrame(np.nan, index=bars.index, columns=numeric_columns)
    blank["event"] = 0.0
    for column in EVENT_DATE_COLUMNS:
        blank[column] = pd.Series(pd.NA, index=bars.index, dtype="string")
    if d.empty:
        return blank[EVENT_COLUMNS], pd.Series(np.nan, index=bars.index)
    prices, volumes = d.close.to_numpy(), d.volume.to_numpy()
    returns = [math.nan] + [log_ratio(prices[t], prices[t - 1])
                           for t in range(1, len(d))]
    sigma = np.full(len(d), np.nan)
    baseline = d.volume.shift().rolling(21).median().to_numpy()
    for t in range(64, len(d)):
        sigma[t] = max(math.sqrt(math.fsum(x * x for x in returns[t - 63:t]) / 63), 1e-8)
    direction, ext = -1, None
    rows = []
    for t, date in enumerate(d.index):
        row = dict(confirmation=math.nan, leg_direction=math.nan,
                   developing_extreme=math.nan, confirmed_pivot=math.nan,
                   event=0.0, pivot_age=math.nan,
                   developing_extreme_price=math.nan, confirmed_pivot_price=math.nan,
                   confirmed_pivot_date=None, developing_extreme_date=None)
        if not math.isfinite(sigma[t] + baseline[t]):
            rows.append(row)
            continue
        if ext is None:
            ext = t
        extreme_order = compare(prices[t], prices[ext])
        if (direction == -1 and extreme_order < 0) or (direction == 1 and extreme_order > 0):
            ext = t
        if t > ext:
            activity = math.sqrt(
                (math.fsum(float(x) for x in volumes[ext + 1:t + 1]) / (t - ext))
                / baseline[ext]
            )
            activity = min(max(activity, 0.5), 2.0)
            confirmation = (-direction) * log_ratio(prices[t], prices[ext]) * activity / (multiplier * math.sqrt(5) * sigma[ext])
            row["confirmation"] = confirmation
            if compare(max(confirmation, 0.0), 1.0) >= 0 and ((direction == -1 and compare(prices[t], max(prices[ext:t])) > 0) or (direction == 1 and compare(prices[t], min(prices[ext:t])) < 0)):
                event = -direction
                pivot = float(prices[ext])
                row.update(event=float(event), confirmed_pivot=math.log(pivot),
                           confirmed_pivot_price=pivot, pivot_age=float(t - ext),
                           confirmed_pivot_date=str(d.index[ext].date()))
                direction, ext = event, t
        row.update(leg_direction=float(direction),
                   developing_extreme=math.log(float(prices[ext])),
                   developing_extreme_price=float(prices[ext]),
                   developing_extreme_date=str(d.index[ext].date()))
        rows.append(row)
    result = pd.DataFrame(rows, index=d.index).reindex(bars.index)
    result["event"] = result.event.fillna(0.0)
    for column in EVENT_DATE_COLUMNS:
        result[column] = result[column].astype("string")
    observations = pd.Series(np.arange(len(d), dtype=float), index=d.index).reindex(bars.index)
    return result[EVENT_COLUMNS], observations
