from typing import Annotated, TypedDict
from langchain_core.messages import SystemMessage, HumanMessage 
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages  # Reducer that appends messages instead of overwriting!
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver  # Saves state snapshots for Human-in-the-Loop pauses

# Import the 4 tools we built in src/agents/tools.py
from src.agents.tools import (
    analyze_server_logs,
    query_past_incidents,
    search_engineering_runbooks,
    execute_recovery_action
)

# 1. DEFINE SHARED GRAPH STATE
# 'Annotated[list, add_messages]' tells LangGraph: "When a node returns new messages, 
# APPEND them to the existing chat history instead of deleting old ones."
class IncidentState(TypedDict):
    messages: Annotated[list, add_messages]

# 2. SEPARATE DIAGNOSTIC TOOLS FROM HIGH-STAKES ACTION TOOLS
diagnostic_tools = [analyze_server_logs, query_past_incidents, search_engineering_runbooks]
action_tools = [execute_recovery_action]
all_tools = diagnostic_tools + action_tools

# 3. INITIALIZE LOCAL OLLAMA LLM & BIND TOOLS
# temperature=0 forces deterministic, reliable tool argument extraction
llm = ChatOllama(model="qwen2.5:7b", temperature=0)
llm_with_tools = llm.bind_tools(all_tools)

SYSTEM_PROMPT = SystemMessage(content="""
You are IncidentPilot, an autonomous Site Reliability Engineering (SRE) assistant.
Follow this strict investigation workflow when a user reports an outage:
1. First, call `analyze_server_logs` to inspect error rates, latency, and error messages.
2. Second, call `query_past_incidents` to check if the affected service had similar outages before.
3. Third, call `search_engineering_runbooks` using the exact error signature to find the official recovery procedure.
4. Finally, if a recovery action is required by the runbook, call `execute_recovery_action` with the exact action name and service.
Always base your answers strictly on tool outputs. Never guess.
""")

# 4. DEFINE GRAPH NODES
def agent_reasoning_node(state: IncidentState) -> dict:
    """The LLM Brain: Reads current message history and decides the next tool call or final answer."""
    # Prepend our system instructions to the conversation history
    messages_to_send = [SYSTEM_PROMPT] + state["messages"]
    response = llm_with_tools.invoke(messages_to_send)
    return {"messages": [response]}


# Prebuilt ToolNode automatically executes whichever tool the LLM requested in its AIMessage
diagnostic_tool_node = ToolNode(diagnostic_tools)
action_tool_node = ToolNode(action_tools)


# 5. CUSTOM CONDITIONAL ROUTER
def route_after_agent(state: IncidentState) -> str:
    """Inspects the LLM's latest message to route to diagnostic tools, action tools, or END."""
    last_message = state["messages"][-1]
    
    # If the LLM did not request any tool calls, we are finished!
    if not getattr(last_message, "tool_calls", None):
        return END
        
    # Check if the requested tool is our high-stakes recovery action
    first_tool_call = next(iter(last_message.tool_calls))
    requested_tool_name = first_tool_call["name"]


    if requested_tool_name == "execute_recovery_action":
        return "action_tools"
        
    # Otherwise, route to our safe, read-only diagnostic tools
    return "diagnostic_tools"


# 6. ASSEMBLE & COMPILE THE LANGGRAPH STATE MACHINE
workflow = StateGraph(IncidentState)

# Register nodes
workflow.add_node("agent", agent_reasoning_node)
workflow.add_node("diagnostic_tools", diagnostic_tool_node)
workflow.add_node("action_tools", action_tool_node)

# Wire edges
workflow.add_edge(START, "agent")
workflow.add_conditional_edges(
    "agent",
    route_after_agent,
    {
        "diagnostic_tools": "diagnostic_tools",
        "action_tools": "action_tools",
        END: END
    }
)

# Both tool nodes always loop back to the 'agent' node so the LLM can read the tool output!
workflow.add_edge("diagnostic_tools", "agent")
workflow.add_edge("action_tools", "agent")

# Initialize MemorySaver checkpointer to enable Human-in-the-Loop pauses
memory = MemorySaver()

# Compile graph with 'interrupt_before=["action_tools"]'
# This forces the graph to FREEZE right before executing any server restart!
incident_graph = workflow.compile(
    checkpointer=memory,
    interrupt_before=["action_tools"]
)


# --- STANDALONE INTERACTIVE TEST ---
if __name__ == "__main__":
    
    # A thread_id tracks this specific incident session inside MemorySaver
    config = {"configurable": {"thread_id": "incident-session-001"}}
    
    user_query = "Users are reporting failures on payment-gateway. Diagnose the root cause and fix it."
    print(f"=== STARTING INCIDENTPILOT INVESTIGATION ===\nUser: {user_query}\n")
    
    # Run the graph until it either finishes OR hits our 'interrupt_before' safety gate!
    for event in incident_graph.stream({"messages": [HumanMessage(content=user_query)]}, config=config):
        for node_name, output in event.items():
            print(f"[GRAPH NODE COMPLETED]: {node_name}")

    # Inspect the current frozen state of the graph
    snapshot = incident_graph.get_state(config)
    if snapshot.next:
        print(f"\n⏸️  [HUMAN-IN-THE-LOOP PAUSE] Graph frozen before node: {snapshot.next}")
        pending_tool_call = next(iter(snapshot.values["messages"][-1].tool_calls))


        print(f"Proposed Action: {pending_tool_call['name']} | Arguments: {pending_tool_call['args']}")
        
        approval = input("\nType 'yes' to approve and execute this recovery action: ")
        if approval.strip().lower() == "yes":
            # Passing 'None' resumes the graph from the exact frozen checkpoint!
            for event in incident_graph.stream(None, config=config):
                for node_name, output in event.items():
                    print(f"[GRAPH NODE COMPLETED]: {node_name}")
            
            final_msg = incident_graph.get_state(config).values["messages"][-1]
            print(f"\n=== FINAL INCIDENT REPORT ===\n{final_msg.content}")
        else:
            print("❌ Action rejected by human operator.")
