# Agents in LangChain

## 1. What is an agent?

An agent is a model that calls tools in a loop until a given task is complete.

A **harness** is everything surrounding that loop: the prompt, the tools, and any middleware that shapes the model's behavior.

**Agent = Model + Harness**

The harness's job is to provide the model with the right context at the right time for the task.

LangChain's `create_agent` function provides a highly configurable harness. Its basic configuration uses the `model`, `tools`, and `system_prompt` parameters. More advanced behavior can be added through middleware.

Deep Agents builds on `create_agent` and includes commonly useful capabilities such as planning, filesystem tools, subagents, and memory. Use `create_agent` when you want to configure the harness yourself.

## 2. Core components

### 2.1 Model

Pass either a model identifier string in the form `"provider:model"` or an initialized model instance to select the model used by the agent.

### 2.2 Tools

Tools give the agent capabilities beyond generating text. They can be supplied as Python callables, LangChain tools, or tool dictionaries.

Tools can be used to perform actions or retrieve information. Their definitions can also specify how they access runtime context and how tool selection is handled.

### 2.3 System prompt

The system prompt shapes how the agent approaches tasks. The `system_prompt` parameter accepts a string or a `SystemMessage`.

For prompts that need to change dynamically at runtime, middleware can be used.

### 2.4 Structured output

The `response_format` parameter allows an agent to return output that conforms to a validated schema.

### 2.5 Agent state

Every agent manages its execution context through an `AgentState` object. It stores the current conversation history and any custom fields required by tools or middleware.

The built-in field is:

| Field | Type | Description |
|---|---|---|
| `messages` | `list[BaseMessage]` in Python | The full conversation history for the current thread. It is append-only: new messages are added rather than replacing earlier messages. |

`AgentState` is also the state type received by node-style middleware hooks, such as `before_model` and `after_model`. Hooks can return a dictionary of updates that are merged into the current state.

Custom state fields can be added by subclassing `AgentState` and passing the subclass to `create_agent` through `state_schema`.

## 3. Invoking an agent

An agent can be invoked with a message. Internally, this passes an update to the agent's state.

All agents include a sequence of messages in their state. To invoke an agent while preserving and resuming conversation history, provide a new message and a `thread_id`.

### 3.1 Conversation persistence

Using `thread_id` to persist conversation history requires the agent to be configured with a checkpointer.

When deployed through LangSmith, a checkpointer is provisioned automatically. When running locally, provide one explicitly, for example:

```python
create_agent(..., checkpointer=InMemorySaver())
```

The `thread_id` identifies the conversation scope, including its message history and checkpoints.

### 3.2 Per-run context

Per-run configuration can be passed alongside the agent configuration through `context`. This can include information such as a user ID, API keys, or feature flags that tools and middleware need during a run.

Define the shape of this data with `context_schema` and access it through `runtime.context`.

The distinction is:

- `thread_id` scopes the conversation, including message history and checkpoints.
- `context` carries per-run data that tools and middleware read at invocation time.

Both are commonly passed together.

## 4. Streaming

The `invoke` method returns the final response when a run finishes.

If an agent executes multiple tool calls, users may need progress updates before completion. Streaming can expose intermediate messages and tool activity as they happen.

## 5. Configuring the harness with middleware

`create_agent` is highly extensible. Middleware is the main customization mechanism: each middleware component handles a particular concern, hooks into the agent loop at the appropriate point, and can be combined with other middleware.

Use only the capabilities needed for the particular application. Common patterns are available as built-in middleware; other behavior can be implemented with custom middleware.

Middleware can provide capabilities in areas such as:

- Tools, filesystems, sandboxes, and code execution.
- Summarization, memory, skills, and prompt caching.
- To-do lists and subagents for parallel, isolated work.
- Retries, fallbacks, and limits on tool calls.
- Personally identifiable information (PII) detection and content controls.
- Human approval before high-impact actions.

`create_deep_agent` assembles a predefined harness for long-running coding and research tasks. Its included capabilities include a filesystem, summarization, subagents, and prompt caching.

## 6. Execution environment

Agents are especially useful when they can take actions rather than only generate text.

An execution environment gives an agent a workspace that can include:

- Tools it can call.
- A filesystem for reading and writing files across turns.
- Code execution for running scripts or shell commands.

The filesystem, sandbox, and interpreter capabilities are available through components associated with the Deep Agents ecosystem.

## 7. Context management

Every model call has a fixed context window. As an agent runs, the context window fills with conversation history, tool results, and intermediate steps.

Several techniques help manage this context:

- **Summarization:** compresses conversation history before the context window overflows.
- **Memory:** loads persistent instructions at startup so useful knowledge can carry across sessions.
- **Skills:** make domain knowledge available on demand instead of loading all of it into the context at once.
- **Prompt caching:** can reuse supported prompt content to reduce repeated processing.

## 8. Planning and delegation

Complex tasks can exceed the capacity of a single context window.

Delegation allows a main agent to divide a task into smaller pieces and assign them to subagents. Each subagent works in its own isolated context, while the main agent focuses on coordination rather than carrying out every task itself.

Subagent work can run in parallel, helping keep the main agent's context focused.

## 9. Naming an agent

An agent can optionally be assigned an identifier. This is especially useful when embedding the agent as a subgraph in a multi-agent system.

## 10. Fault tolerance

Agents in production can encounter failures that are uncommon during development, including rate limits, model timeouts, and transient API errors.

Fault-tolerance middleware handles these failures at the infrastructure level, reducing the need to add `try`/`except` handling around every tool or business-logic call.

Relevant built-in patterns include model retries and tool retries.

## 11. Guardrails

Some policies should not rely solely on a prompt. They need to be enforced deterministically regardless of the model's behavior.

Guardrails intercept data as it moves through the agent loop and apply compliance rules or content policies before tool results reach the model's context.

One example is middleware that detects or handles personally identifiable information (PII).

## 12. Human oversight and steering

Full autonomy is not appropriate for every task.

Human-in-the-loop steering allows people to intervene at specific decision points, such as before destructive writes, expensive API calls, or actions that require judgment.

The agent can pause and wait for a person to approve, edit, or reject the proposed action. Execution then continues according to that decision.

A common implementation is human-in-the-loop middleware.

## Key concepts at a glance

- **Agent:** a model that repeatedly decides whether to call tools and continues until the task is complete.
- **Harness:** the prompt, tools, and middleware that shape the agent's behavior.
- **Model:** the language model used for reasoning and deciding what to do next.
- **Tools:** callable capabilities the model can invoke to take actions or retrieve information.
- **System prompt:** instructions that shape the agent's approach to a task.
- **Agent state:** the conversation history and other data used during execution.
- **`thread_id`:** identifies a conversation thread and its persisted history.
- **Checkpointer:** saves agent state so execution or conversation history can be resumed.
- **`context`:** per-run data made available to tools and middleware.
- **Middleware:** composable components that customize or control parts of the agent loop.
- **Streaming:** exposes intermediate messages and tool activity before the run completes.
- **Summarization and memory:** help manage context limits and carry useful information across sessions.
- **Subagents:** agents with isolated contexts that handle delegated parts of a larger task.
- **Fault tolerance:** handles operational failures such as timeouts and transient errors.
- **Guardrails:** enforce policies and content controls around the agent's execution.
- **Human-in-the-loop:** pauses execution for human approval, editing, or rejection at selected decision points.
