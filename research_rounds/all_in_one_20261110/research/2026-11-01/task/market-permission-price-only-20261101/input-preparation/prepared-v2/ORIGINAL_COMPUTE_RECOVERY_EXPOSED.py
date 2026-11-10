def compute_recovery(signals, roster):
    """Exact frozen market price clock and independently valid amount breadth."""
    returns = {}
    mom = {}
    for sid in roster.symbol:
        f = signals[sid]
        valid = f.price_eligible & f.observed_bar & ~f.synthetic_event_bar
        raw = f.loc[valid]
        rs = []
        ms = []
        for _, g in raw.groupby('segment_id', sort=False):
            r = np.log(g.close).diff()
            q = g.amount / g.amount.shift().rolling(21, min_periods=21).median()
            u = r * np.minimum(1, np.sqrt(q))
            m = u.ewm(span=21, adjust=False).mean()
            ready = np.arange(len(g)) >= 64
            rs.append(r.where(ready))
            m.iloc[:64] = np.nan
            ms.append(m)
        returns[sid] = pd.concat(rs).sort_index()
        mom[sid] = pd.concat(ms).sort_index()
    sector_r = []
    sector_b = []
    for sector, group in roster.groupby('sector_id'):
        sector_r.append(pd.concat({s: returns[s] for s in group.symbol}, axis=1).mean(axis=1))
        f = pd.concat({s: mom[s] for s in group.symbol}, axis=1)
        n = f.notna().sum(axis=1)
        sector_b.append((f.gt(0).sum(axis=1) / n).where(n >= 5))
    r = pd.concat(sector_r, axis=1).mean(axis=1)
    price = np.exp(r.fillna(0)).cumprod()
    b = pd.concat(sector_b, axis=1)
    breadth = b.mean(axis=1).where(b.notna().sum(axis=1) >= 8)
    z = pd.DataFrame(dict(market=price, prior_high63=price.shift().rolling(63, min_periods=63).max(), breadth=breadth))
    z['breakout'] = (z.market > z.prior_high63) & (z.market.diff() > 0) & (z.breadth > 0.6)
    return (z, mom, sector_b, returns, sector_r, r)
