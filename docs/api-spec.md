# API Specification — SmartVOCAB AI

Base URL: `http://localhost:8000` (dev) hoặc `http://localhost:8080/api` (qua nginx Docker).
Public (không cần token): `/health`, `/auth/register`, `/auth/login` và 3 endpoint
`/auth/password-reset/request|verify|confirm`. Mọi endpoint khác yêu cầu header:

```
Authorization: Bearer <access_token>
```

Mã lỗi chung xem ở cuối tài liệu. Swagger thật: `GET /docs`.

---

## Health

### `GET /health`

```json
{
  "status": "ok",
  "app": "SmartVOCAB AI",
  "database": "capstone1",
  "mongo": "mongodb+srv://user:***@cluster.mongodb.net | db=capstone1"
}
```

---

## Auth — `/auth`

### `POST /auth/register`

Body:

```json
{ "email": "user@example.com", "username": "nguyenvana", "password": "secret123" }
```

- `201 Created` → `Token` (xem dưới). Email chuẩn hóa lowercase; `_id` = email.
- `409 Conflict` → `"Email already registered"`

### `POST /auth/login`

Body: `{ "email": "...", "password": "..." }`

- `200 OK` → `Token`
- `401` → `"Incorrect email or password"`
- `403` → tài khoản bị khóa

`Token`:

```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "user": { "id": "user@example.com", "email": "user@example.com", "username": "nguyenvana", "role": "user", "xp": 0, "streak": 0, "onboarded": false, "learning_level": null, "placement_levels": {}, "interests": [], "daily_goal": 10, "daily_new_limit": 10, "daily_review_limit": 30, "avatar_url": null }
}
```

### `GET /auth/me`

Trả `UserOut` của user hiện tại. `401` nếu token sai/hết hạn/bị thu hồi.

### `PUT /auth/me`

Body (tất cả optional): `username`, `learning_level` (`A1..C2`), `interests` (mảng không rỗng),
`daily_goal` (5–100), `daily_new_limit` (1–100), `daily_review_limit` (1–200), `onboarded`.
Trả `UserOut` đã cập nhật.

### `POST /auth/onboarding`

Body:

```json
{ "learning_level": "B1", "interests": ["technology", "business"] }
```

Đặt `onboarded = true`, `profile_completed_at`. Trả `UserOut`.

### `PUT /auth/password`

Body: `{ "current_password": "...", "new_password": "..." }`

- `200` → `{ "message": "...", "access_token": "...", "token_type": "bearer" }`
  (token cũ bị thu hồi do `token_version` tăng, token mới của phiên hiện tại vẫn dùng được)
- `400` → sai mật khẩu hiện tại / mật khẩu mới trùng cũ

### `POST /auth/me/avatar`

Body: multipart/form-data với field `avatar` (ảnh, tối đa `AVATAR_MAX_BYTES`, mặc định 2 MB).
Trả `UserOut` với `avatar_url` mới; ảnh cũ bị xóa. Lưu tại `/uploads/...`.

### `POST /auth/password-reset/request` (public)

Body: `{ "email": "user@example.com" }`. Trả thông báo trung tính dù email không tồn tại
(tránh lộ tài khoản). Gửi OTP 6 chữ số qua SMTP nếu email hợp lệ và đang active.

### `POST /auth/password-reset/verify` (public)

Body: `{ "email": "...", "otp": "123456" }` · `200` → `{ "verified": true }`.
`400` nếu OTP sai/hết hạn/quá số lần thử.

### `POST /auth/password-reset/confirm` (public)

Body: `{ "email": "...", "otp": "123456", "new_password": "..." }`.
`200` → thông báo đăng nhập lại; mật khẩu được đổi và `token_version` tăng.

---

## Domains — `/domains`

### `GET /domains`

Trả danh sách lĩnh vực đang active: `slug`, `name`, `name_vi`, `description`,
`order`, `active`, `vocabulary_count`, `lesson_count`, `lessons`.

---

## Vocabulary — `/vocabulary` (chỉ 2 GET có alias `/vocabularies`: list và detail)

### `GET /vocabulary`

Query: `topic?`, `domain?` (`general|technology|business`), `level?` (`A1..C2`),
`search?` (≤100), `page=1`, `page_size=20` (1–100).

```json
{ "total": 42, "page": 1, "page_size": 20, "items": [ { "...VocabularyOut" } ] }
```

### `GET /vocabulary/{id}`

`200` → `VocabularyOut` · `404` nếu không có.

### `POST /vocabulary` (admin)

Body:

```json
{
  "word": "ephemeral",
  "phonetic": "ɪˈfem(ə)rəl",
  "part_of_speech": "adjective",
  "meaning": "tạm thời, ngắn ngủi",
  "example": "Fame is often ephemeral.",
  "synonyms": ["fleeting", "transient"],
  "antonyms": ["permanent"],
  "topic": "general",
  "domain": "general",
  "level": "B2"
}
```

`201` → `VocabularyOut`.

### `PUT /vocabulary/{id}` (admin)

Body: bất kỳ trường nào cần cập nhật · `200` → `VocabularyOut`.

### `DELETE /vocabulary/{id}` (admin)

`204 No Content`.

### `POST /vocabulary/ai-generate`

Body: `{ "word": "ubiquitous", "target_language": "vi" }`

`200` → object từ vựng đã điền (phonetic, part_of_speech, meaning, example, synonyms, antonyms, topic, level).

- `502` → lỗi AI / thiếu `GEMINI_API_KEY` / hết quota

### `POST /vocabulary/ai-generate-batch` (admin)

Body:

```json
{ "words": ["ubiquitous"], "topic": "technology", "level": "B1", "count": 10, "save": true, "target_language": "vi" }
```

`200` → `{ "requested", "succeeded", "failed", "saved", "items": [ { "word", "ok", "saved", "data"?, "error"? } ] }`.

---

## Lessons — `/lessons`

### `GET /lessons`

Danh sách bài học theo lĩnh vực/cấp độ kèm tiến độ (`learned_count`, `progress_percent`, `completed`).

Mỗi bài được chia thành các unit ổn định, tối đa 15 từ. Response bổ sung:

- `total_words`: tổng số từ của cả bài.
- `unit_count`: số unit.
- `next_unit`: unit đầu tiên chưa hoàn thành (fallback `1`).
- `next_unit_word_count`: số từ của unit tiếp theo.
- `unlocked`: `false` khi cấp độ trước trong cùng lĩnh vực chưa hoàn thành.
- `unlock_requirement`: `{ lesson_id, level }` của cấp độ cần hoàn thành trước, hoặc `null`.
- `units[]`: `{ index, unit, word_count, learned, mastered, progress_percent, completed, unlocked }`.

### `GET /lessons/{lesson_id}`

Chi tiết một unit + danh sách từ · `404` nếu không có.

Query: `unit` (1-based, optional). Bỏ qua `unit` để tự chọn unit đầu tiên chưa hoàn thành.
`400` nếu `unit` ngoài khoảng `1..unit_count` hoặc cấp độ trước chưa hoàn thành.

Response bổ sung `unit`, `unit_count`, `total_words`, `lesson_completed`; `completed` phản ánh
trạng thái của unit hiện tại.

### `GET /lessons/{lesson_id}/quiz`

Query: `count=10` (3–50), `unit` (1-based, optional; cùng quy tắc với chi tiết bài học).
Trả câu hỏi (không kèm đáp án). `404` nếu không đủ từ.

### `POST /lessons/{lesson_id}/quiz/submit`

Body:

```json
{ "lesson_id": "general-a1", "results": [ { "vocabulary_id": "...", "question_token": "...", "user_answer": "...", "response_time_ms": 3200, "hint_used": false } ] }
```

Query: `unit` (1-based, optional). Khi đạt ≥70%, unit tương ứng được đánh dấu hoàn thành;
bỏ qua `unit` sẽ dùng unit mặc định (unit đầu tiên chưa hoàn thành).

`200` →

```json
{ "correct": 8, "total": 10, "percent": 80, "xp_gained": 84, "passed": true, "new_level": 3, "new_xp": 240, "streak": 4 }
```

- `400` → câu hỏi không hợp lệ/hết hạn/không khớp.
- Response thực tế cũng có `results[]` (chi tiết từng câu) và `wrong_count`.

### `POST /lessons/quiz/analyze-all-mistakes`

Body: `{ "mistakes": [ { "vocabulary_id": "...", "question": "...", "correct_answer": "...", "user_answer": "..." } ] }` (1–20 mục).
`200` → `{ "analyses": [ { "error_type", "what_went_wrong", "explanation", "correct_answer", "example", "tip" } | null ] }`.
Chỉ phân tích lỗi bằng AI, **không** tham gia chấm điểm; lỗi AI trả `null` ở vị trí tương ứng.
Giới hạn 10 request/phút/người.

---

## Learning — `/learning`

### `GET /learning/due`

Danh sách thẻ đến hạn ôn FSRS (kèm thông tin từ vựng).

### `POST /learning/review`

Body:

```json
{ "vocabulary_id": "657abc...", "rating": 3, "review_id": "uuid-tu-chon" }
```

- `rating`: 1 Again · 2 Hard · 3 Good · 4 Easy. Hỗ trợ legacy `remembered` (true→3, false→1).
- `200` → trạng thái FSRS đã cập nhật + `retrievability`.
- `422` nếu thiếu cả `rating` và `remembered`; `400` nếu dữ liệu sai.
- Idempotent theo `review_id`.

### `GET /learning/stats`

```json
{ "total_words": 50, "mastered": 12, "learning": 38, "due_today": 7 }
```

### `GET /learning/daily?tz_offset=420`

Kế hoạch học trong ngày, tổng hợp từ FSRS + lịch sử trả lời (chỉ đọc). `tz_offset` là số phút lệch so với UTC (JS: `-new Date().getTimezoneOffset()`, mặc định `0`, hợp lệ `-720..840`).

```json
{
  "date": "2026-11-12",
  "goal": 10,
  "new_limit": 10,
  "review_limit": 30,
  "studied_today": 3,
  "remaining": 7,
  "goal_met": false,
  "due_count": 2,
  "new_count": 7,
  "new_available": 7,
  "streak": 4,
  "studied_today_flag": true,
  "answered_today": 5,
  "correct_today": 4,
  "xp_today": 48,
  "tasks": [
    { "id": "review", "title": "Ôn 2 từ đến hạn", "count": 2, "href": "/flashcards", "done": false },
    { "id": "new", "title": "Học 7 từ mới", "count": 7, "href": "/lessons/general-a1", "done": false },
    { "id": "goal", "title": "Mục tiêu: 10 từ", "count": 3, "href": "/progress", "done": false }
  ],
  "next_lesson": { "id": "general-a1", "slug": "general-a1", "title": "General English - A1", "domain": "general", "level": "A1", "href": "/lessons/general-a1" },
  "due_preview": [{ "vocabulary_id": "...", "word": "apple", "meaning": "...", "level": "A1", "domain": "general" }],
  "new_preview": [{ "vocabulary_id": "...", "word": "book", "meaning": "...", "phonetic": "", "level": "A1", "domain": "general" }],
  "week": [{ "date": "2026-11-06", "answered": 0, "correct": 0, "xp": 0, "studied": 0, "studied_flag": false }]
}
```

- `studied_today` đếm số từ **khác nhau** có `answer_attempts` hoặc `fsrs_review_logs` trong ngày địa phương.
- `new_limit` / `review_limit` lấy từ hồ sơ người học (mặc định `10` / `30`).
- `due_preview` tối đa 5 thẻ, không vượt quá `review_limit`.
- `week` luôn có 7 phần tử, cũ nhất → hôm nay.
- `new_count = min(goal - studied_today, số từ mới phù hợp)`; từ mới ưu tiên lĩnh vực quan tâm và CEFR của người học.
- `422` nếu `tz_offset` ngoài khoảng.

### `GET /learning/dashboard?tz_offset=420`

Gộp 4 luồng thành một request cho trang tổng quan:
`{ "progress": UserProgressOut, "stats": {...}, "lessons": [...], "daily": {...} }`.
Mỗi trường có cấu trúc như endpoint tương ứng (`/progress`, `/learning/stats`,
`/lessons`, `/learning/daily`).

### `POST /learning/sessions`

Body:

```json
{ "lesson_id": "general-a1", "skills": ["meaning", "spelling", "context"], "count": 10 }
```

`201` → `SessionOut`. `400` nếu dữ liệu không hợp lệ.

### `GET /learning/sessions/{session_id}`

`200` → `SessionOut` · `404` nếu không có/không thuộc user.

### `GET /learning/sessions/{session_id}/exercises`

Câu hỏi của phiên (`ExerciseItemOut[]`, không kèm đáp án).

### `POST /learning/sessions/{session_id}/answers`

Body:

```json
{ "exercise_item_id": "657abc...:meaning", "answer": "tạm thời", "attempt_id": "uuid", "response_time_ms": 3200, "hint_used": false }
```

`200` → `AnswerResult` (`is_correct`, `correct_answer`, `mastery`, `xp_gained`, ...).
`attempt_id` idempotent → retry không cộng điểm hai lần. (`correct`/`correct_answer`
do client gửi sẽ bị bỏ qua.)

### `POST /learning/sessions/{session_id}/finish`

`200` →

```json
{ "session_id": "...", "status": "finished", "total": 10, "answered": 10, "correct": 8, "percent": 80, "passed": true, "xp_gained": 50, "lesson_completed": true, "finished_at": "..." }
```

---

## Progress — `/progress`

### `GET /progress`

`UserProgressOut`: `{ "xp", "level", "streak", "last_study_date", "words_learned", "words_mastered", "lessons_completed" }`.

### `GET /progress/summary`

Tổng hợp tiến độ theo lĩnh vực/kỹ năng.

### `GET /progress/mastery`

Phân rã Mastery (`meaning`, `spelling`, `context`) theo từ/kỹ năng.

### `GET /progress/history`

Query: `limit=50` (1–200). Lịch sử trả lời gần đây.

### `GET /progress/assessment-status`

Trạng thái đánh giá của user hiện tại cho Level-Up Hub:

```json
{ "domains": [ { "id": "general", "name": "General English", "name_vi": "...",
  "levels": [ { "level": "A1", "completed": true, "assessment_passed": false,
                "status": "ready", "total_words": 42 } ] } ] }
```

`status`: `locked` (chưa xong bài) · `ready` (xong bài, chưa đạt assessment) · `passed`.

### `POST /progress/study-answer`

Body:

```json
{ "vocabulary_id": "657abc...", "answer": "...", "skill": "meaning", "attempt_id": "uuid", "response_time_ms": 3200, "hint_used": false }
```

`200` → `AnswerResult`. `400` nếu dữ liệu/kiểu kỹ năng không hợp lệ.

---

## Level Assessment — `/assessments`

Mọi endpoint yêu cầu user đã đăng nhập. Đạt ≥ `ASSESSMENT_PASS_PERCENT` (mặc định 70)
sẽ lưu kết quả và mở cấp độ tiếp theo; nộp lại cùng `attempt_id` trả lại result cũ.

### `POST /assessments`

Body: `{ "domain": "general", "level": "B1", "skip_learning": false, "placement_target": null }`.
`201` → `AssessmentOut`: `{ "attempt_id", "domain", "level", "question_count",
"expires_at", "questions": [ExerciseItemOut] }` (câu hỏi **không** kèm đáp án).
`400` nếu đã đạt, chưa xong các unit trước, đang cooldown hoặc không đủ câu hỏi.

### `GET /assessments/attempts/{attempt_id}`

`200` → attempt còn active/chưa hết hạn (kèm câu hỏi) · `404` nếu không có/hết hạn.

### `GET /assessments/{domain}/{level}`

Trạng thái của user cho một cấp độ:
`{ "units_completed", "units_total", "completed", "passed", "assessment_required", "retry_at" }`.

### `POST /assessments/attempts/{attempt_id}/submit`

Body: `{ "answers": [ { "exercise_item_id": "...", "answer": "..." } ] }` (phải khớp đúng
danh sách câu đã phát). `200` →
`{ "attempt_id", "domain", "level", "correct", "total", "percent", "passed",
"next_level", "opened_level", "placement_target", "results": [...], "submitted_at" }`.
`400` nếu sai số lượng/sai câu/hết hạn.

---

## Speaking — `/speaking`

### `POST /speaking/check-word`

Body `{ "word": "invoice" }` · `200` →
`{ "word": "invoice", "valid": true, "definition": "...", "suggestions": [...] }`.
Từ hợp lệ được cache 24 giờ/tối đa 1000 từ; gợi ý lấy từ Datamuse rồi đối chiếu lại từ điển.
`400` nếu đầu vào không phải một từ tiếng Anh; `503` nếu dictionary API không phản hồi.
Giới hạn 60 request/phút/người.

### `GET /speaking/words`

Danh sách từ đã học của user: `[{ "id", "word", "meaning" }]`.

### `POST /speaking/exercises`

Body: `{ "vocabulary_ids": ["..."], "custom_words": ["invoice"], "auto_select": false }`
(chọn một cách; tối đa 20 mỗi bài). Từ tùy chỉnh được kiểm tra lại server-side.
`200` → `{ "id", "items": [{ "text", "source" }], "results": {} }`.
`400` nếu không có từ/chọn từ chưa học. Giới hạn 10 request/phút/người.

### `GET /speaking/exercises/{exercise_id}`

Chi tiết bài của chính user (kèm `results` đã chấm) · `404` nếu không có/không thuộc user.

### `POST /speaking/exercises/{exercise_id}/items/{index}/score`

Body: audio thô (`audio/webm`, `audio/mp4`, ...) tối đa 5 MB. Chấm qua Speechace hoặc
Chivox theo `PRONUNCIATION_PROVIDER`, lưu kết quả vào `results[index]`.
`413` nếu vượt 5 MB; `503` nếu provider lỗi. Giới hạn 10 request/phút/người.

Chi tiết: [speaking-word-validation.md](speaking-word-validation.md).

---

## Story game — `/games/story`

| Method | Path | Mô tả |
|---|---|---|
| `GET` | `/games/story/words` | Từ đã học để chọn vào truyện |
| `POST` | `/games/story/stories` | `{ "topic", "tone", "vocabulary_ids" }` (1–7 từ) → tạo truyện bằng Mistral |
| `POST` | `/games/story/demo` | Lưu truyện mẫu, không cần AI key |
| `GET` | `/games/story/stories` | 20 truyện gần nhất của user |
| `GET` | `/games/story/stories/{id}` | Chi tiết truyện của chính user, chưa trả đáp án quiz |
| `POST` | `/games/story/stories/{id}/answers` | `{ "answers": [0, 1, 2] }` (index 0-based); nộp lại trả result đầu tiên |

Tạo truyện bị giới hạn 5 request/phút/người; provider lỗi trả `503` kèm thông báo thử lại.
Chi tiết: [story-game.md](story-game.md).

---

## AI Chat — `/chat`

### `POST /chat/messages`

Body:

```json
{
  "message": "Giải thích giúp mình từ này",
  "history": [{ "role": "user", "content": "..." }],
  "context": { "page": "dashboard", "intent": "word_explanation", "selected_text": "ephemeral" }
}
```

`200` → `{ "message": "...", "suggestions": ["..."], "action_label": "...", "action_href": "/..." }`.
`429` khi chạm quota Gemini; `503` khi AI không phản hồi. Giới hạn 10 request/phút/người.

---

## Admin (RBAC) — `/admin`

Mọi endpoint `/admin/*` yêu cầu JWT hợp lệ **và** `role = "admin"` (đọc từ MongoDB).
Token hợp lệ nhưng role `user` → `403 {"detail": "Admin privileges required"}`.

### Thống kê
- `GET /admin/stats` — số tài khoản (admin/learner, 5 mới nhất), từ vựng theo lĩnh vực/cấp độ,
  bài học có dữ liệu, câu hỏi theo kỹ năng/trạng thái.

### Người dùng
- `GET /admin/users` — query `search?`, `role?` (`user|admin`), `page`, `page_size` (≤200).
- `GET /admin/users/{user_id}` — chi tiết (không trả `password_hash`).
- `PUT /admin/users/{user_id}` — sửa `username`, `email`, `learning_level`, `interests`,
  `daily_goal`, `daily_new_limit`, `daily_review_limit`.
- `PUT /admin/users/{user_id}/role` — body `{ "role": "admin" | "user" }`.
  `400` khi tự thu quyền admin của mình hoặc thu quyền admin cuối cùng.
- `PUT /admin/users/{user_id}/status` — body `{ "is_active": true | false }` (khóa/mở).
- `POST /admin/users/{user_id}/reset-password` — reset mật khẩu, tăng `token_version`.
- `DELETE /admin/users/{user_id}` — xóa user + dữ liệu học tập liên quan.

### Từ vựng
- `GET /admin/vocabularies` — query `domain?`, `level?`, `search?`, `page`, `page_size`.
- `POST /admin/vocabularies` — tạo (`201`).
- `PUT /admin/vocabularies/{vocab_id}` — cập nhật.
- `DELETE /admin/vocabularies/{vocab_id}` — xóa (`204`).

### Lĩnh vực
- `GET /admin/domains` — cả lĩnh vực đang ẩn.
- `PUT /admin/domains/{slug}` — sửa `name`, `name_vi`, `description`, `order`, `active`.
- `POST /admin/domains/ensure` — khôi phục lĩnh vực mặc định bị thiếu (không ghi đè tùy chỉnh).

### Bài học
- `GET /admin/lessons` — nhóm theo lĩnh vực + cấp độ từ kho từ vựng.
- `POST /admin/lessons` — tạo/cập nhật metadata (idempotent theo `domain`+`level`).
- `PUT /admin/lessons/{lesson_id}` — sửa `title`, `description`, `order`.
- `DELETE /admin/lessons/{lesson_id}` — xóa metadata; `409` nếu bài còn từ vựng.
- `GET /admin/lessons/{lesson_id}/words` — danh sách từ của bài (phân trang).

### Câu hỏi (exercise bank)
- `GET /admin/exercises` — query `lesson_id?`, `domain?`, `level?`, `skill?`, `active?`, `search?`, `page`, `page_size`.
- `GET /admin/exercises/{item_id}` — chi tiết.
- `POST /admin/exercises` — tạo (`201`).
- `PUT /admin/exercises/{item_id}` — sửa prompt/options/đáp án/trạng thái.
- `DELETE /admin/exercises/{item_id}` — xóa (`204`).
- `POST /admin/exercises/regenerate?lesson_id=...` — sinh lại ngân hàng câu hỏi cho bài.

---

## Mã lỗi dùng chung

| Mã | Ý nghĩa |
|---|---|
| 400 | Dữ liệu/hành động không hợp lệ (vd. role admin cuối cùng, câu hỏi hết hạn) |
| 401 | Chưa đăng nhập / token sai / hết hạn / đã bị thu hồi |
| 403 | Không đủ quyền (cần `admin`) hoặc tài khoản bị khóa |
| 404 | Không tìm thấy tài nguyên |
| 409 | Dữ liệu trùng lặp (email, bài học còn từ vựng) |
| 413 | Audio/upload vượt giới hạn |
| 422 | Validation lỗi (Pydantic) |
| 429 | Chạm rate limit hoặc quota AI |
| 502 | Lỗi dịch vụ AI (sinh từ vựng) |
| 503 | Dịch vụ phụ trợ không sẵn sàng (AI chat, Mistral, dictionary, chấm phát âm) |
