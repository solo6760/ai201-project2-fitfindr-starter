import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tools import search_listings, suggest_outfit, create_fit_card

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0

def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []  # empty list, no exception

def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)

def test_suggest_outfit_empty_wardrobe():
    new_item = {
        "id": "lst_001",
        "title": "Vintage Levi's 501 Jeans",
        "description": "Classic 501s",
        "category": "bottoms",
        "style_tags": ["vintage", "classic"],
        "size": "W30 L30",
        "condition": "good",
        "price": 38.00,
        "colors": ["blue"],
        "brand": "Levi's",
        "platform": "depop"
    }
    wardrobe = {"items": []}
    suggestion = suggest_outfit(new_item, wardrobe)
    assert isinstance(suggestion, str)
    assert len(suggestion.strip()) > 0

def test_suggest_outfit_with_items():
    new_item = {
        "id": "lst_002",
        "title": "Y2K Baby Tee",
        "description": "Super cute baby tee",
        "category": "tops",
        "style_tags": ["y2k", "vintage"],
        "size": "S",
        "condition": "excellent",
        "price": 18.00,
        "colors": ["white"],
        "brand": None,
        "platform": "depop"
    }
    wardrobe = {
        "items": [
            {
                "id": "w_001",
                "name": "Baggy straight-leg jeans",
                "category": "bottoms",
                "colors": ["dark blue"],
                "style_tags": ["denim", "streetwear"],
                "notes": "High-waisted"
            }
        ]
    }
    suggestion = suggest_outfit(new_item, wardrobe)
    assert isinstance(suggestion, str)
    assert len(suggestion.strip()) > 0

def test_create_fit_card_success():
    new_item = {
        "title": "Y2K Baby Tee",
        "price": 18.00,
        "platform": "depop"
    }
    outfit = "Pair it with your baggy jeans and chunky white sneakers."
    caption = create_fit_card(outfit, new_item)
    assert isinstance(caption, str)
    assert len(caption.strip()) > 0

def test_create_fit_card_empty_outfit():
    new_item = {
        "title": "Y2K Baby Tee",
        "price": 18.00,
        "platform": "depop"
    }
    caption = create_fit_card("", new_item)
    assert "Error" in caption or "Cannot" in caption
