"""Call Claude with retrieved context. Returns answer + source chunks.

To be ported from project 1 in Task 3. The Claude-facing code is
unchanged; only the upstream `retrieve()` call carries the user_id.
"""

CLAUDE_MODEL = "claude-sonnet-4-6"


def generate_answer(question: str, chunks: list[dict]) -> dict:
    """Return {"answer": str, "sources": list[dict]}."""
    # TODO: copy from engineering-rag/src/generate.py
    # TODO: temperature=0.0, prompt caching on SYSTEM_PROMPT
    raise NotImplementedError
