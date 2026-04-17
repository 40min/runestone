# WordKeeper Vocabulary Save Standardization

## Context

WordKeeper should save clean, canonical vocabulary rows that are useful for future
recall, search, and manual editing. The saved `word_phrase` should be the Swedish
learning item, not a noisy slice of the surrounding sentence.

`extra_info` already exists on Vocabulary rows. For this standardization pass,
WordKeeper may generate all candidate fields for every save candidate, even when a
later persistence step decides that an existing row only needs prioritization.

Related tasks: `E9Ab5IJvRjbI`, `jupHbDxQJeeu`.

## Problem

WordKeeper can currently save unstandardized vocabulary items exactly as they appear
in chat. That can produce rows with leading articles, accidental capitalization,
context-only inflections, surrounding punctuation, or near-duplicate variants of the
same learning item. Examples include `en hund` instead of `hund`, `HUND` instead of
`hund`, or punctuation/casing variants that make search, recall, and duplicate handling
less predictable.

## SaveCandidate Field Rules

- `word_phrase`: canonical Swedish learning item.
- `translation`: concise target-language translation, not a grammar explanation.
- `example_phrase`: natural Swedish sentence, preferably from the current chat or
  teacher response.
- `extra_info`: concise grammar or usage note when useful.
- `reason`: short internal reason for why the word should be saved or prioritized.

## Normalization Rules

1. No leading articles: save `hund`, not `en hund`; save `äpple`, not `ett äpple`.
2. Allow definite or bestämd forms when the form itself is the learning target.
3. Use smart lowercase: lowercase ordinary words, but preserve acronyms, personal
   names, proper nouns, and fixed casing.
4. Prefer lemma or base form unless the inflected form matters.
5. Do not save bare `att` for verbs; keep `att` inside real constructions such as
   `ha svårt att`, `komma att`, or `se till att`.
6. Preserve particles, prepositions, and reflexives that change meaning, such as
   `tycka om`, `hälsa på`, `höra av sig`, and `se fram emot`.
7. Preserve fixed phrases exactly, minus surrounding punctuation and extra whitespace.
8. Keep Swedish characters; never ASCII-fold `å`, `ä`, or `ö`.
9. Use canonical duplicate handling so casing, articles, and punctuation do not create
   near-duplicates.
10. Do not save grammar-only tokens as vocabulary unless explicitly presented as
    learning items.
11. Ensure examples naturally demonstrate the saved item or full phrase.
12. Keep translations concise; put morphology and usage in `extra_info`, not
    `translation`.

## Extra Info Guidance

`extra_info` is a compact learner note, not a second translation and not a full
grammar lesson. Use it for high-value morphology or usage details, for example:

- `en-word noun; plural: hundar; definite: hunden`
- `verb; infinitive: förstå; present: förstår; past: förstod; supine: förstått`
- `adjective; common: vacker; neuter: vackert; plural/definite: vackra`
- `particle verb; "tycka om" means "to like"`
- `fixed phrase; common in spoken Swedish`

If a saved item is canonicalized from a context form, mention the relation when useful,
for example `en-word noun; context form "hunden" is definite singular`.

If WordKeeper is unsure, it should leave `extra_info` empty rather than guess.

## Follow-Up Refactoring Note

The current standardization allows WordKeeper to generate complete candidate payloads
before knowing whether the word already exists. A follow-up refactor should split
prioritization from addition:

1. Normalize candidate word keys and prioritize existing vocabulary rows.
2. Only for genuinely new words, ask the LLM to generate full add payload fields:
   `translation`, `example_phrase`, and optional `extra_info`.

Existing prioritized rows should not get blank `translation`, `example_phrase`, or
`extra_info` fields auto-filled by that follow-up prioritization flow. Those fields
should remain manual and user-owned unless a future explicit enrichment flow is built.

Tracked follow-up task: `lcG7KhIjLo0W`.
