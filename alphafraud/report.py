"""Plotly figure builders. Each returns a JSON string (fig.to_json()) that a template
embeds and renders with the vendored plotly.min.js. Kept free of Flask so it can also be
used from the CLI or notebooks.

The signature figure is the "fraud quadrant": AlphaFold confidence (pLDDT) vs. how right it
actually was (TM-score). High-confidence / low-TM = confidently wrong.
"""

from __future__ import annotations

import json
import re
from typing import Optional

import plotly.graph_objects as go

from . import config

_DISEASE_RE = re.compile(
    r"amyloid|prion|transthyretin|synuclein|\bsod1\b|superoxide dismutase|tumou?r|oncogene|"
    r"cancer|alzheimer|parkinson|huntingtin|\btau\b|islet amyloid|microglobulin|gelsolin", re.I)

# marcdeller.com brand palette (mirrors banner.py and static/brand.css).
BRAND = {
    "primary": "#1e73be",
    "primary_light": "#4a9fd4",
    "amber": "#fcb900",
    "green": "#00d084",
    "red": "#d62728",
    "ink": "#1c2733",
    "grid": "rgba(120,140,160,0.18)",
}

_LAYOUT = dict(
    autosize=True,   # always size to the container (critical for narrow mobile widths)
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, system-ui, sans-serif", color=BRAND["ink"], size=13),
    # Generous top margin so the title clears the legend row and subplot titles.
    margin=dict(l=60, r=24, t=88, b=56),
    title=dict(y=0.97, yanchor="top", x=0.02, xanchor="left", font=dict(size=15)),
    colorway=[BRAND["primary"], BRAND["amber"], BRAND["green"], BRAND["primary_light"], BRAND["red"]],
    hoverlabel=dict(font_size=12),
)


def _fig(fig: go.Figure) -> str:
    fig.update_layout(**_LAYOUT)
    fig.update_xaxes(gridcolor=BRAND["grid"], zeroline=False)
    fig.update_yaxes(gridcolor=BRAND["grid"], zeroline=False)
    return fig.to_json()


# --------------------------------------------------------------------------------------
# KPIs
# --------------------------------------------------------------------------------------
def kpis(entities: list[dict]) -> dict:
    n = len(entities)
    fully = sum(1 for e in entities if e.get("status") == "compared")
    cw = sum(1 for e in entities if e.get("confidently_wrong"))
    novel = sum(1 for e in entities if e.get("is_novel"))
    novel_wrong = sum(1 for e in entities if e.get("is_novel") and e.get("confidently_wrong"))
    tms = [e["tm_by_experiment"] for e in entities if e.get("tm_by_experiment") is not None]

    def pct(x):
        return round(100.0 * x / n, 1) if n else None

    return {
        "n_analysed": n,
        "n_fully": fully,
        "full_pct": pct(fully),
        "confidently_wrong": cw,
        "confidently_wrong_pct": pct(cw),
        "novel": novel,
        "novel_pct": pct(novel),
        "novel_and_wrong": novel_wrong,
        "novel_and_wrong_pct": pct(novel_wrong),
        "median_tm": round(sorted(tms)[len(tms) // 2], 3) if tms else None,
    }


# --------------------------------------------------------------------------------------
# "This week's notable releases" — curated, novelty-first highlight panel (on-the-fly)
# --------------------------------------------------------------------------------------
def _highlight_annotation(e: dict, f: dict) -> str:
    """Plain-English 'why it matters' (server-generated; the only <b> tags are ours)."""
    nov = f["nov_id"]
    id_txt = f" ({nov:.0f}% identity to anything AlphaFold trained on)" if nov is not None else ""
    parts = []
    if f["novel"] and f["cw"]:
        parts.append(f"Genuinely unseen sequence{id_txt} — and AlphaFold got the fold "
                     f"<b>wrong</b> despite high confidence.")
    elif f["novel"]:
        tm = e.get("tm_by_experiment")
        if e.get("status") == "compared" and tm is not None and tm >= 0.7:
            parts.append(f"Genuinely unseen sequence{id_txt} — AlphaFold predicted it "
                         f"<b>correctly</b> (TM {tm:.2f}).")
        else:
            parts.append(f"Genuinely unseen sequence{id_txt}.")
    elif f["cw"]:
        cp = e.get("closest_pre_cutoff")
        homolog = f" ({nov:.0f}% identity to {cp})" if (nov is not None and cp) else ""
        parts.append(f"A close pre-cutoff homolog existed{homolog} yet AlphaFold "
                     f"<b>confidently missed</b> the fold.")
    if f["first"]:
        parts.append("First structure of this protein we've seen.")
    if f["disease"]:
        parts.append("Disease-linked.")
    return " ".join(parts)


def week_highlights(entities: list[dict], seen_uniprots: Optional[set] = None, cap: int = 6) -> dict:
    """Curated novelty-first shortlist for the top of a release-week page. On-the-fly from the
    entities already loaded; returns a verdict line + up to `cap` annotated rows."""
    seen_uniprots = seen_uniprots or set()
    scored = []
    for e in entities:
        novel, cw = bool(e.get("is_novel")), bool(e.get("confidently_wrong"))
        if not (novel or cw):                       # only genuinely notable rows
            continue
        nov_id = e.get("novelty_identity")
        deficit = max(0.0, (30 - nov_id) / 30) if nov_id is not None else (0.5 if novel else 0)
        first = bool(e.get("uniprot") and e["uniprot"] not in seen_uniprots)
        text = " ".join(filter(None, [e.get("description"), e.get("uniprot_name")]))
        disease = bool(_DISEASE_RE.search(text))
        f = {"novel": novel, "cw": cw, "nov_id": nov_id, "first": first, "disease": disease}
        score = 2.0 * novel + 1.5 * deficit + 2.0 * cw + 1.0 * (e.get("fraud_score") or 0) + 0.5 * first
        scored.append((score, e, f))
    scored.sort(key=lambda t: t[0], reverse=True)

    rows = []
    for _s, e, f in scored[:cap]:
        badges = []
        if f["novel"]:
            badges.append({"label": f"novel · {100 - f['nov_id']:.0f}%" if f["nov_id"] is not None else "novel", "cls": "novel"})
        if f["cw"]:
            badges.append({"label": "confidently wrong", "cls": "wrong"})
        if f["first"]:
            badges.append({"label": "first seen", "cls": "firstseen"})
        if f["disease"]:
            badges.append({"label": "disease", "cls": "disease"})
        rows.append({
            "entity_id": e["entity_id"], "entry_id": e["entry_id"], "chain": e.get("chain"),
            "uniprot": e.get("uniprot"),
            "protein": (e.get("uniprot_name") or e.get("description") or e["entry_id"])[:48],
            "badges": badges, "annotation": _highlight_annotation(e, f), "wrong": f["cw"],
        })

    n_novel = sum(1 for e in entities if e.get("is_novel"))
    n_cw = sum(1 for e in entities if e.get("confidently_wrong"))
    if n_novel == 0 and n_cw == 0:
        verdict = "No novel or confidently-wrong structures this week — AlphaFold kept up."
        severity = "good"
    else:
        top = rows[0]["protein"] if rows else "—"
        verdict = (f"{n_novel} novel sequence{'s' if n_novel != 1 else ''}, "
                   f"{n_cw} confidently wrong. Highlight: {top}.")
        severity = "alert" if n_cw else "amber"
    return {"rows": rows, "verdict": verdict, "severity": severity,
            "n_novel": n_novel, "n_cw": n_cw, "total": len(entities)}


# --------------------------------------------------------------------------------------
# Signature scatter
# --------------------------------------------------------------------------------------
def _downsample_points(entities: list[dict], cap: int = 6000) -> tuple[list[dict], int]:
    """Keep the scatter light and WebGL-free: retain every 'interesting' point (confidently
    wrong or novel) and randomly sample the dense, well-predicted cluster down to `cap`.
    Returns (points, n_sampled_omitted)."""
    if len(entities) <= cap:
        return entities, 0
    import random

    must = [e for e in entities if e.get("confidently_wrong") or e.get("is_novel")]
    rest = [e for e in entities if not (e.get("confidently_wrong") or e.get("is_novel"))]
    budget = cap - len(must)
    if budget <= 0:
        kept = random.sample(must, cap)
    elif len(rest) > budget:
        kept = must + random.sample(rest, budget)
    else:
        kept = must + rest
    return kept, len(entities) - len(kept)


def fraud_scatter(entities: list[dict], zoom: bool = False) -> str:
    """The pLDDT-vs-TM 'fraud quadrant'. `zoom=True` restricts the axes to just the
    confidently-wrong region (pLDDT ≥ CONFIDENT_PLDDT, TM < WRONG_TM) for a closer look."""
    points, omitted = _downsample_points(entities)
    fig = go.Figure()
    # Shade the fraud quadrant: confident (pLDDT > threshold) yet wrong (TM < threshold).
    fig.add_shape(
        type="rect", x0=config.CONFIDENT_PLDDT, x1=102, y0=0, y1=config.WRONG_TM,
        fillcolor="rgba(214,39,40,0.08)", line=dict(width=0), layer="below",
    )
    if not zoom:
        # Label sits at the inside-bottom of the box so it never overlaps the data points.
        fig.add_annotation(
            x=(config.CONFIDENT_PLDDT + 102) / 2, y=0.015, yanchor="bottom",
            text="confidently wrong", showarrow=False,
            font=dict(color=BRAND["red"], size=12), opacity=0.75,
        )
    for novel, color, name in [(1, BRAND["amber"], "novel sequence"), (0, BRAND["primary"], "has pre-cutoff homolog")]:
        pts = [e for e in points if bool(e.get("is_novel")) == bool(novel)
               and e.get("mean_plddt") is not None and e.get("tm_by_experiment") is not None]
        if not pts:
            continue
        fig.add_trace(go.Scatter(
            x=[e["mean_plddt"] for e in pts],
            y=[e["tm_by_experiment"] for e in pts],
            mode="markers",
            name=name,
            cliponaxis=False,   # render markers fully even at the axis edges (pLDDT~100, TM~1)
            marker=dict(
                color=color, size=[6 + 20 * (e.get("fraud_score") or 0) for e in pts],
                line=dict(width=0.4, color="white"),
                # Lower opacity so overlapping points read as density in the big cumulative cloud.
                opacity=(0.5 if len(points) > 3000 else 0.8),
            ),
            customdata=[[e["entity_id"], e.get("uniprot"), e.get("fraud_score"),
                         (round(100 - e["novelty_identity"]) if e.get("novelty_identity") is not None else "n/a")]
                        for e in pts],
            hovertemplate=("<b>%{customdata[0]}</b> (%{customdata[1]})<br>"
                           "pLDDT %{x:.1f} · TM %{y:.3f}<br>"
                           "FRAUD %{customdata[2]:.3f} · novelty %{customdata[3]}%<extra></extra>"),
        ))
    # Second legend, to the right of the colour legend, explaining that marker size = FRAUD.
    for frac in (0.1, 0.5):
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers", name=f"FRAUD {frac}", legend="legend2",
            marker=dict(color="rgba(120,140,160,0.75)", size=6 + 20 * frac, line=dict(width=0.4, color="white")),
        ))
    title = ("Confidently wrong — zoomed on the red zone (high confidence, low agreement)"
             if zoom else "AlphaFold confidence vs. agreement with experiment")
    fig.update_layout(
        title=title,
        xaxis_title="mean pLDDT (AlphaFold confidence)",
        yaxis_title="TM-score to experiment",
        legend=dict(orientation="h", y=1.09, x=0, itemsizing="constant"),
        legend2=dict(orientation="h", y=1.09, x=0.58, itemsizing="trace",
                     title=dict(text="marker size:"), font=dict(size=11)),
    )
    if zoom:                                # restrict to the confidently-wrong box
        fig.update_xaxes(range=[config.CONFIDENT_PLDDT, 100.5])
        fig.update_yaxes(range=[0, config.WRONG_TM])
    else:
        fig.update_xaxes(range=[0, 102])   # headroom so pLDDT~100 markers sit inside the frame
        fig.update_yaxes(range=[0, 1.03])
    return _fig(fig)


def fraud_dumbbell(entities: list[dict], top: int = 50) -> Optional[str]:
    """Ranked 'promise vs. reality' dumbbell: the worst confidently-wrong predictions, one row
    per *protein*, sorted by the gap between what AlphaFold claimed (mean pLDDT/100) and what the
    experiment showed (TM-score). The connector length *is* the sort key, so the ranking is
    self-evident. Deduplicated by UniProt (see below) and soft-capped at `top`."""
    cw = [e for e in entities
          if e.get("confidently_wrong") and e.get("mean_plddt") is not None
          and e.get("tm_by_experiment") is not None]
    if not cw:
        return None

    def gap(e):
        return e["mean_plddt"] / 100.0 - e["tm_by_experiment"]

    # Deduplicate by protein: AlphaFold DB holds ONE model per UniProt sequence, so many
    # depositions of the same protein share an identical prediction and would otherwise flood the
    # chart with near-duplicates (e.g. 33 transthyretin structures crowding out everything else).
    # Keep the single worst deposition per UniProt and badge it with the deposition count, so
    # "top N" means N *distinct* proteins. Entities lacking a UniProt stay individual (by id).
    from collections import defaultdict
    groups: dict = defaultdict(list)
    for e in cw:
        groups[e.get("uniprot") or e["entity_id"]].append(e)
    reps = [(max(members, key=gap), len(members)) for members in groups.values()]
    reps.sort(key=lambda rc: gap(rc[0]), reverse=True)
    reps = reps[:top][::-1]                      # cap, then reverse so the worst sits at the TOP
    ranked = [e for e, _c in reps]
    counts = [c for _e, c in reps]
    n = len(ranked)

    def _nov(e):
        v = e.get("novelty_identity")
        return round(100 - v) if v is not None else "n/a"

    def _short(e):
        d = (e.get("description") or "").strip()
        return (d[:20] + "…") if len(d) > 21 else d

    def _label(e, c):
        base = f"{e['entity_id']}  {_short(e)}".rstrip()
        return f"{base}  ×{c}" if c > 1 else base            # ×N = number of depositions

    def _cntstr(c):
        return f"worst of {c} structures of this protein" if c > 1 else "1 structure"

    labels = [_label(e, c) for e, c in zip(ranked, counts)]
    cd = [[e["entity_id"], e.get("description") or "—", _nov(e),
           e["mean_plddt"], e["tm_by_experiment"], gap(e), _cntstr(c)]
          for e, c in zip(ranked, counts)]

    fig = go.Figure()
    # Faint band left of the WRONG_TM line — the "wrong" half every TM dot lands in.
    fig.add_shape(type="rect", x0=0, x1=config.WRONG_TM, y0=-0.6, y1=n - 0.4,
                  fillcolor="rgba(214,39,40,0.06)", line=dict(width=0), layer="below")
    fig.add_shape(type="line", x0=config.WRONG_TM, x1=config.WRONG_TM, y0=-0.6, y1=n - 0.4,
                  line=dict(color=BRAND["red"], width=1, dash="dot"), layer="below")

    # Connectors (one trace, None-separated) — the visible "size of the lie".
    cx, cy = [], []
    for i, e in enumerate(ranked):
        cx += [e["tm_by_experiment"], e["mean_plddt"] / 100.0, None]
        cy += [i, i, None]
    fig.add_trace(go.Scatter(x=cx, y=cy, mode="lines", showlegend=False, hoverinfo="skip",
                             line=dict(color="rgba(120,140,160,0.5)", width=2)))

    ys = list(range(n))
    fig.add_trace(go.Scatter(
        x=[e["tm_by_experiment"] for e in ranked], y=ys, mode="markers",
        name="actual (TM-score)", cliponaxis=False,
        marker=dict(color=BRAND["red"], size=9, line=dict(width=0.6, color="white")),
        customdata=cd,
        hovertemplate=("<b>%{customdata[0]}</b><br>%{customdata[1]}<br>"
                       "actual TM %{customdata[4]:.3f}<br>"
                       "gap %{customdata[5]:.2f} · novelty %{customdata[2]}%<br>"
                       "<i>%{customdata[6]}</i><extra></extra>"),
    ))
    fig.add_trace(go.Scatter(
        x=[e["mean_plddt"] / 100.0 for e in ranked], y=ys, mode="markers",
        name="AlphaFold claim (pLDDT)", cliponaxis=False,
        marker=dict(color=BRAND["primary"], size=9, line=dict(width=0.6, color="white")),
        customdata=cd,
        hovertemplate=("<b>%{customdata[0]}</b><br>%{customdata[1]}<br>"
                       "claimed pLDDT %{customdata[3]:.0f}<br>"
                       "gap %{customdata[5]:.2f} · novelty %{customdata[2]}%<br>"
                       "<i>%{customdata[6]}</i><extra></extra>"),
    ))

    fig.update_layout(
        title=f"The {n} worst proteins: what AlphaFold promised vs. what the structure showed",
        xaxis_title="score 0–1  (TM-score ● · pLDDT/100 ●)",
        legend=dict(orientation="h", y=1.03, x=0, itemsizing="constant"),
        # Tall, fixed-height list: ~19 px/row. app.js honours meta.keepHeight on mobile.
        height=max(320, 132 + 19 * n),
        meta=dict(keepHeight=True),
        margin=dict(l=176, r=24, t=104, b=52),
    )
    fig.update_xaxes(range=[0, 1.02])
    fig.update_yaxes(tickvals=ys, ticktext=labels, tickfont=dict(size=11, family="Roboto Mono, monospace"),
                     showgrid=False, range=[-0.6, n - 0.4])
    return _fig(fig)


def sampling_note(entities: list[dict]) -> str:
    """Caption for the scatter card when the dense cluster was sampled (empty otherwise)."""
    _, omitted = _downsample_points(entities)
    if omitted:
        return (f"All confidently-wrong and novel points are shown; {omitted:,} well-predicted "
                "points were sampled out for legibility.")
    return ""


def metric_histograms(entities: list[dict]) -> str:
    from plotly.subplots import make_subplots

    # Cα-RMSD and lDDT are only computed for the fully-compared subset (screened entities are
    # TM-only), so restrict ALL three panels to that same population. Otherwise the TM panel would
    # summarise ~83k structures while the other two summarise only the ~15k disagreements — three
    # different populations side by side.
    comp = [e for e in entities if e.get("ca_rmsd") is not None and e.get("lddt") is not None]
    # Stacked vertically (not 3-across) so each histogram gets the full width and stays legible
    # on a narrow phone; on desktop it reads as a clean column of three.
    fig = make_subplots(rows=3, cols=1, vertical_spacing=0.12,
                        subplot_titles=("TM-score", "Cα-RMSD (Å)", "lDDT"))
    fig.add_trace(go.Histogram(x=[e["tm_by_experiment"] for e in comp if e.get("tm_by_experiment") is not None],
                               marker_color=BRAND["primary"], nbinsx=25), row=1, col=1)
    fig.add_trace(go.Histogram(x=[e["ca_rmsd"] for e in comp if e.get("ca_rmsd") is not None],
                               marker_color=BRAND["amber"], nbinsx=25), row=2, col=1)
    fig.add_trace(go.Histogram(x=[e["lddt"] for e in comp if e.get("lddt") is not None],
                               marker_color=BRAND["green"], nbinsx=25), row=3, col=1)
    fig.update_layout(title=f"Metric distributions ({len(comp):,} fully-compared structures)",
                      showlegend=False, height=560)
    return _fig(fig)


# --------------------------------------------------------------------------------------
# Trend across weeks
# --------------------------------------------------------------------------------------
def _tm_trend(monthly: list[dict]) -> Optional[dict]:
    """Non-parametric trend test for mean TM over deposit month: Mann-Kendall (Kendall's tau)
    for significance + a Theil-Sen slope for the line. Rank-based, so robust to the skewed TM
    distribution and noisy low-n months; run over the ~99 monthly points (not the 80k raw rows,
    which would make any slope 'significant'). Returns tau/p always, plus the fitted endpoints
    only when p<0.05; None if too few points or scipy is unavailable."""
    pts = [(w["label"], w["mean_tm"]) for w in monthly if w.get("mean_tm") is not None]
    if len(pts) < 8:
        return None
    try:
        from scipy import stats as _st
    except Exception:
        return None

    def _decyear(lbl):                                   # 'YYYY-MM' -> decimal year (mid-month)
        return int(lbl[:4]) + (int(lbl[5:7]) - 0.5) / 12.0

    xs = [_decyear(l) for l, _ in pts]
    ys = [y for _, y in pts]
    tau, p = _st.kendalltau(xs, ys)
    if tau is None or p is None:
        return None
    out = {"tau": float(tau), "p": float(p), "significant": p < 0.05}
    if out["significant"]:
        slope, intercept, _lo, _hi = _st.theilslopes(ys, xs)
        out.update(slope_yr=float(slope), x0=pts[0][0], x1=pts[-1][0],
                   y0=intercept + slope * xs[0], y1=intercept + slope * xs[-1])
    return out


def trend_figure(monthly: list[dict], cw_trend: Optional[dict] = None) -> str:
    """monthly: list of {label (YYYY-MM), mean_tm, confidently_wrong, n_compared} oldest->newest,
    binned by structure deposit month (see db.deposit_month_trend). `cw_trend` is the logistic
    confidently-wrong-rate trend from db.cw_rate_trend() (drawn only if significant)."""
    fig = go.Figure()
    labels = [w["label"] for w in monthly]
    # Left axis: mean TM-score.
    fig.add_trace(go.Scatter(x=labels, y=[w.get("mean_tm") for w in monthly], name="mean TM-score",
                             mode="lines+markers", line=dict(color=BRAND["primary"], width=2), yaxis="y",
                             customdata=[[w.get("n_compared")] for w in monthly],
                             hovertemplate="%{x}<br>mean TM %{y:.3f}<br>%{customdata[0]} structures<extra></extra>"))
    # Right axis y2: confidently-wrong COUNT, de-emphasised (grey) since count is confounded by
    # deposition volume — the meaningful signal is the rate, on y3.
    fig.add_trace(go.Bar(x=labels, y=[w.get("confidently_wrong") for w in monthly],
                         name="confidently-wrong count", yaxis="y2",
                         marker_color="rgba(120,140,160,0.35)",
                         hovertemplate="%{x}<br>%{y} confidently wrong<extra></extra>"))
    # Right axis y3: confidently-wrong RATE (%) markers.
    rate = [(100 * (w.get("confidently_wrong") or 0) / w["n_compared"]) if w.get("n_compared") else None
            for w in monthly]
    fig.add_trace(go.Scatter(x=labels, y=rate, name="confidently-wrong rate", yaxis="y3", mode="markers",
                             marker=dict(color=BRAND["red"], size=4, opacity=0.55),
                             hovertemplate="%{x}<br>CW rate %{y:.1f}%<extra></extra>"))

    notes = []
    # TM trend line (Mann-Kendall + Theil-Sen), only if significant.
    tr = _tm_trend(monthly)
    if tr and tr.get("significant"):
        fig.add_trace(go.Scatter(x=[tr["x0"], tr["x1"]], y=[tr["y0"], tr["y1"]], mode="lines", yaxis="y",
                                 showlegend=False, hoverinfo="skip",
                                 line=dict(color=BRAND["ink"], width=2, dash="dash")))
        notes.append(f"TM {'declining' if tr['slope_yr'] < 0 else 'rising'}: "
                     f"{tr['slope_yr'] * 1000:+.1f} milli-TM/yr (Mann-Kendall τ={tr['tau']:+.2f}, p={tr['p']:.2g})")
    elif tr:
        notes.append(f"No significant TM trend (Mann-Kendall p={tr['p']:.2g})")
    # CW-rate trend line (logistic regression), only if significant.
    if cw_trend and cw_trend.get("significant"):
        fig.add_trace(go.Scatter(x=[labels[0], labels[-1]],
                                 y=[cw_trend["rate0"] * 100, cw_trend["rate1"] * 100],
                                 mode="lines", yaxis="y3", showlegend=False, hoverinfo="skip",
                                 line=dict(color=BRAND["red"], width=2, dash="dash")))
        notes.append(f"CW rate rising: ×{cw_trend['or_decade']:.2f} odds/decade (logistic p={cw_trend['p']:.1g})")

    if notes:
        fig.add_annotation(xref="paper", yref="paper", x=0.015, y=0.03, xanchor="left", yanchor="bottom",
                           showarrow=False, align="left", text="<br>".join(notes),
                           font=dict(size=11, color=BRAND["ink"]), bordercolor=BRAND["grid"],
                           borderwidth=1, borderpad=4, bgcolor="rgba(255,255,255,0.82)")

    fig.update_layout(
        title="Accuracy over deposition time (by month)",
        xaxis=dict(title="structure deposit month", domain=[0.0, 0.9]),
        yaxis=dict(title="mean TM-score", range=[0, 1]),
        yaxis2=dict(title="# confidently wrong", overlaying="y", side="right", showgrid=False),
        yaxis3=dict(title=dict(text="CW rate (%)", font=dict(color=BRAND["red"])), overlaying="y",
                    side="right", anchor="free", position=1.0, showgrid=False, rangemode="tozero",
                    tickfont=dict(color=BRAND["red"])),
        legend=dict(orientation="h", y=1.12, x=0),
    )
    return _fig(fig)


# --------------------------------------------------------------------------------------
# Per-entry figures
# --------------------------------------------------------------------------------------
def per_residue_tracks(per_res: dict) -> str:
    x = per_res.get("af_res_id") or list(range(len(per_res.get("ca_deviation", []))))
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=per_res.get("ca_deviation", []), name="Cα deviation (Å)",
                             cliponaxis=False, line=dict(color=BRAND["red"], width=1.5)))
    fig.add_trace(go.Scatter(x=x, y=[v * 100 for v in per_res.get("lddt", [])], name="per-residue lDDT (×100)",
                             cliponaxis=False, line=dict(color=BRAND["green"], width=1.5), yaxis="y2"))
    fig.add_trace(go.Scatter(x=x, y=[p if p is not None else None for p in per_res.get("plddt", [])],
                             name="pLDDT", cliponaxis=False,
                             line=dict(color=BRAND["primary"], width=1.5, dash="dot"), yaxis="y2"))
    fig.update_layout(
        title="Per-residue error vs. AlphaFold confidence",
        xaxis_title="residue (UniProt/model numbering)",
        yaxis=dict(title="Cα deviation (Å)"),
        yaxis2=dict(title="lDDT×100 / pLDDT", overlaying="y", side="right", range=[0, 103], showgrid=False),
        legend=dict(orientation="h", y=1.12, x=0),
    )
    return _fig(fig)


def heatmap(matrix: list, title: str, colorscale: Optional[list] = None) -> str:
    fig = go.Figure(go.Heatmap(z=matrix, colorscale=colorscale or "Viridis", colorbar=dict(thickness=12)))
    fig.update_layout(title=title, yaxis=dict(autorange="reversed", scaleanchor="x"))
    return _fig(fig)


def pae_honesty_pair(pae: list, observed: list) -> str:
    from plotly.subplots import make_subplots

    fig = make_subplots(rows=1, cols=2, subplot_titles=("AlphaFold PAE (predicted, Å)",
                                                        "observed error |Δdistance| (Å)"))
    fig.add_trace(go.Heatmap(z=pae, colorscale="Inferno", coloraxis="coloraxis"), row=1, col=1)
    fig.add_trace(go.Heatmap(z=observed, colorscale="Inferno", coloraxis="coloraxis"), row=1, col=2)
    fig.update_layout(title="Was AlphaFold's self-reported uncertainty honest?",
                      coloraxis=dict(colorscale="Inferno", colorbar=dict(thickness=12)))
    fig.update_yaxes(autorange="reversed")
    return _fig(fig)


# --------------------------------------------------------------------------------------
# Analysis-tab figures (built from the cached analysis snapshot)
# --------------------------------------------------------------------------------------
def analysis_enrichment(enr: list, title: str, cap: int = 15) -> Optional[str]:
    enr = [e for e in enr if e.get("n_bg", 0) >= 3][:cap]
    if not enr:
        return None
    enr = enr[::-1]   # highest at top
    fig = go.Figure(go.Bar(
        y=[e["label"] for e in enr], x=[e["cw_rate"] for e in enr], orientation="h",
        marker_color=BRAND["amber"],
        error_x=dict(type="data", symmetric=False,
                     array=[max(0, e["ci_hi"] - e["cw_rate"]) for e in enr],
                     arrayminus=[max(0, e["cw_rate"] - e["ci_lo"]) for e in enr],
                     color="rgba(120,140,160,0.7)", thickness=1.2),
        customdata=[[e["n_cw"], e["n_bg"], e["enrichment"]] for e in enr],
        hovertemplate=("<b>%{y}</b><br>confidently-wrong rate %{x:.1f}%<br>"
                       "%{customdata[0]}/%{customdata[1]} · enrichment %{customdata[2]}×<extra></extra>"),
    ))
    fig.update_layout(title=title, xaxis_title="confidently-wrong rate (%)",
                      margin=dict(l=200, r=24, t=88, b=56))
    return _fig(fig)


# Distinct qualitative colours per CATH class so classes never collide (e.g. two blues).
_CATH_COLORS = {
    "Mainly Alpha": "#d62728", "Mainly Beta": "#1e73be", "Alpha Beta": "#00d084",
    "Few Secondary Structures": "#fcb900", "Special": "#9b51e0", "unclassified": "#9aa7b3",
}


def analysis_cath_folds(cf: dict) -> Optional[str]:
    """Confidently-wrong counts by CATH architecture: named, sorted horizontal bars coloured
    by CATH class. The '92% have no fold' fact is stated in the title, not drawn as a tile --
    a ranked bar of the classified minority is far more legible than the old treemap."""
    bars = cf.get("bars") or []
    if not bars:
        return None
    bars = bars[::-1]   # Plotly draws bottom-up; reverse so the largest sits at the top
    counts = [b["count"] for b in bars]
    labels = [b["label"] for b in bars]
    colors = [_CATH_COLORS.get(b["class_name"], "#5b6b7a") for b in bars]
    customdata = [[b["class_name"], b.get("top_topo") or "—"] for b in bars]
    fig = go.Figure(go.Bar(
        y=labels, x=counts, orientation="h", marker_color=colors, showlegend=False,
        text=counts, textposition="outside", cliponaxis=False,
        customdata=customdata,
        hovertemplate=("<b>%{y}</b><br>%{x} confidently wrong<br>CATH class: "
                       "%{customdata[0]}<br>most common fold: %{customdata[1]}<extra></extra>"),
    ))
    total = cf.get("total_cw", 0)
    n_uncl = cf.get("n_unclassified", 0)
    pct = cf.get("pct_unclassified", 0)
    n_cls = cf.get("n_classified", 0)
    fig.update_layout(
        title=(f"Confidently-wrong by CATH architecture<br>"
               f"<sub>{n_uncl:,}/{total:,} ({pct:.0f}%) have no CATH fold — amyloids, peptides, "
               f"disordered. The {n_cls:,} with a known architecture:</sub>"),
        xaxis_title="structures confidently wrong",
        margin=dict(l=210, r=48, t=92, b=52),
    )
    # A compact class-colour legend (bars carry per-point colour, so add proxy legend traces).
    for cls_name, col in [("Mainly Alpha", _CATH_COLORS["Mainly Alpha"]),
                          ("Mainly Beta", _CATH_COLORS["Mainly Beta"]),
                          ("Alpha Beta", _CATH_COLORS["Alpha Beta"]),
                          ("Few Secondary Structures", _CATH_COLORS["Few Secondary Structures"])]:
        if any(b["class_name"] == cls_name for b in bars):
            fig.add_trace(go.Bar(y=[None], x=[None], orientation="h", name=cls_name,
                                 marker_color=col, showlegend=True, hoverinfo="skip"))
    fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0,
                                  font=dict(size=11)), barmode="overlay")
    return _fig(fig)


def analysis_cluster_heatmap(cl: dict) -> Optional[str]:
    if cl.get("n", 0) < 4:
        return None
    n = cl["n"]
    fig = go.Figure(go.Heatmap(
        z=cl["matrix"], x=cl["order_labels"], colorscale="Viridis",
        colorbar=dict(title="% identity", thickness=12),
        hovertemplate="%{x}<br>%{z:.0f}% identity<extra></extra>",
    ))
    # Outline each sequence-family block on the diagonal; label families via y-axis ticks
    # with automargin so Plotly reserves the space and never truncates the names.
    shapes = []
    pal = [BRAND["amber"], BRAND["green"], BRAND["red"], BRAND["primary_light"], "#9b51e0", "#ff6900"]
    tickvals, ticktext = [], []
    for k, b in enumerate(cl.get("blocks", [])):
        col = pal[k % len(pal)]
        s, e = b["start"] - 0.5, b["end"] + 0.5
        shapes.append(dict(type="rect", x0=s, x1=e, y0=s, y1=e,
                           line=dict(color=col, width=2), fillcolor="rgba(0,0,0,0)"))
        if b["size"] >= 2:
            tickvals.append((b["start"] + b["end"]) / 2)
            ticktext.append(f"{b['label']} ({b['size']})")
    fig.update_layout(
        title=f"Sequence-identity clustering of the worst offenders (n={n})",
        xaxis=dict(showticklabels=False, title="worst offenders, ordered by sequence similarity → (families outlined & labelled)"),
        yaxis=dict(autorange="reversed", showgrid=False, automargin=True,
                   tickmode="array", tickvals=tickvals, ticktext=ticktext, tickfont=dict(size=10)),
        shapes=shapes, margin=dict(r=24, t=88, b=56),
    )
    return _fig(fig)


def analysis_embedding(emb: dict) -> Optional[str]:
    if emb.get("n", 0) < 5:
        return None
    fig = go.Figure()
    # Draw 'unclassified' (grey) first so it sits behind the coloured, classified points.
    classes = sorted(set(emb["cath_class"]))
    classes = [c for c in classes if c == "unclassified"] + [c for c in classes if c != "unclassified"]
    for cls in classes:
        idx = [i for i, c in enumerate(emb["cath_class"]) if c == cls]
        fig.add_trace(go.Scatter(
            x=[emb["x"][i] for i in idx], y=[emb["y"][i] for i in idx], mode="markers", name=cls,
            marker=dict(color=_CATH_COLORS.get(cls, "#5b6b7a"),
                        size=[6 + 22 * (emb["fraud"][i] or 0) for i in idx],
                        line=dict(width=0.4, color="white"), opacity=0.78),
            customdata=[[emb["label"][i]] for i in idx],
            hovertemplate="<b>%{customdata[0]}</b><extra></extra>",
        ))
    fig.update_layout(title="Failure-mode map (PCA of the metric fingerprints)",
                      xaxis_title="PC1", yaxis_title="PC2",
                      legend=dict(orientation="h", y=1.09, x=0))
    return _fig(fig)


def analysis_themes(themes: dict) -> Optional[str]:
    c = themes.get("counts") or []
    if not any(t["n"] for t in c):
        return None
    colors = [BRAND["red"], BRAND["primary"], BRAND["amber"], BRAND["green"], BRAND["primary_light"]]
    fig = go.Figure(go.Bar(x=[t["theme"] for t in c], y=[t["n"] for t in c],
                           marker_color=colors[:len(c)]))
    fig.update_layout(title="Confidently-wrong by structural theme", yaxis_title="structures")
    return _fig(fig)


def analysis_correlates(corr: dict) -> Optional[str]:
    from plotly.subplots import make_subplots

    fig = make_subplots(rows=2, cols=2,
                        subplot_titles=("by method", "by resolution (Å)", "by chain length", "by novelty"))
    specs = [("method", 1, 1, BRAND["primary"]), ("resolution", 1, 2, BRAND["amber"]),
             ("length", 2, 1, BRAND["green"]), ("novelty", 2, 2, BRAND["red"])]
    for key, row, col, color in specs:
        data = corr.get(key) or []
        fig.add_trace(go.Bar(x=[d["bucket"] for d in data], y=[d["cw_rate"] for d in data],
                             marker_color=color), row=row, col=col)
    fig.update_layout(title="Confidently-wrong rate vs. structure attributes", showlegend=False, height=520)
    return _fig(fig)


def calibration_scatter(per_res: dict) -> str:
    plddt = per_res.get("plddt", [])
    lddt = per_res.get("lddt", [])
    xs = [p for p in plddt if p is not None]
    ys = [l * 100 for p, l in zip(plddt, lddt) if p is not None]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="markers", cliponaxis=False,
                             marker=dict(color=BRAND["primary"], size=5, opacity=0.6)))
    fig.add_trace(go.Scatter(x=[0, 100], y=[0, 100], mode="lines", name="ideal",
                             line=dict(color=BRAND["ink"], dash="dash", width=1)))
    fig.update_layout(title="Calibration: pLDDT vs. actual lDDT",
                      xaxis_title="pLDDT (predicted)", yaxis_title="per-residue lDDT ×100 (observed)",
                      showlegend=False)
    fig.update_xaxes(range=[-2, 102])
    fig.update_yaxes(range=[-2, 102])
    return _fig(fig)
