import os
import logging
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from flask import Blueprint, render_template, request
from flask_login import current_user

# High-level InterOp Python API alongside low-level binary loading utilities
from interop import (
    py_interop_run, 
    py_interop_run_metrics, 
    imaging, 
    summary, 
    indexing, 
    index_summary
)

from interop.core import summary as interop_summary

from idms.common.irods.irods_sessions import irods_manager

bp = Blueprint('websav', __name__, url_prefix='/websav')

CHANNEL_COLORS = {
    'A': '#2ca02c', 'C': '#1f77b4', 'G': '#000000', 'T': '#d62728',
    'green': '#2ca02c', 'blue': '#1f77b4', 'red': '#d62728'
}

METRIC_ENUM_MAP = {
    "QMetrics": py_interop_run.Q,
    "TileMetrics": py_interop_run.Tile,
    "ExtendedTileMetrics": py_interop_run.ExtendedTile,
    "ExtractionMetrics": py_interop_run.Extraction,
    "ErrorMetrics": py_interop_run.Error,
    "CorrectedIntMetrics": py_interop_run.CorrectedInt,
    "IndexMetrics": py_interop_run.Index,
}


def read_irods_file_to_bytes(session, path):
    """Reads an iRODS data object directly into memory as bytes."""
    try:
        obj = session.data_objects.get(path)
        with obj.open('r') as f:
            return f.read()
    except Exception as e:
        logging.warning(f"Failed to read file from iRODS: {path} - {e}")
        return None


def parse_run_info_cycles(run_info_bytes):
    """Extracts read boundaries from RunInfo.xml byte content."""
    if not run_info_bytes:
        return []
    try:
        root = ET.fromstring(run_info_bytes)
        reads = root.findall(".//Read")
        cycles = [int(r.attrib['NumCycles']) for r in reads[:-1]] if len(reads) > 1 else [int(r.attrib['NumCycles']) for r in reads]
        return list(np.cumsum(cycles))
    except Exception as e:
        logging.error(f"Error parsing RunInfo.xml: {e}")
        return []


def load_interop_metrics(session, collection_path):
    metrics = py_interop_run_metrics.run_metrics()
    
    # 1. Fetch RunInfo.xml from iRODS and write to a temporary file
    try:
        runinfo_path = f"{collection_path.rstrip('/')}/RunInfo.xml"
        runinfo_obj = session.data_objects.get(runinfo_path)
        
        with runinfo_obj.open('r') as f:
            xml_data = f.read()
            
        xml_bytes = xml_data.encode('utf-8') if isinstance(xml_data, str) else xml_data

        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_xml_path = os.path.join(tmp_dir, "RunInfo.xml")
            with open(temp_xml_path, "wb") as f:
                f.write(xml_bytes)
            
            for param_name in ["RunParameters.xml", "runParameters.xml"]:
                try:
                    param_obj = session.data_objects.get(f"{collection_path.rstrip('/')}/{param_name}")
                    with param_obj.open('r') as pf:
                        p_data = pf.read()
                        p_bytes = p_data.encode('utf-8') if isinstance(p_data, str) else p_data
                    
                    with open(os.path.join(tmp_dir, param_name), "wb") as pf:
                        pf.write(p_bytes)
                    break
                except Exception:
                    continue

            metrics.read_xml(tmp_dir)

    except Exception as e:
        logging.warning(f"Could not load RunInfo.xml: {e}")

    # 2. Process binary metrics from iRODS into NumPy uint8 arrays
    interop_dir = f"{collection_path.rstrip('/')}/InterOp"
    coll = session.collections.get(interop_dir)

    for data_obj in coll.data_objects:
        if not data_obj.name.endswith(".bin"):
            continue

        for prefix, metric_group in METRIC_ENUM_MAP.items():
            if data_obj.name.startswith(prefix):
                print(f'LOAD : {data_obj.name}')
                with data_obj.open('r') as f:
                    raw_data = f.read()
                raw_bytes = raw_data.encode('latin1') if isinstance(raw_data, str) else bytes(raw_data)
                buffer_array = np.frombuffer(raw_bytes, dtype=np.uint8)
                try:
                    metrics.read_metrics_from_buffer(metric_group, buffer_array)
                except Exception as e:
                    logging.warning(f"Failed loading buffer {data_obj.name}: {e}")
                break

    # 3. Finalize internal state after buffer population
    metrics.finalize_after_load()

    # 4. Extract cycle boundaries
    cycle_boundaries = []
    reads = metrics.run_info().reads()
    cum_cycles = 0
    
    for r in range(reads.size()):
        read = reads[r]
        cum_cycles += read.total_cycles()
        cycle_boundaries.append(cum_cycles)

    return metrics, cycle_boundaries


# --- High-Level Figure Generators ---

def q30bycycle(metrics, cycle_boundaries):
    fig = go.Figure()
    if not metrics:
        return pio.to_html(fig, full_html=False)

    df = pd.DataFrame()

    # 1. Try fetching from high-level imaging table
    img_data = imaging(metrics)
    if img_data is not None and len(img_data) > 0:
        temp_df = pd.DataFrame(img_data)
        # Look for matching Q30 column names
        q30_cols = [c for c in temp_df.columns if 'q30' in c.lower()]
        if q30_cols:
            df = temp_df
            q30_col = q30_cols[0]
            df['Q30_Val'] = df[q30_col]

    # 2. Fallback: Revert to direct Q-metric set parsing if high-level table lacks Q30
    if df.empty or 'Q30_Val' not in df.columns:
        q_metrics = metrics.q_metric_set()
        data = []
        for i in range(q_metrics.size()):
            item = q_metrics.at(i)
            cycle = item.cycle()
            hist = item.qscore_hist()
            hist_size = len(hist) if hasattr(hist, '__len__') else hist.size()

            if hist_size > 30:
                total_q30 = sum(item.qscore_hist(q) for q in range(30, hist_size))
                total_bases = sum(item.qscore_hist(q) for q in range(hist_size))
            else:
                total_q30 = item.qscore_hist(hist_size - 1)
                total_bases = sum(item.qscore_hist(q) for q in range(hist_size))

            if total_bases > 0:
                data.append({
                    "Cycle": cycle,
                    "Q30_Val": (total_q30 / total_bases) * 100.0
                })

        if data:
            df = pd.DataFrame(data)

    # 3. Render Graph
    if not df.empty and 'Q30_Val' in df.columns:
        df = df[df['Q30_Val'] >= 0]
        grouped = df.groupby("Cycle")["Q30_Val"].mean().reset_index()

        fig.add_trace(go.Box(x=df["Cycle"], y=df["Q30_Val"], line=dict(color="blue"), name="Q30"))
        fig.add_trace(go.Scatter(x=grouped["Cycle"], y=grouped["Q30_Val"], name="Mean Q30", mode="lines"))

        for h in cycle_boundaries:
            fig.add_vline(x=h, line_width=1, line_dash="dash", line_color="black")

    fig.update_layout(
        title="Q30 by Cycle",
        xaxis={"title": "Cycle"},
        yaxis={"title": "%>= Q30", "range": [0, 100]},
        showlegend=False
    )
    return pio.to_html(fig, full_html=False)


def intensitybycycle(metrics, cycle_boundaries):
    fig = go.Figure()
    img_data = imaging(metrics)

    if img_data is not None and len(img_data) > 0:
        df = pd.DataFrame(img_data)
        corr_cols = [c for c in df.columns if c.startswith('Corrected/')]

        for col in corr_cols:
            base = col.split('/')[-1]
            grouped = df.groupby("Cycle")[col].mean().reset_index()

            fig.add_trace(go.Scatter(
                x=grouped["Cycle"],
                y=grouped[col],
                mode="lines",
                name=f"Base {base}",
                line=dict(color=CHANNEL_COLORS.get(base, "grey"))
            ))

        for h in cycle_boundaries:
            fig.add_vline(x=h, line_width=1, line_dash="dash", line_color="black")

    fig.update_layout(
        title="Intensity by Cycle",
        xaxis={"title": "Cycle"},
        yaxis={"title": "Intensity"},
        showlegend=True
    )
    return pio.to_html(fig, full_html=False)


def base_percent_by_cycle(metrics, cycle_boundaries):
    fig = go.Figure()
    img_data = imaging(metrics)

    if img_data is not None and len(img_data) > 0:
        df = pd.DataFrame(img_data)
        base_cols = [c for c in df.columns if c.startswith('% Base/')]

        for col in base_cols:
            base = col.split('/')[-1]
            grouped = df.groupby("Cycle")[col].mean().reset_index()

            fig.add_trace(go.Scatter(
                x=grouped["Cycle"],
                y=grouped[col],
                mode="lines",
                name=f"%{base}",
                line=dict(color=CHANNEL_COLORS.get(base, "grey"))
            ))

        for h in cycle_boundaries:
            fig.add_vline(x=h, line_width=1, line_dash="dash", line_color="black")

    fig.update_layout(
        title="% Base by Cycle",
        xaxis={"title": "Cycle"},
        yaxis={"title": "% Base", "range": [0, 100]},
        showlegend=True
    )
    return pio.to_html(fig, full_html=False)


def fwhm_by_cycle(metrics, cycle_boundaries):
    fig = go.Figure()
    img_data = imaging(metrics)

    if img_data is not None and len(img_data) > 0:
        df = pd.DataFrame(img_data)
        fwhm_cols = [c for c in df.columns if c.startswith('Fwhm/')]

        for col in fwhm_cols:
            ch_name = col.split('/')[-1]
            grouped = df.groupby("Cycle")[col].mean().reset_index()
            grouped = grouped[grouped[col] > 0]

            if not grouped.empty:
                fig.add_trace(go.Scatter(
                    x=grouped["Cycle"],
                    y=grouped[col],
                    mode="lines",
                    name=f"Channel {ch_name}",
                    line=dict(color=CHANNEL_COLORS.get(ch_name, "grey"))
                ))

        for h in cycle_boundaries:
            fig.add_vline(x=h, line_width=1, line_dash="dash", line_color="black")

    fig.update_layout(
        title="FWHM by Cycle",
        xaxis={"title": "Cycle"},
        yaxis={"title": "FWHM"},
        showlegend=True
    )
    return pio.to_html(fig, full_html=False)

def pf_vs_occupied(metrics):
    """
    SAV-style Custom Plot:
        X-axis: % Occupied
        Y-axis: % Pass Filter

    One point per tile.
    """
    fig = go.Figure()

    if not metrics:
        return pio.to_html(fig, full_html=False)

    try:
        img_data = imaging(metrics)

        if img_data is None or len(img_data) == 0:
            logging.warning("No imaging metrics available")
            return pio.to_html(fig, full_html=False)

        df = pd.DataFrame(img_data)

        # Useful while developing:
        logging.info(f"Imaging columns: {list(df.columns)}")

        # Expected InterOp Imaging table names
        occupied_col = "% Occupied"
        pf_col = "% Pass Filter"

        if occupied_col not in df.columns or pf_col not in df.columns:
            logging.warning(
                f"Required columns unavailable. "
                f"Need '{occupied_col}' and '{pf_col}'. "
                f"Available columns: {list(df.columns)}"
            )

            fig.add_annotation(
                text="% Occupied / % Pass Filter metrics not available",
                showarrow=False
            )

            return pio.to_html(fig, full_html=False)

        # Keep identifiers + metrics
        columns = ["Lane", "Tile", occupied_col, pf_col]
        plot_df = df[columns].copy()

        # Make sure values are numeric
        plot_df[occupied_col] = pd.to_numeric(
            plot_df[occupied_col],
            errors="coerce"
        )
        plot_df[pf_col] = pd.to_numeric(
            plot_df[pf_col],
            errors="coerce"
        )

        # Remove rows without either metric
        plot_df = plot_df.dropna(
            subset=[occupied_col, pf_col]
        )

        # imaging() is cycle based, while these are tile-level metrics.
        # Therefore the same tile values can occur on many cycle rows.
        # We want one point per tile.
        plot_df = plot_df.drop_duplicates(
            subset=["Lane", "Tile"]
        )

        # Plot lane separately so lanes can be distinguished
        for lane, lane_df in plot_df.groupby("Lane"):
            fig.add_trace(
                go.Scatter(
                    x=lane_df[occupied_col],
                    y=lane_df[pf_col],
                    mode="markers",
                    name=f"Lane {int(lane)}",
                    customdata=lane_df[["Tile"]],
                    hovertemplate=(
                        "Lane: " + str(int(lane)) +
                        "<br>Tile: %{customdata[0]}" +
                        "<br>% Occupied: %{x:.2f}%" +
                        "<br>% Pass Filter: %{y:.2f}%" +
                        "<extra></extra>"
                    )
                )
            )

    except Exception as e:
        logging.warning(f"Failed generating PF vs Occupied plot: {e}")

    fig.update_layout(
        title="Custom Plot: % Passing Filter vs % Occupied",
        xaxis={
            "title": "% Occupied",
            "range": [0, 100]
        },
        yaxis={
            "title": "% Passing Filter",
            "range": [0, 100]
        }
    )

    return pio.to_html(fig, full_html=False)


def snr_by_cycle(metrics, cycle_boundaries):
    fig = go.Figure()
    img_data = imaging(metrics)

    if img_data is not None and len(img_data) > 0:
        df = pd.DataFrame(img_data)

        if 'Signal To Noise' in df.columns:
            grouped = df.groupby("Cycle")['Signal To Noise'].mean().reset_index()
            grouped = grouped[grouped['Signal To Noise'] > 0]

            if not grouped.empty:
                fig.add_trace(go.Scatter(
                    x=grouped["Cycle"],
                    y=grouped['Signal To Noise'],
                    mode="lines",
                    name="SNR",
                    line=dict(color="#1f77b4")
                ))

        for h in cycle_boundaries:
            fig.add_vline(x=h, line_width=1, line_dash="dash", line_color="black")

    fig.update_layout(
        title="Signal-to-Noise Ratio (SNR) by Cycle",
        xaxis={"title": "Cycle"},
        yaxis={"title": "SNR"},
        showlegend=True
    )
    return pio.to_html(fig, full_html=False)


def clusterlane(metrics):
    fig = go.Figure()
    sum_data = summary(metrics, level="Lane")

    if sum_data is not None and len(sum_data) > 0:
        df = pd.DataFrame(sum_data)
        if 'Density' in df.columns and 'Density Pf' in df.columns:
            fig.add_trace(go.Box(x=df['Lane'], y=df['Density'] / 1000.0, line=dict(color="blue"), name="Raw Cluster Density"))
            fig.add_trace(go.Box(x=df['Lane'], y=df['Density Pf'] / 1000.0, line=dict(color="green"), name="Cluster Density PF"))

    fig.update_layout(title="Cluster Density by Lane (k/mm²)", xaxis={"title": "Lane"}, yaxis={"title": "Density (k/mm²)"})
    return pio.to_html(fig, full_html=False)


def error_rate_by_cycle(metrics, cycle_boundaries):
    fig = go.Figure()
    img_data = imaging(metrics)

    if img_data is not None and len(img_data) > 0:
        df = pd.DataFrame(img_data)

        if 'Error Rate' in df.columns:
            df = df[df['Error Rate'] >= 0]
            avg_df = df.groupby("Cycle")["Error Rate"].mean().reset_index()

            fig.add_trace(go.Box(
                x=df["Cycle"], 
                y=df["Error Rate"], 
                name="Error Rate Dist", 
                marker_color="red"
            ))
            fig.add_trace(go.Scatter(
                x=avg_df["Cycle"], 
                y=avg_df["Error Rate"], 
                mode="lines", 
                name="Mean Error Rate", 
                line=dict(color="darkred", width=2)
            ))

            for h in cycle_boundaries:
                fig.add_vline(x=h, line_width=1, line_dash="dash", line_color="black")

    fig.update_layout(
        title="Error Rate by Cycle (%)",
        xaxis={"title": "Cycle"},
        yaxis={"title": "Error Rate (%)"},
        showlegend=False
    )
    return pio.to_html(fig, full_html=False)


def summary_tables(metrics):
    if not metrics:
        return "<p>No Summary Data Available</p>"

    sum_data = summary(metrics, level="Lane")
    if sum_data is None or len(sum_data) == 0:
        return "<p>No Summary Statistics Found</p>"

    df = pd.DataFrame(sum_data)
    return df.to_html(classes="table table-striped table-bordered text-center align-middle", index=False)

def overview_metrics_table(metrics):
    """
    Generate SAV-style overview metrics for the complete run.
    """
    if not metrics:
        return "<p class='text-muted p-3'>No Metrics Loaded</p>"

    try:
        arr = interop_summary(
            metrics,
            level="Total",
            columns=[
                "Yield G",
                "% >= Q30",
                "First Cycle Intensity",
                "Cluster Count",
                "Cluster Count Pf",
                "% Occupied",
                "% Aligned",
                "Error Rate",
            ],
            ignore_missing_columns=False,
        )

        if arr is None or len(arr) == 0:
            return "<p class='text-muted p-3'>No Overview Metrics Found</p>"

        row = arr[0]

        def get_value(name):
            """Return metric value or None if missing/NaN."""
            if name not in arr.dtype.names:
                return None

            value = row[name]

            try:
                if np.isnan(value):
                    return None
            except TypeError:
                pass

            return float(value)

        # Official InterOp summary values
        yield_g = get_value("Yield G")
        q30 = get_value("% >= Q30")
        intensity = get_value("First Cycle Intensity")
        cluster_count = get_value("Cluster Count")
        cluster_count_pf = get_value("Cluster Count Pf")
        occupied = get_value("% Occupied")
        aligned = get_value("% Aligned")
        error_rate = get_value("Error Rate")

        # % Passing Filter should be weighted by cluster counts,
        # rather than taking an arithmetic mean of tile %PF.
        if (
            cluster_count is not None
            and cluster_count_pf is not None
            and cluster_count > 0
        ):
            percent_pf = (
                cluster_count_pf / cluster_count
            ) * 100.0
        else:
            percent_pf = None

        def fmt_percent(value):
            return f"{value:.2f}%" if value is not None else "N/A"

        def fmt_number(value):
            return f"{value:.2f}" if value is not None else "N/A"

        overview = [
            ("Actual Yield",
             f"{yield_g:.2f} GB" if yield_g is not None else "N/A"),

            ("Average % >= Q30",
             fmt_percent(q30)),

            ("Intensity",
             fmt_number(intensity)),

            ("% Clusters Passing Filter",
             fmt_percent(percent_pf)),

            # SAV reports N/A for this run in your screenshot.
            ("Base Composition",
             "N/A"),

            ("% Occupied",
             fmt_percent(occupied)),

            ("% Aligned to PhiX",
             fmt_percent(aligned)),

            ("% PhiX Error Rate",
             fmt_percent(error_rate)),
        ]

        df = pd.DataFrame(
            overview,
            columns=["Metric", "Value"]
        )

        return df.to_html(
            classes=(
                "table table-sm table-bordered "
                "align-middle overview-table"
            ),
            index=False,
            header=False
        )

    except Exception as e:
        logging.warning(
            f"Failed generating overview metrics: {e}"
        )
        return "<p class='text-muted p-3'>Could not calculate overview metrics</p>"
    

def get_indexing_metrics(metrics):
    """
    Extracts indexing statistics using high-level interop routines.
    """
    if not metrics:
        return {
            "chart": "<p class='text-muted p-3'>No Metrics Loaded</p>",
            "table": "<p class='text-muted p-3'>No Metrics Loaded</p>"
        }

    df = pd.DataFrame()

    try:
        arr = indexing(metrics, per_sample=True)
        if arr is not None and len(arr) > 0:
            df = pd.DataFrame(arr)
    except Exception as e:
        logging.warning(f"interop.indexing failed: {e}")

    if df.empty:
        try:
            arr = index_summary(metrics, level="Barcode")
            if arr is not None and len(arr) > 0:
                df = pd.DataFrame(arr)
        except Exception as e:
            logging.warning(f"interop.index_summary failed: {e}")

    if df.empty:
        return {
            "chart": "<p class='text-muted p-3'>No Indexing Metrics Found in Run</p>",
            "table": "<p class='text-muted p-3'>No Indexing Metrics Found in Run</p>"
        }

    if "Barcode" in df.columns:
        df["Index Sequence"] = df["Barcode"].astype(str)
    elif "Index1" in df.columns:
        if "Index2" in df.columns:
            df["Index Sequence"] = df["Index1"].astype(str) + "-" + df["Index2"].astype(str)
        else:
            df["Index Sequence"] = df["Index1"].astype(str)

    sample_col = "SampleID" if "SampleID" in df.columns else ("Sample Id" if "Sample Id" in df.columns else None)
    if sample_col:
        df["Sample"] = df[sample_col].astype(str)
        df["Display Name"] = df["Sample"] + " (" + df["Index Sequence"] + ")"
    else:
        df["Display Name"] = df["Index Sequence"]

    count_col = "Cluster Count PF" if "Cluster Count PF" in df.columns else ("Cluster Count" if "Cluster Count" in df.columns else None)
    df["Reads"] = df[count_col] if count_col else 0

    if "% Demux" in df.columns:
        df["% Reads Identified"] = df["% Demux"]
    elif "Fraction Mapped" in df.columns:
        df["% Reads Identified"] = df["Fraction Mapped"] * 100.0
    else:
        total_reads = df["Reads"].sum()
        df["% Reads Identified"] = (df["Reads"] / total_reads * 100.0) if total_reads > 0 else 0.0

    # Aggregate total reads per sample/index across all tiles
    grouped = df.groupby(["Display Name", "Index Sequence"])["Reads"].sum().reset_index()

    # Recalculate percentage relative to total mapped reads across the whole run
    total_run_reads = grouped["Reads"].sum()
    grouped["% Reads Identified"] = np.where(
        total_run_reads > 0,
        (grouped["Reads"] / total_run_reads) * 100.0,
        0.0
    )

    # 1. Bar Chart
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=grouped["Display Name"],
        y=grouped["% Reads Identified"],
        marker_color="#1f77b4"
    ))

    fig.update_layout(
        title="Index Representation (% Reads Identified)",
        xaxis={"title": "Index / Sample"},
        yaxis={"title": "% Reads Identified"},
        showlegend=False
    )
    chart_html = pio.to_html(fig, full_html=False)

    # 2. Table HTML
    df_display = grouped[["Display Name", "Index Sequence", "Reads", "% Reads Identified"]].copy()
    df_display["Reads"] = df_display["Reads"].apply(lambda x: f"{int(x):,}")
    df_display["% Reads Identified"] = df_display["% Reads Identified"].apply(lambda x: f"{x:.2f}%")

    table_html = df_display.to_html(
        classes="table table-sm table-striped table-bordered align-middle text-center", 
        index=False
    )

    return {
        "chart": chart_html,
        "table": table_html
    }


# --- Flask Routes ---

@bp.route("/", methods=["GET"])
def index():
    irods_path = request.args.get("path", "")
    context = {"irods_path": irods_path}
        
    print(f'PATH : {irods_path}')

    if request.method == "GET" and irods_path:
        with irods_manager.session(current_user) as session:
            if session.collections.exists(irods_path):
                metrics, cycle_boundaries = load_interop_metrics(session, irods_path)
                
                run_info = metrics.run_info()
                
                context["run_info"] = run_info
                
                context["q30_chart"] = q30bycycle(metrics, cycle_boundaries)
                context["cluster_chart"] = clusterlane(metrics)
                context["pf_occupied_chart"] = pf_vs_occupied(metrics)
                context["summary_table"] = summary_tables(metrics)
                context["overview_table"] = overview_metrics_table(metrics)
                context["intensity_chart"] = intensitybycycle(metrics, cycle_boundaries)
                context["base_percent_chart"] = base_percent_by_cycle(metrics, cycle_boundaries)
                context["fwhm_chart"] = fwhm_by_cycle(metrics, cycle_boundaries)
                context["error_rate_chart"] = error_rate_by_cycle(metrics, cycle_boundaries)
                context["snr_chart"] = snr_by_cycle(metrics, cycle_boundaries)
                
                idx_data = get_indexing_metrics(metrics)
                context["index_chart"] = idx_data["chart"]
                context["index_table"] = idx_data["table"]

            else:
                context["error"] = f"iRODS Collection path not found: {irods_path}"

    return render_template("websav.html", context=context)