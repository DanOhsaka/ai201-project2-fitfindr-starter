"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """Initialize and return a fresh session dict for one user interaction."""
    return {
        "query": query,
        "parsed": {},
        "search_results": [],
        "selected_item": None,
        "wardrobe": wardrobe,
        "outfit_suggestion": None,
        "fit_card": None,
        "error": None,
    }


# ── query parsing ─────────────────────────────────────────────────────────────

def _parse_query(query: str) -> dict:
    """
    Extract description, size, and max_price from a natural language query.
    Uses regex — documented in planning.md.
    """
    remaining = query.strip()
    max_price = None
    size = None

    price_patterns = [
        r"(?:under|below|less than|max|up to)\s*\$?\s*(\d+(?:\.\d+)?)",
        r"\$\s*(\d+(?:\.\d+)?)\s*(?:or less|max)?",
    ]
    for pattern in price_patterns:
        match = re.search(pattern, remaining, re.IGNORECASE)
        if match:
            max_price = float(match.group(1))
            remaining = remaining[: match.start()] + remaining[match.end() :]
            break

    size_patterns = [
        r"\b(?:in\s+)?size\s+(\d+(?:\.\d+)?|XXS|XXXL|[XSML]+)\b",
    ]
    for pattern in size_patterns:
        match = re.search(pattern, remaining, re.IGNORECASE)
        if match:
            size = match.group(1).upper()
            remaining = remaining[: match.start()] + remaining[match.end() :]
            break

    description = re.sub(
        r"\b(i'm looking for|looking for|i want|find me|search for|what's out there)\b",
        "",
        remaining,
        flags=re.IGNORECASE,
    )
    description = re.sub(
        r"\b(how would i style it|how to style|what would i wear|style it)\??\s*",
        "",
        description,
        flags=re.IGNORECASE,
    )
    description = re.sub(r"\s+in\s*$", "", description)
    description = re.sub(r"\s+", " ", description).strip(" .,!?")
    description = description or query.strip()

    return {
        "description": description,
        "size": size,
        "max_price": max_price,
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.
    """
    session = _new_session(query, wardrobe)

    parsed = _parse_query(query)
    session["parsed"] = parsed

    description = parsed["description"]
    size = parsed["size"]
    max_price = parsed["max_price"]

    results = search_listings(description, size=size, max_price=max_price)
    size_loosened = False

    if not results and size is not None:
        results = search_listings(description, size=None, max_price=max_price)
        size_loosened = True

    session["search_results"] = results

    if not results:
        size_note = f"size {size}, " if size else ""
        price_note = f"under ${max_price:.0f}" if max_price else "any price"
        session["error"] = (
            f"No listings found for '{description}' ({size_note}{price_note}). "
            "Try broadening your search — remove the size filter, raise your price "
            "limit, or use different keywords like 'graphic tee' instead of 'band shirt'."
        )
        return session

    session["selected_item"] = results[0]

    outfit = suggest_outfit(session["selected_item"], wardrobe)
    session["outfit_suggestion"] = outfit

    fit_card = create_fit_card(outfit, session["selected_item"])
    if size_loosened:
        fit_card = (
            f"(Note: no exact size match found — showing best match regardless of size.)\n\n"
            + fit_card
        )
    session["fit_card"] = fit_card

    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
