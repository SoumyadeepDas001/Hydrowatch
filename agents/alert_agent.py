import os
import sys
import json
import uuid
from datetime import datetime
from google.adk import Agent
from schema.bq_schema import StorageManager

storage = StorageManager()

# Village contacts mapping
VILLAGE_CONTACTS = {
    "VIL-RAM-001": "health_officer_rampur@gov.in",
    "VIL-SUN-002": "health_officer_sundarpur@gov.in",
    "VIL-HAR-003": "health_officer_haripur@gov.in"
}
DEFAULT_CONTACT = "district_health_officer@gov.in"

# Define the alert drafting tool
def draft_alert(source_id: str, severity: str, recipient_type: str = "health_officer") -> str:
    """
    Drafts, logs, and stores a health alert for a water source. Applies a 48-hour rate limit on
    IMMEDIATE_HAZARD alerts per source to prevent alert fatigue.
    
    Args:
        source_id: The Source ID e.g. SRC-BOR-0003
        severity: The severity tier (IMMEDIATE_HAZARD, WATCHLIST, NORMAL)
        recipient_type: Category of recipient e.g. health_officer
    """
    try:
        # 1. Retrieve history to determine village_id
        history = storage.get_source_history(source_id)
        village_id = "VIL-UNKNOWN-999"
        if history:
            village_id = history[0].get("village_id", "VIL-UNKNOWN-999")
            
        recipient = VILLAGE_CONTACTS.get(village_id, DEFAULT_CONTACT)
        
        # 2. Check 48-hour rate limiting on IMMEDIATE_HAZARD
        if severity == "IMMEDIATE_HAZARD":
            recent_alerts = storage.get_recent_alerts(source_id, limit_hours=48)
            if recent_alerts:
                return json.dumps({
                    "alert_id": recent_alerts[0]["alert_id"],
                    "status": "rate_limited",
                    "recipient": recipient,
                    "message": "Alert was suppressed due to 48-hour rate limit on IMMEDIATE_HAZARD notifications."
                })

        # 3. Create alert
        alert_id = f"ALT-{uuid.uuid4().hex[:8].upper()}"
        timestamp = datetime.utcnow().isoformat()
        
        if severity == "IMMEDIATE_HAZARD":
            message = (
                f"[URGENT PUBLIC HEALTH ALERT] Critical contamination detected at water source {source_id} "
                f"in village {village_id}. Exposure risks present. Immediate shutoff or warning required."
            )
        elif severity == "WATCHLIST":
            message = (
                f"[WATCHLIST DIGEST] Water source {source_id} in village {village_id} has demonstrated "
                f"a slow-drift contamination trend over recent readings. Remedial maintenance recommended."
            )
        else:
            message = f"[NORMAL STATUS LOG] Water source {source_id} in village {village_id} is operating within normal safety limits."
            
        # 4. Save to DB
        storage.save_alert(
            alert_id=alert_id,
            source_id=source_id,
            village_id=village_id,
            severity=severity,
            message=message,
            recipient=recipient,
            timestamp_str=timestamp
        )
        
        return json.dumps({
            "alert_id": alert_id,
            "status": "drafted",
            "recipient": recipient,
            "message": message
        })
    except Exception as e:
        return json.dumps({"error": str(e)})

ALERT_INSTRUCTIONS = """
You are the Alert & Report Agent of the HydroWatch system.
Your job is to read the risk classification tier (IMMEDIATE_HAZARD, WATCHLIST, or NORMAL) for a water source, call the `draft_alert` tool, and present the drafted alert details to the user.

STEPS:
1. Identify the severity tier, source_id, and parameter from the risk classification signal.
2. Call the `draft_alert` tool with the source_id and severity.
3. Show the final alert outcome clearly in JSON. Specify whether the alert was drafted or rate-limited.
"""

alert_agent = Agent(
    name="alert_agent",
    model="gemini-2.5-flash",
    instruction=ALERT_INSTRUCTIONS,
    tools=[draft_alert]
)
