"""Empirical-Bayes estimate of tariff-transition effects from change_tariff.csv.

For every ARPU segment the relative ARPU change of a transition A -> B is
modelled as

    change = a + b * price_gap(A, B) + u_B + v_AB + noise

* a + b * price_gap — weighted regression on the price difference from
  dict_tariff.csv, so transitions never seen in the history still get an
  estimate (only 9 of 21 tariffs ever appear as a destination);
* u_B — the destination tariff's own effect, shrunk towards the regression;
* v_AB — the pair's deviation, shrunk towards the tariff mean. Pairs with
  fewer than MIN_SUPPORT events are not trusted and use the tariff mean.

Variance components are method-of-moments estimates. The history describes a
different sample than the campaign audience, so the resulting variance is
inflated before it is used as a prior for the pilots.

The campaign effect also depends on how often an offer converts, so a
smoothed share of switchers choosing B is estimated as a conversion proxy.

Adapted from teammate commit e2b864d. The integrated agent uses the estimated
means for candidate ranking, with its own fixed cross-audience uncertainty;
the sampling-based effect_sd below remains available for offline diagnostics.
"""

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

ARPU_SEGMENTS = ("LOW", "MID", "HIGH")
MIN_SUPPORT = 5
# The judged audience differs from the history, so the EB posterior variance is
# inflated (sd x4). Chosen on runs where the true effects were perturbed away
# from the history, not on the mock, which is built from this same history.
VARIANCE_INFLATION = 16.0
CONVERSION_PSEUDO_COUNT = 10.0
MIN_EFFECT_SD = 0.05


def load_history(path: Optional[Path]) -> pd.DataFrame:
    """Deduplicated change events with the documented ARPU bands and a clipped ratio."""
    if path is None or not Path(path).is_file():
        return pd.DataFrame(columns=["from", "to", "segment", "ratio"])
    history = pd.read_csv(path).drop_duplicates()
    history = history[history["AVG_ARPU_PREV_3M"] >= 100]
    segment = pd.cut(
        history["AVG_ARPU_PREV_3M"],
        bins=[-np.inf, 1000, 5000, np.inf],
        labels=list(ARPU_SEGMENTS),
    ).astype(str)
    ratio = (
        (history["AVG_ARPU_NEXT_3M"] - history["AVG_ARPU_PREV_3M"])
        / history["AVG_ARPU_PREV_3M"]
    ).clip(-1, 3)
    return pd.DataFrame({
        "from": history["tariff_plan_code_from"].astype(str),
        "to": history["tariff_plan_code_to"].astype(str),
        "segment": segment,
        "ratio": ratio,
    })


def _segment_estimates(events: pd.DataFrame, prices: pd.Series, scale: float) -> pd.DataFrame:
    pairs = (
        events.groupby(["from", "to"])["ratio"]
        .agg(support="size", raw_mean="mean")
        .reset_index()
    )
    n = pairs["support"].to_numpy(dtype=float)
    mean = pairs["raw_mean"].to_numpy(dtype=float)

    # pooled within-pair (sampling) variance
    within = events.groupby(["from", "to"])["ratio"].transform("mean")
    dof = len(events) - len(pairs)
    sigma2 = float(((events["ratio"] - within) ** 2).sum() / dof) if dof > 0 else float(events["ratio"].var())

    # price-difference regression on pair means, weighted by support
    gap = ((prices.reindex(pairs["to"]).to_numpy() - prices.reindex(pairs["from"]).to_numpy()) / scale)
    design = np.column_stack([np.ones_like(gap), gap])
    weights = np.sqrt(n)
    coef, *_ = np.linalg.lstsq(design * weights[:, None], mean * weights, rcond=None)
    residual = mean - design @ coef

    # pair-level variance tau_v^2: one-way random effects within destination tariffs
    pairs = pairs.assign(n=n, residual=residual)
    ssb, excess_dof, denom = 0.0, 0.0, 0.0
    target_stats = {}
    for target, group in pairs.groupby("to"):
        gn = group["n"].to_numpy()
        gr = group["residual"].to_numpy()
        total = gn.sum()
        target_mean = float((gn * gr).sum() / total)
        ssb += float((gn * (gr - target_mean) ** 2).sum())
        excess_dof += len(group) - 1
        denom += total - float((gn ** 2).sum()) / total
        target_stats[target] = (target_mean, gn, total)
    tau_v2 = max(0.0, (ssb - sigma2 * excess_dof) / denom) if denom > 0 else 0.0

    # tariff-level variance tau_u^2 and shrunk destination effects
    sampling = {
        target: float((gn ** 2 * (tau_v2 + sigma2 / gn)).sum() / total ** 2)
        for target, (_, gn, total) in target_stats.items()
    }
    target_means = np.array([s[0] for s in target_stats.values()])
    tau_u2 = 0.0
    if len(target_means) > 1:
        tau_u2 = max(0.0, float(target_means.var(ddof=1)) - float(np.mean(list(sampling.values()))))
    tariff_effect = {}
    for target, (target_mean, _, _) in target_stats.items():
        v = sampling[target]
        weight = tau_u2 / (tau_u2 + v) if tau_u2 + v > 0 else 0.0
        tariff_effect[target] = (weight * target_mean, weight * v)

    observed = pairs.set_index(["from", "to"])
    codes = list(prices.index)
    rows = []
    for source in codes:
        for target in codes:
            if source == target:
                continue
            price_gap = (prices[target] - prices[source]) / scale
            regression = float(coef[0] + coef[1] * price_gap)
            u, u_var = tariff_effect.get(target, (0.0, tau_u2))
            tariff_mean = regression + u
            support, raw_mean = 0, np.nan
            if (source, target) in observed.index:
                support = int(observed.loc[(source, target), "support"])
                raw_mean = float(observed.loc[(source, target), "raw_mean"])
            if support >= MIN_SUPPORT:
                noise = sigma2 / support
                weight = tau_v2 / (tau_v2 + noise) if tau_v2 + noise > 0 else 0.0
                shrunk = tariff_mean + weight * (raw_mean - tariff_mean)
                variance = weight * noise + (1 - weight) ** 2 * u_var
            else:
                weight, shrunk, variance = 0.0, tariff_mean, tau_v2 + u_var
            rows.append({
                "from": source, "to": target, "support": support, "raw_mean": raw_mean,
                "price_gap": price_gap, "regression_mean": regression, "tariff_mean": tariff_mean,
                "shrink_weight": weight, "change_mean": shrunk, "change_sd": float(np.sqrt(variance)),
            })
    return pd.DataFrame(rows)


def estimate_transitions(events: pd.DataFrame, tariffs: pd.DataFrame) -> pd.DataFrame:
    """Return shrunk ARPU-change and effect priors for every (from, to, segment).

    Columns: change_mean / change_sd (relative ARPU change, EB posterior),
    conversion (smoothed share of switchers choosing `to`), and
    effect_mean / effect_sd — the prior for the lift ratio a pilot measures at
    channel multiplier 1.0, with the variance inflated by VARIANCE_INFLATION.
    """
    prices = tariffs.set_index(tariffs["tariff_plan_code"].astype(str))["price_tariff"].astype(float)
    scale = max(float(prices.median()), 1.0)
    frames = []
    for segment in ARPU_SEGMENTS:
        seg_events = events[events["segment"] == segment]
        if seg_events["ratio"].count() < 2:
            continue
        estimates = _segment_estimates(seg_events, prices, scale)

        counts = seg_events.groupby(["from", "to"]).size()
        leaving = seg_events.groupby("from").size()
        share_prior = float((counts / leaving.reindex(counts.index.get_level_values(0)).to_numpy()).median())
        pair_counts = counts.reindex(pd.MultiIndex.from_frame(estimates[["from", "to"]])).fillna(0).to_numpy()
        totals = leaving.reindex(estimates["from"]).fillna(0).to_numpy()
        conversion = (pair_counts + CONVERSION_PSEUDO_COUNT * share_prior) / (totals + CONVERSION_PSEUDO_COUNT)
        conversion_var = conversion * (1 - conversion) / (totals + CONVERSION_PSEUDO_COUNT + 1)

        change_mean = estimates["change_mean"].to_numpy()
        change_var = estimates["change_sd"].to_numpy() ** 2
        effect_var = conversion ** 2 * change_var + change_mean ** 2 * conversion_var
        frames.append(estimates.assign(
            segment=segment,
            conversion=conversion,
            effect_mean=change_mean * conversion,
            effect_sd=np.maximum(np.sqrt(VARIANCE_INFLATION * effect_var), MIN_EFFECT_SD),
        ))
    if not frames:
        return pd.DataFrame()
    columns = ["from", "to", "segment"]
    result = pd.concat(frames, ignore_index=True)
    return result[columns + [c for c in result.columns if c not in columns]]
