# LangGraph Core Concepts

## Graphs
At its core, LangGraph models agent workflows as graphs. You define the behavior of your agents using three key components:
1. State: A shared data structure that represents the current snapshot of your application. It can be any data type, but is typically defined using a shared state schema.
2. Nodes: Functions that encode the logic of your agents. They receive the current state as input, perform some computation or side-effect, and return an updated state.
3. Edges: Functions that determine which Node to execute next based on the current state. They can be conditional branches or fixed transitions.

By composing Nodes and Edges, you can create complex, looping workflows that evolve the state over time. Nodes and Edges are functions—they can contain an LLM or traditional code. In short: nodes do the work, edges tell what to do next.

LangGraph's underlying graph algorithm uses message passing to define a general program. When a Node completes its operation, it sends messages along one or more edges to other nodes. These recipient nodes execute their functions, pass the resulting messages to the next set of nodes, and the process continues. Inspired by Google's Pregel system, the program proceeds in discrete "super-steps."

A super-step can be considered a single iteration over the graph nodes. Nodes that run in parallel are part of the same super-step, while nodes that run sequentially belong to separate super-steps. At the start of graph execution, all nodes begin in an inactive state. A node becomes active when it receives a new message (state) on any of its incoming edges or channels. The active node runs its function and responds with updates. At the end of each super-step, nodes with no incoming messages vote to halt by marking themselves as inactive. The graph execution terminates when all nodes are inactive and no messages are in transit.

## StateGraph
The `StateGraph` class is the main graph class to use. This is parameterized by a user-defined State object.

### Compiling your graph
To build your graph, you first define the state, then add nodes and edges, and finally compile it. Compiling provides basic checks on the structure of your graph (e.g., ensuring no orphaned nodes exist). It is also where you specify runtime arguments like checkpointers and breakpoints. You MUST compile your graph before you can use it.

Python Example:
```python
graph = graph_builder.compile(...)
```

JavaScript Example:
```javascript
const graph = new StateGraph(StateAnnotation)
  .addNode("nodeA", nodeA)
  .addEdge(START, "nodeA")
  .addEdge("nodeA", END)
  .compile();
```

## State
The first thing you do when defining a graph is defining its State. The State consists of the schema of the graph as well as reducer functions which specify how to apply updates to the state. The schema of the State will be the input schema to all Nodes and Edges in the graph. All Nodes will emit updates to the State which are then applied using the specified reducer function.

In Python, the State schema can be a `TypedDict` or a `Pydantic` model.
In JavaScript, you define state using the `StateSchema` class, which accepts standard schemas (like Zod) along with special value types like `ReducedValue` and `MessagesValue`.

### Schema
- **Python**: The main documented way to specify the schema is using a `TypedDict`. For default values, use a `dataclass`. `Pydantic BaseModel` is supported for recursive data validation (though less performant). Note: The higher-level `create_agent` factory in `langchain` does not support Pydantic state schemas.
- **JavaScript**: Specified using `StateSchema`. Fields can be a Standard schema for simple fields ("last value" channel), `ReducedValue` for custom reducers, `MessagesValue` for chat message lists, or `UntrackedValue` for transient state.

JavaScript Schema Example:
```javascript
import { StateSchema, ReducedValue, MessagesValue, UntrackedValue } from "@langchain/langgraph";
import { z } from "zod/v4";

const AgentState = new StateSchema({
  messages: MessagesValue,
  currentStep: z.string(),
  retryCount: z.number().default(0),
  allSteps: new ReducedValue(
    z.array(z.string()).default(() => []),
    {
      inputSchema: z.string(),
      reducer: (current, newStep) => [...current, newStep],
    }
  ),
  tempCache: new UntrackedValue(z.record(z.string(), z.unknown())),
});

type State = typeof AgentState.State;
type Update = typeof AgentState.Update;

const graph = new StateGraph(AgentState)
  .addNode("myNode", ...)
  .compile();
```

By default, the graph has matching input and output schemas. Explicit input and output schemas can be defined directly if you want to constrain input/output parameters.

### Multiple Schemas and Private Channels
Typically, all graph nodes communicate with a single schema. However, you can define different schemas for advanced control:
- **Internal/Private State**: Nodes can write to private state channels (e.g., `PrivateState`) for internal communication without exposing these fields in the graph output.
- **Explicit Input/Output Schemas**: Define sub-sets of an internal schema to strictly constrain inputs and outputs.

Key behaviors:
1. A node can write to any state channel in the overall graph state, even if that channel is not part of the node's input schema.
2. Nodes can declare additional state channels dynamically if the state schema definition exists.
3. Private channels are NOT redacted when streaming with `stream_mode="values"` or `streamMode: "values"`. To restrict streamed values to specific channels, pass `output_keys` (Python) or `outputKeys` (JS). Use `stream_mode="updates"` / `streamMode: "updates"` to stream only the channel changes produced by a node in each step.

Python Streaming Filter Example:
```python
stream = graph.stream_events(
    {"user_input": "My"},
    version="v3",
    output_keys=["graph_output"],
)
for snapshot in stream.values:
    print(snapshot)
```

JavaScript Streaming Filter Example:
```javascript
const stream = await graph.streamEvents(
  { userInput: "My" },
  { version: "v3", outputKeys: ["graphOutput"] }
);
for await (const snapshot of stream.values) {
  console.log(snapshot);
}
```

## Reducers
Reducers determine how updates from nodes are applied to the State. Each key in the State has its own independent reducer function. If no reducer function is explicitly specified, updates default to replacing/overwriting the key's previous value.

### Reducer Arguments
Every reducer is a binary function with two positional arguments:
- **Left argument**: Current value stored in state for that key.
- **Right argument**: Update for that key returned by a node.

Evaluation model:
```
new_value = reducer(left=current_state[key], right=node_update[key])
```

### Default vs Custom Reducers
- **Default Reducer**: Ignores the left argument and replaces the state value with the right argument (e.g., updating `foo: 1` with `foo: 2` yields `foo: 2`).
- **Custom Reducers**: Combines left and right arguments (e.g., appending items to a list via `operator.add` in Python or `ReducedValue` in JS).

### Resetting a Reducer Field and Overwriting
Returning an empty value to a merging reducer does not clear a field because the reducer merges the right argument into the left. 
To bypass a reducer and directly overwrite or clear a state value, use the `Overwrite` wrapper/type provided by LangGraph.

## Untracked Values
`UntrackedValue` is used for state fields that exist during graph execution but should never be checkpointed. When resuming execution from a checkpoint, untracked values reset to their initial/default state.

Common use cases:
- Non-serializable database connections
- Temporary runtime caches
- Large objects not intended for persistence
- Dynamic runtime configuration

JavaScript UntrackedValue Example:
```javascript
import { StateSchema, UntrackedValue, MessagesValue } from "@langchain/langgraph";
import { z } from "zod/v4";

const State = new StateSchema({
  messages: MessagesValue,
  dbConnection: new UntrackedValue<DatabaseConnection>(), // Throws error on multi-node concurrent write (guard: true)
  tempCache: new UntrackedValue(z.record(z.string(), z.unknown()), { guard: false }), // Keeps last value on multi-write
  runtimeConfig: new UntrackedValue(),
});
```

*Note*: Do not use `UntrackedValue` for data that must persist across interrupts or time travel.

## TypeScript Type Utilities
LangGraph provides type utilities for enhanced TypeScript type safety:
- **GraphNode**: Types node functions defined outside the graph builder (`GraphNode<typeof State>`).
- **State.Node**: Shorthand for typing nodes (`typeof State.Node`).
- **ConditionalEdgeRouter**: Types routing functions for conditional edges.
- **StateSchema.State & StateSchema.Update**: Extracts full state and partial update types from a schema.

Example:
```typescript
import { GraphNode, StateSchema, Command, ConditionalEdgeRouter, END } from "@langchain/langgraph";
import { z } from "zod/v4";

const State = new StateSchema({
  count: z.number().default(0),
  result: z.string(),
});

type MyState = typeof State.State;
type MyUpdate = typeof State.Update;

const incrementNode: GraphNode<typeof State> = (state) => {
  return { count: state.count + 1 };
};

const router: ConditionalEdgeRouter<{ InputSchema: typeof State; Nodes: "process" | "done" }> = (state) => {
  return state.count >= 10 ? END : "process";
};
```

## Working with Messages in Graph State
Chat models in LangChain process sequences of message objects (e.g., `HumanMessage`, `AIMessage`).

### Storing Messages
- **Python**: Use `add_messages` reducer via `Annotated[list[AnyMessage], add_messages]`. It handles appending new messages and updating existing messages in-place matching by ID. Alternatively, inherit from `MessagesState`.
- **JavaScript**: Use `MessagesValue`, which wraps an internal message-aware reducer to handle updates, deletions, and ID tracking automatically.

### Deserialization
LangGraph automatically deserializes raw dictionary or object inputs on the messages channel into LangChain `Message` instances.

Python Messages Definition:
```python
from langchain.messages import AnyMessage
from langgraph.graph.message import add_messages
from langgraph.graph import MessagesState
from typing import Annotated
from typing_extensions import TypedDict

class GraphState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]

# Subclassing MessagesState:
class CustomState(MessagesState):
    documents: list[str]
```

JavaScript Messages Definition:
```javascript
import { StateGraph, StateSchema, MessagesValue } from "@langchain/langgraph";
import * as z from "zod";

const State = new StateSchema({
  messages: MessagesValue,
  documents: z.array(z.string()),
});
```

## Nodes
Nodes are functions (synchronous or asynchronous) that process state.
- **Python Arguments**: `state`, `config` (`RunnableConfig`), and `runtime` (`Runtime`).
- **JavaScript Arguments**: `state` and `config` (`RunnableConfig`).

Functions are automatically converted to `RunnableLambda` instances to support async execution, batching, tracing, and debugging.

Python Node Example:
```python
from langgraph.graph import StateGraph
from langgraph.runtime import Runtime

def my_node(state: State, runtime: Runtime):
    print("Execution thread ID:", runtime.execution_info.thread_id)
    return {"results": f"Hello, {state['input']}!"}

builder = StateGraph(State)
builder.add_node("my_node", my_node)
```

JavaScript Node Example:
```javascript
import { StateGraph, StateSchema, GraphNode } from "@langchain/langgraph";

const myNode: GraphNode<typeof State> = (state, config) => {
  console.log("User ID:", config?.configurable?.user_id);
  return { results: `Hello, ${state.input}!` };
};

const builder = new StateGraph(State).addNode("myNode", myNode);
```

### Re-execution and Idempotency
- **Super-step Checkpointing**: LangGraph saves state checkpoints at super-step boundaries, not mid-function inside a node. If an execution resumes after an interrupt or failure, the node executes again from the beginning.
- **Idempotency**: Node logic should be idempotent (e.g., using upserts or read-before-write logic) to avoid unintended duplicate side effects upon re-execution.
- **Deterministic Rules**: When using tasks or `interrupt()` inside a node, ordering must remain deterministic across resumes so cached task outputs map correctly.

### Special Nodes: START and END
- **START**: Virtual node representing user input entry. Used to set entry edges.
- **END**: Virtual terminal node denoting execution end.

Python:
```python
from langgraph.graph import START, END
builder.add_edge(START, "first_node")
builder.add_edge("last_node", END)
```

JavaScript:
```javascript
import { START, END } from "@langchain/langgraph";
graph.addEdge(START, "firstNode");
graph.addEdge("lastNode", END);
```

### Node Caching
Nodes support caching outputs based on inputs using a `CachePolicy` (specifying `ttl` in seconds and key generation functions) and passing a cache instance (e.g., `InMemoryCache`) to `.compile()`.

## Edges
Edges route control flow across the graph:
1. **Normal Edges**: Direct static transitions between nodes.
2. **Conditional Edges**: Dynamic routing using custom routing functions based on state.
3. **Entry Points**: First node(s) called when execution begins (`START`).
4. **Conditional Entry Points**: Dynamic functions determining the initial node from `START`.

*Best Practice*: Choose either normal static edges OR conditional dynamic routing/`Command` per node. Avoid mixing static and dynamic outgoing edges from the same node.

Python Edges Example:
```python
# Static
graph.add_edge("node_a", "node_b")

# Conditional
graph.add_conditional_edges("node_a", routing_function, {True: "node_b", False: "node_c"})
```

JavaScript Edges Example:
```javascript
// Static
graph.addEdge("nodeA", "nodeB");

// Conditional
graph.addConditionalEdges("nodeA", routingFunction, { true: "nodeB", false: "nodeC" });
```

### Send (Map-Reduce Pattern)
`Send` objects allow dynamic edge creation and branching at runtime when destination edges or state variants are not known ahead of time.

Python Send Example:
```python
from langgraph.types import Send

def continue_to_jokes(state: OverallState):
    return [Send("generate_joke", {"subject": s}) for s in state['subjects']]

graph.add_conditional_edges("node_a", continue_to_jokes)
```

JavaScript Send Example:
```javascript
import { Send } from "@langchain/langgraph";

graph.addConditionalEdges("nodeA", (state) => {
  return state.subjects.map((subject) => new Send("generateJoke", { subject }));
});
```

## Command Primitive
`Command` is a control flow primitive with four parameters:
- `update`: Apply state updates.
- `goto`: Route to target nodes.
- `graph`: Target parent graph (`Command.PARENT`) when executing inside subgraphs.
- `resume`: Provide a value to resume execution after an interrupt.

### Node Return with Command
Combines state updates and routing into a single step:

Python:
```python
def my_node(state: State) -> Command[Literal["my_other_node"]]:
    return Command(
        update={"foo": "bar"},
        goto="my_other_node"
    )
```

JavaScript:
```javascript
import { Command } from "@langchain/langgraph";

graph.addNode("myNode", (state) => {
  return new Command({
    update: { foo: "bar" },
    goto: "myOtherNode",
  });
}, { ends: ["myOtherNode"] });
```

### Resuming Interrupts with Command
Pass `Command(resume=...)` into `invoke()` or `stream()` to resume a graph paused by an `interrupt()`.

JavaScript Interrupt & Resume Example:
```javascript
import { Command, interrupt } from "@langchain/langgraph";

const humanReview = async (state) => {
  const answer = interrupt("Do you approve?");
  return { messages: [{ role: "user", content: answer }] };
};

// Initial run pauses at interrupt
const result = await graph.invoke({ messages: [...] }, config);

// Resuming execution
const resumed = await graph.invoke(new Command({ resume: "yes" }), config);
```

*Important*: Do not pass `Command(update=...)` alone to continue multi-turn conversations on finished threads, as `Command` resumes from the latest checkpoint rather than restarting from `__start__`. Use plain dictionary/object inputs to continue existing threads.

## Graph Migrations
LangGraph supports updating graph topologies and state schemas when using checkpointers:
- **Completed Threads**: Full topology changes (adding, removing, renaming nodes/edges) are supported.
- **Interrupted Threads**: Adding/modifying nodes is supported, but renaming/removing active nodes currently in flight is restricted.
- **State Changes**: Adding and removing state keys is fully backward and forward compatible. Renaming keys resets saved values for that key on historical threads.

## Runtime Context
Context schemas allow passing non-state runtime dependencies (such as database client connections or model configuration) directly to nodes.

Python Context Example:
```python
@dataclass
class ContextSchema:
    llm_provider: str = "openai"

graph = StateGraph(State, context_schema=ContextSchema)
graph.invoke(inputs, context={"llm_provider": "anthropic"})
```

JavaScript Context Example:
```javascript
const ContextSchema = z.object({
  llm: z.union([z.literal("openai"), z.literal("anthropic")]),
});

const graph = new StateGraph(State, ContextSchema);
await graph.invoke(inputs, { context: { llm: "anthropic" } });
```

## Recursion Limit
The recursion limit specifies the maximum number of super-steps a graph can execute per run. Exceeding the limit raises `GraphRecursionError`.
- Default Python limit: 1000 steps.
- Default JS limit: 25 steps.

Configured via runtime parameters:
```python
graph.invoke(inputs, config={"recursion_limit": 5})
```

### Accessing Step Metadata & Proactive Recursion
Current execution steps can be monitored within nodes via `config["metadata"]["langgraph_step"]`.

LangGraph provides `RemainingSteps` to proactively handle approaching execution limits:
```python
from langgraph.managed import RemainingSteps

class State(TypedDict):
    messages: list
    remaining_steps: RemainingSteps

def reasoning_node(state: State) -> dict:
    if state["remaining_steps"] <= 2:
        return {"messages": ["Approaching limit, wrapping up..."]}
    return {"messages": ["Thinking..."]}
```

### Proactive vs. Reactive Recursion Handling
- **Proactive Handling**: Monitors `RemainingSteps` within the graph logic to route gracefully to fallback nodes before exceeding limits. The graph finishes execution cleanly.
- **Reactive Handling**: Catches `GraphRecursionError` in an external `try/catch` block after failure occurs.