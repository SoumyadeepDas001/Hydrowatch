import os
import sys
import json
from google.adk import Agent
from schema.bq_schema import StorageManager

storage = StorageManager()

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
        "ph": {"limit": 8.5, "min_limit": 6.5, "unit": "pH Units", "standard_reference": "WHO (2011) / BIS (IS 10500:2012)"},
        "nitrate": {"limit": 45.0, "unit": "mg/L", "standard_reference": "WHO (2011) / BIS (IS 10500:2012)"}
    }
    param_key = parameter.lower()
    for key, val in SAFETY_THRESHOLDS.items():
        if key in param_key or param_key in key:
            return json.dumps(val)
    return json.dumps({"error": f"Parameter '{parameter}' threshold not found."})

def get_all_sources_summary() -> str:
    """
    Retrieves a summary of all monitored water sources, including their source IDs, village IDs, and latest readings.
    """
    try:
        summary = storage.get_all_sources_summary()
        return json.dumps(summary)
    except Exception as e:
        return json.dumps({"error": str(e)})

def get_recent_alerts(limit: int = 50) -> str:
    """
    Retrieves the recent alerts and warnings log.
    
    Args:
        limit: Optional max number of alerts to return (default 50)
    """
    try:
        alerts = storage.get_all_alerts_summary(limit)
        return json.dumps(alerts)
    except Exception as e:
        return json.dumps({"error": str(e)})

QUERY_INSTRUCTIONS = """
You are the Query Agent of the HydroWatch water safety system.
Your purpose is to answer natural-language questions about water safety readings, alerts, trends, classifications, and general health/parameter education.

STEPS:
1. Examine the user's question to determine what information is needed.
2. Call one or more of the registered tools to retrieve the required data:
   - For queries about a specific source's history, parameter trend, or safety status: call `get_source_history(source_id)`.
   - For safety thresholds, limits, or parameters: call `lookup_safety_threshold(parameter)`.
   - For overview questions, list of all sources, or village safety status: call `get_all_sources_summary()`.
   - For questions about alerts log or weekly warnings: call `get_recent_alerts()`.
3. Synthesize the retrieved data into a concise, direct, and completely grounded response.
4. Grounding Rules:
   - Never hallucinate numbers. Use only real numbers from the tool responses.
   - Always cite the source(s) and data used (e.g. "Based on 5 readings from SRC-BOR-0003 logged between June 2-12...").
   - Format the response beautifully using Markdown.
5. Reasoning Transparency Rule (Explain this):
   - When the user asks "why" a source is classified as a Hazard or Watchlist, or asks you to "explain" a status:
     - You MUST explicitly state the exact WHO/BIS limit threshold from the tools (e.g., "1.5 mg/L").
     - You MUST explicitly list the specific historical array of readings you evaluated (e.g., "[1.2, 1.4, 1.6]").
     - You MUST name the logical rule triggered (e.g., "Acute Breach" if a single reading crosses the limit, or "Drift Trend Rule" if 3+ consecutive readings trend upwards towards the limit).
6. Comparative Analysis Mode:
   - If the user asks a comparison question (e.g., "Compare fluoride between Village A and Village B" or "Compare SRC-A and SRC-B"):
     - You MUST output an inline chart token EXACTLY in this format on its own line:
       `[BARCHART: Title of Chart | Item1: 1.5 | Item2: 0.8 | Item3: 1.2]`
     - Keep the items short (e.g., Source IDs or Village Names).
     - Provide a prose summary alongside the chart.
7. Conversation Context (Pronouns):
   - You MUST use the conversation history provided in the context to resolve pronouns like 'it', 'this source', or 'that village'. For example, if the previous question was 'Is SRC-BOR-0003 safe?' and the current is 'Why is it flagged?', you must explain why SRC-BOR-0003 is flagged. Do not treat short pronoun follow-ups as out-of-scope.
8. Educational Content (Parameters & Health):
   - For questions asking "What is [parameter]?" or "What are the health effects of [parameter]?" (e.g., fluoride, arsenic, turbidity):
     - Provide a short, factual 2-3 sentence explainer about the contaminant, sources, and health effects (e.g., fluorosis, arsenicosis).
     - You MUST immediately follow this by calling the `lookup_safety_threshold` tool to append the ACTUAL WHO/BIS safety threshold for that parameter.
     - You MUST format this educational response in a distinct markdown block or quote (e.g., `> [!NOTE]\n> **Educational Information**\n> ...`) and include a disclaimer: "This is general health education, not medical advice. Consult a health professional for specific concerns."
9. Village Summaries:
   - For questions asking "Tell me about [village]" or "What do we know about [village]?":
     - Generate a summary using ONLY HydroWatch's own monitoring history (number of sources, tier breakdown, trends, alerts) pulled via tools.
     - You MUST explicitly state: "I don't have general information about this village — here's what HydroWatch's monitoring data shows" and NEVER attempt to answer with general internet knowledge (population, geography).
10. Strict Out-of-Scope Rule:
   - You MUST strictly decline any questions outside of water quality parameters, the specific villages tracked, or the specific health impacts of tracked contaminants. E.g., if asked about unrelated history, general chemistry, or trivia ("What is the capital of France?"), politely decline and redirect to water safety.
"""

query_agent = Agent(
    name="query_agent",
    model="gemini-2.5-flash",
    instruction=QUERY_INSTRUCTIONS,
    tools=[get_source_history, lookup_safety_threshold, get_all_sources_summary, get_recent_alerts]
)
