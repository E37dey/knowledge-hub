"""Call Claude with retrieved context and return an answer + sources.

Design notes:
  * `temperature=0.0` — RAG is a factual-retrieval task; we want maximum
    determinism, not creativity. Any temperature > 0 raises the chance
    of the model wandering off the source text.
  * The system prompt is sent with `cache_control: ephemeral` so
    Anthropic caches it across requests. SYSTEM_PROMPT is identical on
    every call and large enough (~1k input tokens) to make caching a
    real win at scale.

Changes from project 1:
  * Takes already-retrieved `chunks` instead of retrieving internally —
    retrieval (which needs the user_id) happens one layer up in the
    service, keeping this function purely Claude-facing.
  * Reads the API key from `settings`, not a local `load_dotenv` call,
    so there is a single source of truth for configuration.
"""
from anthropic import Anthropic

from app.config import settings
from app.rag.prompts import SYSTEM_PROMPT, build_user_prompt

CLAUDE_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1024
TEMPERATURE = 0.0

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    """Lazy singleton accessor for the Anthropic client."""
    global _client
    if _client is None:
        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Add it to backend/.env "
                "and restart."
            )
        _client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


def generate_answer(question: str, chunks: list[dict]) -> dict:
    """Ask Claude the question grounded in `chunks`; return answer + sources.

    Returns:
        {
            "answer": str,             # Claude's response text
            "sources": list[dict],     # the chunks shown to the model,
                                       # ordered by retrieval score desc
        }
    """
    user_prompt = build_user_prompt(question, chunks)

    response = _get_client().messages.create(
        model=CLAUDE_MODEL,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_prompt}],
    )

    answer = response.content[0].text
    return {"answer": answer, "sources": chunks}
