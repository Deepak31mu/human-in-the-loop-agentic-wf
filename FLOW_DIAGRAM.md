# Human-in-the-Loop Workflow — Flow Diagram

## Application Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         main()                                      │
│                                                                     │
│  task = "Send refund email of $100 to John"                         │
│  config = { thread_id: "case-1" }                                   │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                    graph.invoke(initial_state, config)
                             │
                             ▼
                    ┌────────────────┐
         START ───► │  analyze_node  │  Produces: analysis = "Proposed action for task: ..."
                    └───────┬────────┘
                            │
                            ▼
                    ┌────────────────┐
                    │  human_node    │  Calls interrupt() ──► graph SUSPENDS
                    └───────┬────────┘        │
                            │                 │ LangGraph saves checkpoint
                            │                 │ under thread_id "case-1"
                            │                 ▼
                            │       ┌──────────────────────┐
                            │       │   ask_human() (CLI)  │
                            │       │                      │
                            │       │  > approve           │
                            │       │  > reject            │
                            │       │  > edit              │
                            │       └──────────┬───────────┘
                            │                  │ human_decision dict
                            │                  ▼
                            │       graph.invoke(Command(resume=human_decision), config)
                            │       LangGraph restores checkpoint, resumes human_node
                            │
                            │  Returns: { approval: { choice: "approve"|"reject"|"edit" } }
                            │
                            ▼
                    ┌────────────────┐
                    │  execute_node  │
                    │                │
                    │  "approve" ───►│─── "Task executed as proposed."
                    │  "edit"    ───►│─── "Task executed with edits: <edited_text>"
                    │  "reject"  ───►│─── "Task rejected by human."
                    └───────┬────────┘
                            │
                           END
                            │
                            ▼
                    final_result printed
```

## Key Mechanics

| Concept | Role |
|---|---|
| `InMemorySaver` | Checkpointer — stores graph state between the two `invoke()` calls |
| `thread_id: "case-1"` | The bookmark that links both `invoke()` calls to the same run |
| `interrupt()` | Suspends the graph inside `human_node`, returning control to `main()` |
| `Command(resume=...)` | Resumes the graph from the exact point it was interrupted |

## Two-Phase Invoke Pattern

The workflow is a **two-phase invoke**:

1. **Phase 1** — `graph.invoke(initial_state, config)`
   - Runs `analyze_node` → `human_node`
   - Graph suspends at `interrupt()` and saves checkpoint

2. **Human Input** — `ask_human()` collects approve / reject / edit decision from CLI

3. **Phase 2** — `graph.invoke(Command(resume=human_decision), config)`
   - LangGraph restores checkpoint using `thread_id`
   - Resumes `human_node` with the human decision
   - Continues to `execute_node` → `END`
