import json
import logging
from datetime import datetime
from typing import AsyncGenerator
from typing_extensions import override
from google.adk.agents.base_agent import BaseAgent
from google.adk.events.event import Event
from google.adk.agents.invocation_context import InvocationContext
from google.genai import types

logger = logging.getLogger("hydrowatch.risk_agent")

class RiskClassificationAgent(BaseAgent):
    """Deterministic, rule-based Risk Classification Agent."""

    # Pydantic model fields
    name: str = "risk_classification_agent"
    description: str = "Assigns severity tier (IMMEDIATE_HAZARD, WATCHLIST, NORMAL) based on deterministic rules."

    @override
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        # 1. Find the Pattern Agent's risk signal output from the session history
        pattern_output = None
        for event in reversed(ctx.session.events):
            if event.author == "pattern_agent" and event.content and event.content.parts:
                text = "".join(part.text or "" for part in event.content.parts).strip()
                if text:
                    # Clean markdown code block formatting if present
                    if text.startswith("```"):
                        lines = text.split("\n")
                        # remove first and last lines
                        text = "\n".join(lines[1:-1]) if lines[-1].startswith("```") else "\n".join(lines[1:])
                    pattern_output = text.strip()
                    break

        # Defaults
        severity = "NORMAL"
        source_id = "UNKNOWN"
        village_id = "UNKNOWN"
        parameter = "none"
        message = "No risk signals analyzed."

        if pattern_output:
            try:
                signals = json.loads(pattern_output)
                if isinstance(signals, list) and len(signals) > 0:
                    # Deterministic priority logic:
                    # IMMEDIATE_HAZARD if any acute breach
                    # WATCHLIST if any drift trend and no acute breach
                    has_acute = False
                    has_drift = False
                    first_sig = signals[0]
                    source_id = first_sig.get("source_id", "UNKNOWN")
                    
                    # Look up village_id in session history if unknown
                    for event in ctx.session.events:
                        if event.content and event.content.parts:
                            event_text = "".join(part.text or "" for part in event.content.parts)
                            if "VIL-" in event_text:
                                import re
                                match = re.search(r"VIL-[A-Z]{3}-[0-9]{3}", event_text)
                                if match:
                                    village_id = match.group(0)
                                    break

                    for sig in signals:
                        if sig.get("has_acute_breach", False):
                            has_acute = True
                            parameter = sig.get("parameter", "unknown")
                        elif sig.get("has_drift_trend", False):
                            has_drift = True
                            if not has_acute:
                                parameter = sig.get("parameter", "unknown")

                    if has_acute:
                        severity = "IMMEDIATE_HAZARD"
                        message = f"Acute hazard breach detected for parameter '{parameter}' at source {source_id}."
                    elif has_drift:
                        severity = "WATCHLIST"
                        message = f"Deteriorating drift trend detected for parameter '{parameter}' at source {source_id}."
                    else:
                        severity = "NORMAL"
                        message = f"Water parameters are normal at source {source_id}."
                else:
                    message = "No signals found in empty pattern list."
            except Exception as e:
                logger.error(f"Error parsing Pattern Agent output: {e}. Output was: {pattern_output}")
                message = f"Error processing pattern signal: {str(e)}"
        else:
            logger.warning("No pattern_agent signal found in session history. Defaulting to NORMAL.")

        result = {
            "source_id": source_id,
            "village_id": village_id,
            "parameter": parameter,
            "severity": severity,
            "message": message
        }

        # Format as an ADK Event
        content = types.Content(
            role="model",
            parts=[types.Part(text=json.dumps(result))]
        )
        
        event = Event(
            author=self.name,
            content=content,
            timestamp=datetime.utcnow().timestamp() if hasattr(datetime, "utcnow") else 0.0
        )
        
        yield event

    @override
    async def _run_live_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        # For our sequential workflow, run_async_impl is the core method.
        # We can simply delegate here to maintain compatibility.
        async for event in self._run_async_impl(ctx):
            yield event
