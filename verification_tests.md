# FitFindr — Verification Tests for Failure Modes

This document details the commands and expected behaviors to verify that all agent tools and failure recovery paths function correctly.

## 1. Test `search_listings` returning zero results (No-Results Path)
Run this command to verify it returns an empty list `[]` without raising an exception:
```bash
python3 -c "from tools import search_listings; print(search_listings('designer ballgown', size='XXS', max_price=5))"
```

Then, verify that running the full agent with this query terminates early, leaves the fit card as `None`, and returns a helpful error message to the user:
```bash
python3 -c "from agent import run_agent; from utils.data_loader import get_example_wardrobe; import json; print(json.dumps(run_agent('designer ballgown size XXS under $5', get_example_wardrobe()), indent=2))"
```

### Expected JSON Output:
```json
{
  "query": "designer ballgown size XXS under $5",
  "parsed": {
    "description": "designer ballgown",
    "size": "XXS",
    "max_price": 5.0
  },
  "search_results": [],
  "selected_item": null,
  "wardrobe": { ... },
  "outfit_suggestion": null,
  "fit_card": null,
  "error": "No matching listings found for 'designer ballgown' with filters: size 'XXS', price under $5.00"
}
```

---

## 2. Test `suggest_outfit` with an empty wardrobe
Run this command to verify that the agent does not crash and instead calls the LLM to generate general styling advice:
```bash
python3 -c "
from tools import search_listings, suggest_outfit
from utils.data_loader import get_empty_wardrobe
results = search_listings('vintage graphic tee', size=None, max_price=50)
print(suggest_outfit(results[0], get_empty_wardrobe()))
"
```

### Expected Output:
A text paragraph styling guide (e.g. recommending to pair it with denim, neutral bottoms, or casual sneakers) rather than an empty string or crash.

---

## 3. Test `create_fit_card` with an empty outfit string
Run this command to verify that it returns a descriptive error message instead of crashing:
```bash
python3 -c "
from tools import search_listings, create_fit_card
results = search_listings('vintage graphic tee', size=None, max_price=50)
print(create_fit_card('', results[0]))
"
```

### Expected Output:
`"Error: Cannot create fit card. Outfit description is empty or missing."`
