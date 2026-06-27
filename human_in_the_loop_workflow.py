"""
human_in_the_loop_workflow.py

Minimal LangGraph example with:
- State graph
- Human approval node using interrupt()
- Pause + resume using Command(resume=...)

Run:
    python human_in_the_loop_workflow.py
"""

from typing import TypedDict, Dict, Any

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import interrupt, Command


# ---------- 1. Define graph state  ---------------------

class State(TypedDict, total=False):
    task: str
    analysis: str
    approval: Dict[str, Any]
    final_result: str


# ---------- 2. Define nodes ----------

def analyze_node(state: State) -> Dict[str, Any]:
    """Fake analysis step (an agent/LLM would normally do this)."""
    task = state.get("task", "")
    analysis = f"Proposed action for task: {task}"
    print(f"[analyze_node] analysis = {analysis}")
    return {"analysis": analysis}


def human_node(state: State) -> Dict[str, Any]:
    """Pauses the graph for human review; resumes when called with Command(resume=...)."""
    question = f"Approve this action?\n{state.get('analysis', '')}"
    payload = {
        "kind": "approval",
        "question": question,
        "options": ["approve", "reject", "edit"],
    }

    print("[human_node] Pausing for human input...")
    decision = interrupt(payload)   # graph suspends here; resumes via Command(resume=...)
    print(f"[human_node] Resumed with decision: {decision}")
    return {"approval": decision}


def execute_node(state: State) -> Dict[str, Any]:
    """Executes, edits, or rejects the proposed action based on the human decision."""
    approval = state.get("approval", {}) or {}
    choice = approval.get("choice")
    print(f"[execute_node] choice = {choice}")

    if choice == "approve":
        result = "Task executed as proposed."
    elif choice == "edit":
        edited_text = approval.get("edited_text", "")
        result = f"Task executed with edits: {edited_text}"
    else:
        result = "Task rejected by human."

    print(f"[execute_node] final_result = {result}")
    return {"final_result": result}


# ---------- 3. Build and compile graph ----------

def build_graph():
    builder = StateGraph(State)

    builder.add_node("analyze", analyze_node)
    builder.add_node("human_review", human_node)
    builder.add_node("execute", execute_node)

    builder.add_edge(START, "analyze")
    builder.add_edge("analyze", "human_review")
    builder.add_edge("human_review", "execute")
    builder.add_edge("execute", END)

    graph = builder.compile(checkpointer=InMemorySaver())
    return graph


# ---------- 4. Simple CLI “human” interaction ----------

def ask_human(question: str, options: list[str]) -> Dict[str, Any]:
    """Console-based human input for approve / reject / edit decisions."""
    print("\n================ HUMAN REVIEW ================")
    print(question)
    print(f"Options: {', '.join(options)}")
    print("Type one of the options (approve / reject / edit): ")
    choice = input("Your choice: ").strip().lower()

    decision: Dict[str, Any] = {"choice": choice}

    if choice == "edit":
        edited_text = input("Enter your edited instructions: ").strip()
        decision["edited_text"] = edited_text

    print("=============================================\n")
    return decision


def main():
    graph = build_graph()

    # Use a thread_id so LangGraph can tie pause + resume together
    config = {"configurable": {"thread_id": "case-1"}}

    # ---------- First invoke: run until interrupt ----------
    print("=== FIRST INVOKE (will pause at human node) ===")
    initial_state = {"task": "Send refund email of $100 to John"}
    result = graph.invoke(initial_state, config)
    print("\n[main] State after first invoke (paused):")
    print(result)

    # Extract the interrupt info for UI (in production, you'd read this from the state/checkpoint)
    approval_payload = {
        "question": result.get("analysis", "No analysis available"),
        "options": ["approve", "reject", "edit"],
    }

    # ---------- Human input ----------
    human_decision = ask_human(
        approval_payload["question"],
        approval_payload["options"],
    )

    # ---------- Second invoke: resume ----------
    print("=== SECOND INVOKE (resuming with human decision) ===")
    result = graph.invoke(
        Command(resume=human_decision),
        config,
    )

    print("\n[main] Final state after resume:")
    print(result)
    print("\n[main] Final result:", result.get("final_result"))


if __name__ == "__main__":
    main()