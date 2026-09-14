import json
import re
from pathlib import Path

from app.services.llm_client import generate_reply_with_context, _run_cascade
from app.services.kb_retrieval import get_documents_by_ids

TREES_DIR = Path(__file__).resolve().parent.parent / "decision_trees"

_tree_cache: dict[str, dict | None] = {}


def get_tree(domain: str) -> dict | None:
    if domain in _tree_cache:
        return _tree_cache[domain]

    path = TREES_DIR / f"{domain}.json"
    if not path.exists():
        _tree_cache[domain] = None
        return None

    with open(path, "r", encoding="utf-8") as f:
        tree = json.load(f)

    _tree_cache[domain] = tree
    return tree


def get_node(tree: dict, node_id: str) -> dict:
    return tree["nodes"][node_id]


_BRANCH_CLASSIFY_SYSTEM = (
    "You are a strict classifier for a structured therapy-style dialogue "
    "flow. You will be given a question that was asked to a user (in "
    "Persian) and the user's free-text reply. Decide which ONE of the "
    "given category codes the reply best matches.\n"
    "Respond with ONLY the category code, nothing else -- no punctuation, "
    "no explanation. If the reply genuinely does not fit any category "
    "(off-topic, asks something else, or too ambiguous), respond with "
    "exactly: unclear"
)


def classify_branch(prompt_to_user: str, user_text: str, branch_keys: list[str]) -> str:
    categories = ", ".join(branch_keys)
    messages = [
        {"role": "system", "content": f"{_BRANCH_CLASSIFY_SYSTEM}\nCategories: {categories}, unclear"},
        {"role": "user", "content": f"Question asked to user: {prompt_to_user}\n\nUser's reply: {user_text}"},
    ]
    result = _run_cascade(messages, log_prefix="TREE_CLASSIFY")
    raw = (result.get("text") or "").strip().lower()

    for key in branch_keys:
        if re.search(rf"\b{re.escape(key.lower())}\b", raw):
            return key
    return "unclear"


def run_tree_node(
    start_node_id: str,
    tree_def: dict,
    db,
    user_text: str,
    profile_context: str | None,
    history: list[dict],
    memory_summary: str | None,
    clarify: bool = False,
) -> tuple[dict, str]:
    """Generates the assistant's message for landing on start_node_id.
    Returns (raw_llm_result_dict, resting_node_id) -- resting_node_id is
    the 'question' node now awaiting the user's answer, or the 'end' node
    just reached."""
    node = get_node(tree_def, start_node_id)
    kb_context = None
    instruction_parts = []
    resting_node_id = start_node_id

    if node["type"] == "leaf":
        docs = get_documents_by_ids(db, node.get("technique_kb_ids", []))
        if docs:
            kb_context = "\n\n".join(f"[{d['title']}] {d['chunk_text']}" for d in docs)
        instruction_parts.append(
            "Warmly explain the technique in the reference material below, "
            "in your own natural Persian words (do not copy it verbatim)."
        )
        next_id = node.get("next_node")
        resting_node_id = next_id
        next_node = get_node(tree_def, next_id) if next_id else None

        if next_node and next_node["type"] == "question":
            instruction_parts.append(
                f"Then, in the SAME message, naturally ask this follow-up "
                f"question: {next_node['prompt_to_user']}"
            )
        elif next_node and next_node["type"] == "end":
            if next_node.get("closing_style") == "positive":
                instruction_parts.append("Then close warmly, wishing them well, in the same message.")
            else:
                instruction_parts.append(
                    "Then, in the same message, gently acknowledge this alone may not "
                    "be enough and invite them to keep talking about what's going on."
                )

    elif node["type"] == "question":
        if clarify:
            instruction_parts.append(
                f"The user's last reply didn't clearly answer your question. "
                f"Gently rephrase and ask again, in your own natural Persian "
                f"words, this question: {node['prompt_to_user']}"
            )
        else:
            instruction_parts.append(
                f"Ask the user this question, in your own natural, warm "
                f"Persian words (don't just paste it verbatim): {node['prompt_to_user']}"
            )

    else:  # "end" reached directly
        if node.get("closing_style") == "positive":
            instruction_parts.append("Close the conversation warmly.")
        else:
            instruction_parts.append(
                "Gently acknowledge more support may be needed and invite them to keep talking."
            )

    tree_instruction = (
        "You are following a structured, pre-approved conversation flow for "
        "this topic. This turn's ONLY job: " + " ".join(instruction_parts) +
        " Do not introduce any other technique or advice beyond what's instructed here."
    )
    combined_kb_context = tree_instruction if not kb_context else f"{tree_instruction}\n\n{kb_context}"

    raw_result = generate_reply_with_context(
        user_text=user_text,
        profile_context=profile_context,
        history=history,
        memory_summary=memory_summary,
        kb_context=combined_kb_context,
    )
    technique_ids_used = node.get("technique_kb_ids", []) if node["type"] == "leaf" else []
    return raw_result, resting_node_id, technique_ids_used