"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()

LLM_MODEL = "llama-3.3-70b-versatile"


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


def _call_llm(prompt: str, temperature: float = 0.7) -> str:
    """Call Groq LLM and return the response text."""
    client = _get_groq_client()
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=512,
    )
    return response.choices[0].message.content.strip()


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def _score_listing(listing: dict, keywords: list[str]) -> int:
    """Score a listing by keyword overlap across searchable text fields."""
    searchable = " ".join([
        listing.get("title", ""),
        listing.get("description", ""),
        listing.get("category", ""),
        " ".join(listing.get("style_tags", [])),
        " ".join(listing.get("colors", [])),
        listing.get("brand") or "",
    ]).lower()

    score = 0
    for kw in keywords:
        if kw in searchable:
            score += 1
        if kw in listing.get("title", "").lower():
            score += 2
        if any(kw in tag.lower() for tag in listing.get("style_tags", [])):
            score += 2
    return score


def _matches_size(listing_size: str, requested_size: str) -> bool:
    """Case-insensitive substring match for size (e.g. 'M' matches 'S/M')."""
    return requested_size.lower() in listing_size.lower()


def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.
    """
    listings = load_listings()
    keywords = [w.lower() for w in re.findall(r"\w+", description) if len(w) > 1]

    candidates = []
    for listing in listings:
        if max_price is not None and listing["price"] > max_price:
            continue
        if size is not None and not _matches_size(listing["size"], size):
            continue
        score = _score_listing(listing, keywords) if keywords else 1
        if score > 0:
            candidates.append((score, listing))

    candidates.sort(key=lambda x: x[0], reverse=True)
    return [listing for _, listing in candidates]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def _format_wardrobe(wardrobe: dict) -> str:
    """Format wardrobe items into a readable string for the LLM prompt."""
    lines = []
    for item in wardrobe.get("items", []):
        tags = ", ".join(item.get("style_tags", []))
        colors = ", ".join(item.get("colors", []))
        notes = item.get("notes") or ""
        line = f"- {item['name']} ({item['category']}, {colors}, tags: {tags})"
        if notes:
            line += f" — {notes}"
        lines.append(line)
    return "\n".join(lines)


def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.
    """
    item_desc = (
        f"{new_item['title']} ({new_item['category']}, "
        f"${new_item['price']:.2f}, tags: {', '.join(new_item.get('style_tags', []))})"
    )
    wardrobe_items = wardrobe.get("items", [])

    if not wardrobe_items:
        prompt = f"""You are a personal stylist helping someone who just found a thrifted piece but has no wardrobe saved yet.

New item they're considering: {item_desc}

Suggest 1-2 complete outfit ideas using general wardrobe staples (don't reference specific owned pieces). Include specific styling tips like how to tuck, layer, or accessorize. Keep it practical and conversational — 3-5 sentences."""
    else:
        wardrobe_text = _format_wardrobe(wardrobe)
        prompt = f"""You are a personal stylist. The user found this thrifted item and wants outfit ideas using pieces they already own.

New item: {item_desc}

Their wardrobe:
{wardrobe_text}

Suggest 1-2 complete outfit combinations that incorporate the new item AND specific pieces from their wardrobe (name the pieces). Include styling tips (tuck, layer, roll sleeves, etc.). Keep it practical — 3-5 sentences."""

    try:
        return _call_llm(prompt, temperature=0.7)
    except Exception:
        tags = ", ".join(new_item.get("style_tags", []))
        return (
            f"Style the {new_item['title']} with pieces that match its "
            f"{tags} vibe. Pair with relaxed bottoms and your favorite sneakers "
            f"for an easy everyday look."
        )


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.
    """
    if not outfit or not outfit.strip():
        return (
            "Cannot create a fit card — no outfit suggestion was provided. "
            "Run suggest_outfit first."
        )

    platform = new_item.get("platform", "depop")
    prompt = f"""Write a casual Instagram/TikTok outfit caption for this thrift find. Sound like a real person posting their OOTD — NOT a product description.

Item: {new_item['title']}
Price: ${new_item['price']:.2f}
Platform: {platform}
Outfit: {outfit}

Rules:
- 2-4 sentences, casual and authentic
- Mention the item, price, and platform naturally (once each)
- Capture the vibe in specific terms
- Use lowercase, emojis sparingly (0-2 max)
- Do NOT sound like marketing copy"""

    try:
        return _call_llm(prompt, temperature=0.9)
    except Exception:
        return (
            f"scored this {new_item['title'].lower()} off {platform} for "
            f"${new_item['price']:.0f} and i'm obsessed. {outfit[:120]}..."
        )
