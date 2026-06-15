"""Tests for FitFindr tools — at least one test per failure mode."""

import tools
from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe, load_listings


def _mock_llm(prompt: str, temperature: float = 0.7) -> str:
    return "Pair with wide-leg jeans and chunky sneakers for a relaxed look."


tools._call_llm = _mock_llm


def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter():
    results = search_listings("track jacket", size="M", max_price=100)
    assert all("m" in item["size"].lower() for item in results)


def test_suggest_outfit_with_wardrobe():
    listings = load_listings()
    result = suggest_outfit(listings[0], get_example_wardrobe())
    assert isinstance(result, str)
    assert len(result) > 0


def test_suggest_outfit_empty_wardrobe():
    listings = load_listings()
    result = suggest_outfit(listings[0], get_empty_wardrobe())
    assert isinstance(result, str)
    assert len(result) > 0


def test_create_fit_card_happy_path():
    listings = load_listings()
    outfit = "Pair with wide-leg jeans and chunky sneakers."
    result = create_fit_card(outfit, listings[0])
    assert isinstance(result, str)
    assert len(result) > 0


def test_create_fit_card_empty_outfit():
    listings = load_listings()
    result = create_fit_card("", listings[0])
    assert "Cannot create a fit card" in result


def test_create_fit_card_whitespace_outfit():
    listings = load_listings()
    result = create_fit_card("   ", listings[0])
    assert "Cannot create a fit card" in result
