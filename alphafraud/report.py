"""Plotly figure builders. Each returns a JSON string (fig.to_json()) that a template
embeds and renders with the vendored plotly.min.js. Kept free of Flask so it can also be
used from the CLI or notebooks.

The signature figure is the "fraud quadrant": AlphaFold confidence (pLDDT) vs. how right it
actually was (TM-score). High-confidence / low-TM = confidently wrong.
"""

from __future__ import annotations

import json
from typing import Optional

import plotly.graph_objects as go

from . import config

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


def fraud_scatter(entities: list[dict]) -> str:
    points, omitted = _downsample_points(entities)
    fig = go.Figure()
    # Shade the fraud quadrant: confident (pLDDT > threshold) yet wrong (TM < threshold).
    fig.add_shape(
        type="rect", x0=config.CONFIDENT_PLDDT, x1=102, y0=0, y1=config.WRONG_TM,
        fillcolor="rgba(214,39,40,0.08)", line=dict(width=0), layer="below",
    )
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
                         e.get("novelty_identity")] for e in pts],
            hovertemplate=("<b>%{customdata[0]}</b> (%{customdata[1]})<br>"
                           "pLDDT %{x:.1f} · TM %{y:.3f}<br>"
                           "FRAUD %{customdata[2]:.3f} · novelty id %{customdata[3]}%<extra></extra>"),
        ))
    # Second legend, to the right of the colour legend, explaining that marker size = FRAUD.
    for frac in (0.1, 0.5):
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers", name=f"FRAUD {frac}", legend="legend2",
            marker=dict(color="rgba(120,140,160,0.75)", size=6 + 20 * frac, line=dict(width=0.4, color="white")),
        ))
    fig.update_layout(
        title="AlphaFold confidence vs. agreement with experiment",
        xaxis_title="mean pLDDT (AlphaFold confidence)",
        yaxis_title="TM-score to experiment",
        legend=dict(orientation="h", y=1.09, x=0, itemsizing="constant"),
        legend2=dict(orientation="h", y=1.09, x=0.58, itemsizing="trace",
                     title=dict(text="marker size:"), font=dict(size=11)),
    )
    fig.update_xaxes(range=[0, 102])       # headroom so pLDDT~100 markers sit inside the frame
    fig.update_yaxes(range=[0, 1.03])
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

    fig = make_subplots(rows=1, cols=3, subplot_titles=("TM-score", "Cα-RMSD (Å)", "lDDT"))
    fig.add_trace(go.Histogram(x=[e["tm_by_experiment"] for e in entities if e.get("tm_by_experiment") is not None],
                               marker_color=BRAND["primary"], nbinsx=25), row=1, col=1)
    fig.add_trace(go.Histogram(x=[e["ca_rmsd"] for e in entities if e.get("ca_rmsd") is not None],
                               marker_color=BRAND["amber"], nbinsx=25), row=1, col=2)
    fig.add_trace(go.Histogram(x=[e["lddt"] for e in entities if e.get("lddt") is not None],
                               marker_color=BRAND["green"], nbinsx=25), row=1, col=3)
    fig.update_layout(title="Metric distributions", showlegend=False)
    return _fig(fig)


# --------------------------------------------------------------------------------------
# Trend across weeks
# --------------------------------------------------------------------------------------
def trend_figure(weekly: list[dict]) -> str:
    """weekly: list of {label, mean_tm, confidently_wrong, n_compared} oldest->newest."""
    fig = go.Figure()
    labels = [w["label"] for w in weekly]
    fig.add_trace(go.Scatter(x=labels, y=[w.get("mean_tm") for w in weekly], name="mean TM-score",
                             mode="lines+markers", line=dict(color=BRAND["primary"], width=2), yaxis="y"))
    fig.add_trace(go.Bar(x=labels, y=[w.get("confidently_wrong") for w in weekly], name="confidently wrong",
                         marker_color=BRAND["red"], opacity=0.5, yaxis="y2"))
    fig.update_layout(
        title="Weekly trend",
        yaxis=dict(title="mean TM-score", range=[0, 1]),
        yaxis2=dict(title="# confidently wrong", overlaying="y", side="right", showgrid=False),
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


def analysis_sunburst(sb: dict) -> Optional[str]:
    if not sb.get("ids"):
        return None
    fig = go.Figure(go.Sunburst(
        ids=sb["ids"], labels=sb["labels"], parents=sb["parents"], values=sb["values"],
        branchvalues="total", insidetextorientation="radial",
        marker=dict(colors=list(range(len(sb["ids"]))), colorscale="Blues", line=dict(width=1, color="white")),
        hovertemplate="<b>%{label}</b><br>%{value} confidently wrong<extra></extra>",
    ))
    fig.update_layout(title="Confidently-wrong by CATH fold hierarchy")
    return _fig(fig)


def analysis_cluster_heatmap(cl: dict) -> Optional[str]:
    if cl.get("n", 0) < 4:
        return None
    fig = go.Figure(go.Heatmap(
        z=cl["matrix"], x=cl["order_labels"], y=cl["order_labels"], colorscale="Viridis",
        colorbar=dict(title="% id", thickness=12),
        hovertemplate="%{y} vs %{x}<br>%{z:.0f}% identity<extra></extra>",
    ))
    fig.update_layout(title=f"Sequence-identity clustering of the worst offenders (n={cl['n']})",
                      yaxis=dict(autorange="reversed", scaleanchor="x"),
                      xaxis=dict(showticklabels=False), margin=dict(l=60, r=24, t=88, b=40))
    return _fig(fig)


def analysis_embedding(emb: dict) -> Optional[str]:
    if emb.get("n", 0) < 5:
        return None
    fig = go.Figure()
    for cls in sorted(set(emb["cath_class"])):
        idx = [i for i, c in enumerate(emb["cath_class"]) if c == cls]
        fig.add_trace(go.Scatter(
            x=[emb["x"][i] for i in idx], y=[emb["y"][i] for i in idx], mode="markers", name=cls,
            marker=dict(size=[6 + 22 * (emb["fraud"][i] or 0) for i in idx],
                        line=dict(width=0.4, color="white"), opacity=0.75),
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
