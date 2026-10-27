# LangGraph Overview

LangGraph is a low-level orchestration framework and runtime for building, managing, and deploying long-running, stateful agents. It gives developers fine-grained control to mix deterministic, hand-coded steps with LLM-driven agentic steps in the same graph, ensuring agents behave according to specific application requirements.

LangGraph is focused entirely on core agent orchestration capabilities, including:
* Durable execution and persistence
* Streaming capabilities
* Human-in-the-loop oversight
* Short-term and long-term state management

## Stack Comparison: Frameworks, Runtimes, and Harnesses

* **Deep Agents**: An agent harness providing planning, subagents, filesystem tools, and context management built on top of LangGraph.
* **LangChain**: The agent framework offering abstractions and integrations for models, tools, and agent loops.
* **LangGraph**: The orchestration runtime providing durable execution, streaming, human-in-the-loop capabilities, and persistence.
* **LangSmith**: The platform for tracing, evaluation, prompts, and deployment across frameworks.
* **LangSmith Engine**: Automatically detects issues in LangGraph agent traces and proposes direct code fixes.
* **LangSmith Fleet**: A no-code agent builder for templates, integrations, and routine automation.

## Installation

### Python
```bash
pip install -U langgraph
# Or using uv
uv add langgraph
```

### JavaScript / TypeScript
```bash
npm install @langchain/langgraph @langchain/core
# Or using pnpm, yarn, bun
pnpm add @langchain/langgraph @langchain/core
```

## Quickstart Examples

### Python Hello World Example

```python
from langgraph.graph import StateGraph, MessagesState, START, END

def mock_llm(state: MessagesState):
    return {"messages": [{"role": "ai", "content": "hello world"}]}

graph = StateGraph(MessagesState)
graph.add_node(mock_llm)
graph.add_edge(START, "mock_llm")
graph.add_edge("mock_llm", END)

graph = graph.compile()
graph.invoke({"messages": [{"role": "user", "content": "hi!"}]})
```

### JavaScript Hello World Example

```typescript
import { StateSchema, MessagesValue, type GraphNode, StateGraph, START, END } from "@langchain/langgraph";

const State = new StateSchema({
  messages: MessagesValue,
});

const mockLlm: GraphNode<typeof State> = (state) => {
  return { messages: [{ role: "ai", content: "hello world" }] };
};

const graph = new StateGraph(State)
  .addNode("mock_llm", mockLlm)
  .addEdge(START, "mock_llm")
  .addEdge("mock_llm", END)
  .compile();

await graph.invoke({ messages: [{ role: "user", content: "hi!" }] });
```

## Core Benefits

* **Mix Deterministic and Agentic Steps**: Combine hand-coded, deterministic logic with LLM-driven decision-making in a single graph. Use deterministic steps for reliability/predictability and agentic steps for flexibility.
* **Persistence**: Build resilient agents that persist through failures, run over extended periods, and resume execution from exact checkpoints.
* **Human-in-the-Loop**: Incorporate human approval or oversight by inspecting, pausing, and modifying agent state at any step.
* **Comprehensive Memory**: Maintain both short-term working memory (ongoing conversation reasoning) and long-term cross-session memory.
* **Debugging with LangSmith**: Gain visibility into complex agent behavior by tracing execution paths, state transitions, and runtime metrics.
* **Production-Ready Deployment**: Infrastructure designed specifically for stateful, long-running agent workflows at scale.

## LangGraph Ecosystem & Integrations

LangGraph can be used standalone or integrated with the broader ecosystem:

1. **LangSmith**: Trace requests, evaluate outputs, debug agent behavior, and monitor deployments. Enable tracing by setting `LANGSMITH_TRACING=true` and providing an API key.
2. **LangSmith Deployment**: Purpose-built deployment platform to scale stateful agents and prototype workflows visually in Studio.
3. **LangChain**: Streamlines LLM application development by providing model integrations, tool wrappers, and prebuilt agent abstractions built on top of LangGraph.

## Acknowledgements

LangGraph is inspired by Google's **Pregel** and **Apache Beam**. Its public interface draws design principles from **NetworkX**. LangGraph is developed by LangChain Inc., but can be used fully independently of the LangChain framework.