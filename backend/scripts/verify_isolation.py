"""Manual verification that the vector layer isolates users.

This is the Task-3 checkpoint artifact. It proves the core security
claim — *user A can never retrieve user B's chunks* — by exercising the
real retrieval path (embed -> Qdrant search with a user_id filter).

It deliberately does NOT touch PDFs or the Anthropic API:
  * No PDF — we upsert hand-written chunks directly, so the test runs
    in seconds and depends on nothing but Qdrant + the local embedder.
  * No Claude — isolation is enforced at retrieval, below generation, so
    `retrieve()` is the highest layer we need to check. No API key needed.

Prerequisite: Qdrant running (docker compose up -d). The first run also
downloads the ~130 MB bge-small embedding model.

Run from backend/:
    py -m scripts.verify_isolation
"""
import sys

# Windows consoles default to cp1252, which can't encode characters this
# script prints (and would crash mid-run on the first one). Force UTF-8
# on stdout so output is identical across platforms / when piped.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.rag import vectorstore
from app.rag.embeddings import EMBEDDING_DIM
from app.rag.retrieval import retrieve

# Two fixed, obviously-fake user IDs. In production these are the UUIDs
# of `users` rows; here we only need them to be distinct and stable.
USER_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
USER_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

DOC_A = "doc-alice-0001"
DOC_B = "doc-bob-0001"

# Alice's corpus is about op-amps; Bob's is about the 555 timer. The two
# topics are semantically far apart, so a query aimed at one user's topic
# would happily surface the other's chunks *if the filter were missing* —
# which is exactly what makes this a meaningful isolation test.
ALICE_CHUNKS = [
    {
        "filename": "alice_lm358.pdf",
        "page": 1,
        "chunk_index": 0,
        "text": (
            "The LM358 is a dual operational amplifier that operates from "
            "a single supply over a wide voltage range of 3V to 32V."
        ),
    },
    {
        "filename": "alice_lm358.pdf",
        "page": 1,
        "chunk_index": 1,
        "text": (
            "The op-amp input common-mode voltage range includes ground, "
            "which simplifies single-supply amplifier design."
        ),
    },
]

BOB_CHUNKS = [
    {
        "filename": "bob_ne555.pdf",
        "page": 1,
        "chunk_index": 0,
        "text": (
            "The NE555 timer can be configured as an astable multivibrator "
            "to generate a continuous square-wave oscillator output."
        ),
    },
    {
        "filename": "bob_ne555.pdf",
        "page": 1,
        "chunk_index": 1,
        "text": (
            "In astable mode the output frequency is set by the two timing "
            "resistors and the timing capacitor connected to the 555."
        ),
    },
]


def _embed(chunks: list[dict]) -> list[list[float]]:
    """Embed chunk texts as documents (import here so model load is lazy)."""
    from app.rag.embeddings import embed_batch

    return embed_batch([c["text"] for c in chunks], show_progress=False)


def _print_results(label: str, results: list[dict]) -> None:
    print(f"  {label}:")
    if not results:
        print("    (no results)")
        return
    for r in results:
        print(
            f"    score={r['score']:.3f}  doc={r['document_id']:<14} "
            f"{r['filename']} p.{r['page']}#{r['chunk_index']}"
        )


def main() -> int:
    failures: list[str] = []

    print("=" * 70)
    print("PER-USER ISOLATION VERIFICATION (vector layer)")
    print("=" * 70)

    # --- Setup -----------------------------------------------------------
    print("\n[1] Initializing collection + seeding two users' corpora...")
    vectorstore.init_collection(EMBEDDING_DIM)

    # Clean any leftovers from a previous run so counts are deterministic.
    vectorstore.delete_by_document_id(DOC_A)
    vectorstore.delete_by_document_id(DOC_B)

    vectorstore.upsert(ALICE_CHUNKS, _embed(ALICE_CHUNKS), user_id=USER_A, document_id=DOC_A)
    vectorstore.upsert(BOB_CHUNKS, _embed(BOB_CHUNKS), user_id=USER_B, document_id=DOC_B)

    total = vectorstore.count()
    a_count = vectorstore.count(user_id=USER_A)
    b_count = vectorstore.count(user_id=USER_B)
    print(f"    points: total>={total}, user A={a_count}, user B={b_count}")
    if a_count < len(ALICE_CHUNKS) or b_count < len(BOB_CHUNKS):
        failures.append("seeding: per-user counts lower than expected")

    # --- Test 1: each user retrieves only their own topic ----------------
    print("\n[2] Each user queries their OWN topic - expect only own chunks.")
    a_self = retrieve("operational amplifier supply voltage range", USER_A)
    b_self = retrieve("555 timer astable oscillator frequency", USER_B)
    _print_results("user A -> op-amp query", a_self)
    _print_results("user B -> 555 timer query", b_self)

    if not a_self or any(r["document_id"] != DOC_A for r in a_self):
        failures.append("user A's own-topic results contained non-A documents")
    if not b_self or any(r["document_id"] != DOC_B for r in b_self):
        failures.append("user B's own-topic results contained non-B documents")

    # --- Test 2: the attack — A queries for B's topic --------------------
    # If the filter were missing, this query would return Bob's 555-timer
    # chunks (they are the best semantic match for it). With the filter,
    # A must NEVER see DOC_B — at worst A gets weak matches from its own
    # corpus, at best nothing.
    print("\n[3] ATTACK: user A queries for user B's topic (555 timer).")
    print("    Expectation: ZERO of user B's chunks may appear.")
    a_cross = retrieve("555 timer astable oscillator frequency capacitor", USER_A)
    _print_results("user A -> 555 timer query", a_cross)

    leaked = [r for r in a_cross if r["document_id"] == DOC_B]
    if leaked:
        failures.append(
            f"ISOLATION BREACH: user A retrieved {len(leaked)} of user B's chunks"
        )
    else:
        print("    -> No user B chunks leaked to user A. [OK]")

    # Symmetric check: B queries for A's topic.
    b_cross = retrieve("operational amplifier single supply common-mode", USER_B)
    if any(r["document_id"] == DOC_A for r in b_cross):
        failures.append("ISOLATION BREACH: user B retrieved user A's chunks")

    # --- Test 3: delete_by_document_id is scoped --------------------------
    print("\n[4] Deleting user A's document — user B must be untouched.")
    vectorstore.delete_by_document_id(DOC_A)
    a_after = vectorstore.count(user_id=USER_A)
    b_after = vectorstore.count(user_id=USER_B)
    print(f"    after delete: user A={a_after}, user B={b_after}")
    if a_after != 0:
        failures.append("delete_by_document_id did not remove all of user A's points")
    if b_after < len(BOB_CHUNKS):
        failures.append("deleting user A's doc also removed user B's points")

    # --- Cleanup ---------------------------------------------------------
    vectorstore.delete_by_document_id(DOC_B)

    # --- Verdict ---------------------------------------------------------
    print("\n" + "=" * 70)
    if failures:
        print("RESULT: FAIL")
        for f in failures:
            print(f"  - {f}")
        print("=" * 70)
        return 1
    print("RESULT: PASS - users are isolated at the vector layer.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
