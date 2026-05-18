"""
LangGraph-based Media Analyst Agent.

Graph topology (ReAct loop):
  ┌──────────┐    tool call?    ┌──────────────┐
  │  llm_node │ ──────────────► │ tools_node   │
  └──────────┘                  └──────────────┘
       ▲                               │
       └───────────────────────────────┘
                  loop until END

The agent:
  1. Receives the user question plus conversation history.
  2. Decides whether to call a tool (BigQuery) or answer directly.
  3. If a tool is called, the result is added to the message list and
     the LLM is invoked again to produce a natural-language insight.
  4. This loops until the LLM returns a final answer (no tool call).
"""

from __future__ import annotations

import json
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from app.agent.tools import ALL_TOOLS
from app.core.config import get_settings

# ──────────────────────────────────────────────────────────────────────────────
# State
# ──────────────────────────────────────────────────────────────────────────────


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


# ──────────────────────────────────────────────────────────────────────────────
# System prompt
# ──────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a **Junior Media Analyst AI** for an e-commerce company.
Your job is to help the Media & Growth team understand traffic quality and channel ROI
using data from our data warehouse (Google BigQuery — thelook_ecommerce dataset).

## Your capabilities
You have access to the following tools to query live data:
- **get_traffic_volume** – new users by channel in a date window.
- **get_channel_performance** – conversion rate, revenue, AOV, RPU per channel.
- **get_revenue_trend** – monthly revenue trend per channel.
- **get_user_demographics** – gender, age group, and country breakdown per channel.
- **get_top_products_by_channel** – best-selling products for a given channel.

## Behavior guidelines
1. **Always use tools** when the user asks about data, metrics, or comparisons.
   Never make up numbers.
2. After receiving tool results, provide a **concise, actionable insight**,
   not just a data dump. Highlight the most relevant finding first.
3. If a question is **out of scope** (unrelated to traffic, media, or e-commerce
   analytics on the available dataset), politely explain what you can help with
   and suggest a relevant question.
4. When comparing channels, always explain *why* one might be better based on
   the metrics available (conversion rate, revenue per user, AOV, etc.).
5. Use clear formatting: bullet points, bold key metrics, and brief explanations.
6. Respond in the same language the user is writing in.
"""

# ──────────────────────────────────────────────────────────────────────────────
# Graph nodes
# ──────────────────────────────────────────────────────────────────────────────


def build_agent_graph() -> Any:
    settings = get_settings()

    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        temperature=settings.gemini_temperature,
        google_api_key=settings.google_api_key,
    ).bind_tools(ALL_TOOLS)

    tool_node = ToolNode(ALL_TOOLS)

    def llm_node(state: AgentState, config: RunnableConfig) -> AgentState:
        """Call the LLM with the current message history."""
        messages = state["messages"]

        # Inject system prompt if this is the first call
        if not any(isinstance(m, SystemMessage) for m in messages):
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages

        response = llm.invoke(messages, config)
        return {"messages": [response]}

    def should_continue(state: AgentState) -> str:
        """Route to tools if the LLM requested a tool call, otherwise end."""
        last_message = state["messages"][-1]
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "tools"
        return END

    # ── Build graph ──────────────────────────────────────────────────────────
    graph = StateGraph(AgentState)

    graph.add_node("llm", llm_node)
    graph.add_node("tools", tool_node)

    graph.set_entry_point("llm")

    graph.add_conditional_edges(
        "llm",
        should_continue,
        {"tools": "tools", END: END},
    )
    graph.add_edge("tools", "llm")

    return graph.compile()


# ──────────────────────────────────────────────────────────────────────────────
# Public interface
# ──────────────────────────────────────────────────────────────────────────────

# Singleton compiled graph (created once per process)
_agent_graph: Any | None = None


def get_agent() -> Any:
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = build_agent_graph()
    return _agent_graph


async def run_agent(
    user_message: str,
    history: list[dict[str, str]] | None = None,
) -> str:
    """
    Run the agent with a user message and optional conversation history.

    Args:
        user_message: The latest user question.
        history:      List of previous turns as [{"role": "user"|"assistant", "content": "..."}].

    Returns:
        The agent's final text response.
    """
    agent = get_agent()

    # Convert history to LangChain message objects
    messages: list[BaseMessage] = []
    for turn in history or []:
        role = turn.get("role", "user")
        content = turn.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        else:
            messages.append(AIMessage(content=content))

    messages.append(HumanMessage(content=user_message))

    result = await agent.ainvoke({"messages": messages})

    last_message = result["messages"][-1]
    return last_message.content if isinstance(last_message, AIMessage) else str(last_message)
