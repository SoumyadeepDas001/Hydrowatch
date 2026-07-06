import os
import sys
import asyncio
import json

# Ensure parent directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import seed
from agents.orchestrator import HydroWatchOrchestrator

async def run_progression():
    print("==================================================")
    print("      HYDRO WATCH DRIFT SEVERITY PROGRESSION      ")
    print("==================================================")
    
    # 1. Clean database to start with a fresh slate
    seed.clean_local_db()
    
    orchestrator = HydroWatchOrchestrator()
    
    # The 5 chronological readings of the drift scenario
    steps = [
        ("June 1, 2026", "1.1mg/L"),
        ("June 2, 2026", "1.2mg/L"),
        ("June 3, 2026", "1.3mg/L"),
        ("June 4, 2026", "1.4mg/L"),
        ("June 5, 2026", "1.6mg/L"),
    ]
    
    progression = []
    
    for idx, (date, value) in enumerate(steps, 1):
        raw_report = f"Village: Rampur, Source: borewell-3, Fluoride {value}, {date}"
        print(f"\nProcessing Reading {idx}: {value} ({date})...")
        
        # Run pipeline
        res = await orchestrator.run_pipeline(raw_report)
        
        # Extract risk classification
        risk_data = json.loads(res["risk"])
        severity = risk_data.get("severity", "UNKNOWN")
        msg = risk_data.get("message", "")
        
        progression.append(severity)
        
        print(f"-> Risk Tier: {severity}")
        print(f"-> Message:   {msg}")
        
    print("\n==================================================")
    print("PROGRESSION SUMMARY:")
    print(" -> ".join(progression))
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_progression())
