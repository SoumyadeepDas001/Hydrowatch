import asyncio
import sys
from agents.orchestrator import HydroWatchOrchestrator
from agents.query_agent import query_agent
import logging

# Suppress debug logs from httpx and ADK for a clean CLI experience
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("google.adk").setLevel(logging.WARNING)

async def main():
    print("==================================================")
    print("           HYDRO WATCH AGENTS CLI                 ")
    print("==================================================")
    print("Welcome to the interactive Agent CLI.")
    print("Type your questions about water safety, alerts, or trends.")
    print("Type 'quit' or 'exit' to stop.")
    print("==================================================\n")

    orchestrator = HydroWatchOrchestrator()
    session = await orchestrator.session_service.create_session(app_name="agents", user_id="cli_user")

    while True:
        try:
            query = input("\n[You]: ")
            if not query.strip():
                continue
            if query.strip().lower() in ['quit', 'exit']:
                break
                
            response = await orchestrator.execute_agent_step(session, query_agent, query)
            
            print(f"\n[HydroWatch Agent]:\n{response}\n")
            
        except (KeyboardInterrupt, EOFError):
            break
        except Exception as e:
            print(f"\n[Error]: {e}\n")

    print("\nExiting HydroWatch Agents CLI. Goodbye!")

if __name__ == "__main__":
    asyncio.run(main())
