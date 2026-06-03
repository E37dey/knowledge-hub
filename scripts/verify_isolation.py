"""End-to-end verification of per-user data isolation.

Hits the live API and proves the isolation contract:

  1. Two users (alice + bob) get distinct JWTs from /auth/login.
  2. Alice uploads a PDF; her /documents shows it indexed.
  3. Bob's /documents is empty — Postgres rows are FK-filtered.
  4. Bob asks a question — his sources are empty and his answer is
     the verbatim refusal phrase. Qdrant vectors are payload-filtered:
     alice's chunks are never even candidates.

Run:
    py scripts/verify_isolation.py
    py scripts/verify_isolation.py --pdf path/to/some.pdf
    py scripts/verify_isolation.py --keep    # don't delete alice's doc

Requires the API + Postgres + Qdrant to be up.
"""
import argparse
import sys
import uuid
from pathlib import Path

import httpx

DEFAULT_API = "http://localhost:8001"
# Default points at project 1's corpus, which the developer running this
# repo also has locally. Override with --pdf for any PDF on disk.
DEFAULT_PDF = Path(
    r"C:\Users\sound\Desktop\engineering-rag\data\NE555.pdf"
)
REFUSAL_PHRASE = "i don't have information on this in the provided documents"


class Checks:
    """Tiny in-process test runner. Prints PASS/FAIL and counts failures."""

    def __init__(self) -> None:
        self.failures = 0

    def __call__(self, label: str, condition: bool, detail: str = "") -> None:
        marker = "PASS" if condition else "FAIL"
        suffix = f"  ({detail})" if detail else ""
        print(f"  [{marker}] {label}{suffix}")
        if not condition:
            self.failures += 1


def register_and_login(client: httpx.Client, email: str, password: str) -> str:
    """Register (or accept 409 if already exists) and return a JWT."""
    r = client.post(
        "/auth/register", json={"email": email, "password": password}
    )
    if r.status_code not in (201, 409):
        raise RuntimeError(f"register failed: {r.status_code} {r.text}")

    r = client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    r.raise_for_status()
    return r.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api", default=DEFAULT_API, help=f"API base URL (default: {DEFAULT_API})"
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=DEFAULT_PDF,
        help="Path to a PDF for the upload test.",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Don't delete alice's uploaded document at the end.",
    )
    args = parser.parse_args()

    if not args.pdf.exists():
        print(f"Sample PDF not found: {args.pdf}")
        print("Pass --pdf <path> to point at any PDF on disk.")
        return 2

    # Unique emails per run so the script is repeatable without manual cleanup.
    run_id = uuid.uuid4().hex[:8]
    alice_email = f"alice+{run_id}@isolation.test"
    bob_email = f"bob+{run_id}@isolation.test"
    password = "isolation-test-pw"

    checks = Checks()
    alice_doc_id: str | None = None

    print(f"\n=== isolation verification (run {run_id}) ===")
    print(f"    api: {args.api}")
    print(f"    pdf: {args.pdf.name}\n")

    # The first ingestion call loads the embedding model — give it room.
    with httpx.Client(base_url=args.api, timeout=180) as client:
        # 1. Two users with distinct tokens.
        print("[1/5] Register + login")
        alice_token = register_and_login(client, alice_email, password)
        bob_token = register_and_login(client, bob_email, password)
        checks(
            "alice and bob have distinct JWTs",
            bool(alice_token) and bool(bob_token) and alice_token != bob_token,
        )

        # 2. Alice uploads.
        print("\n[2/5] Alice uploads a PDF (ingestion may take ~15s on first run)")
        with args.pdf.open("rb") as f:
            r = client.post(
                "/documents/upload",
                headers=auth(alice_token),
                files={"file": (args.pdf.name, f, "application/pdf")},
            )
        checks("upload returns 201", r.status_code == 201, f"got {r.status_code}")
        if r.status_code != 201:
            print(f"  body: {r.text[:300]}")
            return 1
        alice_doc = r.json()
        alice_doc_id = alice_doc["id"]
        checks(
            'status == "indexed"',
            alice_doc["status"] == "indexed",
            detail=f"status={alice_doc['status']}",
        )
        checks(
            "chunk_count > 0",
            alice_doc["chunk_count"] > 0,
            detail=f"{alice_doc['chunk_count']} chunks",
        )

        # 3. Alice can see her own doc.
        print("\n[3/5] Alice lists her documents")
        alice_docs = client.get("/documents", headers=auth(alice_token)).json()
        checks(
            "alice sees exactly 1 doc — her own",
            len(alice_docs) == 1 and alice_docs[0]["id"] == alice_doc_id,
            detail=f"got {len(alice_docs)} docs",
        )

        # 4. Bob sees nothing — Postgres FK isolation.
        print("\n[4/5] Bob lists documents — MUST be empty")
        bob_docs = client.get("/documents", headers=auth(bob_token)).json()
        checks(
            "bob's /documents is empty (Postgres FK isolation)",
            isinstance(bob_docs, list) and len(bob_docs) == 0,
            detail=f"got {len(bob_docs)} docs",
        )

        # 5. Bob's query is refused — Qdrant payload isolation.
        print("\n[5/5] Bob asks a question — MUST refuse (Qdrant payload isolation)")
        r = client.post(
            "/query",
            headers=auth(bob_token),
            json={"question": "What is the typical supply voltage of NE555?"},
        )
        checks("/query returns 200", r.status_code == 200, f"got {r.status_code}")
        if r.status_code == 200:
            body = r.json()
            checks(
                "bob's sources list is empty",
                len(body["sources"]) == 0,
                detail=f"got {len(body['sources'])} sources",
            )
            checks(
                'bob\'s answer is the verbatim refusal phrase',
                REFUSAL_PHRASE in body["answer"].lower(),
                detail=body["answer"][:80].replace("\n", " ") + "...",
            )

        # Cleanup.
        if not args.keep and alice_doc_id is not None:
            print("\n[cleanup] deleting alice's doc")
            client.delete(f"/documents/{alice_doc_id}", headers=auth(alice_token))

    print()
    if checks.failures == 0:
        print("ALL ISOLATION CHECKS PASSED")
        return 0
    print(f"{checks.failures} CHECK(S) FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
