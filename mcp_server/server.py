import json
import sys
import os
import traceback
import uuid
from datetime import datetime
from schema.bq_schema import StorageManager

# Set up StorageManager
storage = StorageManager()

# Static versioned WHO/BIS thresholds reference
SAFETY_THRESHOLDS = {
    "fluoride": {
        "limit": 1.5,
        "unit": "mg/L",
        "standard_reference": "WHO (2011) / BIS (IS 10500:2012)"
    },
    "arsenic": {
        "limit": 0.01,
        "unit": "mg/L",
        "standard_reference": "WHO (2011) / BIS (IS 10500:2012)"
    },
    "turbidity": {
        "limit": 5.0,
        "unit": "NTU",
        "standard_reference": "WHO (2011) / BIS (IS 10500:2012)"
    },
    "bacterial counts": {
        "limit": 0.0,
        "unit": "CFU/100mL",
        "standard_reference": "WHO (2011) / BIS (IS 10500:2012)"
    },
    "ph": {
        "limit": 8.5,
        "min_limit": 6.5,
        "unit": "pH Units",
        "standard_reference": "WHO (2011) / BIS (IS 10500:2012)"
    },
    "nitrate": {
        "limit": 45.0,
        "unit": "mg/L",
        "standard_reference": "WHO (2011) / BIS (IS 10500:2012)"
    }
}

# Village contacts mapping
VILLAGE_CONTACTS = {
    "VIL-RAM-001": "health_officer_rampur@gov.in",
    "VIL-SUN-002": "health_officer_sundarpur@gov.in",
    "VIL-HAR-003": "health_officer_haripur@gov.in"
}
DEFAULT_CONTACT = "district_health_officer@gov.in"

def log_error(msg):
    """Utility to print errors to stderr so it doesn't pollute stdout."""
    print(f"[MCP Error] {msg}", file=sys.stderr)
    sys.stderr.flush()

def handle_log_reading(arguments):
    """log_reading(source_id, village_id, parameter, value, unit, date, reported_by_id)"""
    required = ["source_id", "village_id", "parameter", "value", "unit", "date", "reported_by_id"]
    for r in required:
        if r not in arguments:
            return {"error": f"Missing required parameter '{r}'"}
            
    # Validate values are plausible (flag obvious entry errors, e.g. negative pH)
    param = arguments["parameter"].lower()
    val = float(arguments["value"])
    
    if val < 0 and param != "ph": # negative values are not allowed except pH in theory (though pH is 0-14, let's check it separately)
        return {"error": f"Invalid value: Negative reading '{val}' is not plausible for '{arguments['parameter']}'"}
        
    if param == "ph" and (val < 0.0 or val > 14.0):
        return {"error": f"Invalid value: pH value '{val}' must be between 0.0 and 14.0"}

    storage.log_reading(
        source_id=arguments["source_id"],
        village_id=arguments["village_id"],
        parameter=arguments["parameter"],
        value=val,
        unit=arguments["unit"],
        date_str=arguments["date"],
        reported_by_id=arguments["reported_by_id"]
    )
    return {"status": "success", "message": f"Reading successfully logged for source {arguments['source_id']}"}

def handle_get_source_history(arguments):
    """get_source_history(source_id)"""
    if "source_id" not in arguments:
        return {"error": "Missing required parameter 'source_id'"}
    
    history = storage.get_source_history(arguments["source_id"])
    return {"history": history}

def handle_lookup_safety_threshold(arguments):
    """lookup_safety_threshold(parameter)"""
    if "parameter" not in arguments:
        return {"error": "Missing required parameter 'parameter'"}
        
    param_key = arguments["parameter"].lower()
    if param_key not in SAFETY_THRESHOLDS:
        # Match substring or parameter name
        matched_key = None
        for key in SAFETY_THRESHOLDS:
            if key in param_key or param_key in key:
                matched_key = key
                break
        if matched_key:
            param_key = matched_key
        else:
            return {"error": f"Unknown safety parameter: '{arguments['parameter']}'"}

    return SAFETY_THRESHOLDS[param_key]

def handle_draft_alert(arguments):
    """draft_alert(source_id, severity, recipient_type)"""
    required = ["source_id", "severity"]
    for r in required:
        if r not in arguments:
            return {"error": f"Missing required parameter '{r}'"}
            
    source_id = arguments["source_id"]
    severity = arguments["severity"]
    
    # 1. Look up village_id from history to find contact
    history = storage.get_source_history(source_id)
    village_id = "VIL-UNKNOWN-999"
    if history:
        village_id = history[0].get("village_id", "VIL-UNKNOWN-999")
        
    recipient = VILLAGE_CONTACTS.get(village_id, DEFAULT_CONTACT)
    
    # 2. Rate-limit alerts per source (max 1 IMMEDIATE_HAZARD alert per source per 48 hours)
    if severity == "IMMEDIATE_HAZARD":
        recent_alerts = storage.get_recent_alerts(source_id, limit_hours=48)
        if recent_alerts:
            log_error(f"Rate-limit triggered for source {source_id}. IMMEDIATE_HAZARD alert already sent in last 48 hours.")
            return {
                "alert_id": recent_alerts[0]["alert_id"],
                "status": "rate_limited",
                "recipient": recipient,
                "message": "Alert was suppressed due to 48-hour rate limit on IMMEDIATE_HAZARD notifications."
            }

    # 3. Generate message
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
        
    # 4. Save alert
    storage.save_alert(
        alert_id=alert_id,
        source_id=source_id,
        village_id=village_id,
        severity=severity,
        message=message,
        recipient=recipient,
        timestamp_str=timestamp
    )
    
    return {
        "alert_id": alert_id,
        "status": "drafted",
        "recipient": recipient,
        "message": message
    }

def handle_get_all_sources_summary(arguments):
    """get_all_sources_summary()"""
    try:
        summary = storage.get_all_sources_summary()
        return {"summary": summary}
    except Exception as e:
        return {"error": str(e)}

def handle_get_recent_alerts(arguments):
    """get_recent_alerts(limit)"""
    limit = int(arguments.get("limit", 50))
    try:
        alerts = storage.get_all_alerts_summary(limit)
        return {"alerts": alerts}
    except Exception as e:
        return {"error": str(e)}

# MCP tools definition
TOOLS = [
    {
        "name": "log_reading",
        "description": (
            "Log a water safety reading. Validates that readings are plausible (e.g. non-negative "
            "and pH in [0, 14]) before writing clean normalized records."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_id": {"type": "string", "description": "Structured Source ID like SRC-BOR-0003"},
                "village_id": {"type": "string", "description": "Structured Village ID like VIL-RAM-001"},
                "parameter": {"type": "string", "description": "Name of parameter: fluoride, arsenic, turbidity, bacterial counts, pH"},
                "value": {"type": "number", "description": "Numeric reading value"},
                "unit": {"type": "string", "description": "Measurement unit e.g. mg/L, NTU, CFU/100mL"},
                "date": {"type": "string", "description": "ISO 8601 string or date format"},
                "reported_by_id": {"type": "string", "description": "Reporter ID like REP-ASHA-001"}
            },
            "required": ["source_id", "village_id", "parameter", "value", "unit", "date", "reported_by_id"]
        }
    },
    {
        "name": "get_source_history",
        "description": "Retrieves the complete reading history for a specified source_id, ordered chronologically.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_id": {"type": "string", "description": "Structured Source ID like SRC-BOR-0003"}
            },
            "required": ["source_id"]
        }
    },
    {
        "name": "lookup_safety_threshold",
        "description": "Looks up the static WHO/BIS safety thresholds and standards reference for a specific water parameter.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "parameter": {"type": "string", "description": "Parameter name (fluoride, arsenic, turbidity, bacterial counts, pH)"}
            },
            "required": ["parameter"]
        }
    },
    {
        "name": "draft_alert",
        "description": (
            "Drafts and stores a health alert for a water source. Applies a 48-hour rate limit on "
            "IMMEDIATE_HAZARD alerts per source to avoid email/SMS spam fatigue."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_id": {"type": "string", "description": "Structured Source ID like SRC-BOR-0003"},
                "severity": {
                    "type": "string",
                    "enum": ["IMMEDIATE_HAZARD", "WATCHLIST", "NORMAL"],
                    "description": "Classification tier"
                },
                "recipient_type": {"type": "string", "description": "Optional contact category indicator"}
            },
            "required": ["source_id", "severity"]
        }
    },
    {
        "name": "get_all_sources_summary",
        "description": "Retrieves a summary of all water sources, their village IDs, and their latest readings.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_recent_alerts",
        "description": "Retrieves the recent alerts and warnings log.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Optional max number of alerts to return (default 50)"}
            }
        }
    }
]

def main():
    log_error("Starting HydroWatch MCP Stdio Server...")
    
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            req_id = request.get("id")
            method = request.get("method")
            
            # Protocol initialization
            if method == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {}
                        },
                        "serverInfo": {
                            "name": "HydroWatchServer",
                            "version": "1.0.0"
                        }
                    }
                }
            elif method == "notifications/initialized":
                # Notifications don't require responses
                continue
            elif method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "tools": TOOLS
                    }
                }
            elif method == "tools/call":
                params = request.get("params", {})
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                
                log_error(f"Executing tool {tool_name} with arguments {arguments}")
                
                result = None
                if tool_name == "log_reading":
                    result = handle_log_reading(arguments)
                elif tool_name == "get_source_history":
                    result = handle_get_source_history(arguments)
                elif tool_name == "lookup_safety_threshold":
                    result = handle_lookup_safety_threshold(arguments)
                elif tool_name == "draft_alert":
                    result = handle_draft_alert(arguments)
                elif tool_name == "get_all_sources_summary":
                    result = handle_get_all_sources_summary(arguments)
                elif tool_name == "get_recent_alerts":
                    result = handle_get_recent_alerts(arguments)
                else:
                    response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {
                            "code": -32601,
                            "message": f"Method not found: {tool_name}"
                        }
                    }
                    print(json.dumps(response))
                    sys.stdout.flush()
                    continue

                if result and "error" in result:
                    response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {
                            "code": -32603,
                            "message": result["error"]
                        }
                    }
                else:
                    response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(result)
                                }
                            ]
                        }
                    }
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }
                
            print(json.dumps(response))
            sys.stdout.flush()
            
        except Exception as e:
            log_error(f"Error handling line: {traceback.format_exc()}")
            response = {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
            print(json.dumps(response))
            sys.stdout.flush()

if __name__ == "__main__":
    main()
