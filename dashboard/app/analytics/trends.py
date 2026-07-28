import math

import numpy as np
import pandas as pd

# Minimum completed weeks before we'll draw any trend line. Fewer than this and a
# regression is meaningless (2 points = a fake "perfect" line).
MIN_WEEKS = 4

# Two-sided 80% critical values of Student's t by degrees of freedom (t_{0.90, df}).
# 80% (not 90%) keeps the displayed range from ballooning on noisy/low-confidence
# metrics while still honestly widening when the fit is poor. We cap the projection
# window at ~12 weeks, so df = n - 2 tops out around 10; the table covers well past
# that and falls back to the normal approximation (1.282) for anything larger.
# Using a table keeps us dependency-free (no scipy).
_T_CRIT_80 = {
    1: 3.078, 2: 1.886, 3: 1.638, 4: 1.533, 5: 1.476, 6: 1.440,
    7: 1.415, 8: 1.397, 9: 1.383, 10: 1.372, 11: 1.363, 12: 1.356,
    13: 1.350, 14: 1.345, 15: 1.341, 16: 1.337, 17: 1.333, 18: 1.330,
    19: 1.328, 20: 1.325, 25: 1.316, 30: 1.310,
}


# Two-sided 90% critical values (t_{0.95, df}) — used only for the slope
# significance test that sets the high/low confidence tier. Kept stricter than the
# 80% display band on purpose: narrowing the *range* shouldn't make us call a noisy
# trend "significant".
_T_CRIT_90 = {
    1: 6.314, 2: 2.920, 3: 2.353, 4: 2.132, 5: 2.015, 6: 1.943,
    7: 1.895, 8: 1.860, 9: 1.833, 10: 1.812, 11: 1.796, 12: 1.782,
    13: 1.771, 14: 1.761, 15: 1.753, 16: 1.746, 17: 1.740, 18: 1.734,
    19: 1.729, 20: 1.725, 25: 1.708, 30: 1.697,
}


def _t_crit(table: dict, df: int, large_sample: float) -> float:
    """t critical value from `table` for `df` degrees of freedom, with fallbacks."""
    if df in table:
        return table[df]
    if df < 1:
        return table[1]
    # Nearest tabulated df at/below, else the large-sample normal value.
    below = [k for k in table if k <= df]
    return table[max(below)] if below else large_sample


def compute_projection(values, week_dates) -> dict:
    """Project next week's value from a mission-wide weekly series, with confidence.

    Pure function — no I/O. `values` is the ordered (oldest→newest) list of weekly
    totals; `week_dates` the matching YYYY-MM-DD week-end labels.

    Returns a dict:
      status         "ok" | "insufficient"
      projected      next-week point estimate (>= 0)
      week_end_date  the projected week's end date (last + 7 days)
      lower, upper   90% prediction interval for next week (floored at 0)
      confidence     "high"  — slope statistically distinguishable from flat
                     "low"   — trend not significant; number shown but don't trust it
      slope_per_week fitted change per week
      r_squared      goodness of fit
      actuals, weeks the input series echoed back (for charting)

    When there is too little history (< MIN_WEEKS completed weeks) status is
    "insufficient" and only actuals/weeks are populated — we refuse to invent a
    trend from 2-3 points.
    """
    y = np.asarray(list(values), dtype=float)
    weeks = list(week_dates)
    n = len(y)

    base = {"status": "insufficient", "actuals": y.tolist(), "weeks": weeks}
    if n < MIN_WEEKS:
        return base

    x = np.arange(n, dtype=float)
    slope, intercept = np.polyfit(x, y, 1)

    x_next = float(n)
    projected = max(0.0, intercept + slope * x_next)

    # Residuals / fit quality.
    y_hat = intercept + slope * x
    ss_res = float(np.sum((y - y_hat) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    df = n - 2
    t_sig  = _t_crit(_T_CRIT_90, df, 1.645)  # slope significance (strict, 90%)
    t_band = _t_crit(_T_CRIT_80, df, 1.282)  # display range (tighter, 80%)
    x_mean = x.mean()
    s_xx = float(np.sum((x - x_mean) ** 2))

    # Residual standard error. df >= 2 here (n >= 4), so this is well-defined.
    s_err = math.sqrt(ss_res / df) if df > 0 else 0.0

    # Is the slope statistically distinguishable from zero? A perfect non-flat fit
    # (s_err == 0, slope != 0) is definitively a real trend.
    if s_err == 0.0:
        significant = slope != 0.0
    else:
        se_slope = s_err / math.sqrt(s_xx) if s_xx > 0 else float("inf")
        t_slope = slope / se_slope if se_slope > 0 else 0.0
        significant = abs(t_slope) >= t_sig

    # Prediction interval (80%) for a NEW observation at x_next.
    if s_err == 0.0 or s_xx == 0.0:
        margin = 0.0
    else:
        se_pred = s_err * math.sqrt(1.0 + 1.0 / n + (x_next - x_mean) ** 2 / s_xx)
        margin = t_band * se_pred

    lower = max(0.0, projected - margin)
    upper = projected + margin

    return {
        "status":         "ok",
        "projected":      round(projected, 1),
        "week_end_date":  _next_week_date(weeks[-1]),
        "lower":          round(lower, 1),
        "upper":          round(upper, 1),
        "confidence":     "high" if significant else "low",
        "slope_per_week": round(float(slope), 2),
        "r_squared":      round(r_squared, 3),
        "actuals":        y.tolist(),
        "weeks":          weeks,
    }


def _next_week_date(last_date) -> str:
    try:
        return (pd.to_datetime(last_date) + pd.Timedelta(days=7)).strftime("%Y-%m-%d")
    except Exception:
        return ""


def project_next_week(
    ki_df: pd.DataFrame,
    metric: str,
    weeks: int = 12,
) -> pd.DataFrame:
    """Legacy df-in/df-out projection: last N weekly totals plus one projected row.

    Kept for its existing DataFrame contract. Delegates the actual math to
    compute_projection so the two projection paths can't drift apart. Returns the
    weekly frame with a boolean `projected` column; a projected row is appended
    only when there is enough history for a trustworthy fit.
    """
    weekly = (
        ki_df.groupby("week_end_date")[metric]
        .sum()
        .reset_index()
        .sort_values("week_end_date")
        .tail(weeks)
        .reset_index(drop=True)
    )
    weekly["projected"] = False

    res = compute_projection(weekly[metric].tolist(), weekly["week_end_date"].tolist())
    if res["status"] != "ok":
        return weekly

    projection_row = pd.DataFrame({
        "week_end_date": [res["week_end_date"]],
        metric:          [res["projected"]],
        "projected":     [True],
    })
    return pd.concat([weekly, projection_row], ignore_index=True)
