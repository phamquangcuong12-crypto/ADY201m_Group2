"""
ADY201m - Group 2 - Analysis Tool (Gradio dashboard)
Short-term aftershock forecasting, Japan-Kuril region.

Run from the repository root, after Notebooks A -> B -> C -> D:

    pip install -r dashboard/requirements.txt
    python dashboard/app.py

Every number on the dashboard is computed from files the notebooks wrote
(data/processed/*.parquet, report/table_*.csv). Nothing is typed in by hand.
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path

import gradio as gr
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression, PoissonRegressor
from sklearn.metrics import brier_score_loss, roc_auc_score

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
REP = ROOT / "report"

# ----------------------------------------------------------------------------
# Palette (matches the slide deck). Blue/orange pass the CVD check.
# ----------------------------------------------------------------------------
NAVY, BLUE, ORANGE, MUTED, INK = "#1F3864", "#2B6CB0", "#EA580C", "#94A3B8", "#2C2C2C"
DEPTH_SCALE = ["#C6DBEF", "#6BAED6", "#2171B5", "#08306B"]  # one hue, light -> dark = deeper
DEPTH_BANDS = ["0-30", "30-70", "70-150", "150-300", "300-700"]
REGIONS = {"South (24-34°N)": (24, 34), "Middle (34-40°N)": (34, 40), "North (40-46°N)": (40, 46.01)}

# ----------------------------------------------------------------------------
# Data (handoff files from the notebooks)
# ----------------------------------------------------------------------------
MAN = json.loads((PROC / "manifest.json").read_text(encoding="utf-8"))
RQ2 = json.loads((PROC / "rq2_summary.json").read_text(encoding="utf-8"))
RQ3 = json.loads((PROC / "rq3_summary.json").read_text(encoding="utf-8"))
MC = float(MAN["Mc"])
CUT = int(RQ2["cut_year"])
CAL_FROM = int(RQ2["calibration"]["window"][0])

MS = pd.read_parquet(PROC / "mainshocks_with_consequences.parquet")
MS["depth_bin"] = MS["depth_bin"].astype(str)
MS["date"] = MS["time"].dt.strftime("%Y-%m-%d")
MS["consequence"] = np.where(MS["has_any_consequence"] == 1, "With consequences", "Not recorded")

# ----------------------------------------------------------------------------
# RQ2 models, rebuilt exactly as in Notebook_B
#   Random Forest (mag+depth): n_estimators=400, max_depth=6, min_samples_leaf=8
#   Extended Omori: Poisson GLM on (M - Mc, depth/100), P = 1 - exp(-lambda)
#   Platt scaling: fit on year < 2006, calibrate on 2006-2015
# ----------------------------------------------------------------------------
FEATS = ["mag", "depth"]
y_all = MS["any_after"].values
tr = (MS["year"] <= CUT).values
te = ~tr
fit = (MS["year"] < CAL_FROM).values
cal = ((MS["year"] >= CAL_FROM) & (MS["year"] <= CUT)).values


def _rf():
    return RandomForestClassifier(n_estimators=400, max_depth=6, min_samples_leaf=8,
                                  random_state=0, n_jobs=-1)


def _om_x(df):
    return np.column_stack([(df["mag"] - MC).values, df["depth"].values / 100.0])


def _logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


# Model trained on 1990-2015, used for the reported test AUC
rf_main = _rf().fit(MS.loc[tr, FEATS], y_all[tr])
AUC_RF_TEST = roc_auc_score(y_all[te], rf_main.predict_proba(MS.loc[te, FEATS])[:, 1])

# Calibrated versions (what the forecast panel shows as a probability)
rf_fit = _rf().fit(MS.loc[fit, FEATS], y_all[fit])
platt_rf = LogisticRegression(C=1e6).fit(
    _logit(rf_fit.predict_proba(MS.loc[cal, FEATS])[:, 1])[:, None], y_all[cal])

om_fit = PoissonRegressor(alpha=1e-6, max_iter=5000).fit(_om_x(MS[fit]), MS.loc[fit, "n_after24h"].values)
platt_om = LogisticRegression(C=1e6).fit(
    _logit(1 - np.exp(-om_fit.predict(_om_x(MS[cal]))))[:, None], y_all[cal])


def p_rf(mag, depth):
    X = pd.DataFrame({"mag": np.atleast_1d(mag), "depth": np.atleast_1d(depth)}, dtype=float)
    return platt_rf.predict_proba(_logit(rf_fit.predict_proba(X)[:, 1])[:, None])[:, 1]


def p_om(mag, depth):
    X = pd.DataFrame({"mag": np.atleast_1d(mag), "depth": np.atleast_1d(depth)}, dtype=float)
    return platt_om.predict_proba(_logit(1 - np.exp(-om_fit.predict(_om_x(X))))[:, None])[:, 1]


BRIER_RF_TEST = brier_score_loss(y_all[te], p_rf(MS.loc[te, "mag"], MS.loc[te, "depth"]))

# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
LAYOUT = dict(template="plotly_white", font=dict(family="Calibri, Carlito, Arial, sans-serif", size=14, color=INK),
              margin=dict(l=60, r=24, t=64, b=56), paper_bgcolor="#FCFCFB", plot_bgcolor="#FCFCFB")


def _style(fig, title, subtitle=""):
    t = f"<b>{title}</b>" + (f"<br><span style='font-size:12px;color:#64748B'>{subtitle}</span>" if subtitle else "")
    fig.update_layout(title=dict(text=t, x=0, xanchor="left"), **LAYOUT)
    fig.update_xaxes(showgrid=False, linecolor="#CBD5E1")
    fig.update_yaxes(gridcolor="#EEF2F7", linecolor="#CBD5E1")
    return fig


def filter_df(year_from, year_to, mag_min, bands, regions):
    y0, y1 = sorted([int(year_from), int(year_to)])
    d = MS[(MS["year"] >= y0) & (MS["year"] <= y1) & (MS["mag"] >= float(mag_min))]
    d = d[d["depth_bin"].isin(bands or [])]
    if regions:
        m = np.zeros(len(d), dtype=bool)
        for r in regions:
            lo, hi = REGIONS[r]
            m |= ((d["latitude"] >= lo) & (d["latitude"] < hi)).values
        d = d[m]
    else:
        d = d.iloc[0:0]
    return d


def kpi_html(d):
    n = len(d)
    pos = d["any_after"].mean() * 100 if n else float("nan")
    med_depth = d["depth"].median() if n else float("nan")
    n_cons = int(d["has_any_consequence"].sum()) if n else 0
    n_tsu = int(d["has_tsunami"].sum()) if n else 0

    def card(label, value, note):
        return (f"<div class='kpi'><div class='kpi-v'>{value}</div>"
                f"<div class='kpi-l'>{label}</div><div class='kpi-n'>{note}</div></div>")

    fmt = lambda x, f: "-" if (isinstance(x, float) and np.isnan(x)) else f.format(x)
    return ("<div class='kpis'>"
            + card("Mainshock sequences", f"{n:,}", "M ≥ 5.5, after declustering")
            + card("With aftershock ≤ 24 h", fmt(pos, "{:.1f}%"), "within 100 km, M ≥ Mc 4.6")
            + card("Median depth", fmt(med_depth, "{:.1f} km"), "of the selected sequences")
            + card("With recorded consequences", f"{n_cons:,}", f"NOAA/NCEI · {n_tsu} with tsunami")
            + card("Best model test AUC", f"{AUC_RF_TEST:.3f}", "Random Forest (mag + depth), 2016-2026")
            + "</div>")


# ----------------------------------------------------------------------------
# RQ1 charts
# ----------------------------------------------------------------------------
def fig_map(d):
    # Plain lon/lat axes (no basemap download needed, so it works offline)
    fig = px.scatter(d, x="longitude", y="latitude", color="depth", size="mag", size_max=14,
                     color_continuous_scale=DEPTH_SCALE, range_color=(0, 700),
                     hover_name="place",
                     hover_data={"date": True, "mag": ":.1f", "depth": ":.1f", "n_after24h": True,
                                 "latitude": False, "longitude": False})
    fig.update_traces(marker=dict(line=dict(width=0.5, color="#FCFCFB"), opacity=0.9))
    fig.update_layout(coloraxis_colorbar=dict(title="Depth (km)"), height=520,
                      xaxis=dict(title="Longitude (°E)", range=[121, 151]),
                      yaxis=dict(title="Latitude (°N)", range=[23, 47], scaleanchor="x", scaleratio=1.2))
    return _style(fig, "RQ1 · Where the mainshocks are",
                  f"{len(d):,} sequences · color = depth · size = magnitude · hover for details")


def fig_depth_bar(d):
    g = (d.groupby("depth_bin", observed=False)["any_after"].agg(["mean", "size"])
           .reindex(DEPTH_BANDS).fillna(0).reset_index())
    g["pct"] = g["mean"] * 100
    g["label"] = [f"{p:.1f}%<br>n={int(n)}" for p, n in zip(g["pct"], g["size"])]
    fig = go.Figure(go.Bar(x=g["depth_bin"], y=g["pct"], marker_color=BLUE, text=g["label"],
                           textposition="outside", marker_line_width=0,
                           hovertemplate="Depth %{x} km<br>%{y:.1f}% with an aftershock<extra></extra>"))
    fig.update_layout(height=520, yaxis=dict(title="% with ≥ 1 aftershock within 24 h", range=[0, 100]),
                      xaxis=dict(title="Depth band (km)"), bargap=0.35)
    return _style(fig, "RQ1 · The deeper, the fewer aftershocks", "share of sequences, by depth band")


# ----------------------------------------------------------------------------
# RQ2 charts
# ----------------------------------------------------------------------------
def forecast(mag, depth):
    prf, pom = float(p_rf(mag, depth)[0]), float(p_om(mag, depth)[0])
    html = ("<div class='kpis'>"
            f"<div class='kpi'><div class='kpi-v'>{prf*100:.0f}%</div><div class='kpi-l'>Random Forest (mag + depth)</div>"
            "<div class='kpi-n'>Platt-calibrated probability of ≥ 1 aftershock within 24 h / 100 km</div></div>"
            f"<div class='kpi'><div class='kpi-v'>{pom*100:.0f}%</div><div class='kpi-l'>Extended Omori (Poisson GLM)</div>"
            "<div class='kpi-n'>same inputs, 2-variable physics model, Platt-calibrated</div></div>"
            "</div>")
    depths = np.arange(0, 701, 5)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=depths, y=p_rf(np.full(len(depths), mag), depths) * 100, mode="lines",
                             name="Random Forest", line=dict(color=BLUE, width=2),
                             hovertemplate="depth %{x} km<br>RF %{y:.1f}%<extra></extra>"))
    fig.add_trace(go.Scatter(x=depths, y=p_om(np.full(len(depths), mag), depths) * 100, mode="lines",
                             name="Extended Omori", line=dict(color=ORANGE, width=2, dash="dash"),
                             hovertemplate="depth %{x} km<br>Omori %{y:.1f}%<extra></extra>"))
    fig.add_trace(go.Scatter(x=[depth], y=[prf * 100], mode="markers", name="Your input",
                             marker=dict(size=12, color=NAVY, line=dict(width=2, color="#FCFCFB")),
                             hovertemplate="your input<br>%{y:.1f}%<extra></extra>"))
    fig.update_layout(height=440, hovermode="x unified", yaxis=dict(title="Probability (%)", range=[0, 100]),
                      xaxis=dict(title="Mainshock depth (km)"),
                      legend=dict(orientation="h", y=-0.2))
    return html, _style(fig, f"RQ2 · Forecast vs depth at M {mag:.1f}",
                        "both models trained on 1990-2005, calibrated on 2006-2015")


def fig_models():
    m = pd.read_csv(REP / "table_rq2_models.csv")[["model", "AUC_test"]]
    base = pd.DataFrame({"model": ["Naive (majority class)", "Omori-Utsu (magnitude only)", "Extended Omori (mag + depth)"],
                         "AUC_test": [RQ2["naive_auc"], RQ2["omori_auc"], RQ2["omori_extended_auc"]]})
    m["kind"], base["kind"] = "Machine learning", "Baseline"
    d = pd.concat([m, base]).sort_values("AUC_test")
    fig = px.bar(d, x="AUC_test", y="model", color="kind", orientation="h", text="AUC_test",
                 color_discrete_map={"Machine learning": BLUE, "Baseline": ORANGE})
    fig.update_traces(texttemplate="%{x:.3f}", textposition="outside", marker_line_width=0,
                      hovertemplate="%{y}<br>test AUC %{x:.3f}<extra></extra>")
    fig.update_layout(height=520, xaxis=dict(title="Test AUC, 2016-2026 (higher is better)", range=[0.4, 0.95]),
                      yaxis=dict(title=None), legend=dict(title=None, orientation="h", y=-0.18), bargap=0.3)
    return _style(fig, "RQ2 · Models against the baselines", "from report/table_rq2_models.csv and rq2_summary.json")


# ----------------------------------------------------------------------------
# RQ3 charts
# ----------------------------------------------------------------------------
def fig_robust():
    rows = []
    for f, grp, col in [("table_rq3_label_threshold.csv", "Label threshold", "label_threshold"),
                        ("table_rq3_mainshock_threshold.csv", "Mainshock threshold", "mainshock_threshold"),
                        ("table_rq3_tohoku.csv", "Tohoku 2011", "scenario"),
                        ("table_rq3_region.csv", "Region held out", "held_out_region"),
                        ("table_rq3_declustering.csv", "Declustering", "method"),
                        ("table_rq3_fixed_depth.csv", "Default depths", "scenario")]:
        t = pd.read_csv(REP / f)
        for _, r in t.iterrows():
            rows.append({"check": grp, "scenario": f"{grp}: {r[col]}", "AUC_test": r["AUC_test"], "gap": r.get("gap", np.nan)})
    d = pd.DataFrame(rows).iloc[::-1]
    fig = go.Figure(go.Bar(x=d["AUC_test"], y=d["scenario"], orientation="h", marker_color=BLUE, marker_line_width=0,
                           text=[f"{a:.3f}" for a in d["AUC_test"]], textposition="outside",
                           customdata=d["gap"], hovertemplate="%{y}<br>test AUC %{x:.3f}<br>train-test gap %{customdata:.3f}<extra></extra>"))
    fig.add_vline(x=RQ3["auc"], line=dict(color=ORANGE, dash="dash", width=2),
                  annotation_text=f"main result {RQ3['auc']:.3f}", annotation_position="top")
    fig.update_layout(height=620, xaxis=dict(title="Test AUC", range=[0.6, 0.92]), yaxis=dict(title=None), bargap=0.3)
    return _style(fig, "RQ3 · Does the result hold when assumptions change?",
                  f"bootstrap CI95 [{RQ3['ci95'][0]:.3f}, {RQ3['ci95'][1]:.3f}] · hover for the train-test gap")


def table_diagnosis():
    return pd.read_csv(REP / "table_rq3_diagnosis.csv")


# ----------------------------------------------------------------------------
# RQ4 charts
# ----------------------------------------------------------------------------
def fig_consequence_scatter(d):
    fig = px.scatter(d.sort_values("has_any_consequence"), x="mag", y="depth", color="consequence",
                     color_discrete_map={"With consequences": ORANGE, "Not recorded": MUTED},
                     category_orders={"consequence": ["With consequences", "Not recorded"]},
                     hover_name="place",
                     hover_data={"date": True, "deathsTotal": True, "damageMillionsDollars": True,
                                 "consequence": False, "mag": ":.1f", "depth": ":.1f"})
    fig.update_traces(marker=dict(size=9, line=dict(width=1, color="#FCFCFB")))
    fig.update_layout(height=520, yaxis=dict(title="Depth (km, deeper = lower)", autorange="reversed"),
                      xaxis=dict(title="Mainshock magnitude"), legend=dict(title=None, orientation="h", y=-0.18))
    n = int(d["has_any_consequence"].sum())
    return _style(fig, "RQ4 · Which sequences leave consequences",
                  f"{n} of {len(d)} selected sequences have deaths, damage or a tsunami in NOAA/NCEI")


def fig_consequence_bar(d):
    d = d.assign(shallow=np.where(d["depth"] < 70, "Shallow (< 70 km)", "Deep (≥ 70 km)"))
    g = d.groupby("shallow")["has_any_consequence"].agg(["mean", "sum", "size"]).reindex(
        ["Shallow (< 70 km)", "Deep (≥ 70 km)"]).fillna(0).reset_index()
    g["pct"] = g["mean"] * 100
    fig = go.Figure(go.Bar(x=g["shallow"], y=g["pct"], marker_color=[ORANGE, BLUE], marker_line_width=0,
                           text=[f"{p:.1f}%<br>{int(s)} of {int(n)}" for p, s, n in zip(g["pct"], g["sum"], g["size"])],
                           textposition="outside", hovertemplate="%{x}<br>%{y:.1f}% with consequences<extra></extra>"))
    top = max(20, g["pct"].max() * 1.3) if len(g) else 20
    fig.update_layout(height=520, yaxis=dict(title="% with recorded consequences", range=[0, top]),
                      xaxis=dict(title=None), bargap=0.45)
    return _style(fig, "RQ4 · Consequences by depth", "absence from NCEI means not recorded, not proof of no consequences")


def table_top(d):
    t = d[d["has_any_consequence"] == 1].sort_values(["deathsTotal", "mag"], ascending=False, na_position="last")
    t = t[["date", "place", "mag", "depth", "n_after24h", "deathsTotal", "damageMillionsDollars", "has_tsunami"]].head(10)
    return t.rename(columns={"n_after24h": "aftershocks_24h", "deathsTotal": "deaths",
                             "damageMillionsDollars": "damage_musd", "has_tsunami": "tsunami"})


# ----------------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------------
CSS = """
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}
.kpi{background:#EEF2FF;border:1px solid #C5CAE9;border-radius:10px;padding:14px 16px}
.kpi-v{font-size:30px;font-weight:700;color:#1F3864;line-height:1.1}
.kpi-l{font-size:14px;font-weight:700;color:#2C2C2C;margin-top:4px}
.kpi-n{font-size:12px;color:#4A5568;margin-top:2px}
.rq{font-size:13px;color:#4A5568}
"""


def update_all(y0, y1, mag_min, bands, regions):
    d = filter_df(y0, y1, mag_min, bands, regions)
    return (kpi_html(d), fig_map(d), fig_depth_bar(d),
            fig_consequence_scatter(d), fig_consequence_bar(d), table_top(d))


THEME = gr.themes.Soft(primary_hue="blue")
_LAUNCH_TAKES_CSS = "css" in inspect.signature(gr.Blocks.launch).parameters   # Gradio 6+
_BLOCKS_KW = {} if _LAUNCH_TAKES_CSS else {"css": CSS, "theme": THEME}         # Gradio 4/5

with gr.Blocks(title="Japan-Kuril Aftershock Dashboard", **_BLOCKS_KW) as demo:
    gr.Markdown("## Short-term Aftershock Forecasting · Japan-Kuril Region, 1990-2026\n"
                "ADY201m · Group 2 · Sources: USGS ANSS ComCat and NOAA/NCEI. "
                "All values are computed live from `data/processed` and `report/`.")
    with gr.Row():
        y_from = gr.Slider(1990, 2026, value=1990, step=1, label="From year")
        y_to = gr.Slider(1990, 2026, value=2026, step=1, label="To year")
        mag_min = gr.Slider(5.5, 9.1, value=5.5, step=0.1, label="Minimum mainshock magnitude")
    with gr.Row():
        bands = gr.CheckboxGroup(DEPTH_BANDS, value=DEPTH_BANDS, label="Depth band (km)")
        regions = gr.CheckboxGroup(list(REGIONS), value=list(REGIONS), label="Region (latitude)")
    kpis = gr.HTML()

    with gr.Tabs():
        with gr.Tab("RQ1 · Distribution & depth"):
            gr.Markdown("<span class='rq'>Answers RQ1: how events are distributed and whether depth relates to "
                        "aftershock productivity. Responds to all filters.</span>")
            with gr.Row():
                map_plot = gr.Plot(show_label=False)
                bar_plot = gr.Plot(show_label=False)
        with gr.Tab("RQ2 · 24-hour forecast"):
            gr.Markdown("<span class='rq'>Answers RQ2. Enter a mainshock; the models are fixed "
                        f"(Random Forest test AUC {AUC_RF_TEST:.3f}, Brier {BRIER_RF_TEST:.3f} after Platt). "
                        "A method demo on USGS data, not an operational forecast.</span>")
            with gr.Row():
                f_mag = gr.Slider(5.5, 9.1, value=6.5, step=0.1, label="Mainshock magnitude")
                f_depth = gr.Slider(0, 700, value=20, step=5, label="Mainshock depth (km)")
            f_out = gr.HTML()
            with gr.Row():
                f_plot = gr.Plot(show_label=False)
                m_plot = gr.Plot(value=fig_models(), show_label=False)
        with gr.Tab("RQ3 · Robustness"):
            gr.Markdown("<span class='rq'>Answers RQ3: the main result under each changed assumption "
                        "(Notebook_C tables).</span>")
            gr.Plot(value=fig_robust(), show_label=False)
            gr.Dataframe(value=table_diagnosis(), wrap=True, label="Diagnosis, verdict thresholds set in advance")
        with gr.Tab("RQ4 · Consequences"):
            gr.Markdown("<span class='rq'>Answers RQ4 with the NOAA/NCEI join. Responds to all filters.</span>")
            with gr.Row():
                c_scatter = gr.Plot(show_label=False)
                c_bar = gr.Plot(show_label=False)
            c_table = gr.Dataframe(label="Top 10 sequences with consequences (by deaths)", wrap=True)

    inputs = [y_from, y_to, mag_min, bands, regions]
    outputs = [kpis, map_plot, bar_plot, c_scatter, c_bar, c_table]
    for comp in inputs:
        comp.change(update_all, inputs, outputs)
    for comp in (f_mag, f_depth):
        comp.change(forecast, [f_mag, f_depth], [f_out, f_plot])
    demo.load(update_all, inputs, outputs)
    demo.load(forecast, [f_mag, f_depth], [f_out, f_plot])


if __name__ == "__main__":
    demo.launch(**({"css": CSS, "theme": THEME} if _LAUNCH_TAKES_CSS else {}))
