import asyncio
import os
import sys

# Ensure parent directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.orchestrator import HydroWatchOrchestrator, query_agent

async def main():
    print("==================================================")
    print("      RUNNING CHAT CAPABILITY GROUNDING TESTS     ")
    print("==================================================")
    
    orchestrator = HydroWatchOrchestrator()
    
    # 1. Question A: Status Check
    print("\n--- [Test A: Status Question] ---")
    session_a = await orchestrator.session_service.create_session(app_name="agents", user_id="test_user")
    q_a = "Which sources are at Immediate Hazard right now?"
    ans_a = await orchestrator.execute_agent_step(session_a, query_agent, q_a)
    print(f"Question: {q_a}")
    print(f"Answer:\n{ans_a}")
    
    # 2. Question B: Trend Check
    print("\n--- [Test B: Trend Question] ---")
    session_b = await orchestrator.session_service.create_session(app_name="agents", user_id="test_user")
    q_b = "What's the fluoride trend for SRC-BOR-0003?"
    ans_b = await orchestrator.execute_agent_step(session_b, query_agent, q_b)
    print(f"Question: {q_b}")
    print(f"Answer:\n{ans_b}")
    
    # 3. Question C: Comparison Question
    print("\n--- [Test C: Comparison Question] ---")
    session_c = await orchestrator.session_service.create_session(app_name="agents", user_id="test_user")
    q_c = "Compare fluoride between Rampur and Beldanga"
    ans_c = await orchestrator.execute_agent_step(session_c, query_agent, q_c)
    print(f"Question: {q_c}")
    print(f"Answer:\n{ans_c}")
    
    # 4. Question D: Multi-turn Pronoun Resolution
    print("\n--- [Test D: Multi-turn Follow-up Question] ---")
    session_d = await orchestrator.session_service.create_session(app_name="agents", user_id="test_user")
    q_d1 = "Is SRC-BOR-0003 safe right now?"
    ans_d1 = await orchestrator.execute_agent_step(session_d, query_agent, q_d1)
    print(f"Turn 1 Question: {q_d1}")
    print(f"Turn 1 Answer:\n{ans_d1}")
    
    q_d2 = "what about arsenic there?"
    ans_d2 = await orchestrator.execute_agent_step(session_d, query_agent, q_d2)
    print(f"Turn 2 Question: {q_d2}")
    print(f"Turn 2 Answer:\n{ans_d2}")
    
    # 5. Question E: Out of Scope Declination
    print("\\n--- [Test E: Out of Scope Question] ---")
    session_e = await orchestrator.session_service.create_session(app_name="agents", user_id="test_user")
    q_e = "what is the capital of France?"
    ans_e = await orchestrator.execute_agent_step(session_e, query_agent, q_e)
    print(f"Question: {q_e}")
    print(f"Answer:\\n{ans_e}")
    
    # 6. Question F: Parameter Explainer
    print("\\n--- [Test F: Parameter Explainer] ---")
    session_f = await orchestrator.session_service.create_session(app_name="agents", user_id="test_user")
    q_f = "What is fluoride?"
    ans_f = await orchestrator.execute_agent_step(session_f, query_agent, q_f)
    print(f"Question: {q_f}")
    print(f"Answer:\\n{ans_f}")

    # 7. Question G: Village Summary
    print("\\n--- [Test G: Village Summary] ---")
    session_g = await orchestrator.session_service.create_session(app_name="agents", user_id="test_user")
    q_g = "Tell me about Rampur"
    ans_g = await orchestrator.execute_agent_step(session_g, query_agent, q_g)
    print(f"Question: {q_g}")
    print(f"Answer:\\n{ans_g}")
    
    # 8. Question H: Health Effects
    print("\\n--- [Test H: Health Effects] ---")
    session_h = await orchestrator.session_service.create_session(app_name="agents", user_id="test_user")
    q_h = "What are the health effects of arsenic?"
    ans_h = await orchestrator.execute_agent_step(session_h, query_agent, q_h)
    print(f"Question: {q_h}")
    print(f"Answer:\\n{ans_h}")

    print("\\n==================================================")
    print("                  TESTS COMPLETED                 ")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(main())
