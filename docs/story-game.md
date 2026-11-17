# AI Story game

Open `/games/story` from the Game navigation item. The existing authenticated user
layout protects the page. Pick 1–7 learned vocabulary entries, a topic and a tone.
Stories contain highlighted words, Vietnamese translations and three comprehension
questions. The latest 20 stories are available from history.

Generation uses Mistral with `MISTRAL_API_KEY` from the backend environment and
`MISTRAL_MODEL` (default: `mistral-small-latest`). It calls the official
[chat completion API](https://docs.mistral.ai/api/endpoint/chat) with JSON output.
An unavailable provider returns a retry message;
it is never represented as successful generation. The separately labelled sample
story is curated and works without an AI key. No credits, payments or XP changes
are implemented.

API (all authenticated):

- `GET /games/story/words`: current user's learned vocabulary.
- `POST /games/story/stories`: `{topic, tone, vocabulary_ids}`; creates a story.
- `POST /games/story/demo`: saves a curated sample for the current user.
- `GET /games/story/stories`: latest 20 summaries for the current user.
- `GET /games/story/stories/{id}`: owned story, without quiz answers before submission.
- `POST /games/story/stories/{id}/answers`: `{answers: [0, 1, 2]}` with 0-based choices;
  grades and stores the first result. Repeated submissions return that result.

Storage: `story_games`, indexed by `(user_id, created_at)`. Creation is limited to
five requests per minute per account. All requested vocabulary IDs are verified
against that account's learned words. Generated content is schema-validated and
must include every requested word. Text renders as React text, never HTML.

Validation: `python -m unittest tests.test_story` from `backend` and
`npm run build` from `frontend`. Browser fixtures use mocked API responses, not
production accounts or shared learning records.

Design reference: user-supplied screenshot of Pencil Test's AI Story. This is an
independent implementation in the existing SmartVocab application.
