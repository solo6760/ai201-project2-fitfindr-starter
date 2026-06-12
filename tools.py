"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.
    """
    # 1. Load all listings
    listings = load_listings()
    
    # 2. Filter by max_price (if provided)
    if max_price is not None:
        listings = [item for item in listings if item.get("price") is not None and item["price"] <= max_price]
        
    # 3. Filter by size (if provided)
    if size is not None:
        size_query = size.lower()
        filtered_listings = []
        for item in listings:
            item_size = item.get("size")
            if item_size is not None and size_query in item_size.lower():
                filtered_listings.append(item)
        listings = filtered_listings

    # 4. Score each remaining listing by keyword overlap with `description`
    import string
    # Tokenize description into words, removing punctuation
    desc_words = [w.lower() for w in description.split() if w]
    desc_words = [w.translate(str.maketrans('', '', string.punctuation)) for w in desc_words]
    # Filter out common stop words to prevent matching keywords like 'under' or 'size'
    stop_words = {"under", "size", "in", "for", "a", "the", "with", "at", "of", "and", "or", "to", "looking", "is", "us"}
    desc_words = [w for w in desc_words if w and w not in stop_words]
    
    if not desc_words:
        # If the description was empty or only punctuation, return nothing or all listings.
        # But description should have keywords. If none, score is 0, so drop.
        return []

    scored_listings = []
    for item in listings:
        score = 0
        title_lower = (item.get("title") or "").lower()
        desc_lower = (item.get("description") or "").lower()
        cat_lower = (item.get("category") or "").lower()
        tags_lower = [t.lower() for t in item.get("style_tags") or []]
        brand_lower = (item.get("brand") or "").lower()
        
        for word in desc_words:
            word_matched = False
            if word in title_lower:
                score += 3
                word_matched = True
            if word in desc_lower:
                score += 1
                word_matched = True
            if word in cat_lower:
                score += 1
                word_matched = True
            if word in brand_lower:
                score += 2
                word_matched = True
            if any(word in tag for tag in tags_lower):
                score += 2
                word_matched = True
                
        if score > 0:
            scored_listings.append((score, item))
            
    # 5. Sort by score, highest first, and return the listing dicts.
    scored_listings.sort(key=lambda x: x[0], reverse=True)
    return [item for score, item in scored_listings]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.
    """
    import json
    
    # 1. Check whether wardrobe['items'] is empty.
    items = wardrobe.get("items", [])
    
    client = _get_groq_client()
    
    if not items:
        # 2. If empty: call the LLM with a prompt for general styling ideas
        system_prompt = (
            "You are FitFindr, an expert fashion stylist. The user's wardrobe is empty. "
            "Suggest general styling advice, compatible categories/colors, and vibes/aesthetics "
            "for the item they are considering buying."
        )
        user_content = (
            f"Please suggest general styling advice for this item:\n"
            f"Title: {new_item.get('title')}\n"
            f"Description: {new_item.get('description')}\n"
            f"Category: {new_item.get('category')}\n"
            f"Style tags: {new_item.get('style_tags')}\n"
            f"Colors: {new_item.get('colors')}\n"
            f"Brand: {new_item.get('brand')}\n"
        )
    else:
        # 3. If not empty: format the wardrobe items into a prompt and ask the LLM
        system_prompt = (
            "You are FitFindr, an expert fashion stylist. Suggest 1-2 complete outfits "
            "by pairing the new item with specific items from the user's wardrobe. "
            "Refer to the wardrobe items by their exact names and explain the styling choices and vibe."
        )
        wardrobe_str = json.dumps(items, indent=2)
        user_content = (
            f"New Item to style:\n"
            f"Title: {new_item.get('title')}\n"
            f"Description: {new_item.get('description')}\n"
            f"Category: {new_item.get('category')}\n"
            f"Style tags: {new_item.get('style_tags')}\n"
            f"Colors: {new_item.get('colors')}\n\n"
            f"User's Wardrobe Items:\n{wardrobe_str}\n"
        )
        
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        temperature=0.7
    )
    return response.choices[0].message.content.strip()


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.
    """
    # 1. Guard against an empty or whitespace-only outfit string
    if not outfit or not outfit.strip():
        return "Error: Cannot create fit card. Outfit description is empty or missing."

    client = _get_groq_client()
    
    # 2. Build a prompt
    system_prompt = (
        "You are a trendy, casual fashion influencer on Instagram and TikTok. "
        "Create a short, authentic outfit caption (2-4 sentences) for a styled thrifted find. "
        "Do NOT write product-style descriptions. Keep it conversational."
    )
    
    user_content = (
        f"Item details:\n"
        f"- Title: {new_item.get('title')}\n"
        f"- Price: ${new_item.get('price')}\n"
        f"- Platform: {new_item.get('platform')}\n\n"
        f"Styled outfit description:\n{outfit}\n\n"
        f"Write a 2-4 sentence social media caption. You MUST naturally mention:\n"
        f"1. The item title (exactly once)\n"
        f"2. The price (exactly once, e.g., '$24' or '$24.00')\n"
        f"3. The platform (exactly once, e.g., 'depop')\n"
        f"Make sure to capture the outfit's specific vibe. Do not use generic sales pitch language."
    )
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        temperature=1.0  # Higher temperature for variance
    )
    return response.choices[0].message.content.strip()

