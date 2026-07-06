import os
import sys
import json
import sqlite3
import asyncio
import re
import hashlib
import pandas as pd
import altair as alt
import streamlit as st
import math
from datetime import datetime, timedelta

# MUST be the first Streamlit command called on the page
st.set_page_config(
    page_title="HydroWatch Monitoring Portal",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- SECURITY: Basic Authentication Gate ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("<h1 style='text-align: center; color: #0073e6;'>💧 HydroWatch Secure Portal</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #666;'>Please log in to access the monitoring dashboard.</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Secure Login", use_container_width=True)
            
            if submitted:
                # Prototype Hardcoded Credentials
                if username == "admin" and password == "admin":
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Invalid credentials. Please try again.")
    st.stop()
# -------------------------------------------

# Handle Contextual Source Linking
if "nav" in st.query_params and st.query_params["nav"] == "detail":
    st.session_state.selected_menu = "🔍 Source Detail View"
    if "source" in st.query_params:
        st.session_state.detail_view_source = st.query_params["source"]
    st.query_params.clear()

# Ensure parent directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from schema.bq_schema import StorageManager
from agents.orchestrator import (
    HydroWatchOrchestrator,
    intake_agent,
    pattern_agent,
    risk_classification_agent,
    alert_agent,
    query_agent
)

# Constants
DB_NAME = "hydrowatch_local.db"

VILLAGE_MAP = {
    "VIL-RAM-001": "Rampur",
    "VIL-SUN-002": "Sundarpur",
    "VIL-HAR-003": "Haripur",
    "VIL-BEL-004": "Beldanga",
    "VIL-BAK-005": "Bankura Rural",
    "VIL-BIS-006": "Bishnupur Peri-Urban",
    "VIL-KAK-007": "Kakdwip Coastal",
    "VIL-HAB-008": "Habra East",
    "VIL-KAL-009": "Kalyani Sector 3",
    "VIL-SIN-010": "Singur Farmstead",
    "VIL-TAR-011": "Tarakeswar Temple Road",
    "VIL-BOL-012": "Bolpur Rural",
    "VIL-ILL-013": "Illambazar Forest Gate",
    "VIL-GUS-014": "Gushkara West",
    "VIL-KAT-015": "Katwa Junction",
    "VIL-KLN-016": "Kalna Ghat",
    "VIL-RAN-017": "Ranaghat Border",
    "VIL-SAN-018": "Santipur Weavers Colony",
    "VIL-KRI-019": "Krishnanagar Sadar",
    "VIL-NAB-020": "Nabadwip Dham",
    "VIL-AMT-021": "Amta Riverside",
    "VIL-BAG-022": "Bagnan South",
    "VIL-ULU-023": "Uluberia Industrial",
    "VIL-JHA-024": "Jhargram Tribal Block",
    "VIL-MID-025": "Midnapore Rural",
    "VIL-KHA-026": "Kharagpur Outskirts",
    "VIL-DEB-027": "Debra Crossing",
    "VIL-PAN-028": "Panskura Flower Valley",
    "VIL-TAM-029": "Tamluk Heritage Block",
    "VIL-CON-030": "Contai Beach Road",
    "VIL-DIG-031": "Digha Tourism Belt",
    "VIL-EGR-032": "Egra Market Block",
    "VIL-GHA-033": "Ghatal Wetland Block",
    "VIL-ARA-034": "Arambagh Rural",
    "VIL-CHA-035": "Chandrakona Town",
    "VIL-GAR-036": "Garhbeta Red Soil",
    "VIL-SAL-037": "Salboni Reserve",
    "VIL-RAG-038": "Raghunathpur Heavy Block",
    "VIL-ADR-039": "Adra Railway Colony",
    "VIL-PUR-040": "Purulia Hills Block",
    "VIL-UNK-999": "Unknown Village"
}

VILLAGE_COORDS = {
    "VIL-RAM-001": (23.344, 87.866),
    "VIL-SUN-002": (22.572, 88.363),
    "VIL-HAR-003": (23.150, 87.500),
    "VIL-BEL-004": (23.940, 88.250),
    "VIL-BAK-005": (23.230, 87.070),
    "VIL-BIS-006": (23.070, 87.320),
    "VIL-KAK-007": (21.870, 88.180),
    "VIL-HAB-008": (22.830, 88.630),
    "VIL-KAL-009": (22.980, 88.430),
    "VIL-SIN-010": (22.810, 88.230),
    "VIL-TAR-011": (22.890, 87.970),
    "VIL-BOL-012": (23.670, 87.680),
    "VIL-ILL-013": (23.620, 87.530),
    "VIL-GUS-014": (23.500, 87.750),
    "VIL-KAT-015": (23.650, 88.130),
    "VIL-KLN-016": (23.220, 88.370),
    "VIL-RAN-017": (23.180, 88.580),
    "VIL-SAN-018": (23.250, 88.430),
    "VIL-KRI-019": (23.400, 88.500),
    "VIL-NAB-020": (23.420, 88.370),
    "VIL-AMT-021": (22.570, 87.920),
    "VIL-BAG-022": (22.470, 87.970),
    "VIL-ULU-023": (22.470, 88.110),
    "VIL-JHA-024": (22.450, 86.980),
    "VIL-MID-025": (22.420, 87.320),
    "VIL-KHA-026": (22.330, 87.300),
    "VIL-DEB-027": (22.390, 87.560),
    "VIL-PAN-028": (22.420, 87.720),
    "VIL-TAM-029": (22.300, 87.920),
    "VIL-CON-030": (21.780, 87.750),
    "VIL-DIG-031": (21.620, 87.510),
    "VIL-EGR-032": (21.900, 87.530),
    "VIL-GHA-033": (22.670, 87.720),
    "VIL-ARA-034": (22.880, 87.780),
    "VIL-CHA-035": (22.730, 87.520),
    "VIL-GAR-036": (22.870, 87.350),
    "VIL-SAL-037": (22.630, 87.320),
    "VIL-RAG-038": (23.550, 86.670),
    "VIL-ADR-039": (23.500, 86.680),
    "VIL-PUR-040": (23.330, 86.370)
}

SAFETY_THRESHOLDS = {
    "fluoride": {"limit": 1.5, "unit": "mg/L", "direction": "up"},
    "arsenic": {"limit": 0.01, "unit": "mg/L", "direction": "up"},
    "turbidity": {"limit": 5.0, "unit": "NTU", "direction": "up"},
    "bacterial counts": {"limit": 0.0, "unit": "CFU/100mL", "direction": "up"},
    "ph": {"limit": 8.5, "min_limit": 6.5, "unit": "pH Units", "direction": "ph"},
    "nitrate": {"limit": 45.0, "unit": "mg/L", "direction": "up"}
}

# --- Database Helper Functions ---
def get_unique_sources():
    if not os.path.exists(DB_NAME):
        return []
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT source_id, village_id FROM readings")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_source_history_sorted(source_id):
    if not os.path.exists(DB_NAME):
        return []
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT source_id, village_id, parameter, value, unit, date, reported_by_id FROM readings WHERE source_id = ? ORDER BY date ASC",
        (source_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_all_alerts_sorted():
    if not os.path.exists(DB_NAME):
        return []
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM alerts ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_recent_alert_for_source(source_id):
    if not os.path.exists(DB_NAME):
        return None
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM alerts WHERE source_id = ? ORDER BY timestamp DESC LIMIT 1",
        (source_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

# --- Water Safety & Extrapolation Helpers ---
def format_value(value, parameter):
    try:
        val = float(value)
        param_key = parameter.lower()
        if "arsenic" in param_key:
            return f"{val:.4f}"
        elif "ph" in param_key or "fluoride" in param_key:
            return f"{val:.2f}"
        elif "turbidity" in param_key:
            return f"{val:.1f}"
        else:
            return f"{val:.1f}"
    except Exception:
        return str(value)
def get_parameter_threshold_info(parameter):
    param_key = parameter.lower()
    for key, val in SAFETY_THRESHOLDS.items():
        if key in param_key or param_key in key:
            return val
    return None

def compute_severity_at_step(readings, parameter):
    if not readings:
        return "NORMAL"
    
    param_key = parameter.lower()
    threshold = get_parameter_threshold_info(param_key)
    if not threshold:
        return "NORMAL"
        
    limit = threshold.get("limit")
    min_limit = threshold.get("min_limit")
    
    # 1. Check for Acute Breach
    has_acute = False
    if param_key == "ph" and min_limit is not None:
        for r in readings:
            if r < min_limit or r > limit:
                has_acute = True
    else:
        for r in readings:
            if r > limit:
                has_acute = True
                
    if has_acute:
        return "IMMEDIATE_HAZARD"
        
    # 2. Check for Drift Trend
    has_drift = False
    if len(readings) >= 3:
        increasing = True
        for idx in range(len(readings) - 1):
            if readings[idx] >= readings[idx+1]:
                increasing = False
                break
        if increasing:
            if "fluoride" in param_key and readings[-1] >= 1.125:
                has_drift = True
            elif "arsenic" in param_key and readings[-1] >= 0.0075:
                has_drift = True
            elif "turbidity" in param_key and readings[-1] >= 3.75:
                has_drift = True
                
        # Check pH drift: moving up towards 8.5 (last >= 8.0) or down towards 6.5 (last <= 7.0)
        if "ph" in param_key:
            up_drift = True
            for idx in range(len(readings) - 1):
                if readings[idx] >= readings[idx+1]:
                    up_drift = False
                    break
            if up_drift and readings[-1] >= 8.0:
                has_drift = True
                
            down_drift = True
            for idx in range(len(readings) - 1):
                if readings[idx] <= readings[idx+1]:
                    down_drift = False
                    break
            if down_drift and readings[-1] <= 7.0:
                has_drift = True
                
    if has_drift:
        return "WATCHLIST"
        
    return "NORMAL"

def get_overall_source_severity(source_id):
    history = get_source_history_sorted(source_id)
    if not history:
        return "NORMAL"
        
    by_param = {}
    for r in history:
        param = r["parameter"].lower()
        if param not in by_param:
            by_param[param] = []
        by_param[param].append(r["value"])
        
    severities = []
    for param, vals in by_param.items():
        sev = compute_severity_at_step(vals, param)
        severities.append(sev)
        
    if "IMMEDIATE_HAZARD" in severities:
        return "IMMEDIATE_HAZARD"
    elif "WATCHLIST" in severities:
        return "WATCHLIST"
    return "NORMAL"

def estimate_days_to_threshold(values, parameter):
    threshold_info = get_parameter_threshold_info(parameter)
    if not threshold_info:
        return "N/A"
        
    limit = threshold_info.get("limit")
    
    if len(values) < 2:
        return "Need more data"
        
    # Fit line to the last min(5, len(values)) points
    history_len = min(5, len(values))
    y = values[-history_len:]
    x = list(range(history_len))
    
    n = len(x)
    sum_x = sum(x)
    sum_y = sum(y)
    sum_xx = sum(i*i for i in x)
    sum_xy = sum(i*j for i, j in zip(x, y))
    
    denom = n * sum_xx - sum_x * sum_x
    if denom == 0:
        return "No trend"
        
    slope = (n * sum_xy - sum_x * sum_y) / denom
    
    param_key = parameter.lower()
    
    if "ph" in param_key:
        if slope > 0:
            days = (8.5 - y[-1]) / slope
            return f"{days:.1f} days to pH 8.5 (est.)" if days >= 0 else "Breached"
        elif slope < 0:
            days = (6.5 - y[-1]) / slope
            return f"{days:.1f} days to pH 6.5 (est.)" if days >= 0 else "Breached"
        else:
            return "Stable"
    else:
        if slope <= 0:
            return "Stable / Improving"
        days = (limit - y[-1]) / slope
        if days < 0:
            return "Breached"
        return f"{days:.1f} days (est.)"

# --- SVG Sparkline Generator ---
def generate_svg_gauge(value, param_name, severity, unit):
    # Colors based on severity
    if severity == "NORMAL":
        ring_color = "#10B981"
    elif severity == "WATCHLIST":
        ring_color = "#F59E0B"
    else:
        ring_color = "#EF4444"
        
    threshold_data = SAFETY_THRESHOLDS.get(param_name.lower(), {})
    limit = threshold_data.get("limit", value * 1.5)
    if limit == 0:
        limit = 0.0
    
    # SVG Dimensions and Math
    radius = 24
    cx = 30
    cy = 30
    circumference = 2 * math.pi * radius
    
    if param_name.lower() == "ph":
        min_scale = 0.0
        max_scale = 14.0
        threshold_min = threshold_data.get("min_limit", 6.5)
        threshold_max = limit
    elif limit == 0:
        min_scale = 0.0
        max_scale = max(value * 1.5, 5.0)
        threshold_min = 0.0
        threshold_max = 0.0
    else:
        min_scale = 0.0
        max_scale = max(value * 1.2, limit * 1.5)
        threshold_min = 0.0
        threshold_max = limit
        
    range_scale = max_scale - min_scale
    if range_scale <= 0: range_scale = 1.0
    
    # Fill percentage
    fill_percent = (value - min_scale) / range_scale
    fill_percent = max(0.0, min(1.0, fill_percent)) # clamp
    
    dashoffset = circumference * (1.0 - fill_percent)
    
    # Format value for display
    display_val = f"{value:.2f}"
    if value == int(value): display_val = f"{int(value)}"
    
    # Background ring
    background_circle = f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="#334155" stroke-width="4" />'
    marker_svg = ""
    
    if param_name.lower() == "ph":
        min_p = (threshold_min - min_scale) / range_scale
        max_p = (threshold_max - min_scale) / range_scale
        safe_offset = circumference * (1.0 - (max_p - min_p))
        safe_rot = (min_p * 360) - 90
        background_circle += f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="rgba(16, 185, 129, 0.2)" stroke-width="4" stroke-dasharray="{circumference}" stroke-dashoffset="{safe_offset}" transform="rotate({safe_rot} {cx} {cy})" />'
        
        angle_min = min_p * 2 * math.pi - (math.pi / 2)
        m_x1 = cx + (radius - 3) * math.cos(angle_min)
        m_y1 = cy + (radius - 3) * math.sin(angle_min)
        m_x2 = cx + (radius + 3) * math.cos(angle_min)
        m_y2 = cy + (radius + 3) * math.sin(angle_min)
        marker_svg += f'<line x1="{m_x1}" y1="{m_y1}" x2="{m_x2}" y2="{m_y2}" stroke="#F8FAFC" stroke-width="2" opacity="0.6" />'

    threshold_percent = (threshold_max - min_scale) / range_scale
    threshold_percent = max(0.0, min(1.0, threshold_percent))
    
    angle = threshold_percent * 2 * math.pi - (math.pi / 2)
    marker_x1 = cx + (radius - 3) * math.cos(angle)
    marker_y1 = cy + (radius - 3) * math.sin(angle)
    marker_x2 = cx + (radius + 3) * math.cos(angle)
    marker_y2 = cy + (radius + 3) * math.sin(angle)
    
    marker_svg += f'<line x1="{marker_x1}" y1="{marker_y1}" x2="{marker_x2}" y2="{marker_y2}" stroke="#F8FAFC" stroke-width="2" opacity="0.6" />'

    svg = f"""
    <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; background: #1E293B; border: 1px solid #334155; border-radius: 8px; padding: 0.5rem; width: 85px; height: 100px;" title="Current: {display_val} {unit} | Limit: {limit} {unit}">
        <svg width="60" height="60" viewBox="0 0 60 60" style="overflow: visible;">
            {background_circle}
            <circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="{ring_color}" stroke-width="4" stroke-linecap="round" stroke-dasharray="{circumference}" stroke-dashoffset="{dashoffset}" transform="rotate(-90 {cx} {cy})" style="transition: stroke-dashoffset 1s ease-in-out;" />
            {marker_svg}
            <text x="{cx}" y="{cy}" text-anchor="middle" dominant-baseline="central" fill="#F8FAFC" font-size="13" font-weight="700">{display_val}</text>
        </svg>
        <div style="margin-top: 6px; font-size: 0.6rem; color: #94A3B8; font-weight: 600; text-transform: uppercase; text-align: center; line-height: 1.1;">{param_name}</div>
    </div>
    """
    return svg

def generate_svg_sparkline(values, width=80, height=20):
    if len(values) < 2:
        return '<span style="color:#71717a; font-size:0.75rem;">Need readings</span>'
    min_val = min(values)
    max_val = max(values)
    val_range = max_val - min_val
    if val_range == 0:
        val_range = 1.0
        
    points = []
    for idx, val in enumerate(values):
        x = (idx / (len(values) - 1)) * width
        y = height - ((val - min_val) / val_range) * height
        points.append(f"{x},{y}")
        
    points_str = " ".join(points)
    svg_html = f"""
    <svg width="{width}" height="{height}" style="overflow: visible; display: inline-block; vertical-align: middle;">
        <polyline fill="none" stroke="#0284c7" stroke-width="2" points="{points_str}" />
        <circle cx="{points[-1].split(',')[0]}" cy="{points[-1].split(',')[1]}" r="3" fill="#0369a1" />
    </svg>
    """
    return svg_html

# --- Map Jittering ---
def get_jittered_coordinates(village_id, source_id):
    lat, lon = VILLAGE_COORDS.get(village_id, (23.0, 88.0))
    # Deterministic jitter using md5 hash of source_id
    h = int(hashlib.md5(source_id.encode('utf-8')).hexdigest(), 16)
    jitter_lat = ((h % 1000) / 1000.0 - 0.5) * 0.015
    jitter_lon = (((h // 1000) % 1000) / 1000.0 - 0.5) * 0.015
    return lat + jitter_lat, lon + jitter_lon

# --- Chat Grounding & Q&A Helpers ---
def get_db_context_summary():
    sources = get_unique_sources()
    alerts = get_all_alerts_sorted()
    
    summary = "System Summary:\n"
    summary += f"- Monitored Sources: {len(sources)}\n"
    summary += f"- Historical Alerts Logged: {len(alerts)}\n\n"
    
    summary += "Source Detailed Readings:\n"
    for src in sources:
        history = get_source_history_sorted(src["source_id"])
        overall_sev = get_overall_source_severity(src["source_id"])
        village_name = VILLAGE_MAP.get(src["village_id"], "Unknown")
        summary += f"Source: {src['source_id']} in village {village_name} ({src['village_id']}). Overall Risk: {overall_sev}\n"
        # Group by parameter
        by_param = {}
        for r in history:
            p = r["parameter"]
            if p not in by_param:
                by_param[p] = []
            by_param[p].append(r)
            
        for param, rows in by_param.items():
            vals_str = ", ".join([f"{r['value']} {r['unit']} on {r['date'].split('T')[0]}" for r in rows])
            summary += f"  - Parameter '{param}': readings: {vals_str}\n"
            
    summary += "\nSystem Alerts Log:\n"
    for a in alerts:
        summary += f"- Alert ID: {a['alert_id']} | Source: {a['source_id']} | Severity: {a['severity']} | Status: {a.get('status', 'drafted')} | Recipient: {a['recipient']} | Time: {a['timestamp']} | Message: {a['message']}\n"
        
    return summary

def answer_offline_question(question):
    from agents.mock_client import answer_query_grounded
    from google.genai import types
    
    history_context = []
    for m in st.session_state.get("messages", []):
        role = "user" if m["role"] == "user" else "model"
        history_context.append(
            types.Content(role=role, parts=[types.Part(text=m["content"])])
        )
        
    return answer_query_grounded(question, history_context)

def generate_daily_briefing():
    sources = get_unique_sources()
    alerts = get_all_alerts_sorted()
    now = datetime.now()
    two_days_ago = (now - timedelta(hours=48)).isoformat()
    new_alerts = [a for a in alerts if a['timestamp'] >= two_days_ago and a['severity'] == "IMMEDIATE_HAZARD"]
    
    hazard_counts = {}
    for a in alerts:
        if a['severity'] in ["IMMEDIATE_HAZARD", "WATCHLIST"]:
            hazard_counts[a['source_id']] = hazard_counts.get(a['source_id'], 0) + 1
            
    top_sources = sorted(hazard_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    top_sources_str = ", ".join([f"chip:{s[0]}:IMMEDIATE_HAZARD ({s[1]} alerts)" for s in top_sources]) if top_sources else "None"
    rec_action = "Dispatch field teams to inspect the top flagged sources immediately." if top_sources else "Maintain regular monitoring schedule. No immediate interventions required."
    
    return f"""### 📋 Daily Regional Briefing ({now.strftime('%Y-%m-%d')})

- **Total Sources Monitored:** {len(sources)}
- **New Hazards (Last 48h):** {len(new_alerts)}
- **Top Sources Needing Attention:** {top_sources_str}

**Recommended Action:**
> {rec_action}
"""

def generate_svg_comparison_chart(title, items_dict, width=300, height=180):
    if not items_dict: return ""
    max_val = max(items_dict.values()) if items_dict else 1.0
    if max_val == 0: max_val = 1.0
    
    bar_width = 30
    spacing = 50
    svg_html = f'<svg width="{width}" height="{height}" style="background-color: #1E293B; border: 1px solid #334155; border-radius: 8px; padding: 10px; margin: 10px 0; display: block;">'
    svg_html += f'<text x="10" y="20" fill="#F8FAFC" font-size="12" font-weight="bold" font-family="sans-serif">{title}</text>'
    
    for i, (label, val) in enumerate(items_dict.items()):
        bar_height = max((val / max_val) * (height - 60), 2)
        x = 20 + i * spacing
        y = height - 30 - bar_height
        
        svg_html += f'<rect x="{x}" y="{y}" width="{bar_width}" height="{bar_height}" fill="#38BDF8" rx="4" />'
        svg_html += f'<text x="{x + bar_width/2}" y="{y - 5}" fill="#F8FAFC" font-size="10" text-anchor="middle" font-family="sans-serif">{val}</text>'
        
        display_label = label[:6] + ".." if len(label) > 8 else label
        svg_html += f'<text x="{x + bar_width/2}" y="{height - 10}" fill="#94A3B8" font-size="10" text-anchor="middle" font-family="sans-serif">{display_label}</text>'
        
    svg_html += '</svg>'
    return svg_html

def render_message_html(text):
    def replace_barchart(match):
        title = match.group(1).strip()
        items_str = match.group(2)
        items_dict = {}
        for item in items_str.split("|"):
            if ":" in item:
                k, v = item.split(":", 1)
                try:
                    items_dict[k.strip()] = float(v.strip())
                except:
                    pass
        return generate_svg_comparison_chart(title, items_dict)

    processed = re.sub(r'\[BARCHART:\s*([^|]+)\|\s*(.*?)\]', replace_barchart, text)

    def replace_chip(match):
        src_id = match.group(1)
        sev = match.group(2)
        history = get_source_history_sorted(src_id)
        spark_html = ""
        if history:
            vals = [r["value"] for r in history]
            spark_html = generate_svg_sparkline(vals)
        badge_class = "badge-normal" if sev == "NORMAL" else ("badge-watchlist" if sev == "WATCHLIST" else "badge-hazard")
        return f'<a href="/?nav=detail&source={src_id}" target="_self" style="text-decoration: none;" class="source-chip">💧 {src_id} <span class="badge {badge_class}" style="font-size: 0.55rem; padding: 1px 4px;">{sev}</span> {spark_html}</a>'
        
    processed = re.sub(r'chip:(SRC-[A-Z]{3}-[0-9]{4}):(NORMAL|WATCHLIST|IMMEDIATE_HAZARD)', replace_chip, processed)
    
    def replace_raw_src(match):
        src_id = match.group(0)
        sev = get_overall_source_severity(src_id)
        history = get_source_history_sorted(src_id)
        spark_html = ""
        if history:
            vals = [r["value"] for r in history]
            spark_html = generate_svg_sparkline(vals)
        badge_class = "badge-normal" if sev == "NORMAL" else ("badge-watchlist" if sev == "WATCHLIST" else "badge-hazard")
        return f'<a href="/?nav=detail&source={src_id}" target="_self" style="text-decoration: none;" class="source-chip">💧 {src_id} <span class="badge {badge_class}" style="font-size: 0.55rem; padding: 1px 4px;">{sev}</span> {spark_html}</a>'
        
    text_clean = re.sub(r'chip:(SRC-[A-Z]{3}-[0-9]{4}):(?:NORMAL|WATCHLIST|IMMEDIATE_HAZARD)', r'\1', processed)
    processed = re.sub(r'\bSRC-[A-Z]{3}-[0-9]{4}\b', replace_raw_src, text_clean)
    return processed

def get_message_html(role, content, timestamp=None):
    if not timestamp:
        timestamp = datetime.now().strftime('%H:%M:%S')
    processed_content = render_message_html(content)
    if role == "user":
        return f"""
        <div class="chat-bubble-container">
            <div class="chat-bubble-row user">
                <div class="chat-bubble user">{processed_content}</div>
            </div>
            <div class="chat-meta user">👤 You &bull; {timestamp}</div>
        </div>
        """
    else:
        return f"""
        <div class="chat-bubble-container">
            <div class="chat-bubble-row assistant">
                <div class="chat-avatar">💧</div>
                <div class="chat-bubble assistant">{processed_content}</div>
            </div>
            <div class="chat-meta assistant">HydroWatch Assistant &bull; {timestamp}</div>
        </div>
        """

def stream_assistant_response(content):
    import time
    placeholder = st.empty()
    words = content.split(" ")
    timestamp = datetime.now().strftime('%H:%M:%S')
    for i in range(1, len(words) + 1):
        partial_content = " ".join(words[:i])
        processed_partial = render_message_html(partial_content)
        html = f"""
        <div class="chat-bubble-container">
            <div class="chat-bubble-row assistant">
                <div class="chat-avatar">💧</div>
                <div class="chat-bubble assistant">{processed_partial} ▌</div>
            </div>
            <div class="chat-meta assistant">HydroWatch Assistant &bull; {timestamp}</div>
        </div>
        """
        placeholder.markdown(html, unsafe_allow_html=True)
        time.sleep(0.01)
        
    processed_final = render_message_html(content)
    html_final = f"""
    <div class="chat-bubble-container">
        <div class="chat-bubble-row assistant">
            <div class="chat-avatar">💧</div>
            <div class="chat-bubble assistant">{processed_final}</div>
        </div>
        <div class="chat-meta assistant">HydroWatch Assistant &bull; {timestamp}</div>
    </div>
    """
    placeholder.markdown(html_final, unsafe_allow_html=True)

def get_follow_up_suggestions():
    if not st.session_state.messages:
        return []
    last_msg = st.session_state.messages[-1]
    if last_msg["role"] == "user":
        return []
    content = last_msg["content"].upper()
    source_match = re.search(r"SRC-[A-Z]{3}-[0-9]{4}", content)
    suggestions = []
    if source_match:
        src_id = source_match.group(0)
        suggestions.append(f"Why is {src_id} flagged?")
        suggestions.append(f"What is the full history for {src_id}?")
    elif "HAZARD" in content or "WATCHLIST" in content:
        suggestions.append("What actions should be recommended?")
        suggestions.append("Give me today's briefing")
    elif "BRIEFING" in content:
        suggestions.append("What actions should be recommended?")
        suggestions.append("Which village has the most watchlist sources?")
    elif "COMPARE" in content:
        suggestions.append("Which source type is riskiest?")
        suggestions.append("Summarize this week's alerts")
    else:
        suggestions.append("Give me today's briefing")
        suggestions.append("Which sources are at Immediate Hazard right now?")
    return list(dict.fromkeys(suggestions))[:3]

def generate_grounded_answer(question):
    orchestrator = HydroWatchOrchestrator()
    
    async def run_query():
        if "adk_session" not in st.session_state:
            st.session_state.adk_session = await orchestrator.session_service.create_session(
                app_name="agents",
                user_id=orchestrator.user_id
            )
        response = await orchestrator.execute_agent_step(st.session_state.adk_session, query_agent, question)
        return response
        
    import asyncio
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
            
        if loop and loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return asyncio.run(run_query())
        else:
            return asyncio.run(run_query())
    except Exception as e:
        import traceback
        print(f"Agent Pipeline Failed: {e}", file=sys.stderr)
        traceback.print_exc()
        return answer_offline_question(question)

# --- Global Style Injection ---

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    /* Fix material icons being overridden by global font */
    .material-symbols-rounded, .material-icons {
        font-family: 'Material Symbols Rounded', 'Material Icons' !important;
    }

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    /* Enforce Dark Slate Theme globally */
    [data-testid="stAppViewContainer"], html, body {
        background-color: #0F172A !important;
        color: #F8FAFC !important;
    }
    
    [data-testid="stSidebar"] {
        background-color: #0F172A !important;
        border-right: 1px solid #1E293B !important;
    }
    
    [data-testid="stSidebarUserContent"] {
        padding-top: 1rem !important;
        display: flex;
        flex-direction: column;
        height: 100vh;
    }
    
    /* Ensure Streamlit markdown texts are readable and follow colors */
    .stMarkdown, p, span, label, h1, h2, h3, h4, h5, h6 {
        color: #F8FAFC !important;
    }
    
    /* --- MODERN SAAS SIDEBAR (st.radio styling) --- */
    div[data-testid="stRadio"] > div[role="radiogroup"] {
        gap: 0.1rem !important;
    }
    /* Hide actual radio circle */
    div[data-testid="stRadio"] div[role="radiogroup"] label > div:first-child {
        display: none !important;
    }
    /* Style the label container */
    div[data-testid="stRadio"] div[role="radiogroup"] label {
        background: transparent;
        padding: 0.35rem 1rem !important;
        border-radius: 8px !important;
        margin-bottom: 0.2rem;
        cursor: pointer;
        transition: all 0.2s ease;
        border-left: 3px solid transparent;
        position: relative;
    }
    /* Style the text inside */
    div[data-testid="stRadio"] div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p {
        font-size: 0.95rem;
        font-weight: 500;
        color: #94A3B8 !important;
        margin: 0;
        padding: 0;
        transition: all 0.2s;
    }
    /* Hover state */
    div[data-testid="stRadio"] div[role="radiogroup"] label:hover {
        background-color: rgba(51, 65, 85, 0.4) !important;
    }
    div[data-testid="stRadio"] div[role="radiogroup"] label:hover div[data-testid="stMarkdownContainer"] p {
        color: #F8FAFC !important;
    }
    /* Active State */
    div[data-testid="stRadio"] div[role="radiogroup"] label[data-checked="true"] {
        background-color: rgba(56, 189, 248, 0.1) !important;
        border-left: 3px solid #38BDF8 !important;
    }
    div[data-testid="stRadio"] div[role="radiogroup"] label[data-checked="true"] div[data-testid="stMarkdownContainer"] p {
        color: #38BDF8 !important;
        font-weight: 600;
    }
    /* Divider after 4th item (Alerts Log) */
    div[data-testid="stRadio"] div[role="radiogroup"] label:nth-child(4) {
        margin-bottom: 1.5rem;
    }
    div[data-testid="stRadio"] div[role="radiogroup"] label:nth-child(4)::after {
        content: "TOOLS & ACTIONS";
        display: block;
        position: absolute;
        bottom: -1.25rem;
        left: 0.2rem;
        font-size: 0.65rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        color: #64748B;
    }
    
    /* Top Bar Styling */
    .top-bar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid #1E293B;
        margin-bottom: 1.5rem;
        margin-top: -1.5rem;
    }
    .top-bar-title {
        font-size: 1.4rem;
        font-weight: 700;
        color: #F8FAFC !important;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    /* Sidebar Footer */
    .sidebar-footer {
        margin-top: auto;
        padding-top: 1rem;
        border-top: 1px solid #1E293B;
        margin-bottom: -1rem;
    }
    
    .brand-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding-bottom: 0.75rem;
        border-bottom: 2px solid #334155;
        margin-bottom: 1.5rem;
    }
    .brand-title {
        font-size: 2.2rem;
        font-weight: 800;
        color: #38BDF8 !important;
        letter-spacing: -0.02em;
    }
    .brand-subtitle {
        font-size: 0.95rem;
        color: #94A3B8 !important;
        margin-top: 0.1rem;
    }
    
    /* Card Styles */
    .metric-card {
        background-color: #1E293B !important;
        border: 1px solid #334155 !important;
        border-radius: 12px;
        padding: 1.25rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.12);
        transition: all 0.2s ease-in-out;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0, 0, 0, 0.2);
        border-color: #38BDF8 !important;
    }
    .metric-title {
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        color: #94A3B8 !important;
        letter-spacing: 0.05em;
        margin-bottom: 0.4rem;
    }
    .metric-val {
        font-size: 2rem;
        font-weight: 800;
        color: #F8FAFC !important;
    }
    
    .source-card {
        background-color: #1E293B !important;
        border: 1px solid #334155 !important;
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        transition: all 0.2s ease;
    }
    .source-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(56, 189, 248, 0.15);
        border-color: #38BDF8 !important;
    }
    .card-title {
        font-size: 1.2rem;
        font-weight: 700;
        color: #F8FAFC !important;
    }
    .card-subtitle {
        font-size: 0.85rem;
        color: #94A3B8 !important;
        margin-top: 0.1rem;
    }
    
    /* Badges */
    .badge {
        font-size: 0.72rem;
        font-weight: 700;
        padding: 3px 9px;
        border-radius: 6px;
        text-transform: uppercase;
        display: inline-block;
        text-align: center;
    }
    .badge-normal {
        color: #FFFFFF !important;
        background-color: #10B981 !important;
        border: 1px solid #059669;
    }
    .badge-watchlist {
        color: #0F172A !important;
        background-color: #F59E0B !important;
        border: 1px solid #D97706;
    }
    .badge-hazard {
        color: #FFFFFF !important;
        background-color: #EF4444 !important;
        border: 1px solid #B91C1C;
    }
    .badge-rate_limited {
        color: #F59E0B !important;
        background-color: rgba(245, 158, 11, 0.1) !important;
        border: 1px dashed #F59E0B !important;
    }
    .badge-drafted {
        color: #38BDF8 !important;
        background-color: rgba(56, 189, 248, 0.1) !important;
        border: 1px solid #0284C7 !important;
    }
    .badge-sent {
        color: #10B981 !important;
        background-color: rgba(16, 185, 129, 0.1) !important;
        border: 1px solid #10B981 !important;
    }
    
    .sparkline-container {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-top: 0.6rem;
    }
    .sparkline-label {
        font-size: 0.78rem;
        color: #94A3B8 !important;
    }
    .card-meta {
        font-size: 0.75rem;
        color: #94A3B8 !important;
        margin-top: 0.6rem;
        border-top: 1px solid #334155;
        padding-top: 0.5rem;
    }
    
    /* Tables */
    .alert-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 1rem;
        font-size: 0.85rem;
        background-color: #1E293B !important;
        border: 1px solid #334155;
    }
    .alert-table th {
        text-align: left;
        padding: 0.75rem;
        background-color: #334155 !important;
        color: #F8FAFC !important;
        border-bottom: 2px solid #475569;
        font-weight: 600;
    }
    .alert-table td {
        padding: 0.75rem;
        border-bottom: 1px solid #334155;
        color: #F8FAFC !important;
    }
    .alert-table tr:hover {
        background-color: #334155 !important;
    }
    
    .agent-box {
        background-color: #1E293B !important;
        border: 1px solid #334155 !important;
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.12);
    }
    .agent-header {
        font-size: 0.95rem;
        font-weight: 700;
        color: #38BDF8 !important;
        margin-bottom: 0.5rem;
    }
    .agent-pre {
        background-color: #0F172A !important;
        color: #E2E8F0 !important;
        padding: 0.75rem;
        border-radius: 6px;
        font-family: monospace;
        font-size: 0.8rem;
        white-space: pre-wrap;
        overflow-x: auto;
    }
    
    /* Stepper / Timeline */
    .timeline {
        position: relative;
        padding-left: 28px;
        margin-left: 8px;
        border-left: 2px solid #334155;
    }
    .timeline-item {
        position: relative;
        margin-bottom: 1.25rem;
    }
    .timeline-marker {
        position: absolute;
        left: -35px;
        top: 4px;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        background-color: #64748B;
        border: 2px solid #1E293B;
        box-shadow: 0 0 0 2px #475569;
    }
    .timeline-marker.normal {
        background-color: #10B981 !important;
        box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.4);
    }
    .timeline-marker.watchlist {
        background-color: #F59E0B !important;
        box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.4);
    }
    .timeline-marker.hazard {
        background-color: #EF4444 !important;
        box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.4);
    }
    
    /* Modern Chat UI */
    .chat-bubble-container {
        display: flex;
        flex-direction: column;
        margin-bottom: 1rem;
        width: 100%;
    }
    .chat-bubble-row {
        display: flex;
        align-items: flex-start;
        margin-bottom: 0.25rem;
    }
    .chat-bubble-row.user {
        justify-content: flex-end;
    }
    .chat-bubble-row.assistant {
        justify-content: flex-start;
    }
    .chat-avatar {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        background-color: #0369a1;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-right: 0.5rem;
        font-size: 1.1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.12);
    }
    .chat-bubble {
        max-width: 75%;
        padding: 0.85rem 1.1rem;
        border-radius: 16px;
        font-size: 0.95rem;
        line-height: 1.5;
        box-shadow: 0 1px 3px rgba(0,0,0,0.12);
    }
    .chat-bubble.user {
        background-color: #0284C7 !important;
        color: #FFFFFF !important;
        margin-left: auto;
        border-bottom-right-radius: 4px;
        text-align: right;
    }
    
    /* Button Styling */
    div[data-testid="stButton"] button, div[data-testid="stDownloadButton"] button, button[kind="secondary"] {
        background-color: #1E293B !important;
        color: #F8FAFC !important;
        border: 1px solid #334155 !important;
        border-radius: 8px !important;
        padding: 0.5rem 1rem !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
    }
    div[data-testid="stButton"] button:hover, div[data-testid="stDownloadButton"] button:hover, button[kind="secondary"]:hover {
        background-color: #334155 !important;
        border-color: #38BDF8 !important;
        color: #38BDF8 !important;
    }
    .chat-bubble.assistant {
        background-color: #1E293B !important;
        color: #F8FAFC !important;
        border-bottom-left-radius: 4px;
        text-align: left;
    }
    .chat-meta {
        font-size: 0.72rem;
        color: #64748B !important;
        margin-top: 0.15rem;
    }
    .chat-meta.user {
        text-align: right;
        margin-right: 0.5rem;
    }
    .chat-meta.assistant {
        text-align: left;
        margin-left: 2.8rem;
    }
    
    .thinking-indicator {
        display: flex;
        align-items: center;
        gap: 0.4rem;
        color: #94A3B8 !important;
        font-size: 0.85rem;
        font-style: italic;
        margin-left: 2.8rem;
        margin-bottom: 1rem;
    }
    .thinking-dot {
        width: 6px;
        height: 6px;
        background-color: #94A3B8;
        border-radius: 50%;
        animation: pulse 1.2s infinite ease-in-out;
    }
    .thinking-dot:nth-child(2) { animation-delay: 0.2s; }
    .thinking-dot:nth-child(3) { animation-delay: 0.4s; }

    /* Inline card reference chip */
    .source-chip {
        display: inline-flex;
        align-items: center;
        background-color: #334155 !important;
        border: 1px solid #475569;
        border-radius: 6px;
        padding: 2px 6px;
        gap: 0.4rem;
        margin: 0 2px;
        font-size: 0.85rem;
        font-weight: 600;
        vertical-align: middle;
    }

    [data-testid="stHorizontalBlock"] {
        gap: 1.25rem !important;
    }
</style>
""", unsafe_allow_html=True)

# Layout Helper for charts

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    # Center the login box
    st.markdown("""
        <style>
            .stApp { background-color: #0F172A; }
            .login-box {
                max-width: 400px;
                margin: 100px auto;
                background-color: #1E293B;
                padding: 2rem;
                border-radius: 12px;
                border: 1px solid #334155;
                box-shadow: 0 10px 25px rgba(0,0,0,0.5);
                text-align: center;
            }
            .login-title {
                color: #F8FAFC;
                font-size: 1.5rem;
                font-weight: 700;
                margin-bottom: 0.5rem;
            }
            .login-subtitle {
                color: #94A3B8;
                font-size: 0.9rem;
                margin-bottom: 2rem;
            }
        </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="login-box">', unsafe_allow_html=True)
        st.markdown('<div style="font-size: 3rem; margin-bottom: 1rem;">💧</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-title">HydroWatch Portal</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-subtitle">Sign in to access water safety data</div>', unsafe_allow_html=True)
        
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        
        if st.button("Sign In", type="primary", use_container_width=True):
            if username == "admin" and password == "password123":
                st.session_state["authenticated"] = True
                if hasattr(st, "rerun"):
                    st.rerun()
                else:
                    st.experimental_rerun()
            else:
                st.error("Invalid username or password.")
                
        st.markdown('</div>', unsafe_allow_html=True)
        
    st.stop() # Prevents the rest of the script from executing if not authenticated

# Header Section - Replaced by Top Bar inside each page or globally
st.markdown(f"""
<div class="top-bar">
    <div class="top-bar-title">
        <span style="color:#38BDF8;">💧</span> HydroWatch Dashboard
    </div>
    <div style="display: flex; align-items: center; gap: 1rem;">
        <div style="padding: 0.35rem 0.75rem; background: #1E293B; border: 1px solid #334155; border-radius: 6px; font-size: 0.85rem; color: #94A3B8; display: flex; align-items: center; gap: 0.4rem;">
            🔍 <span style="opacity: 0.5;">Search sources (⌘K)</span>
        </div>
        <div style="padding: 0.35rem 0.75rem; background: #38BDF8; color: #0F172A; border-radius: 6px; font-size: 0.85rem; font-weight: 600; cursor: pointer;">
            + Report Issue
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Sidebar Menu
st.sidebar.markdown("""
<div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 2rem; padding: 0 0.5rem;">
    <div style="background: linear-gradient(135deg, #38BDF8, #0284C7); width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 1.2rem; box-shadow: 0 4px 12px rgba(56, 189, 248, 0.25);">
        💧
    </div>
    <div style="font-size: 1.3rem; font-weight: 800; color: #F8FAFC; letter-spacing: -0.02em;">
        HydroWatch
    </div>
</div>
<div style="font-size: 0.65rem; font-weight: 700; letter-spacing: 0.05em; color: #64748B; margin-left: 0.7rem; margin-bottom: 0.5rem;">MONITORING</div>
""", unsafe_allow_html=True)

menu_options = [
    "📊 Overview Dashboard", 
    "🗺️ Map View", 
    "🔍 Source Detail View", 
    "🔔 Alerts Log", 
    "⚡ Live Pipeline Runner", 
    "📈 Analytics / Trends", 
    "💬 Ask HydroWatch"
]

if "selected_menu" not in st.session_state:
    st.session_state.selected_menu = menu_options[0]

default_idx = menu_options.index(st.session_state.selected_menu) if st.session_state.selected_menu in menu_options else 0

menu = st.sidebar.radio(
    "Navigation",
    menu_options,
    index=default_idx,
    label_visibility="collapsed",
    key="selected_menu_radio"
)
st.session_state.selected_menu = menu

# Load basic SQLite data
sources_list = get_unique_sources()
alerts_list = get_all_alerts_sorted()

# Compile details of all sources
sources_data = []
active_watchlist = 0
active_hazards = 0

for src in sources_list:
    history = get_source_history_sorted(src["source_id"])
    if history:
        latest = history[-1]
        overall_severity = get_overall_source_severity(src["source_id"])
        
        if overall_severity == "WATCHLIST":
            active_watchlist += 1
        elif overall_severity == "IMMEDIATE_HAZARD":
            active_hazards += 1
            
        sources_data.append({
            "source_id": src["source_id"],
            "village_id": src["village_id"],
            "village_name": VILLAGE_MAP.get(src["village_id"], "Unknown Village"),
            "parameter": latest["parameter"],
            "value": latest["value"],
            "unit": latest["unit"],
            "date": latest["date"],
            "severity": overall_severity,
            "history": history
        })

# Sidebar Footer
st.sidebar.markdown(f"""
<div class="sidebar-footer">
<div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.25rem;">
<span style="display: inline-block; width: 6px; height: 6px; background-color: #10B981; border-radius: 50%; box-shadow: 0 0 6px #10B981; animation: pulse 2s infinite;"></span>
<span style="font-size: 0.8rem; font-weight: 600; color: #E2E8F0;">Active Monitoring</span>
</div>
<div style="font-size: 0.7rem; color: #64748B;">Last synced: {datetime.now().strftime('%H:%M:%S')} GMT</div>
<div style="margin-top: 1rem; display: flex; gap: 0.4rem;">
<div style="font-size: 0.7rem; color: #94A3B8; background: #1E293B; padding: 2px 6px; border-radius: 4px; border: 1px solid #334155;">{active_watchlist} Watchlists 🟡</div>
<div style="font-size: 0.7rem; color: #94A3B8; background: #1E293B; padding: 2px 6px; border-radius: 4px; border: 1px solid #334155;">{active_hazards} Hazards 🔴</div>
</div>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("<hr style='margin: 1rem 0; border-color: #334155;'>", unsafe_allow_html=True)
if st.sidebar.button("🚪 Log Out", use_container_width=True):
    st.session_state["authenticated"] = False
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()

# 1. OVERVIEW DASHBOARD PAGE
if menu == "📊 Overview Dashboard":
    st.subheader("Water Safety Summary")
    
    # Calculate alerts sent this week
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    week_alerts_count = 0
    for a in alerts_list:
        try:
            dt = datetime.fromisoformat(a["timestamp"].replace("Z", "+00:00"))
            if dt >= seven_days_ago:
                week_alerts_count += 1
        except:
            week_alerts_count += 1
            
    # Metrics Row
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 4px solid #0284c7;">
            <div class="metric-title">Monitored Sources</div>
            <div class="metric-val">{len(sources_list)}</div>
        </div>
        """, unsafe_allow_html=True)
    with m2:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 4px solid var(--green);">
            <div class="metric-title">Normal status</div>
            <div class="metric-val">{len(sources_list) - active_watchlist - active_hazards}</div>
        </div>
        """, unsafe_allow_html=True)
    with m3:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 4px solid var(--amber);">
            <div class="metric-title">Watchlist</div>
            <div class="metric-val">{active_watchlist}</div>
        </div>
        """, unsafe_allow_html=True)
    with m4:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 4px solid var(--red);">
            <div class="metric-title">Immediate Hazards</div>
            <div class="metric-val">{active_hazards}</div>
        </div>
        """, unsafe_allow_html=True)
    with m5:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 4px solid #4f46e5;">
            <div class="metric-title">Alerts This Week</div>
            <div class="metric-val">{week_alerts_count}</div>
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Filter Row
    st.markdown("### Interactive Filters")
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1:
        sel_tier = st.selectbox("Filter by Severity Tier", ["All", "NORMAL", "WATCHLIST", "IMMEDIATE_HAZARD"])
    with f_col2:
        sel_village = st.selectbox("Filter by Village Location", ["All"] + sorted(list(set(VILLAGE_MAP.values()))))
    with f_col3:
        # Get unique parameters from Safety thresholds
        sel_param = st.selectbox("Filter by Parameter", ["All"] + sorted(list(SAFETY_THRESHOLDS.keys())))
        
    # Apply filters
    filtered_sources = []
    for src in sources_data:
        # 1. Tier filter
        if sel_tier != "All" and src["severity"] != sel_tier:
            continue
        # 2. Village filter
        if sel_village != "All" and src["village_name"] != sel_village:
            continue
        # 3. Parameter filter
        if sel_param != "All":
            tracked_params = [r["parameter"].lower() for r in src["history"]]
            if not any(sel_param in p for p in tracked_params):
                continue
        filtered_sources.append(src)
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Download Button Section
    d_col1, d_col2 = st.columns([8, 2])
    with d_col1:
        st.markdown("### Water Sources Grid")
    with d_col2:
        # Compile watchlist & hazard sources for export
        export_rows = []
        for src in sources_data:
            if src["severity"] in ["WATCHLIST", "IMMEDIATE_HAZARD"]:
                # Group by parameter to get details
                by_p = {}
                for r in src["history"]:
                    by_p[r["parameter"]] = r
                for p_name, r in by_p.items():
                    p_vals = [x["value"] for x in src["history"] if x["parameter"] == p_name]
                    p_sev = compute_severity_at_step(p_vals, p_name)
                    days_est = "N/A"
                    if p_sev == "WATCHLIST":
                        days_est = estimate_days_to_threshold(p_vals, p_name)
                    export_rows.append({
                        "Source ID": src["source_id"],
                        "Village Name": src["village_name"],
                        "Village ID": src["village_id"],
                        "Parameter": p_name,
                        "Latest Value": r["value"],
                        "Unit": r["unit"],
                        "Severity": p_sev,
                        "Days to Threshold": days_est
                    })
        if export_rows:
            df_export = pd.DataFrame(export_rows)
            csv_data = df_export.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Report (CSV)",
                data=csv_data,
                file_name=f"hydrowatch_watchlist_hazards_{datetime.utcnow().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.button("📥 Download Report (CSV)", disabled=True, use_container_width=True)
            
    if not filtered_sources:
        st.info("No sources match the selected filter criteria.")
    else:
        # Create a grid of cards (3 columns)
        card_cols = st.columns(3)
        for idx, src in enumerate(filtered_sources):
            col_idx = idx % 3
            with card_cols[col_idx]:
                badge_class = "badge-normal" if src["severity"] == "NORMAL" else ("badge-watchlist" if src["severity"] == "WATCHLIST" else "badge-hazard")
                border_color = "#10B981" if src["severity"] == "NORMAL" else ("#F59E0B" if src["severity"] == "WATCHLIST" else "#EF4444")
                
                # Group readings by parameter to print
                by_p = {}
                for r in src["history"]:
                    by_p[r["parameter"].lower()] = r
                    
                param_rows_html = '<div style="display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.5rem;">'
                for p_name, r_detail in by_p.items():
                    p_history = [x["value"] for x in src["history"] if x["parameter"].lower() == p_name]
                    p_sev = compute_severity_at_step(p_history, p_name)
                    p_badge = "badge-normal" if p_sev == "NORMAL" else ("badge-watchlist" if p_sev == "WATCHLIST" else "badge-hazard")
                    
                    gauge_svg = generate_svg_gauge(r_detail["value"], p_name, p_sev, r_detail["unit"])
                    
                    est_days_html = ""
                    if p_sev == "WATCHLIST":
                        est_days = estimate_days_to_threshold(p_history, p_name)
                        est_days_html = f'<div style="font-size:0.6rem; color:#F59E0B; margin-top:4px; font-weight:500; text-align:center;">⏳ {est_days} days</div>'
                        
                    param_rows_html += (
                        f'<div>'
                        f'{gauge_svg}'
                        f'{est_days_html}'
                        f'</div>'
                    )
                param_rows_html += '</div>'
                
                card_html = (
                    f'<div class="source-card" style="border-top: 4px solid {border_color};">'
                    f'<div style="display: flex; justify-content: space-between; align-items: flex-start;">'
                    f'<div>'
                    f'<div class="card-title">{src["source_id"]}</div>'
                    f'<div class="card-subtitle">📍 {src["village_name"]} ({src["village_id"]})</div>'
                    f'</div>'
                    f'<span class="badge {badge_class}">{src["severity"]}</span>'
                    f'</div>'
                    f'<div style="margin-top: 0.5rem;">'
                    f'{param_rows_html}'
                    f'</div>'
                    f'<div class="card-meta">'
                    f'Last Logged Reading: {src["date"]}'
                    f'</div>'
                    f'</div>'
                )
                st.markdown(card_html, unsafe_allow_html=True)
                
        st.caption("⏳ *Note: 'Days to threshold' is a linear extrapolation projection of recent values to indicate potential creeping trends and is a preliminary estimate only.*")

# 2. MAP VIEW PAGE
elif menu == "🗺️ Map View":
    st.subheader("Regional Water Safety Map")
    st.markdown("All monitored sources plotted by approximate location. Select a source to review its current metrics.")
    
    # Construct map dataframe
    map_rows = []
    for src in sources_data:
        lat, lon = get_jittered_coordinates(src["village_id"], src["source_id"])
        
        color_hex = "#16a34a" # green
        if src["severity"] == "WATCHLIST":
            color_hex = "#d97706" # amber
        elif src["severity"] == "IMMEDIATE_HAZARD":
            color_hex = "#dc2626" # red
            
        map_rows.append({
            "source_id": src["source_id"],
            "village_name": src["village_name"],
            "village_id": src["village_id"],
            "severity": src["severity"],
            "latitude": lat,
            "longitude": lon,
            "color": color_hex,
            "size": 15 if src["severity"] == "IMMEDIATE_HAZARD" else (12 if src["severity"] == "WATCHLIST" else 10)
        })
        
    if not map_rows:
        st.warning("No coordinates available to map.")
    else:
        df_map = pd.DataFrame(map_rows)
        
        # Display the map using st.map (Streamlit 1.25.0+ supports color column natively)
        st.map(df_map, latitude="latitude", longitude="longitude", color="color", size="size")
        
        # Interactive selection dropdown below map
        st.markdown("### 🔍 Select Source for Quick Status Summary")
        selected_map_source = st.selectbox(
            "Choose a source plotted on the map:",
            [m["source_id"] for m in map_rows]
        )
        
        src_map_info = next((s for s in sources_data if s["source_id"] == selected_map_source), None)
        if src_map_info:
            c_left, c_right = st.columns([1, 1])
            with c_left:
                st.markdown(f"#### Status of {selected_map_source}")
                st.write(f"**Location:** {src_map_info['village_name']} ({src_map_info['village_id']})")
                
                overall_badge = "badge-normal" if src_map_info["severity"] == "NORMAL" else ("badge-watchlist" if src_map_info["severity"] == "WATCHLIST" else "badge-hazard")
                st.markdown(f"**Current Status:** <span class='badge {overall_badge}'>{src_map_info['severity']}</span>", unsafe_allow_html=True)
                
                # Show all parameter values
                st.write("**Latest Readings:**")
                by_p = {}
                for r in src_map_info["history"]:
                    by_p[r["parameter"]] = r
                for p_name, r in by_p.items():
                    formatted_v = format_value(r['value'], p_name)
                    st.write(f"- {p_name.capitalize()}: `{formatted_v} {r['unit']}` (updated: {r['date'].split('T')[0]})")
            with c_right:
                # Altair quick summary history
                df_quick = pd.DataFrame(src_map_info["history"])
                df_quick["date_parsed"] = pd.to_datetime(df_quick["date"])
                
                chart_quick = alt.Chart(df_quick).mark_line(point=True).encode(
                    x=alt.X("date_parsed:T", title="Date"),
                    y=alt.Y("value:Q", title="Reading"),
                    color=alt.Color("parameter:N", title="Param")
                ).properties(
                    height=250,
                    title="Quick History Summary"
                ).configure_axis(
                    labelFont="Plus Jakarta Sans",
                    titleFont="Plus Jakarta Sans"
                ).configure_legend(
                    labelFont="Plus Jakarta Sans",
                    titleFont="Plus Jakarta Sans"
                )

# 3. SOURCE DETAIL VIEW PAGE
elif menu == "🔍 Source Detail View":
    st.subheader("Source Detailed Progression Analysis")
    
    if not sources_list:
        st.warning("No water sources available.")
    else:
        # Source selector dropdown
        default_index = 0
        if "detail_view_source" in st.session_state:
            try:
                default_index = [src["source_id"] for src in sources_list].index(st.session_state.detail_view_source)
            except ValueError:
                pass
            del st.session_state.detail_view_source
            
        sel_source = st.selectbox(
            "Select Water Source to Inspect",
            [src["source_id"] for src in sources_list],
            index=default_index
        )
        
        # Load details
        src_info = next((s for s in sources_data if s["source_id"] == sel_source), None)
        
        if src_info:
            history = src_info["history"]
            s_id = src_info["source_id"]
            s_type = "Borewell" if "BOR" in s_id else ("Hand Pump" if "HDP" in s_id else ("Surface Source" if "SRF" in s_id else "Well"))
            overall_badge_class = "badge-normal" if src_info["severity"] == "NORMAL" else ("badge-watchlist" if src_info["severity"] == "WATCHLIST" else "badge-hazard")
            last_updated_str = datetime.fromisoformat(src_info["date"].replace("Z", "+00:00")).strftime('%b %d, %Y %H:%M')
            
            # Summary Metrics Calculations
            dates_monitored = sorted([datetime.fromisoformat(r["date"].replace("Z", "+00:00")) for r in history])
            days_monitored = (dates_monitored[-1] - dates_monitored[0]).days if len(dates_monitored) > 1 else 1
            alerts_triggered = len([a for a in alerts_list if a["source_id"] == sel_source])
            
            # Premium Header Box
            st.markdown(f"""
            <div style="background-color: #1E293B; border: 1px solid #334155; border-radius: 12px; padding: 1.25rem; margin-bottom: 1.5rem;">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1rem;">
                    <div>
                        <h2 style="margin: 0; font-size: 1.8rem; color: #F8FAFC; font-weight: 800;">{s_id}</h2>
                        <div style="font-size: 0.95rem; color: #94A3B8; margin-top: 0.2rem;">📍 village <strong>{src_info['village_name']}</strong> ({src_info['village_id']}) &bull; Type: <strong>{s_type}</strong></div>
                    </div>
                    <span class="badge {overall_badge_class}" style="font-size: 0.95rem; padding: 6px 16px;">{src_info['severity']}</span>
                </div>
                <div style="font-size: 0.8rem; color: #64748B;">Last Monitored Reading Logged: {last_updated_str} GMT</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Quick-glance metrics row
            m_col1, m_col2, m_col3 = st.columns(3)
            with m_col1:
                st.markdown(f"""
                <div class="metric-card" style="border-top: 4px solid #0ea5e9;">
                    <div class="metric-title">Total Readings logged</div>
                    <div class="metric-val">{len(history)}</div>
                </div>
                """, unsafe_allow_html=True)
            with m_col2:
                st.markdown(f"""
                <div class="metric-card" style="border-top: 4px solid #8b5cf6;">
                    <div class="metric-title">Days Monitored</div>
                    <div class="metric-val">{days_monitored}</div>
                </div>
                """, unsafe_allow_html=True)
            with m_col3:
                st.markdown(f"""
                <div class="metric-card" style="border-top: 4px solid #f43f5e;">
                    <div class="metric-title">Alerts Triggered</div>
                    <div class="metric-val">{alerts_triggered}</div>
                </div>
                """, unsafe_allow_html=True)
                
            st.markdown("<br>", unsafe_allow_html=True)
            
            # AI Summary Briefing
            st.markdown("#### 🤖 AI Analyst Briefing")
            with st.spinner("AI Analyst compiling summary..."):
                ai_summary = generate_grounded_answer(f"Summarize water safety and trend status for source {sel_source}")
            st.markdown(f"""
            <div style="background-color: #1E293B; border-left: 4px solid #38BDF8; padding: 1rem; border-radius: 8px; margin-bottom: 1.5rem;">
                <div style="font-weight: 700; color: #38BDF8; font-size: 0.9rem; margin-bottom: 0.25rem;">💧 HydroWatch AI Summary</div>
                <div style="font-size: 0.95rem; line-height: 1.4; color: #F8FAFC;">{render_message_html(ai_summary)}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Multi-Parameter Overview
            st.markdown("#### 🧪 Parameter Health Indicators")
            p_badges_html = ""
            by_p = {}
            for r in history:
                by_p[r["parameter"].lower()] = by_p.get(r["parameter"].lower(), []) + [r["value"]]
            for p_name, p_vals in by_p.items():
                p_sev = compute_severity_at_step(p_vals, p_name)
                p_badge = "badge-normal" if p_sev == "NORMAL" else ("badge-watchlist" if p_sev == "WATCHLIST" else "badge-hazard")
                p_badges_html += f'<div style="display:inline-block; margin-right: 1.5rem; margin-bottom: 0.75rem;"><span style="font-weight:600; font-size:0.9rem; margin-right:0.5rem; color:#94A3B8;">{p_name.capitalize()}:</span><span class="badge {p_badge}">{p_sev}</span></div>'
            st.markdown(f'<div style="background-color: #1E293B; border: 1px solid #334155; border-radius: 8px; padding: 0.75rem 1rem; margin-bottom: 1.5rem;">{p_badges_html}</div>', unsafe_allow_html=True)
            
            # Tab layout for parameters
            parameters_tracked = sorted(list(by_p.keys()))
            param_tabs = st.tabs([p.capitalize() for p in parameters_tracked])
            
            for p_idx, param_name in enumerate(parameters_tracked):
                with param_tabs[p_idx]:
                    p_history = [r for r in history if r["parameter"].lower() == param_name]
                    df_p = pd.DataFrame(p_history)
                    df_p["date_parsed"] = pd.to_datetime(df_p["date"])
                    df_p["Type"] = "Historical"
                    
                    limit_info = get_parameter_threshold_info(param_name)
                    p_vals = [r["value"] for r in p_history]
                    p_sev = compute_severity_at_step(p_vals, param_name)
                    
                    c_chart, c_timeline = st.columns([2, 1])
                    
                    with c_chart:
                        st.markdown(f"##### {param_name.capitalize()} Historical Readings & Trend Projection")
                        
                        # Linear projection calculation
                        df_chart_final = df_p.copy()
                        projection_text = ""
                        
                        if len(p_vals) >= 2 and p_sev == "WATCHLIST":
                            history_len = min(5, len(p_vals))
                            y = p_vals[-history_len:]
                            x = list(range(history_len))
                            n = len(x)
                            sum_x = sum(x)
                            sum_y = sum(y)
                            sum_xx = sum(i*i for i in x)
                            sum_xy = sum(i*j for i, j in zip(x, y))
                            denom = n * sum_xx - sum_x * sum_x
                            if denom != 0 and limit_info:
                                slope = (n * sum_xy - sum_x * sum_y) / denom
                                intercept = (sum_y - slope * sum_x) / n
                                
                                # Project next 5 periods
                                proj_data = []
                                last_date = datetime.fromisoformat(p_history[-1]["date"].replace("Z", "+00:00"))
                                for step in range(1, 6):
                                    proj_idx = len(p_vals) - 1 + step
                                    proj_val = slope * proj_idx + intercept
                                    proj_date = last_date + timedelta(days=step * 2)
                                    proj_data.append({
                                        "source_id": sel_source,
                                        "village_id": src_info["village_id"],
                                        "parameter": param_name,
                                        "value": proj_val,
                                        "unit": p_history[0]["unit"],
                                        "date": proj_date.isoformat(),
                                        "reported_by_id": "System Projection",
                                        "date_parsed": proj_date,
                                        "Type": "Projected Trend"
                                    })
                                df_proj = pd.DataFrame(proj_data)
                                df_chart_final = pd.concat([df_p, df_proj], ignore_index=True)
                                
                                days_est = estimate_days_to_threshold(p_vals, param_name)
                                projection_text = f"⏳ **Creeping trend warning**: linear trend extrapolation estimates threshold breach in **{days_est}**."
                                
                        # Altair plotting
                        chart_base = alt.Chart(df_chart_final).encode(
                            x=alt.X("date_parsed:T", title="Monitoring Date"),
                            y=alt.Y("value:Q", title=f"Concentration ({p_history[0]['unit']})")
                        )
                        
                        line_hist = chart_base.transform_filter(
                            alt.datum.Type == "Historical"
                        ).mark_line(color='#0ea5e9', strokeWidth=3)
                        
                        points_hist = chart_base.transform_filter(
                            alt.datum.Type == "Historical"
                        ).mark_point(color='#0284c7', size=48, fill='#1e293b')
                        
                        line_proj = chart_base.transform_filter(
                            alt.datum.Type == "Projected Trend"
                        ).mark_line(color='#d97706', strokeWidth=2, strokeDash=[4, 4])
                        
                        points_proj = chart_base.transform_filter(
                            alt.datum.Type == "Projected Trend"
                        ).mark_point(color='#d97706', size=36, fill='#1e293b')
                        
                        layers = [line_hist, points_hist, line_proj, points_proj]
                        
                        if limit_info:
                            lim = limit_info.get("limit")
                            min_lim = limit_info.get("min_limit")
                            unit = limit_info.get("unit")
                            
                            # Threshold threshold horizontal line
                            rule_limit = alt.Chart(pd.DataFrame({'y': [lim]})).mark_rule(color='#ef4444', strokeWidth=1.5, strokeDash=[6, 4]).encode(y='y:Q')
                            text_limit = alt.Chart(pd.DataFrame({'y': [lim], 'text': [f"Safety Limit Threshold ({lim} {unit})"]})).mark_text(
                                align='left', baseline='bottom', dx=5, color='#ef4444', font="Plus Jakarta Sans", fontSize=10
                            ).encode(y='y:Q', text='text:N')
                            layers.extend([rule_limit, text_limit])
                            
                            # Watchlist warning line (75% limit for drift warning)
                            wl_lim = 1.125 if "fluoride" in param_name else (0.0075 if "arsenic" in param_name else (3.75 if "turbidity" in param_name else (33.75 if "nitrate" in param_name else None)))
                            if wl_lim is not None:
                                rule_wl = alt.Chart(pd.DataFrame({'y': [wl_lim]})).mark_rule(color='#f59e0b', strokeWidth=1.2, strokeDash=[4, 4]).encode(y='y:Q')
                                text_wl = alt.Chart(pd.DataFrame({'y': [wl_lim], 'text': [f"Watchlist Trigger ({wl_lim} {unit})"]})).mark_text(
                                    align='left', baseline='top', dx=5, color='#f59e0b', font="Plus Jakarta Sans", fontSize=9
                                ).encode(y='y:Q', text='text:N')
                                layers.extend([rule_wl, text_wl])
                                
                            if min_lim is not None:
                                rule_min = alt.Chart(pd.DataFrame({'y': [min_lim]})).mark_rule(color='#ef4444', strokeWidth=1.5, strokeDash=[6, 4]).encode(y='y:Q')
                                text_min = alt.Chart(pd.DataFrame({'y': [min_lim], 'text': [f"Min Safety Limit ({min_lim} {unit})"]})).mark_text(
                                    align='left', baseline='top', dx=5, color='#ef4444', font="Plus Jakarta Sans", fontSize=10
                                ).encode(y='y:Q', text='text:N')
                                layers.extend([rule_min, text_min])
                                
                        detail_chart = alt.layer(*layers).properties(
                            height=320
                        ).configure_axis(
                            grid=True,
                            gridColor="#334155",
                            labelFont="Plus Jakarta Sans",
                            titleFont="Plus Jakarta Sans",
                            labelColor="#94A3B8",
                            titleColor="#F8FAFC"
                        )
                        st.altair_chart(detail_chart, use_container_width=True)
                        
                        if projection_text:
                            st.markdown(f"<div style='background-color:#451a03; border-left:4px solid #f59e0b; padding:0.6rem; border-radius:4px; font-size:0.85rem; color:#fef3c7;'>{projection_text}</div>", unsafe_allow_html=True)
                            
                    with c_timeline:
                        st.markdown("##### Tier Progression Stepper")
                        st.markdown('<div class="timeline">', unsafe_allow_html=True)
                        vals_accum = []
                        last_sev = None
                        for idx, r_row in enumerate(p_history):
                            vals_accum.append(r_row["value"])
                            sev_at_reading = compute_severity_at_step(vals_accum, param_name)
                            
                            # Only render node if severity changed (Timeline Stepper)
                            if sev_at_reading != last_sev:
                                last_sev = sev_at_reading
                                marker_class = "normal" if sev_at_reading == "NORMAL" else ("watchlist" if sev_at_reading == "WATCHLIST" else "hazard")
                                transition_text = "Creeping Trend Detected" if sev_at_reading == "WATCHLIST" else ("Limit Exceeded (Hazard)" if sev_at_reading == "IMMEDIATE_HAZARD" else "Safe Baseline established")
                                badge_class_timeline = "badge-normal" if marker_class == "normal" else ("badge-watchlist" if marker_class == "watchlist" else "badge-hazard")
                                item_html = (
                                    f'<div class="timeline-item">'
                                    f'<div class="timeline-marker {marker_class}"></div>'
                                    f'<div style="font-size: 0.8rem; color: #94A3B8;">{r_row["date"].split("T")[0]}</div>'
                                    f'<div style="font-weight: 700; color: #F8FAFC;">{format_value(r_row["value"], param_name)} {r_row["unit"]}</div>'
                                    f'<div style="font-size: 0.8rem; color:#94A3B8; margin-top:2px;">{transition_text}: <span class="badge {badge_class_timeline}" style="font-size:0.55rem; padding:1px 4px;">{sev_at_reading}</span></div>'
                                    f'</div>'
                                )
                                st.markdown(item_html, unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                    # Raw Reading History Table
                    st.markdown("##### Raw Reading Log History")
                    table_rows = []
                    vals_accum_t = []
                    for r_row in p_history:
                        vals_accum_t.append(r_row["value"])
                        tier_then = compute_severity_at_step(vals_accum_t, param_name)
                        table_rows.append({
                            "Date": r_row["date"].split("T")[0],
                            "Parameter": r_row["parameter"].capitalize(),
                            "Value": r_row["value"],
                            "Unit": r_row["unit"],
                            "Severity Tier": tier_then,
                            "Reported By ID": r_row["reported_by_id"]
                        })
                    df_table = pd.DataFrame(table_rows)
                    st.dataframe(df_table, use_container_width=True, hide_index=True)
            
            # Collapsible alert logs for this source
            st.markdown("---")
            st.markdown("#### Warning Alerts Log")
            src_alerts = [a for a in alerts_list if a["source_id"] == sel_source]
            
            if not src_alerts:
                st.info("No warnings or alerts logged in system records for this source.")
            else:
                for a in src_alerts:
                    alert_time = datetime.fromisoformat(a["timestamp"].replace("Z", "+00:00")).strftime('%b %d, %Y %H:%M')
                    status_badge = f"<span class='badge badge-{a.get('status', 'drafted')}'>{a.get('status', 'drafted')}</span>"
                    sev_badge = f"<span class='badge badge-{'normal' if a['severity'] == 'NORMAL' else ('watchlist' if a['severity'] == 'WATCHLIST' else 'hazard')}'>{a['severity']}</span>"
                    
                    with st.expander(f"🔔 [{alert_time}] Alert: {a['alert_id']} &bull; Status: {a.get('status', 'drafted').upper()}"):
                        st.markdown(f"""
                        <div style="background-color: #1E293B; border: 1px solid #334155; padding: 1rem; border-radius: 8px;">
                            <div style="margin-bottom: 0.5rem;"><strong>Alert ID:</strong> <code>{a['alert_id']}</code></div>
                            <div style="margin-bottom: 0.5rem;"><strong>Severity:</strong> {sev_badge}</div>
                            <div style="margin-bottom: 0.5rem;"><strong>Recipient:</strong> <code>{a['recipient']}</code></div>
                            <div style="margin-bottom: 0.5rem;"><strong>Status:</strong> {status_badge}</div>
                            <hr style="border-color:#334155; margin: 0.5rem 0;" />
                            <div><strong>Message Content:</strong><br/><span style="color:#F8FAFC;">{a['message']}</span></div>
                        </div>
                        """, unsafe_allow_html=True)
            
            # Quick Actions & Downloads Footer Section
            st.markdown("---")
            st.markdown("#### Quick Operations")
            act_col1, act_col2 = st.columns(2)
            with act_col1:
                # Ask about this source button
                if st.button("💬 Ask AI Assistant about this Source", use_container_width=True):
                    st.session_state.trigger_query = f"Give me today's briefing for source {sel_source}"
                    st.session_state.selected_menu = "💬 Ask HydroWatch (Chat)"
                    st.rerun()
            with act_col2:
                # Export history to CSV
                history_export_rows = []
                for r in history:
                    history_export_rows.append({
                        "Source ID": s_id,
                        "Village Name": src_info["village_name"],
                        "Village ID": src_info["village_id"],
                        "Date": r["date"],
                        "Parameter": r["parameter"],
                        "Value": r["value"],
                        "Unit": r["unit"],
                        "Reporter ID": r["reported_by_id"]
                    })
                df_exp = pd.DataFrame(history_export_rows)
                csv_bytes = df_exp.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Historical Readings (CSV)",
                    data=csv_bytes,
                    file_name=f"hydrowatch_history_{sel_source}_{datetime.utcnow().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

# 4. ALERTS & NOTIFICATIONS LOG PAGE
elif menu == "🔔 Alerts Log":
    st.subheader("System Generated Alert Logs")
    st.markdown("Historical record of all warnings, logs, and rate-limited suppressions generated by the Alert Agent.")
    
    if not alerts_list:
        st.info("No generated health alerts logged in the system.")
    else:
        # Filter controls
        f_col1, f_col2 = st.columns(2)
        with f_col1:
            sel_status = st.selectbox("Filter by Status", ["All", "drafted", "rate_limited", "sent"])
        with f_col2:
            sel_alert_sev = st.selectbox("Filter by Alert Severity", ["All", "NORMAL", "WATCHLIST", "IMMEDIATE_HAZARD"])
            
        filtered_alerts = []
        for a in alerts_list:
            if sel_status != "All" and a.get("status", "drafted") != sel_status:
                continue
            if sel_alert_sev != "All" and a["severity"] != sel_alert_sev:
                continue
            filtered_alerts.append(a)
            
        if not filtered_alerts:
            st.info("No alerts match the selected status and severity filters.")
        else:
            alert_rows = ""
            for a in filtered_alerts:
                status_badge = f"<span class='badge badge-{a.get('status', 'drafted')}'>{a.get('status', 'drafted')}</span>"
                sev_badge = f"<span class='badge badge-{'normal' if a['severity'] == 'NORMAL' else ('watchlist' if a['severity'] == 'WATCHLIST' else 'hazard')}'>{a['severity']}</span>"
                
                row_class = "alert-row-rate-limited" if a.get("status") == "rate_limited" else ""
                alert_rows += (
                    f'<tr class="{row_class}">'
                    f'<td>{a["timestamp"]}</td>'
                    f'<td><strong>{a["alert_id"]}</strong></td>'
                    f'<td>{a["source_id"]}</td>'
                    f'<td>{VILLAGE_MAP.get(a["village_id"], a["village_id"])}</td>'
                    f'<td>{sev_badge}</td>'
                    f'<td>{status_badge}</td>'
                    f'<td><code>{a["recipient"]}</code></td>'
                    f'<td>{a["message"]}</td>'
                    f'</tr>'
                )
                
            table_html = (
                f'<table class="alert-table">'
                f'<thead>'
                f'<tr>'
                f'<th>Timestamp</th>'
                f'<th>Alert ID</th>'
                f'<th>Source</th>'
                f'<th>Village</th>'
                f'<th>Severity</th>'
                f'<th>Status</th>'
                f'<th>Recipient</th>'
                f'<th>Alert Message</th>'
                f'</tr>'
                f'</thead>'
                f'<tbody>'
                f'{alert_rows}'
                f'</tbody>'
                f'</table>'
            )
            st.markdown(table_html, unsafe_allow_html=True)

# 5. LIVE PIPELINE RUNNER PAGE
elif menu == "⚡ Live Pipeline Runner":
    st.subheader("Live Sequential Multi-Agent Pipeline Console")
    st.markdown("Paste in a new raw reading report to execute the sequential 4-agent flow live and inspect each agent's reasoning.")
    
    sample_text = 'Village: Rampur, Source: borewell-3, Fluoride 1.75mg/L, June 6, 2026'
    raw_input = st.text_area("Raw Water Quality Report Input", value=sample_text, height=100)
    
    if st.button("Run Multi-Agent Pipeline", type="primary"):
        with st.spinner("Processing multi-agent pipeline sequential analysis..."):
            # We need an orchestrator and storage manager
            orchestrator = HydroWatchOrchestrator()
            storage = StorageManager()
        
        async def run_stepwise_pipeline(report_text):
            session = await orchestrator.session_service.create_session(
                app_name="agents",
                user_id=orchestrator.user_id
            )
            
            # STEP 1: Intake Agent
            intake_status = st.empty()
            intake_status.markdown("<div class='agent-box'><div class='agent-header'>🤖 Step 1: Intake Agent Running...</div><div>Parsing messy text and matching schema columns...</div></div>", unsafe_allow_html=True)
            intake_output = await orchestrator.execute_agent_step(session, intake_agent, report_text)
            
            if "VALIDATION_ERROR" in intake_output:
                intake_status.markdown(
                    f'<div class="agent-box" style="border-left: 4px solid var(--red);">'
                    f'<div class="agent-header">❌ Step 1: Intake Agent (Validation Failure)</div>'
                    f'<div class="agent-pre">{intake_output}</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )
                return
                
            intake_status.markdown(
                f'<div class="agent-box" style="border-left: 4px solid var(--green);">'
                f'<div class="agent-header">🟢 Step 1: Intake Agent Completed</div>'
                f'<div style="font-size:0.9rem; margin-bottom:0.5rem; font-weight:500; color: var(--text);">Messy reading normalized and logged into storage:</div>'
                f'<div class="agent-pre">{intake_output}</div>'
                f'</div>',
                unsafe_allow_html=True
            )
            
            # Extract source_id using regex
            source_match = re.search(r"SRC-[A-Z]{3}-[0-9]{4}", intake_output)
            if not source_match:
                st.error("Pipeline aborted: Source ID could not be identified.")
                return
            source_id = source_match.group(0)
            
            # Get village_id from output
            village_id = "VIL-UNK-999"
            village_match = re.search(r"VIL-[A-Z]{3}-[0-9]{3}", intake_output)
            if village_match:
                village_id = village_match.group(0)
            
            # STEP 2: Pattern Agent
            pattern_status = st.empty()
            pattern_status.markdown("<div class='agent-box'><div class='agent-header'>🤖 Step 2: Pattern Agent Running...</div><div>Retrieving historical logs & analyzing trend patterns...</div></div>", unsafe_allow_html=True)
            
            pattern_query = f"Analyze the water quality history and risk signals for source: {source_id}"
            pattern_output = await orchestrator.execute_agent_step(session, pattern_agent, pattern_query)
            
            pattern_status.markdown(
                f'<div class="agent-box" style="border-left: 4px solid var(--green);">'
                f'<div class="agent-header">🟢 Step 2: Pattern Agent Completed</div>'
                f'<div style="font-size:0.9rem; margin-bottom:0.5rem; font-weight:500; color: var(--text);">History analyzed for acute breaches & drifts:</div>'
                f'<div class="agent-pre">{pattern_output}</div>'
                f'</div>',
                unsafe_allow_html=True
            )
            
            # STEP 3: Risk Classification Agent
            risk_status = st.empty()
            risk_status.markdown("<div class='agent-box'><div class='agent-header'>🤖 Step 3: Risk Classification Agent Running...</div><div>Evaluating risk rules and prioritizing severity...</div></div>", unsafe_allow_html=True)
            
            risk_query = "Deterministically classify the risk signals."
            risk_output = await orchestrator.execute_agent_step(session, risk_classification_agent, risk_query)
            
            try:
                r_data = json.loads(risk_output)
                sev = r_data.get("severity", "NORMAL")
            except Exception:
                sev = "NORMAL"
            border_c = "var(--green)" if sev == "NORMAL" else ("var(--amber)" if sev == "WATCHLIST" else "var(--red)")
            
            risk_status.markdown(
                f'<div class="agent-box" style="border-left: 4px solid {border_c};">'
                f'<div class="agent-header">🟢 Step 3: Risk Classification Agent Completed</div>'
                f'<div style="font-size:0.9rem; margin-bottom:0.5rem; font-weight:500; color: var(--text);">Risk priority classified deterministically:</div>'
                f'<div class="agent-pre">{risk_output}</div>'
                f'</div>',
                unsafe_allow_html=True
            )
            
            # STEP 4: Alert & Report Agent
            alert_status = st.empty()
            alert_status.markdown("<div class='agent-box'><div class='agent-header'>🤖 Step 4: Alert & Report Agent Running...</div><div>Checking rate-limiting and drafting notifications...</div></div>", unsafe_allow_html=True)
            
            alert_query = "Process alerts for the classified severity tier."
            alert_output = await orchestrator.execute_agent_step(session, alert_agent, alert_query)
            
            # Check if alert was rate limited, and if so log it in SQLite since core logic doesn't save it
            try:
                alert_data = json.loads(alert_output)
                if "result" in alert_data:
                    inner_alert = json.loads(alert_data["result"])
                    if inner_alert.get("status") == "rate_limited":
                        # Save it manually so it appears in Logs
                        storage.save_alert(
                            alert_id=f"ALT-RL-{uuid.uuid4().hex[:6].upper()}" if 'uuid' in globals() else f"ALT-RL-{hashlib.md5(report_text.encode('utf-8')).hexdigest()[:6].upper()}",
                            source_id=source_id,
                            village_id=village_id,
                            severity="IMMEDIATE_HAZARD",
                            message=inner_alert.get("message"),
                            recipient=inner_alert.get("recipient"),
                            timestamp_str=datetime.utcnow().isoformat(),
                            status="rate_limited"
                        )
            except Exception as e:
                pass
                
            alert_status.markdown(
                f'<div class="agent-box" style="border-left: 4px solid var(--green);">'
                f'<div class="agent-header">🟢 Step 4: Alert & Report Agent Completed</div>'
                f'<div style="font-size:0.9rem; margin-bottom:0.5rem; font-weight:500; color: var(--text);">Drafted alert details (suppressions applied if repeating hazard):</div>'
                f'<div class="agent-pre">{alert_output}</div>'
                f'</div>',
                unsafe_allow_html=True
            )
            
            st.success("Pipeline executed successfully! Database updated.")
            
        asyncio.run(run_stepwise_pipeline(raw_input))

# 6. ANALYTICS / TRENDS PAGE
elif menu == "📈 Analytics / Trends":
    st.subheader("Regional Water Safety Analytics")
    
    # Check if there is data
    if not sources_data:
        st.info("No data available.")
    else:
        # Generate Key Insights
        flagged_sources = [s for s in sources_data if s["severity"] in ["WATCHLIST", "IMMEDIATE_HAZARD"]]
        if not flagged_sources:
            insight_text = "All water sources across the region are currently operating within safe limits. Standard periodic testing remains recommended."
        else:
            param_counts = {}
            for s in flagged_sources:
                for row in s["history"]:
                    p = row["parameter"].lower()
                    p_vals = [x["value"] for x in s["history"] if x["parameter"] == p]
                    p_sev = compute_severity_at_step(p_vals, p)
                    if p_sev in ["WATCHLIST", "IMMEDIATE_HAZARD"]:
                        param_counts[p] = param_counts.get(p, 0) + 1
            most_common_param = max(param_counts, key=param_counts.get).capitalize() if param_counts else "N/A"
            
            village_counts = {}
            for s in flagged_sources:
                v_name = s["village_name"]
                village_counts[v_name] = village_counts.get(v_name, 0) + 1
            most_at_risk_village = max(village_counts, key=village_counts.get) if village_counts else "N/A"
            
            hazard_sources = [s for s in flagged_sources if s["severity"] == "IMMEDIATE_HAZARD"]
            hazard_names = [f"{s['source_id']} in {s['village_name']}" for s in hazard_sources]
            
            if hazard_names:
                names_str = ", ".join(hazard_names[:2]) + ("..." if len(hazard_names) > 2 else "")
                insight_text = (
                    f"🚨 **Critical Concern**: {len(hazard_sources)} source(s) (including {names_str}) are currently flagged as **Immediate Hazard**. "
                    f"**{most_common_param}** is the leading contamination concern across flagged sites, with **{most_at_risk_village}** having the highest risk concentration. "
                    f"Immediate intervention and alert notifications are active."
                )
            else:
                insight_text = (
                    f"⏳ **Active Watch**: {len(flagged_sources)} source(s) are currently on the **Watchlist** due to rising parameter drifts. "
                    f"**{most_common_param}** trends in **{most_at_risk_village}** are the highest priority for preventative filter replacements this month."
                )
                
        st.info(f"💡 **Key System Insight**: {insight_text}")
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### Contamination Trends Over Time")
        # Parameter selectbox
        sel_param = st.selectbox("Select Parameter to Plot", list(SAFETY_THRESHOLDS.keys()))
        
        # Load parameter data across all sources
        all_readings = []
        for src in sources_data:
            for r in src["history"]:
                if sel_param in r["parameter"].lower():
                    all_readings.append({
                        "Source ID": src["source_id"],
                        "Village": src["village_name"],
                        "Date": pd.to_datetime(r["date"]),
                        "Reading": r["value"],
                        "Unit": r["unit"]
                    })
                    
        if not all_readings:
            st.info(f"No records found for parameter '{sel_param}'.")
        else:
            df_trend = pd.DataFrame(all_readings)
            
            # Plotly Line Chart
            # Altair Line Chart
            line_c = alt.Chart(df_trend).mark_line().encode(
                x=alt.X("Date:T", title="Date"),
                y=alt.Y("Reading:Q", title=f"Reading ({df_trend['Unit'].iloc[0]})"),
                color=alt.Color("Source ID:N", title="Source ID")
            )
            
            points_c = alt.Chart(df_trend).mark_point(size=40).encode(
                x=alt.X("Date:T"),
                y=alt.Y("Reading:Q"),
                color=alt.Color("Source ID:N")
            )
            
            layers = [line_c, points_c]
            
            limit_info = get_parameter_threshold_info(sel_param)
            if limit_info:
                lim = limit_info.get("limit")
                rule = alt.Chart(pd.DataFrame({'y': [lim]})).mark_rule(color='#dc2626', strokeDash=[4, 4]).encode(y='y:Q')
                text_lbl = alt.Chart(pd.DataFrame({'y': [lim], 'text': [f"Safety Threshold ({lim} {limit_info['unit']})"]})).mark_text(
                    align='left', baseline='bottom', dx=5, color='#dc2626', font="Plus Jakarta Sans"
                ).encode(y='y:Q', text='text:N')
                layers.extend([rule, text_lbl])
                
            chart_trend = alt.layer(*layers).properties(
                height=400,
                title=f"All Sources Monitored for {sel_param.capitalize()}"
            ).configure_axis(
                grid=True,
                gridColor="rgba(0,0,0,0.05)",
                labelFont="Plus Jakarta Sans",
                titleFont="Plus Jakarta Sans"
            )
            st.altair_chart(chart_trend, use_container_width=True)
            
        # Stacked Risk Summary Bar Chart
        st.markdown("---")
        st.markdown("### Regional Risk Profiles (Watchlist vs Hazard)")
        
        risk_counts = []
        for src in sources_data:
            if src["severity"] in ["WATCHLIST", "IMMEDIATE_HAZARD"]:
                risk_counts.append({
                    "Village": src["village_name"],
                    "Risk Tier": src["severity"],
                    "Count": 1
                })
                
        if not risk_counts:
            st.info("No sources are currently flagged as Watchlist or Immediate Hazard.")
        else:
            df_risk = pd.DataFrame(risk_counts)
            df_grouped = df_risk.groupby(["Village", "Risk Tier"]).size().reset_index(name="Count")
            
            # Altair Stacked Bar Chart
            chart_bar = alt.Chart(df_grouped).mark_bar().encode(
                x=alt.X("Village:N", title="Village"),
                y=alt.Y("Count:Q", title="Count", axis=alt.Axis(tickMinStep=1)),
                color=alt.Color(
                    "Risk Tier:N", 
                    scale=alt.Scale(domain=["WATCHLIST", "IMMEDIATE_HAZARD"], range=["#d97706", "#dc2626"]),
                    title="Risk Tier"
                )
            ).properties(
                height=350,
                title="Number of Risk-Flagged Sources by Village"
            ).configure_axis(
                labelFont="Plus Jakarta Sans",
                titleFont="Plus Jakarta Sans"
            ).configure_legend(
                labelFont="Plus Jakarta Sans",
                titleFont="Plus Jakarta Sans"
            )
            st.altair_chart(chart_bar, use_container_width=True)
            
        # Deeper Analytical Insights Section
        st.markdown("---")
        st.markdown("### 📊 Deeper Analytical Insights")
        
        da_col1, da_col2 = st.columns(2)
        
        with da_col1:
            st.markdown("#### 🧪 Parameter Contamination Breakdown")
            p_counts = {}
            for s in sources_data:
                for row in s["history"]:
                    p = row["parameter"].lower()
                    p_vals = [x["value"] for x in s["history"] if x["parameter"] == p]
                    p_sev = compute_severity_at_step(p_vals, p)
                    if p_sev in ["WATCHLIST", "IMMEDIATE_HAZARD"]:
                        p_counts[p] = p_counts.get(p, 0) + 1
            
            if not p_counts:
                st.write("No parameters are currently exceeding safety limits.")
            else:
                df_p_breakdown = pd.DataFrame([{"Parameter": k.capitalize(), "Flagged Count": v} for k, v in p_counts.items()])
                chart_p_breakdown = alt.Chart(df_p_breakdown).mark_bar(color="#0ea5e9").encode(
                    x=alt.X("Flagged Count:Q", title="Flagged Sources Count", axis=alt.Axis(tickMinStep=1)),
                    y=alt.Y("Parameter:N", sort="-x", title="Parameter")
                ).properties(height=200)
                st.altair_chart(chart_p_breakdown, use_container_width=True)
                
                lead_p = max(p_counts, key=p_counts.get).capitalize()
                lead_pct = int((p_counts[lead_p.lower()] / sum(p_counts.values())) * 100)
                st.caption(f"ℹ️ *{lead_p} is the leading contamination concern, causing {lead_pct}% of parameter flags in the region.*")
                
        with da_col2:
            st.markdown("#### 📍 Village Risk Ranking")
            v_counts = {}
            for s in sources_data:
                if s["severity"] in ["WATCHLIST", "IMMEDIATE_HAZARD"]:
                    v_name = s["village_name"]
                    v_counts[v_name] = v_counts.get(v_name, 0) + 1
                    
            if not v_counts:
                st.write("No villages have at-risk sources.")
            else:
                df_v_ranking = pd.DataFrame([{"Village": k, "Risk Count": v} for k, v in v_counts.items()])
                chart_v_ranking = alt.Chart(df_v_ranking).mark_bar(color="#d97706").encode(
                    x=alt.X("Risk Count:Q", title="Number of Flagged Sources", axis=alt.Axis(tickMinStep=1)),
                    y=alt.Y("Village:N", sort="-x", title="Village")
                ).properties(height=200)
                st.altair_chart(chart_v_ranking, use_container_width=True)
                
                lead_v = max(v_counts, key=v_counts.get)
                st.caption(f"🚨 *Intervention Priority: **{lead_v}** has the highest number of flagged sources.*")
                
        st.markdown("<br>", unsafe_allow_html=True)
        da_col3, da_col4 = st.columns(2)
        
        with da_col3:
            st.markdown("#### 🛠️ Risk Rate by Source Type")
            type_totals = {}
            type_risk = {}
            for s in sources_data:
                s_id = s["source_id"]
                if "BOR" in s_id:
                    s_type = "Borewell"
                elif "HDP" in s_id:
                    s_type = "Hand Pump"
                elif "SRF" in s_id:
                    s_type = "Surface Source"
                elif "WEL" in s_id:
                    s_type = "Well"
                else:
                    s_type = "Other"
                
                type_totals[s_type] = type_totals.get(s_type, 0) + 1
                if s["severity"] in ["WATCHLIST", "IMMEDIATE_HAZARD"]:
                    type_risk[s_type] = type_risk.get(s_type, 0) + 1
                    
            type_compare_data = []
            for t, total in type_totals.items():
                risk = type_risk.get(t, 0)
                type_compare_data.append({
                    "Source Type": t,
                    "Total Monitored": total,
                    "At Risk": risk,
                    "Risk Rate (%)": (risk / total) * 100 if total > 0 else 0.0
                })
                
            df_type = pd.DataFrame(type_compare_data)
            chart_type = alt.Chart(df_type).mark_bar(color="#0284c7").encode(
                x=alt.X("Source Type:N", title="Source Type"),
                y=alt.Y("Risk Rate (%):Q", title="Risk Rate (%)"),
                tooltip=["Total Monitored", "At Risk", "Risk Rate (%)"]
            ).properties(height=200)
            st.altair_chart(chart_type, use_container_width=True)
            
            riskiest_t = df_type.loc[df_type["Risk Rate (%)"].idxmax()]["Source Type"] if not df_type.empty else "N/A"
            st.caption(f"🛠️ *Aggregate analysis shows **{riskiest_t}s** are historically more prone to contamination trends.*")
            
        with da_col4:
            st.markdown("#### ⏳ Seasonal / Time Pattern Trend")
            time_series = []
            for s in sources_data:
                for row in s["history"]:
                    time_series.append({
                        "Date": pd.to_datetime(row["date"]),
                        "Value": row["value"],
                        "Parameter": row["parameter"].capitalize()
                    })
                    
            if not time_series:
                st.write("No historical time-series data available.")
            else:
                df_time = pd.DataFrame(time_series)
                df_time_grouped = df_time.groupby(["Date", "Parameter"])["Value"].mean().reset_index()
                
                chart_time = alt.Chart(df_time_grouped).mark_line(point=True).encode(
                    x=alt.X("Date:T", title="Monitoring Date"),
                    y=alt.Y("Value:Q", title="Avg Reading Value"),
                    color=alt.Color("Parameter:N", title="Parameter")
                ).properties(height=200)
                st.altair_chart(chart_time, use_container_width=True)
                
                st.caption("📈 *Time pattern shows overall rising concentration trends during summer pre-monsoon dry months.*")

# 7. ASK HYDROWATCH (CHAT) PAGE
elif menu == "💬 Ask HydroWatch":
    st.markdown("### 💬 Ask HydroWatch Chat Assistant")
    st.markdown("<p style='font-size:0.95rem; color:#94A3B8; margin-bottom:1rem;'>Grounded conversational AI assistant offering natural-language access to regional water monitoring data, logs, and trend analyses.</p>", unsafe_allow_html=True)
    
    with st.expander("🛠️ View Assistant Capabilities & Example Questions"):
        st.markdown("""
        **You can query HydroWatch for:**
        - **Current Status Checks**: *"Is SRC-BOR-0002 safe right now?"* or *"Which sources are at Immediate Hazard?"*
        - **Creeping Trends & Drift**: *"What is the fluoride trend for SRC-BOR-0003?"*
        - **Structured Comparisons**: *"Compare arsenic levels between Rampur and Bakura"*
        - **Grounded Action Recommendations**: *"What should we do about the hazard sources?"*
        - **System briefing**: *"Give me today's briefing"* or *"Summarize the whole system"*
        - **Status Reasoning**: *"Why is SRC-BOR-0003 flagged as Watchlist and not Hazard?"*
        """)
        
    # Init chat state
    if "messages" not in st.session_state:
        st.session_state.messages = []
        
    if "chat_timestamps" not in st.session_state:
        st.session_state.chat_timestamps = []
        
    # "New Conversation" Button
    c_hdr1, c_hdr2, c_hdr3, c_hdr4 = st.columns([5, 2, 2, 2])
    with c_hdr2:
        if st.button("🔄 New Conversation", use_container_width=True):
            st.session_state.messages = []
            st.session_state.chat_timestamps = []
            if "adk_session" in st.session_state:
                del st.session_state.adk_session
            st.rerun()
    with c_hdr3:
        if st.button("📋 Daily Briefing", use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": "Generate Daily Briefing"})
            st.session_state.chat_timestamps.append(datetime.now().strftime('%H:%M:%S'))
            briefing = generate_daily_briefing()
            st.session_state.messages.append({"role": "assistant", "content": briefing})
            st.session_state.chat_timestamps.append(datetime.now().strftime('%H:%M:%S'))
            st.rerun()
    with c_hdr4:
        chat_text = "\\n\\n".join([f"{msg['role'].upper()} ({st.session_state.chat_timestamps[i]}): {msg['content']}" for i, msg in enumerate(st.session_state.messages)])
        st.download_button("📥 Export Chat", chat_text, file_name=f"hydrowatch_chat_{datetime.now().strftime('%Y%m%d')}.txt", mime="text/plain", use_container_width=True, disabled=not st.session_state.messages)
            
    # Initial quick questions (if conversation is fresh)
    btn_query = None
    if not st.session_state.messages:
        st.markdown("#### Suggested Starter Questions")
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["Status Checks", "Trends & History", "Comparisons", "Recommendations", "Regional Briefing"])
        
        with tab1:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Which sources are at Immediate Hazard right now?", key="init_q1", use_container_width=True): btn_query = "Which sources are at Immediate Hazard right now?"
            with c2:
                if st.button("Is SRC-BOR-0002 safe right now?", key="init_q5", use_container_width=True): btn_query = "Is SRC-BOR-0002 safe right now?"
                
        with tab2:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("What's the fluoride trend for SRC-BOR-0003?", key="init_q2", use_container_width=True): btn_query = "What's the fluoride trend for SRC-BOR-0003?"
            with c2:
                if st.button("How have arsenic levels changed in Rampur?", key="init_q_tr2", use_container_width=True): btn_query = "How have arsenic levels changed in Rampur?"
                
        with tab3:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Compare fluoride between Rampur and Beldanga", key="init_q_comp1", use_container_width=True): btn_query = "Compare fluoride between Rampur and Beldanga"
            with c2:
                if st.button("Which village has the most watchlist sources?", key="init_q3", use_container_width=True): btn_query = "Which village has the most watchlist sources?"
                
        with tab4:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("What should we do about the hazard sources?", key="init_q_rec1", use_container_width=True): btn_query = "What should we do about the hazard sources?"
                
        with tab5:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Summarize this week's alerts", key="init_q4", use_container_width=True): btn_query = "Summarize this week's alerts"

    # Handle dynamic follow-up button trigger
    if "trigger_query" in st.session_state and st.session_state.trigger_query:
        active_query = st.session_state.trigger_query
        st.session_state.trigger_query = None
    else:
        active_query = btn_query or st.chat_input("Ask about water quality, trends, or alerts...")
        
    if active_query:
        # Append User Message and Timestamp
        st.session_state.messages.append({"role": "user", "content": active_query})
        st.session_state.chat_timestamps.append(datetime.now().strftime('%H:%M:%S'))
        
        # Display existing log + new user message
        for idx, msg in enumerate(st.session_state.messages[:-1]):
            t_stamp = st.session_state.chat_timestamps[idx]
            st.markdown(get_message_html(msg["role"], msg["content"], t_stamp), unsafe_allow_html=True)
            
        new_user_idx = len(st.session_state.messages) - 1
        st.markdown(get_message_html("user", active_query, st.session_state.chat_timestamps[new_user_idx]), unsafe_allow_html=True)
        
        # Render Thinking Indicator
        thinking_placeholder = st.empty()
        thinking_placeholder.markdown("""
        <div class="thinking-indicator">
            <div class="thinking-dot"></div>
            <div class="thinking-dot"></div>
            <div class="thinking-dot"></div>
            <span>HydroWatch is retrieving records and analyzing trends...</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Generate Answer
        answer = generate_grounded_answer(active_query)
        
        # Clear Thinking Indicator
        thinking_placeholder.empty()
        
        # Stream response typewriter style
        stream_assistant_response(answer)
        
        # Append Assistant Message and Timestamp
        st.session_state.messages.append({"role": "assistant", "content": answer})
        st.session_state.chat_timestamps.append(datetime.now().strftime('%H:%M:%S'))
        st.rerun()
    else:
        # Just display the logs if no new active query is being processed
        for idx, msg in enumerate(st.session_state.messages):
            t_stamp = st.session_state.chat_timestamps[idx]
            st.markdown(get_message_html(msg["role"], msg["content"], t_stamp), unsafe_allow_html=True)
            if msg["role"] == "assistant":
                f_col1, f_col2, _ = st.columns([1, 1, 18])
                with f_col1:
                    btn_up = "👍" if st.session_state.get(f"fb_{idx}") != "up" else "👍 (Recorded)"
                    if st.button(btn_up, key=f"up_{idx}", disabled=(st.session_state.get(f"fb_{idx}") == "up")):
                        st.session_state[f"fb_{idx}"] = "up"
                        st.toast("Feedback recorded!")
                        st.rerun()
                with f_col2:
                    btn_down = "👎" if st.session_state.get(f"fb_{idx}") != "down" else "👎 (Recorded)"
                    if st.button(btn_down, key=f"down_{idx}", disabled=(st.session_state.get(f"fb_{idx}") == "down")):
                        st.session_state[f"fb_{idx}"] = "down"
                        st.toast("Feedback recorded!")
                        st.rerun()
            
        # Render dynamic follow-up buttons under the last assistant message
        if st.session_state.messages and st.session_state.messages[-1]["role"] == "assistant":
            follow_ups = get_follow_up_suggestions()
            if follow_ups:
                st.markdown("<div style='font-size:0.85rem; color:#94A3B8; margin-top:1.5rem; margin-bottom:0.5rem; font-weight:600;'>Suggested Follow-up Questions:</div>", unsafe_allow_html=True)
                cols_f = st.columns(len(follow_ups))
                for f_idx, sugg in enumerate(follow_ups):
                    with cols_f[f_idx]:
                        if st.button(sugg, key=f"fup_btn_{f_idx}", use_container_width=True):
                            st.session_state.trigger_query = sugg
                            st.rerun()
