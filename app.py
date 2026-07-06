import os
import sys
import json
import asyncio
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

from agents.orchestrator import HydroWatchOrchestrator
from schema.bq_schema import StorageManager

app = FastAPI(title="HydroWatch - Water Quality Monitoring System")

# Initialize orchestrator and storage
orchestrator = HydroWatchOrchestrator()
storage = StorageManager()

# HTML Dashboard Template
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HydroWatch Dashboard | Public Health Water Monitoring</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0a0f1d;
            --bg-secondary: #131b2e;
            --bg-tertiary: #1e2942;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-blue: #3b82f6;
            --accent-green: #10b981;
            --accent-red: #ef4444;
            --accent-yellow: #f59e0b;
            --border-color: rgba(255, 255, 255, 0.08);
            --glow-color: rgba(59, 130, 246, 0.15);
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Plus Jakarta Sans', sans-serif;
        }

        body {
            background-color: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            overflow-x: hidden;
        }

        header {
            background: linear-gradient(135deg, var(--bg-secondary) 0%, rgba(19, 27, 46, 0.8) 100%);
            padding: 1.5rem 2rem;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
            backdrop-filter: blur(10px);
            position: sticky;
            top: 0;
            z-index: 100;
        }

        .logo-container {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }

        .logo-icon {
            width: 2.2rem;
            height: 2.2rem;
            background: linear-gradient(135deg, var(--accent-blue) 0%, #60a5fa 100%);
            border-radius: 30% 70% 70% 30% / 30% 30% 70% 70%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            color: white;
            box-shadow: 0 0 15px var(--accent-blue);
            animation: morph 8s ease-in-out infinite;
        }

        @keyframes morph {
            0% { border-radius: 30% 70% 70% 30% / 30% 30% 70% 70%; }
            50% { border-radius: 70% 30% 30% 70% / 70% 70% 30% 30%; }
            100% { border-radius: 30% 70% 70% 30% / 30% 30% 70% 70%; }
        }

        .logo-text {
            font-size: 1.5rem;
            font-weight: 700;
            letter-spacing: -0.5px;
            background: linear-gradient(to right, #fff 30%, var(--text-secondary) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .tagline {
            font-size: 0.8rem;
            color: var(--accent-blue);
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1.5px;
        }

        .container {
            max-width: 1400px;
            margin: 2rem auto;
            padding: 0 1.5rem;
            width: 100%;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2rem;
            flex-grow: 1;
        }

        @media (max-width: 1024px) {
            .container {
                grid-template-columns: 1fr;
            }
        }

        .card {
            background-color: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 1rem;
            padding: 2rem;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
            transition: all 0.3s ease;
        }

        .card:hover {
            border-color: rgba(59, 130, 246, 0.3);
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.3), 0 0 15px var(--glow-color);
        }

        .card-title {
            font-size: 1.25rem;
            font-weight: 600;
            margin-bottom: 1.5rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 0.75rem;
        }

        /* Form styling */
        .form-group {
            margin-bottom: 1.25rem;
        }

        label {
            display: block;
            font-size: 0.875rem;
            color: var(--text-secondary);
            margin-bottom: 0.5rem;
            font-weight: 500;
        }

        textarea {
            width: 100%;
            height: 120px;
            background-color: var(--bg-primary);
            border: 1px solid var(--border-color);
            border-radius: 0.5rem;
            padding: 1rem;
            color: var(--text-primary);
            font-size: 0.95rem;
            resize: none;
            transition: border-color 0.2s;
        }

        textarea:focus {
            outline: none;
            border-color: var(--accent-blue);
        }

        .btn {
            background: linear-gradient(135deg, var(--accent-blue) 0%, #1d4ed8 100%);
            color: white;
            border: none;
            border-radius: 0.5rem;
            padding: 0.85rem 1.5rem;
            font-weight: 600;
            cursor: pointer;
            width: 100%;
            transition: all 0.2s;
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
        }

        .btn:hover {
            transform: translateY(-1px);
            box-shadow: 0 6px 18px rgba(59, 130, 246, 0.4);
        }

        /* Status Metrics */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 1rem;
            margin-bottom: 1.5rem;
        }

        .metric-card {
            background-color: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 0.75rem;
            padding: 1.25rem;
            text-align: center;
        }

        .metric-value {
            font-size: 1.75rem;
            font-weight: 700;
            margin-bottom: 0.25rem;
        }

        .metric-label {
            font-size: 0.75rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        /* Log tables */
        .table-container {
            max-height: 400px;
            overflow-y: auto;
            margin-top: 1rem;
            border: 1px solid var(--border-color);
            border-radius: 0.5rem;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 0.875rem;
        }

        th {
            background-color: var(--bg-tertiary);
            color: var(--text-primary);
            padding: 0.75rem 1rem;
            font-weight: 600;
            position: sticky;
            top: 0;
        }

        td {
            padding: 0.75rem 1rem;
            border-bottom: 1px solid var(--border-color);
            color: var(--text-secondary);
        }

        tr:hover td {
            background-color: rgba(255, 255, 255, 0.02);
            color: var(--text-primary);
        }

        .badge {
            display: inline-block;
            padding: 0.25rem 0.5rem;
            border-radius: 0.25rem;
            font-size: 0.75rem;
            font-weight: 600;
        }

        .badge-hazard {
            background-color: rgba(239, 68, 68, 0.15);
            color: var(--accent-red);
        }

        .badge-normal {
            background-color: rgba(16, 185, 129, 0.15);
            color: var(--accent-green);
        }

        .badge-watchlist {
            background-color: rgba(245, 158, 11, 0.15);
            color: var(--accent-yellow);
        }

        .json-result-box {
            background-color: #05070f;
            border: 1px solid var(--border-color);
            border-radius: 0.5rem;
            padding: 1rem;
            font-family: monospace;
            font-size: 0.85rem;
            max-height: 250px;
            overflow-y: auto;
            color: #38bdf8;
            margin-top: 1.5rem;
            display: none;
        }

        footer {
            text-align: center;
            padding: 2rem;
            color: var(--text-secondary);
            font-size: 0.85rem;
            border-top: 1px solid var(--border-color);
            margin-top: auto;
        }
    </style>
</head>
<body>
    <header>
        <div class="logo-container">
            <div class="logo-icon">H</div>
            <div>
                <h1 class="logo-text">HydroWatch</h1>
                <div class="tagline">Water Quality Multi-Agent System</div>
            </div>
        </div>
        <div style="font-size: 0.85rem; color: var(--accent-green); display: flex; align-items: center; gap: 0.5rem;">
            <span style="display: inline-block; width: 8px; height: 8px; background-color: var(--accent-green); border-radius: 50%; box-shadow: 0 0 8px var(--accent-green);"></span>
            Dual-Mode (GCP BigQuery / SQLite) Fallback Layer Active
        </div>
    </header>

    <div class="container">
        <!-- Left Column: Input Form -->
        <div style="display: flex; flex-direction: column; gap: 2rem;">
            <div class="card">
                <h2 class="card-title">📝 Ingest Raw Water Quality Report</h2>
                <form id="ingest-form" onsubmit="submitReading(event)">
                    <div class="form-group">
                        <label for="readingText">ASHA Worker / Volunteer Raw Text (CSV or Free-text)</label>
                        <textarea id="readingText" name="text" placeholder="e.g. Village: Rampur, Source: borewell-3, pH 7.2, Fluoride 1.8mg/L, June 5" required></textarea>
                    </div>
                    <button type="submit" class="btn">🚀 Ingest & Process Pipeline</button>
                </form>

                <div class="json-result-box" id="result-box"></div>
            </div>

            <!-- Real-time Alerts Panel -->
            <div class="card">
                <h2 class="card-title">🚨 Active Safety Alerts / Logs</h2>
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Alert ID</th>
                                <th>Source</th>
                                <th>Severity</th>
                                <th>Recipient</th>
                                <th>Timestamp</th>
                            </tr>
                        </thead>
                        <tbody id="alerts-table-body">
                            <!-- Populated dynamically -->
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Right Column: Monitoring Logs & Stats -->
        <div style="display: flex; flex-direction: column; gap: 2rem;">
            <div class="card">
                <h2 class="card-title">📊 Monitor Analytics</h2>
                <div class="metrics-grid">
                    <div class="metric-card">
                        <div class="metric-value" style="color: var(--accent-blue);" id="stat-readings">0</div>
                        <div class="metric-label">Readings</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value" style="color: var(--accent-red);" id="stat-hazards">0</div>
                        <div class="metric-label">Hazards</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value" style="color: var(--accent-yellow);" id="stat-alerts">0</div>
                        <div class="metric-label">Total Alerts</div>
                    </div>
                </div>

                <h3 style="font-size: 1rem; margin-bottom: 0.5rem; color: var(--text-secondary);">Recent Logged Readings</h3>
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Source</th>
                                <th>Parameter</th>
                                <th>Value</th>
                                <th>Unit</th>
                                <th>Timestamp</th>
                            </tr>
                        </thead>
                        <tbody id="readings-table-body">
                            <!-- Populated dynamically -->
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <footer>
        <p>&copy; 2026 HydroWatch multi-agent system. Developed for Kaggle Capstone Project (Agents for Good track).</p>
    </footer>

    <script>
        async function loadData() {
            try {
                const response = await fetch('/api/data');
                const data = await response.json();
                
                // Update metrics
                document.getElementById('stat-readings').innerText = data.stats.total_readings;
                document.getElementById('stat-hazards').innerText = data.stats.hazard_count;
                document.getElementById('stat-alerts').innerText = data.stats.total_alerts;

                // Populate readings
                const readingsTbody = document.getElementById('readings-table-body');
                readingsTbody.innerHTML = '';
                data.readings.forEach(row => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td>${row.source_id}</td>
                        <td>${row.parameter}</td>
                        <td><strong>${row.value}</strong></td>
                        <td>${row.unit}</td>
                        <td style="font-size: 0.75rem;">${row.date.replace('T', ' ')}</td>
                    `;
                    readingsTbody.appendChild(tr);
                });

                // Populate alerts
                const alertsTbody = document.getElementById('alerts-table-body');
                alertsTbody.innerHTML = '';
                data.alerts.forEach(row => {
                    const tr = document.createElement('tr');
                    let badgeClass = 'badge-normal';
                    if (row.severity === 'IMMEDIATE_HAZARD') badgeClass = 'badge-hazard';
                    if (row.severity === 'WATCHLIST') badgeClass = 'badge-watchlist';
                    
                    tr.innerHTML = `
                        <td style="font-family: monospace;">${row.alert_id}</td>
                        <td>${row.source_id}</td>
                        <td><span class="badge ${badgeClass}">${row.severity}</span></td>
                        <td style="font-size: 0.75rem;">${row.recipient}</td>
                        <td style="font-size: 0.75rem;">${row.created_at.replace('T', ' ')}</td>
                    `;
                    alertsTbody.appendChild(tr);
                });

            } catch (err) {
                console.error("Error loading dashboard data:", err);
            }
        }

        async function submitReading(e) {
            e.preventDefault();
            const text = document.getElementById('readingText').value;
            const resultBox = document.getElementById('result-box');
            resultBox.style.display = 'block';
            resultBox.innerHTML = 'Processing through sequential agent pipeline...';

            try {
                const response = await fetch('/api/ingest', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ text })
                });
                const result = await response.json();
                resultBox.innerHTML = JSON.stringify(result, null, 2);
                document.getElementById('readingText').value = '';
                
                // Reload dashboard stats
                await loadData();
            } catch (err) {
                resultBox.innerHTML = 'Error calling pipeline: ' + err;
            }
        }

        // Initial load and periodic refresh
        loadData();
        setInterval(loadData, 5000);
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    return DASHBOARD_HTML

@app.get("/api/data")
async def get_api_data():
    """Returns analytics, historical readings and drafted alerts."""
    try:
        # Get readings and alerts history
        # (Using safe SQLite fallbacks for simple query outputs)
        import sqlite3
        from schema.bq_schema import DB_NAME
        
        # If BigQuery is configured, query BigQuery. Otherwise query SQLite.
        if not storage.use_sqlite:
            # Dual-mode: for dashboard we query the local SQLite fallback for speed,
            # or BigQuery client. Let's fallback to local SQLite for simplicity.
            pass
        
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Readings
        cursor.execute("SELECT source_id, village_id, parameter, value, unit, date, reported_by_id FROM readings ORDER BY date DESC LIMIT 30")
        readings = [dict(row) for row in cursor.fetchall()]
        
        # Alerts
        cursor.execute("SELECT alert_id, source_id, severity, recipient, message, timestamp AS created_at FROM alerts ORDER BY timestamp DESC LIMIT 30")
        alerts = [dict(row) for row in cursor.fetchall()]
        
        # Total counts
        cursor.execute("SELECT COUNT(*) FROM readings")
        total_readings = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM alerts")
        total_alerts = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT source_id) FROM alerts WHERE severity='IMMEDIATE_HAZARD'")
        hazard_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "readings": readings,
            "alerts": alerts,
            "stats": {
                "total_readings": total_readings,
                "total_alerts": total_alerts,
                "hazard_count": hazard_count
            }
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/ingest")
async def ingest_reading(payload: dict):
    """POST endpoint to ingest raw reading text and run sequential agent pipeline."""
    text = payload.get("text", "")
    if not text:
        return JSONResponse(status_code=400, content={"error": "Text payload is empty"})
        
    try:
        res = await orchestrator.run_pipeline(text)
        return res
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
