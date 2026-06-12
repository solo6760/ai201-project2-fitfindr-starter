"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

from tools import search_listings, suggest_outfit, create_fit_card


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def _parse_query_with_llm(query: str) -> dict:
    """Uses the Groq LLM to parse a query into structured search parameters."""
    from tools import _get_groq_client
    import json
    
    try:
        client = _get_groq_client()
        system_prompt = (
            "You are a precise query parser for a fashion search engine. "
            "Extract the following three fields from the user's request: "
            "'description', 'size', and 'max_price'.\n"
            "Return ONLY a raw JSON object with these exact keys, and nothing else. Do not wrap it in markdown. Do not add any text before or after the JSON.\n"
            "Rules:\n"
            "1. 'description': string. A concise description of the item searched (e.g., 'vintage graphic tee'). If not found, use the query.\n"
            "2. 'size': string or null. The size requested (e.g., 'M', 'W30', '8'). If not found, return null.\n"
            "3. 'max_price': float or null. The maximum budget/price ceiling. Extract numeric value (e.g. 30.0 for '$30'). If not found, return null."
        )
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content.strip()
        data = json.loads(content)
        return {
            "description": str(data.get("description", query)),
            "size": data.get("size") if data.get("size") else None,
            "max_price": float(data["max_price"]) if data.get("max_price") is not None else None
        }
    except Exception:
        # Fallback to regex parsing if LLM parsing fails/times out
        import re
        
        max_price = None
        # match "under $30", "under 30", "under 30.00", "$30", etc.
        price_match = re.search(r'under\s*\$?\s*(\d+(?:\.\d+)?)', query, re.IGNORECASE)
        if price_match:
            try:
                max_price = float(price_match.group(1))
            except ValueError:
                pass
        else:
            dollar_match = re.search(r'\$\s*(\d+(?:\.\d+)?)', query)
            if dollar_match:
                try:
                    max_price = float(dollar_match.group(1))
                except ValueError:
                    pass
                    
        size = None
        # match "size M", "size: M", "size 8", etc.
        size_match = re.search(r'\bsize\b\s*(?:is|of|:)?\s*([a-zA-Z0-9/]+)', query, re.IGNORECASE)
        if size_match:
            size = size_match.group(1)
        else:
            # check standalone standard size tokens
            for sz in ['XXS', 'XXL', 'XS', 'S', 'M', 'L', 'XL']:
                if re.search(r'\b' + sz + r'\b', query, re.IGNORECASE):
                    size = sz
                    break
                    
        # Clean up query for description
        desc = query
        desc = re.sub(r'under\s*\$?\s*\d+(?:\.\d+)?', '', desc, flags=re.IGNORECASE)
        desc = re.sub(r'\$\s*\d+(?:\.\d+)?', '', desc, flags=re.IGNORECASE)
        desc = re.sub(r'\bsize\b\s*(?:is|of|:)?\s*[a-zA-Z0-9/]+', '', desc, flags=re.IGNORECASE)
        for sz in ['XXS', 'XXL', 'XS', 'S', 'M', 'L', 'XL']:
            desc = re.sub(r'\b' + sz + r'\b', '', desc, flags=re.IGNORECASE)
            
        desc = re.sub(r'\b(looking for|search for|find|i want|want)\b', '', desc, flags=re.IGNORECASE)
        desc = re.sub(r'\s+', ' ', desc).strip()
        
        return {
            "description": desc if desc else query,
            "size": size,
            "max_price": max_price
        }


def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.
    """
    # Step 1: Initialize the session
    session = _new_session(query, wardrobe)
    
    # Step 2: Parse the user's query
    parsed = _parse_query_with_llm(query)
    session["parsed"] = parsed
    
    # Step 3: Call search_listings
    results = search_listings(
        description=parsed["description"],
        size=parsed["size"],
        max_price=parsed["max_price"]
    )
    session["search_results"] = results
    
    # Check if results is empty
    if not results:
        err_msg = f"No matching listings found for '{parsed['description']}'"
        filters = []
        if parsed["size"]:
            filters.append(f"size '{parsed['size']}'")
        if parsed["max_price"]:
            filters.append(f"price under ${parsed['max_price']:.2f}")
        if filters:
            err_msg += f" with filters: {', '.join(filters)}"
        session["error"] = err_msg
        return session
        
    # Step 4: Select the item to use (top result)
    selected_item = results[0]
    session["selected_item"] = selected_item
    
    # Step 5: Call suggest_outfit
    try:
        outfit = suggest_outfit(selected_item, wardrobe)
        session["outfit_suggestion"] = outfit
    except Exception as e:
        session["error"] = f"Error generating outfit recommendation: {str(e)}"
        return session
        
    # Step 6: Call create_fit_card
    try:
        fit_card = create_fit_card(outfit, selected_item)
        session["fit_card"] = fit_card
    except Exception as e:
        session["error"] = f"Error generating fit card: {str(e)}"
        return session
        
    # Step 7: Return the session
    return session



# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

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
