import os
import sys
import json
from google.adk import Agent
from schema.bq_schema import StorageManager

storage = StorageManager()

def log_reading(source_id: str, village_id: str, parameter: str, value: float, unit: str, date: str, reported_by_id: str) -> str:
    """
    Logs a normalized water quality reading into the storage system.
    
    Args:
        source_id: Structured Source ID matching SRC-[A-Z]{3}-[0-9]{4} (e.g. SRC-BOR-0003)
        village_id: Structured Village ID matching VIL-[A-Z]{3}-[0-9]{3} (e.g. VIL-RAM-001)
        parameter: Parameter name e.g. fluoride, arsenic, turbidity, bacterial counts, pH
        value: Numeric measurement value
        unit: Unit of measurement e.g. mg/L, NTU, CFU/100mL
        date: ISO 8601 formatted date string
        reported_by_id: Reporter ID e.g. REP-ASHA-001
    """
    try:
        param_lower = parameter.lower()
        val_float = float(value)
        if val_float < 0 and param_lower != "ph":
            return json.dumps({"error": f"Invalid value: Negative reading '{value}' is not allowed for parameter '{parameter}'."})
        if param_lower == "ph" and (val_float < 0.0 or val_float > 14.0):
            return json.dumps({"error": f"Invalid value: pH '{value}' must be between 0.0 and 14.0."})

        storage.log_reading(
            source_id=source_id,
            village_id=village_id,
            parameter=parameter,
            value=val_float,
            unit=unit,
            date_str=date,
            reported_by_id=reported_by_id
        )
        return json.dumps({"status": "success", "message": f"Reading successfully logged for source {source_id}", "source_id": source_id, "village_id": village_id})
    except Exception as e:
        return json.dumps({"error": str(e)})

INTAKE_INSTRUCTIONS = """
You are the Intake Agent of the HydroWatch public health system.
Your goal is to parse messy manual water quality readings and normalize them into a clean, structured schema.

INPUT FORMATS:
- You will receive reports in inconsistent formats: structured CSV-like strings OR free-text (e.g., "Village: Rampur, Source: borewell-3, pH 7.2, Fluoride 1.8mg/L, 2 June").

NORMALIZATION RULES:
1. Parse the village name and map it to a structured Village ID:
   - Rampur -> VIL-RAM-001
   - Sundarpur -> VIL-SUN-002
   - Haripur -> VIL-HAR-003
   - If unknown, use VIL-UNK-999
2. Parse the source name and map it to a structured Source ID:
   - borewell-3 -> SRC-BOR-0003
   - borewell-5 -> SRC-BOR-0005
   - well-1 -> SRC-WEL-0001
   - well-2 -> SRC-WEL-0002
   - handpump-1 -> SRC-HDP-0001
   - handpump-2 -> SRC-HDP-0002
   - If unknown, generate based on name or use SRC-UNK-9999
3. Standardize parameters to lowercase singular names:
   - "Fluoride", "fluoride", "flouride" -> "fluoride"
   - "Arsenic", "arsenic" -> "arsenic"
   - "Turbidity", "turbidity" -> "turbidity"
   - "Bacterial Counts", "bacteria", "bacterial count" -> "bacterial counts"
   - "pH", "ph" -> "ph"
4. Standardize units:
   - Fluoride, Arsenic -> mg/L
   - Turbidity -> NTU
   - Bacterial counts -> CFU/100mL
   - pH -> pH Units
5. Normalize the date:
   - Parse dates like "2 June", "June 2, 2026", etc. Convert into ISO 8601 format e.g. "2026-06-02T12:00:00". If no year is provided, assume 2026.
6. Normalize the reported_by_id:
   - If not specified, default to "REP-VOL-999".

VALIDATION RULES:
- pH must be between 0.0 and 14.0.
- Negative values are invalid for fluoride, arsenic, turbidity, and bacterial counts.
If validation fails, do NOT call log_reading. Instead, return an error message starting with 'VALIDATION_ERROR: ' describing the invalid fields.

ACTION:
- If valid, call the log_reading tool.
- If the tool responds with success, report: 'SUCCESS: Logged reading for source [source_id]' and provide the logged details in JSON format.
"""

intake_agent = Agent(
    name="intake_agent",
    model="gemini-2.5-flash",
    instruction=INTAKE_INSTRUCTIONS,
    tools=[log_reading]
)
