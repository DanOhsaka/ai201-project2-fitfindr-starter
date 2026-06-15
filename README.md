# FitFindr

FitFindr is a multi-tool AI agent that helps users find secondhand clothing and figure out how to wear it. Given a natural language query, the agent searches mock listings, suggests outfits based on the user's wardrobe, and generates a shareable fit card caption.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```
GROQ_API_KEY=your_key_here
```

Get a free key at [console.groq.com](https://console.groq.com).

## Run

```bash
python app.py
```

Open the localhost URL shown in your terminal (usually http://localhost:7860).

Test the agent from the command line:

```bash
python agent.py
```

Run tool tests:

```bash
pytest tests/ -v
```

---

## Tool Inventory

### 1. `search_listings(description, size, max_price)`

| | |
|---|---|
| **Purpose** | Search the mock listings dataset for items matching keywords, optional size, and price ceiling |
| **Inputs** | `description` (str) — search keywords; `size` (str \| None) — size filter; `max_price` (float \| None) — max price inclusive |
| **Output** | `list[dict]` — matching listings sorted by relevance. Each dict has `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform` |

### 2. `suggest_outfit(new_item, wardrobe)`

| | |
|---|---|
| **Purpose** | Suggest 1–2 complete outfit combinations using the new item and the user's wardrobe |
| **Inputs** | `new_item` (dict) — listing from search; `wardrobe` (dict) — wardrobe with `items` list |
| **Output** | `str` — outfit suggestion with styling tips |

### 3. `create_fit_card(outfit, new_item)`

| | |
|---|---|
| **Purpose** | Generate a casual, shareable social media caption for the outfit |
| **Inputs** | `outfit` (str) — suggestion from `suggest_outfit`; `new_item` (dict) — listing dict |
| **Output** | `str` — 2–4 sentence Instagram/TikTok-style caption |

---

## Planning Loop

The agent in `agent.py` uses conditional logic — it does **not** call all three tools in a fixed sequence regardless of context.

1. **Parse** the user query with regex to extract `description`, `size`, and `max_price`.
2. **Search** via `search_listings()`.
3. **Branch on results:**
   - If empty and a size filter was used → retry without size (fallback).
   - If still empty → set `session["error"]` with actionable advice and **return early**. `suggest_outfit` and `create_fit_card` are never called.
   - If results exist → store top match as `session["selected_item"]`.
4. **Suggest outfit** using `selected_item` + wardrobe → store in `session["outfit_suggestion"]`.
5. **Create fit card** using outfit + selected item → store in `session["fit_card"]`.
6. **Return** the session dict.

The key decision point is step 3: when search returns nothing, the agent stops and tells the user what to try differently instead of proceeding with empty input.

---

## State Management

All state lives in a single `session` dict per interaction:

| Field | Set by | Consumed by |
|-------|--------|-------------|
| `parsed` | Query parser | `search_listings` |
| `search_results` | `search_listings` | Item selection |
| `selected_item` | Top result pick | `suggest_outfit`, `create_fit_card` |
| `outfit_suggestion` | `suggest_outfit` | `create_fit_card` |
| `fit_card` | `create_fit_card` | UI output |
| `error` | Failure branches | UI (checked first) |

The same `selected_item` dict flows from search → outfit → fit card without re-prompting the user.

---

## Error Handling

### search_listings — no results

**Failure:** Query returns zero matches (e.g., "designer ballgown size XXS under $5").

**Agent response:** Sets `session["error"]` to a message like: *"No listings found for 'designer ballgown' (size XXS, under $5). Try broadening your search — remove the size filter, raise your price limit, or use different keywords."* Returns early; outfit and fit card panels stay empty.

**Tested with:**
```bash
python -c "from tools import search_listings; print(search_listings('designer ballgown', size='XXS', max_price=5))"
# Output: []
```

### suggest_outfit — empty wardrobe

**Failure:** `wardrobe['items']` is an empty list (new user).

**Agent response:** Tool returns general styling advice instead of referencing owned pieces. Agent continues normally to `create_fit_card` — no error is set.

**Tested with:**
```bash
python -c "
from tools import search_listings, suggest_outfit
from utils.data_loader import get_empty_wardrobe
results = search_listings('vintage graphic tee', size=None, max_price=50)
print(suggest_outfit(results[0], get_empty_wardrobe()))
"
```

### create_fit_card — empty outfit

**Failure:** `outfit` is empty or whitespace-only.

**Agent response:** Tool returns `"Cannot create a fit card — no outfit suggestion was provided. Run suggest_outfit first."` without raising an exception.

**Tested with:**
```bash
python -c "
from tools import search_listings, create_fit_card
results = search_listings('vintage graphic tee', size=None, max_price=50)
print(create_fit_card('', results[0]))
"
```

---

## AI Usage

### Instance 1 — Tool implementations (Milestone 3)

**Input given:** Tool 1–3 spec blocks from `planning.md` (inputs, return values, failure modes) plus the function stubs in `tools.py`.

**Produced:** Implementations of `search_listings` (keyword scoring + filters), `suggest_outfit` (Groq LLM with wardrobe-aware prompts), and `create_fit_card` (Groq LLM at temperature 0.9).

**Changes made:** Added `_score_listing` helper for weighted keyword matching (title and style_tags weighted higher). Added try/except fallbacks in LLM tools so API failures don't crash the agent.

### Instance 2 — Planning loop (Milestone 4)

**Input given:** Architecture diagram, Planning Loop section, and State Management section from `planning.md`, plus the `run_agent()` TODO steps in `agent.py`.

**Produced:** `run_agent()` with regex query parsing, conditional branching on empty search results, size-loosening retry fallback, and session dict state passing.

**Changes made:** Added `_parse_query()` with multiple regex patterns for price and size extraction. Added size-loosening retry that annotates the fit card when triggered.

---

## Spec Reflection

The planning loop ended up simpler than initially envisioned — regex parsing instead of LLM parsing keeps the agent fast and deterministic for structured fields like price and size. The most important design decision was the early-return branch on empty search results; without it, the agent would call `suggest_outfit` with no item and produce nonsense. Testing each tool in isolation before wiring the loop caught the empty-outfit guard in `create_fit_card` early.

---

## Project Structure

```
├── agent.py              # Planning loop and query parsing
├── app.py                # Gradio UI
├── tools.py              # Three agent tools
├── planning.md           # Design spec and architecture
├── data/
│   ├── listings.json     # 40 mock listings
│   └── wardrobe_schema.json
├── utils/
│   └── data_loader.py
└── tests/
    └── test_tools.py
```
