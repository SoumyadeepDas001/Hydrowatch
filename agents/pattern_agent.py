import os
import sys
import json
from google.adk import Agent
from schema.bq_schema import StorageManager

storage = StorageManager()

# Define the tools
def get_source_history(source_id: str) -> str:
    """
    Retrieves the complete historical water quality readings list for a specified source_id.
    
    Args:
        source_id: The Source ID e.g. SRC-BOR-0003
    """
    try:
        history = storage.get_source_history(source_id)
        return json.dumps(history)
    except Exception as e:
        return json.dumps({"error": str(e)})

def lookup_safety_threshold(parameter: str) -> str:
    """
    Looks up safety thresholds and limits for a specific parameter based on static WHO/BIS guidelines.
    
    Args:
        parameter: Parameter name e.g. fluoride, arsenic, turbidity, bacterial counts, pH
    """
    SAFETY_THRESHOLDS = {
        "fluoride": {"limit": 1.5, "unit": "mg/L", "standard_reference": "WHO (2011) / BIS (IS 10500:2012)"},
        "arsenic": {"limit": 0.01, "unit": "mg/L", "standard_reference": "WHO (2011) / BIS (IS 10500:2012)"},
        "turbidity": {"limit": 5.0, "unit": "NTU", "standard_reference": "WHO (2011) / BIS (IS 10500:2012)"},
        "bacterial counts": {"limit": 0.0, "unit": "CFU/100mL", "standard_reference": "WHO (2011) / BIS (IS 10500:2012)"},
        "ph": {"limit": 8.5, "min_limit": 6.5, "unit": "pH Units", "standard_reference": "WHO (2011) / BIS (IS 10500:2012)"}
    }
    param_key = parameter.lower()
    for key, val in SAFETY_THRESHOLDS.items():
        if key in param_key or param_key in key:
            return json.dumps(val)
    return json.dumps({"error": f"Parameter '{parameter}' threshold not found."})

PATTERN_INSTRUCTIONS = """
You are the Pattern Agent of the HydroWatch system.
Your job is to analyze the historical readings of a water source and determine if there are any risk signals.

STEPS:
1. Given a source_id in the prompt, call get_source_history to pull all past readings for that source.
2. Group the readings by parameter (e.g. fluoride, arsenic, ph, turbidity, bacterial counts).
3. For each parameter found, call lookup_safety_threshold to retrieve its safety limits.
4. For each parameter, analyze the chronological readings list:
   - **Acute Breach**: A single reading exceeds the threshold limit.
     - For fluoride: > 1.5
     - For arsenic: > 0.01
     - For turbidity: > 5.0
     - For bacterial counts: > 0.0
     - For pH: outside [6.5, 8.5]
   - **Drift Trend**: A sequence of 3 or more consecutive readings steadily moving towards the safety limit, where the final reading is within 25% of the safety limit.
     - For fluoride: 3+ increasing readings (e.g., 1.1, 1.2, 1.3, 1.4), with the last reading >= 1.125 (within 25% of 1.5).
     - For arsenic: 3+ increasing readings (e.g. 0.007, 0.008, 0.009), last >= 0.0075.
     - For turbidity: 3+ increasing readings, last >= 3.75.
     - For bacterial counts: 3+ increasing readings.
     - For pH: 3+ consecutive readings either moving down towards 6.5 (last <= 7.0) or moving up towards 8.5 (last >= 8.0).
5. Output your analysis as a structured risk signal in RAW JSON format. Do not write markdown blocks or any other explanation.

OUTPUT FORMAT:
Return a JSON array of risk signals. Each object in the array must be a JSON object containing keys:
- source_id: string
- parameter: string
- has_acute_breach: boolean
- has_drift_trend: boolean
- readings_analyzed: list of reading values (numbers)

If no history is found or no signals are detected, output an empty list: [].
"""

pattern_agent = Agent(
    name="pattern_agent",
    model="gemini-2.5-flash",
    instruction=PATTERN_INSTRUCTIONS,
    tools=[get_source_history, lookup_safety_threshold]
)
