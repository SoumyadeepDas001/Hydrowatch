import agents.mock_client
import os
import sys
import json
import re
import asyncio
import logging
from google.adk.runners import Runner
from google.adk.apps import App
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.auth.credential_service.in_memory_credential_service import InMemoryCredentialService
from google.genai import types
from google.adk.utils.context_utils import Aclosing

# Import the agents
from agents.intake_agent import intake_agent
from agents.pattern_agent import pattern_agent
from agents.risk_agent import RiskClassificationAgent
from agents.alert_agent import alert_agent
from agents.query_agent import query_agent

# Suppress warnings from ADK runners (e.g. unknown agents warnings caused by sequential execution)
logging.getLogger("google_adk.google.adk.runners").setLevel(logging.ERROR)

risk_classification_agent = RiskClassificationAgent()

class HydroWatchOrchestrator:
    """Orchestrates the 4-agent HydroWatch pipeline sequentially sharing a single session context."""

    def __init__(self):
        self.session_service = InMemorySessionService()
        self.artifact_service = InMemoryArtifactService()
        self.credential_service = InMemoryCredentialService()
        self.user_id = "volunteer_user"

    async def execute_agent_step(self, session, agent, query: str) -> str:
        """Helper to run a specific agent in the shared session."""
        app = App(name="agents", root_agent=agent)
        runner = Runner(
            app=app,
            session_service=self.session_service,
            artifact_service=self.artifact_service,
            credential_service=self.credential_service
        )
        
        output_parts = []
        async with Aclosing(
            runner.run_async(
                user_id=session.user_id,
                session_id=session.id,
                new_message=types.Content(
                    role="user",
                    parts=[types.Part(text=query)]
                )
            )
        ) as agen:
            async for event in agen:
                if event.content and event.content.parts:
                    text = "".join(part.text or "" for part in event.content.parts)
                    if text:
                        output_parts.append(text)
                        
        await runner.close()
        return "".join(output_parts)

    async def run_pipeline(self, raw_reading_report: str) -> dict:
        """Runs the entire 4-agent pipeline for a raw water reading report."""
        # Create a new session for this pipeline run
        session = await self.session_service.create_session(
            app_name="agents",
            user_id=self.user_id
        )

        pipeline_result = {
            "session_id": session.id,
            "raw_input": raw_reading_report,
            "intake": None,
            "pattern": None,
            "risk": None,
            "alert": None,
            "status": "FAILED"
        }

        # Step 1: Intake Agent
        print(f"\n[Step 1] Ingesting and Normalizing Reading...")
        intake_output = await self.execute_agent_step(session, intake_agent, raw_reading_report)
        pipeline_result["intake"] = intake_output
        print(f"Intake Output:\n{intake_output}")

        if "VALIDATION_ERROR" in intake_output:
            print("[Pipeline halted] Intake validation error detected.")
            pipeline_result["status"] = "VALIDATION_FAILED"
            return pipeline_result

        # Extract source_id using regex
        source_match = re.search(r"SRC-[A-Z]{3}-[0-9]{4}", intake_output)
        if not source_match:
            # Try to look for source_id in tool outputs
            print("[Pipeline halted] Could not identify source_id in intake response.")
            pipeline_result["status"] = "SOURCE_NOT_FOUND"
            return pipeline_result
            
        source_id = source_match.group(0)
        print(f"Parsed Source ID: {source_id}")

        # Step 2: Pattern Agent
        print(f"\n[Step 2] Retrieving History and Analyzing Quality Patterns for {source_id}...")
        pattern_query = f"Analyze the water quality history and risk signals for source: {source_id}"
        pattern_output = await self.execute_agent_step(session, pattern_agent, pattern_query)
        pipeline_result["pattern"] = pattern_output
        print(f"Pattern Output (JSON):\n{pattern_output}")

        # Step 3: Risk Classification Agent
        print(f"\n[Step 3] Deterministically Classifying Risk Severity Tier...")
        risk_query = "Deterministically classify the risk signals."
        risk_output = await self.execute_agent_step(session, risk_classification_agent, risk_query)
        pipeline_result["risk"] = risk_output
        print(f"Risk Output (JSON):\n{risk_output}")

        # Step 4: Alert & Report Agent
        print(f"\n[Step 4] Processing Alerts & Notifications...")
        alert_query = "Process alerts for the classified severity tier."
        alert_output = await self.execute_agent_step(session, alert_agent, alert_query)
        pipeline_result["alert"] = alert_output
        print(f"Alert Output (JSON):\n{alert_output}")

        pipeline_result["status"] = "SUCCESS"
        return pipeline_result

if __name__ == "__main__":
    # Test script run
    async def test():
        orchestrator = HydroWatchOrchestrator()
        test_input = "Village: Rampur, Source: borewell-3, pH 7.2, Fluoride 1.8mg/L, 2 June"
        res = await orchestrator.run_pipeline(test_input)
        print("\nPipeline Result:")
        print(json.dumps(res, indent=2))
        
    asyncio.run(test())
