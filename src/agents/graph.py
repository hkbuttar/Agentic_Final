"""Builds the router -> planner -> retriever -> answerer LangGraph state
graph. Node logic lives in router.py/planner.py/retriever.py/answerer.py —
this module only wires them together. See README.md for the diagram.
"""
from langgraph.graph import END, START, StateGraph

import answerer as answerer_node
import planner as planner_node
import retriever as retriever_node
import router as router_node
from llm_client import LLMClient
from mcp_client import MCPToolClient
from state import AgentState


def build_graph(llm: LLMClient, mcp_client: MCPToolClient):
    graph = StateGraph(AgentState)

    async def run_router(state: AgentState) -> dict:
        return await router_node.run(state, llm)

    async def run_planner(state: AgentState) -> dict:
        return await planner_node.run(state, llm)

    async def run_retriever(state: AgentState) -> dict:
        return await retriever_node.run(state, mcp_client)

    async def run_answerer(state: AgentState) -> dict:
        return await answerer_node.run(state, llm)

    graph.add_node("router", run_router)
    graph.add_node("planner", run_planner)
    graph.add_node("retriever", run_retriever)
    graph.add_node("answerer", run_answerer)

    graph.add_edge(START, "router")
    graph.add_edge("router", "planner")
    graph.add_edge("planner", "retriever")
    graph.add_edge("retriever", "answerer")
    graph.add_edge("answerer", END)

    return graph.compile()
