# Custom speaking words

The authenticated `POST /speaking/check-word` endpoint accepts `{ "word": "invoice" }`.
It returns `valid`, a normalized `word`, an optional English `definition`, and verified
`suggestions`. Each entry is one English word, including hyphenated words and apostrophes.

Dictionary lookup uses [Free Dictionary API](https://dictionaryapi.dev/).
Spelling suggestions use [Datamuse](https://www.datamuse.com/api/), then undergo the same
dictionary lookup before display. A missing entry means unconfirmed, not proof that a
rare or specialist word does not exist. An unavailable dictionary returns HTTP 503,
never a spelling verdict. No AI-generated definitions are used as validation evidence.

Valid entries are cached in each worker for 24 hours, bounded to 1,000 entries.
Exercise creation revalidates custom words on the server using that cache or a fresh
lookup. Practice does not automatically mark custom words as learned.

Datamuse documents an API-key requirement starting February 1, 2027. Revisit suggestion
authentication before that date. Suggestion failures do not bypass word validation.

The same feature area also exposes `GET /speaking/words`,
`POST /speaking/exercises`, `GET /speaking/exercises/{exercise_id}` and
`POST /speaking/exercises/{exercise_id}/items/{index}/score`. Scoring sends raw audio
(max 5 MB) to Speechace or Chivox according to `PRONUNCIATION_PROVIDER`; a provider
failure returns HTTP 503. See [api-spec.md](api-spec.md) for request/response shapes.

Checks: `python -m unittest tests.test_word_validation tests.test_speaking tests.test_chivox`.
