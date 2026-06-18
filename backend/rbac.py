"""
rbac.py — Role-Based Access Control configuration for MediBot.

Defines which document collections each staff role can access, and builds
the Qdrant metadata filter that enforces this at the retrieval layer.
Every query through the vector store must carry this filter so that
restricted chunks are never returned to the application, let alone the LLM.
"""

from qdrant_client.models import Filter, FieldCondition, MatchAny


# Which document collections each role is permitted to query.
# This is the source of truth for RBAC — used both to build Qdrant filters
# and to populate the frontend's "accessible collections" display.
ROLE_COLLECTIONS: dict[str, list[str]] = {
    "doctor":            ["clinical", "nursing", "general"],
    "nurse":             ["nursing", "general"],
    "billing_executive": ["billing", "general"],
    "technician":        ["equipment", "general"],
    "admin":             ["clinical", "nursing", "billing", "equipment", "general"],
}

# The inverse map: which roles are allowed to see each collection.
# This is stored as metadata on every chunk at index time so that
# Qdrant can filter on it directly during retrieval.
COLLECTION_ACCESS_ROLES: dict[str, list[str]] = {
    "general":   ["doctor", "nurse", "billing_executive", "technician", "admin"],
    "clinical":  ["doctor", "admin"],
    "nursing":   ["nurse", "doctor", "admin"],
    "billing":   ["billing_executive", "admin"],
    "equipment": ["technician", "admin"],
}

# Roles that are allowed to use SQL RAG (analytical/numbers questions).
SQL_ALLOWED_ROLES: list[str] = ["billing_executive", "admin"]


def get_qdrant_filter(role: str) -> Filter:
    """
    Build the Qdrant Filter that restricts retrieval to chunks this role
    can access. Applied on every vector store query — not in application code
    after the fact — so restricted chunks never reach the LLM.

    The filter checks the 'access_roles' payload field on each chunk, which
    was set at index time from COLLECTION_ACCESS_ROLES.
    """
    return Filter(
        must=[
            # LangChain's Qdrant integration stores all document metadata
            # under a nested "metadata" key in the Qdrant payload, so the
            # correct path is "metadata.access_roles" not "access_roles".
            FieldCondition(
                key="metadata.access_roles",
                match=MatchAny(any=[role]),
            )
        ]
    )


def get_accessible_collections(role: str) -> list[str]:
    """
    Return the list of collection names the given role can access.
    Used by the /collections/{role} API endpoint and the frontend sidebar.
    Falls back to an empty list for unknown roles.
    """
    return ROLE_COLLECTIONS.get(role, [])


def is_sql_allowed(role: str) -> bool:
    """Return True if this role is permitted to use SQL RAG."""
    return role in SQL_ALLOWED_ROLES
