# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches the mock listings dataset (`data/listings.json`) for items matching a keyword description, optional size filter, and optional price ceiling. Scores each candidate by keyword overlap across title, description, style_tags, and category, then returns matches sorted by relevance (highest score first).

**Input parameters:**
- `description` (str): Keywords describing what the user is looking for (e.g., "vintage graphic tee"). Split into lowercase tokens for matching.
- `size` (str | None): Size string to filter by, or None to skip size filtering. Matching is case-insensitive substring match (e.g., "M" matches "S/M" or "M").
- `max_price` (float | None): Maximum price inclusive, or None to skip price filtering.

**What it returns:**
A `list[dict]` of matching listing dicts, sorted by relevance score (best first). Each dict contains: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`. Returns an empty list `[]` if no listings match — never raises an exception.

**What happens if it fails or returns nothing:**
The agent sets `session["error"]` to a helpful message explaining no matches were found, suggests loosening constraints (try a larger size, raise the price limit, or broaden keywords), and returns the session early without calling `suggest_outfit` or `create_fit_card`. The agent may also retry once with the size filter removed and inform the user.

---

### Tool 2: suggest_outfit

**What it does:**
Given a specific thrifted listing and the user's wardrobe, calls Groq's `llama-3.3-70b-versatile` LLM to suggest 1–2 complete outfit combinations. If the wardrobe has items, the LLM references specific pieces by name. If the wardrobe is empty, it offers general styling advice for the new item.

**Input parameters:**
- `new_item` (dict): A listing dict from `search_listings` — must include at least `title`, `category`, `style_tags`, `colors`, and `price`.
- `wardrobe` (dict): A wardrobe dict with an `items` key containing a list of wardrobe item dicts. Each item has `id`, `name`, `category`, `colors`, `style_tags`, and optional `notes`. May be empty.

**What it returns:**
A non-empty `str` containing 1–2 outfit suggestions with specific styling tips (how to tuck, layer, roll sleeves, etc.). Always returns a string — never raises an exception.

**What happens if it fails or returns nothing:**
If `wardrobe['items']` is empty, the tool still returns general styling advice (what categories pair well, what vibe suits the item) rather than crashing. If the LLM call fails, return a fallback string with basic pairing suggestions based on the item's category and style_tags.

---

### Tool 3: create_fit_card

**What it does:**
Takes the outfit suggestion string and the thrifted item details, then calls Groq's `llama-3.3-70b-versatile` LLM (temperature 0.9) to generate a short, casual, shareable caption — the kind someone would post on Instagram or TikTok.

**Input parameters:**
- `outfit` (str): The outfit suggestion string returned by `suggest_outfit`.
- `new_item` (dict): The listing dict for the thrifted item, used for title, price, and platform in the caption.

**What it returns:**
A `str` of 2–4 sentences usable as a social media caption. Mentions the item name, price, and platform naturally. Uses casual, authentic tone. Outputs vary across runs due to higher temperature.

**What happens if it fails or returns nothing:**
If `outfit` is empty or whitespace-only, return the error string `"Cannot create a fit card — no outfit suggestion was provided. Run suggest_outfit first."` without raising an exception. If the LLM call fails, return a simple template-based caption using the item details.

---

### Additional Tools (if any)

None — stretch features not implemented in this version.

---

## Planning Loop

**How does your agent decide which tool to call next?**

The planning loop in `run_agent()` follows conditional logic based on tool return values:

1. **Initialize** session with `_new_session(query, wardrobe)`.
2. **Parse query** using regex to extract `description`, `size`, and `max_price`. Store in `session["parsed"]`.
3. **Call `search_listings`** with parsed parameters. Store results in `session["search_results"]`.
4. **Branch on search results:**
   - If `search_results` is empty AND a size filter was used: retry `search_listings` with `size=None`, store retry results, and note in session that size was loosened.
   - If still empty: set `session["error"]` to a specific message with suggestions, **return early** — do NOT call further tools.
   - If results exist: set `session["selected_item"] = search_results[0]` (top match).
5. **Call `suggest_outfit`** with `selected_item` and `wardrobe`. Store in `session["outfit_suggestion"]`.
6. **Call `create_fit_card`** with `outfit_suggestion` and `selected_item`. Store in `session["fit_card"]`.
7. **Return** the completed session.

The loop does NOT call all three tools unconditionally — step 4's empty-results branch terminates early before `suggest_outfit` or `create_fit_card` run.

---

## State Management

**How does information from one tool get passed to the next?**

All state lives in a single `session` dict created by `_new_session()`. Key fields and their flow:

| Field | Set by | Used by |
|-------|--------|---------|
| `parsed` | Query parser (step 2) | `search_listings` input |
| `search_results` | `search_listings` (step 3) | Item selection (step 4) |
| `selected_item` | Top result selection (step 4) | `suggest_outfit` and `create_fit_card` |
| `wardrobe` | Passed in at init | `suggest_outfit` |
| `outfit_suggestion` | `suggest_outfit` (step 5) | `create_fit_card` |
| `fit_card` | `create_fit_card` (step 6) | Final output to user |
| `error` | Any failure branch | Checked first by UI before displaying results |

The same `selected_item` dict object flows from search → outfit → fit card without the user re-entering anything.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Sets `session["error"]` to: "No listings found for '{description}' (size: {size}, max price: ${max_price}). Try broadening your search — remove the size filter, raise your price limit, or use different keywords like 'graphic tee' instead of 'band shirt'." Returns session early; outfit and fit card panels stay empty. |
| suggest_outfit | Wardrobe is empty | Tool returns general styling advice (e.g., "Pair this graphic tee with wide-leg jeans and chunky sneakers for a 90s grunge look"). Agent continues to `create_fit_card` normally — no error set. |
| create_fit_card | Outfit input is missing or incomplete | Tool returns: "Cannot create a fit card — no outfit suggestion was provided. Run suggest_outfit first." Agent stores this string in `session["fit_card"]` so the user sees the message in the fit card panel. |

---

## Architecture

```mermaid
flowchart TD
    U[User Query] --> PL[Planning Loop]
    PL --> PARSE[Parse Query → session.parsed]
    PARSE --> SL[search_listings]
    SL -->|results=[]| ERR1{Size filter used?}
    ERR1 -->|yes| RETRY[Retry without size]
    RETRY -->|still empty| ERR_MSG[session.error = helpful message]
    ERR_MSG --> RETURN1[Return session early]
    ERR1 -->|no| ERR_MSG
    SL -->|results=[item,...]| SEL[session.selected_item = results0]
    SEL --> SO[suggest_outfit]
    SO --> SESSION1[session.outfit_suggestion]
    SESSION1 --> FC[create_fit_card]
    FC --> SESSION2[session.fit_card]
    SESSION2 --> RETURN2[Return completed session]
```

ASCII equivalent:

```
User query
    │
    ▼
Planning Loop ───────────────────────────────────────────┐
    │                                                    │
    ├─► Parse query → session["parsed"]                  │
    │       │                                            │
    ├─► search_listings(description, size, max_price)    │
    │       │ results=[]                                 │
    │       ├──► Retry without size (if size was set)    │
    │       │       │ still=[]                           │
    │       │       └──► [ERROR] → return early ─────────┤
    │       │                                            │
    │       │ results=[item, ...]                        │
    │       ▼                                            │
    │   Session: selected_item = results[0]              │
    │       │                                            │
    ├─► suggest_outfit(selected_item, wardrobe)          │
    │       │                                            │
    │   Session: outfit_suggestion = "..."               │
    │       │                                            │
    └─► create_fit_card(outfit_suggestion, selected_item)│
            │                                            │
        Session: fit_card = "..."                        │
            │                                            └─ error path returns here
            ▼
        Return session
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

For each tool, I'll give Cursor the corresponding Tool spec block from this planning.md (inputs, return value, failure mode) plus the function stub from `tools.py`, and ask it to implement one function at a time using `load_listings()` or `_get_groq_client()`.

- **search_listings:** Verify the code filters by all three parameters, scores by keyword overlap, sorts by score, and returns `[]` on no match. Test with 3 queries: happy path, price filter, impossible query.
- **suggest_outfit:** Verify it handles empty wardrobe without crashing and calls Groq with `llama-3.3-70b-versatile`. Test with `get_example_wardrobe()` and `get_empty_wardrobe()`.
- **create_fit_card:** Verify empty-outfit guard returns error string, temperature is ≥ 0.8, and outputs differ on repeated calls.

**Milestone 4 — Planning loop and state management:**

I'll give Cursor the Architecture diagram, Planning Loop section, and State Management section from this planning.md plus the `run_agent()` TODO steps in `agent.py`. I'll verify the generated code branches on empty search results, stores values in session dict fields, and does not call all three tools unconditionally. Test with `python agent.py` for both happy path and no-results path.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
Agent parses the query: `description="vintage graphic tee"`, `size=None`, `max_price=30.0`. Stores in `session["parsed"]`. Calls `search_listings("vintage graphic tee", size=None, max_price=30.0)`. Returns 2–3 matches; top result is `lst_006` — "Graphic Tee — 2003 Tour Bootleg Style" at $24 on Depop. Stored in `session["search_results"]` and `session["selected_item"]`.

**Step 2:**
Agent calls `suggest_outfit(selected_item=lst_006, wardrobe=example_wardrobe)`. LLM references "Baggy straight-leg jeans, dark wash" and "Chunky white sneakers" from the wardrobe. Returns: "Pair this faded bootleg tee with your baggy straight-leg jeans and chunky white sneakers for a classic 90s grunge look. Roll the sleeves once and do a front tuck for shape." Stored in `session["outfit_suggestion"]`.

**Step 3:**
Agent calls `create_fit_card(outfit=<step 2 string>, new_item=lst_006)`. LLM generates a casual caption. Stored in `session["fit_card"]`.

**Final output to user:**
- **Top listing panel:** "Graphic Tee — 2003 Tour Bootleg Style — $24.00 on depop (Good condition, size L)"
- **Outfit idea panel:** The styling suggestion referencing wardrobe pieces
- **Fit card panel:** Something like "thrifted this bootleg tee off depop for $24 and it was literally made for my baggy jeans era 🖤 full fit on my stories"

---

## FitFindr Overview (Milestone 1)

FitFindr is a multi-tool AI agent that helps users find secondhand clothing and figure out how to wear it. When a user describes what they want, the agent searches mock listings, picks the best match, suggests outfits using the user's wardrobe (or general advice if the wardrobe is empty), and generates a shareable fit card caption. If search returns no results, the agent tells the user what to try differently and stops — it never calls outfit or fit card tools with empty input.
