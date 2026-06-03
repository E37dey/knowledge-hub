"""Semantic search — now per-user.

Difference from project 1: takes `user_id` and threads it through to
the vector store filter.
"""


def retrieve(query: str, user_id: str, top_k: int = 5) -> list[dict]:
    """Embed `query` and return top_k chunks belonging to `user_id`."""
    # TODO: vector = embed_query(query)
    # TODO: return search(vector, user_id=user_id, top_k=top_k)
    raise NotImplementedError
