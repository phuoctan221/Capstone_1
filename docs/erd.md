# ERD — SmartVOCAB AI (MongoDB)

> Cập nhật theo code hiện tại. MongoDB không có schema cứng; tài liệu mô tả các
> trường chính đang được đọc/ghi. `users._id` là **email** (chuỗi, lowercase).
> Ngoài collections học tập lõi, codebase còn có story/speaking/assessment/reset/rate limit
> (mô tả ở dưới). `vocab_raw_cache` và `vocab_enrichment_jobs` do script import quản lý,
> không được tạo index trong `ensure_indexes()`.

## 1. Collections

### users

```json
{
  "_id": "user@example.com",
  "email": "user@example.com",
  "username": "nguyenvana",
  "password_hash": "$2b$12$...",
  "role": "user | admin",
  "created_at": "ISODate",
  "learning_level": "A1..C2 | null",
  "placement_levels": { "general": "B1", "technology": "A2", "business": "A1" },
  "interests": ["technology", "business"],
  "onboarded": false,
  "daily_goal": 10,
  "xp": 0,
  "streak": 0,
  "last_study_date": "ISODate | null",
  "profile_completed_at": "ISODate | null",
  "token_version": 0,
  "is_active": true,
  "updated_at": "ISODate | null",
  "avatar_url": "/uploads/avatar-....png | null"
}
```

- `_id` = email lowercase → đăng nhập/tra cứu trực tiếp bằng email.
- `token_version` tăng khi đổi/reset mật khẩu hoặc khóa tài khoản → thu hồi JWT cũ.
- `is_active = false` → tài khoản bị khóa (`403`).

### domains

```json
{
  "_id": "general | technology | business",
  "slug": "general",
  "name": "General English",
  "name_vi": "Tiếng Anh tổng quát",
  "description": "...",
  "order": 1,
  "active": true,
  "created_at": "ISODate",
  "updated_at": "ISODate"
}
```

- 3 lĩnh vực MVP cố định (`MVP_DOMAIN_ORDER`), seed bằng `ensure_domains()`;
  admin sửa metadata nhưng không tạo/xóa.
- `topic` legacy được map về `domain` qua `app/core/domains.py`.

### lessons

```json
{
  "_id": "<lesson_id, vd general-a1>",
  "slug": "general-a1",
  "domain": "general",
  "level": "A1",
  "title": "General English · A1",
  "description": "",
  "order": 0,
  "created_at": "ISODate",
  "updated_at": "ISODate"
}
```

- Lesson là **metadata**; danh sách từ suy ra từ `vocabularies` theo `domain` + `level`.

### vocabularies

```json
{
  "_id": ObjectId("..."),
  "word": "ephemeral",
  "word_key": "ephemeral",
  "phonetic": "/ɪˈfem(ə)rəl/",
  "phonetic_source": "dictionaryapi.dev",
  "part_of_speech": "adjective",
  "english_definition": "Lasting for a short time.",
  "meaning": "tạm thời, ngắn ngủi",
  "meaning_key": "tạm thời, ngắn ngủi",
  "example": "Fame is often ephemeral.",
  "example_id": 123456,
  "synonyms": ["fleeting", "transient"],
  "antonyms": ["permanent", "lasting"],
  "topic": "general",
  "domain": "general | technology | business",
  "topic_source": "gemini | keyword",
  "level": "A1..C2",
  "review_status": "imported | auto_validated | human_approved",
  "data_source": "dnizfor/vocabulary-flashcard-dataset (MIT) + Tatoeba (CC BY 2.0)",
  "created_at": "ISODate",
  "updated_at": "ISODate"
}
```

- `topic` được đồng bộ bằng `domain` (3 lĩnh vực MVP); dữ liệu cũ có thể còn
  `daily-life`, `travel`, `science`, `academic` và được map qua `app/core/domains.py`.
- Unique theo `word_key` (`word_key_unique`) → mỗi từ chỉ có một document.
  Importer/enrichment dùng khóa này để upsert idempotent.
- `phonetic_source` / `topic_source` cho biết nguồn làm giàu; `review_status`
  chuẩn hóa trạng thái duyệt (`NULL` được đổi thành `imported`).

### vocab_raw_cache

```json
{
  "_id": "<word_key>",
  "word": "ephemeral",
  "payload": { "...phản hồi gốc từ dictionary API..." },
  "updated_at": "ISODate"
}
```

- Cache phản hồi API khi importer chạy lại, tránh gọi mạng lặp lại.

### vocab_enrichment_jobs

```json
{
  "_id": "phonetic:ephemeral | topic:ephemeral",
  "field": "phonetic | topic",
  "word_key": "ephemeral",
  "status": "done | failed",
  "domain": "general",
  "source": "gemini | keyword",
  "last_error": "...",
  "created_at": "ISODate",
  "updated_at": "ISODate"
}
```

- Lưu tiến độ `enrich_vocabularies.py`; job `failed` sẽ được thử lại ở lần chạy sau.

### exercise_items

```json
{
  "_id": ObjectId("..."),
  "exercise_item_id": "<vocab_id>:meaning",
  "vocabulary_id": "657abc...",
  "domain": "general",
  "level": "B1",
  "skill": "meaning | spelling | context",
  "prompt": "...",
  "options": ["...", "..."],
  "correct_answer": "...",
  "accepted_answers": ["..."],
  "cloze": "Fame is often ____.",
  "hint": "...",
  "active": true,
  "created_at": "ISODate",
  "updated_at": "ISODate"
}
```

- Đáp án chỉ nằm ở server; payload câu hỏi trả cho client không có `correct_answer`.
- Sinh tự động từ từ vựng (`exercise_service.ensure_exercise_bank`), admin sửa được.

### learning_sessions

```json
{
  "_id": ObjectId("..."),
  "session_id": "uuid",
  "user_id": "user@example.com",
  "lesson_id": "general-a1",
  "domain": "general",
  "level": "A1",
  "skills": ["meaning", "spelling", "context"],
  "status": "active | finished",
  "question_count": 10,
  "answered_count": 0,
  "correct_count": 0,
  "started_at": "ISODate",
  "finished_at": "ISODate | null"
}
```

### answer_attempts

```json
{
  "_id": ObjectId("..."),
  "attempt_id": "uuid",
  "user_id": "user@example.com",
  "session_id": "uuid | null",
  "exercise_item_id": "657abc...:meaning",
  "vocabulary_id": "657abc...",
  "skill": "meaning",
  "is_correct": true,
  "response_time_ms": 3200,
  "hint_used": false,
  "answered_at": "ISODate",
  "result": { "...kết quả đầy đủ trả cho client..." }
}
```

- `attempt_id` unique (partial index) → retry không cộng XP/Mastery hai lần.

### user_word_states

```json
{
  "_id": ObjectId("..."),
  "user_id": "user@example.com",
  "vocabulary_id": "657abc...",
  "mastery": { "meaning": 82.0, "spelling": 40.0, "context": 55.0 },
  "fsrs": {
    "card_json": "...",
    "card_id": 12,
    "state": 2,
    "step": 0,
    "difficulty": 5.1,
    "stability": 3.4,
    "due_at": "ISODate",
    "last_reviewed_at": "ISODate | null"
  },
  "review_count": 3,
  "started_at": "ISODate",
  "updated_at": "ISODate"
}
```

- Unique `(user_id, vocabulary_id)`.
- `mastery`: 3 kỹ năng độc lập 0–100; `mastered` khi cả 3 ≥ ngưỡng (mặc định 80).
- `fsrs.due_at` dùng cho `/learning/due`.

### lesson_progress

```json
{
  "_id": ObjectId("..."),
  "user_id": "user@example.com",
  "lesson_id": "general-a1",
  "topic": "general",
  "unit": 1,
  "units": [1, 2],
  "completed": true,
  "completed_at": "ISODate",
  "learned_count": 12,
  "mastered_count": 4,
  "completion_source": "quiz | assessment"
}
```

- Mỗi bài được chia thành unit ổn định (tối đa 15 từ) nên hoàn thành được lưu **theo unit**.
- Unique `(user_id, lesson_id, unit)` (partial, tên `uniq_user_lesson_unit`); index legacy
  `(user_id, topic)` và `uniq_user_lesson` bị xóa lúc khởi động.

### fsrs_review_logs

```json
{
  "_id": ObjectId("..."),
  "review_id": "uuid",
  "user_id": "user@example.com",
  "vocabulary_id": "657abc...",
  "rating": 1,
  "reviewed_at": "ISODate",
  "review_log_json": "...",
  "retrievability": 0.87
}
```

- `rating`: 1 Again · 2 Hard · 3 Good · 4 Easy.
- `review_id` unique (partial) → idempotent khi retry.

### quiz_questions (legacy quiz, TTL)

```json
{
  "_id": ObjectId("..."),
  "question_id": "uuid",
  "user_id": "user@example.com",
  "lesson_id": "general-a1",
  "vocabulary_id": "657abc...",
  "skill": "meaning",
  "question": "...",
  "options": ["..."],
  "answer": "...",
  "expires_at": "ISODate"
}
```

- TTL index `expires_at` (`expireAfterSeconds: 0`) → tự xóa câu hỏi hết hạn.

### flashcard_progress (legacy — Leitner)

```json
{
  "_id": ObjectId("..."),
  "user_id": "user@example.com",
  "vocabulary_id": "657abc...",
  "box": 1,
  "correct_count": 0,
  "wrong_count": 0,
  "next_review": "ISODate",
  "last_reviewed": "ISODate | null"
}
```

> Giữ để tương thích dữ liệu cũ/migration. Luồng ôn tập hiện tại dùng
> `user_word_states.fsrs` + `fsrs_review_logs`, không dùng `box`.

### story_games

```json
{
  "_id": ObjectId("..."),
  "user_id": "user@example.com",
  "words": [{ "id": "657abc...", "word": "ephemeral", "meaning": "..." }],
  "topic": "travel",
  "tone": "warm",
  "source": "ai | demo",
  "title": "A Small Trip",
  "paragraphs": ["..."],
  "translation": ["..."],
  "questions": [{ "question": "...", "options": ["..."], "answer": 2, "explanation": "..." }],
  "result": { "answers": [0, 1, 2], "correct": 3, "total": 3, "submitted_at": "ISODate" } | null,
  "created_at": "ISODate"
}
```

- Chỉ chủ sở hữu mới đọc được; API ẩn `questions[].answer` trước khi nộp bài.
- Index `(user_id, created_at desc)` phục vụ 20 truyện gần nhất.

### speaking_exercises

```json
{
  "_id": ObjectId("..."),
  "user_id": "user@example.com",
  "items": [{ "text": "invoice", "source": "learned | custom" }],
  "results": { "0": { "score": 85, "provider": "speechace", "assessment_details": {} } },
  "created_at": "ISODate"
}
```

- `results[index]` được ghi khi chấm audio; provider và cấu trúc điểm do Speechace/Chivox trả về.

### level_assessment_attempts

```json
{
  "_id": ObjectId("..."),
  "attempt_id": "uuid",
  "user_id": "user@example.com",
  "domain": "general",
  "level": "B1",
  "item_ids": ["657abc...:meaning"],
  "status": "active | submitted | expired",
  "created_at": "ISODate",
  "expires_at": "ISODate (TTL)",
  "submitted_at": "ISODate | null",
  "passed": false,
  "result": { "...kết quả chấm điểm..." } | null
}
```

### level_assessment_results

```json
{
  "_id": ObjectId("..."),
  "user_id": "user@example.com",
  "domain": "general",
  "level": "B1",
  "attempt_id": "uuid",
  "passed_at": "ISODate"
}
```

- Unique `(user_id, domain, level)`; tồn tại nghĩa là cấp độ đã đạt assessment.

### password_reset_otps

```json
{
  "_id": ObjectId("..."),
  "email": "user@example.com",
  "otp_hash": "HMAC-SHA256(email:otp, JWT_SECRET)",
  "attempts": 0,
  "created_at": "ISODate",
  "expires_at": "ISODate (TTL)",
  "used_at": "ISODate | null",
  "invalidated_at": "ISODate | null"
}
```

- OTP không lưu plaintext; TTL dùng `PASSWORD_RESET_OTP_TTL_MINUTES`.

### ai_rate_limits

```json
{
  "_id": "user@example.com:1234567",
  "count": 3,
  "expires_at": "ISODate (TTL 3600s)"
}
```

- Bucket theo phút, dùng chung cho AI chat, quiz mistake analysis, speaking và story.

## 2. Mối quan hệ (logic)

```
users (email) 1───* user_word_states *───1 vocabularies (ObjectId)
users         1───* answer_attempts   *───1 vocabularies
users         1───* learning_sessions *───1 lessons
users         1───* lesson_progress   *───1 lessons
users         1───* fsrs_review_logs  *───1 vocabularies
vocabularies  1───* exercise_items
users         1───* quiz_questions    *───1 vocabularies
users         1───* story_games       *───* vocabularies (words[])
users         1───* speaking_exercises
users         1───* level_assessment_attempts *───1 exercise_items (item_ids)
users         1───1 level_assessment_results
users         1───* password_reset_otps (theo email)
```

| Quan hệ | Khóa |
|---|---|
| users → user_word_states | `users._id` = `user_word_states.user_id` |
| users → answer_attempts | `users._id` = `answer_attempts.user_id` |
| users → learning_sessions | `users._id` = `learning_sessions.user_id` |
| users → lesson_progress | `users._id` = `lesson_progress.user_id` |
| users → fsrs_review_logs | `users._id` = `fsrs_review_logs.user_id` |
| vocabularies → user_word_states | `vocabularies._id` (str) = `user_word_states.vocabulary_id` |
| vocabularies → exercise_items | `vocabularies._id` (str) = `exercise_items.vocabulary_id` |
| lessons → learning_sessions | `lessons._id` = `learning_sessions.lesson_id` |
| domains → lessons | `lessons.domain` = `domains.slug` |

## 3. Indexes (tạo trong `app/db/mongodb.py::ensure_indexes`)

```javascript
// AI/rate limit & story
db.ai_rate_limits.createIndex({ expires_at: 1 }, { expireAfterSeconds: 3600 })
db.story_games.createIndex({ user_id: 1, created_at: -1 })

// users
db.users.createIndex({ email: 1 }, { unique: true, sparse: true })
db.users.createIndex({ role: 1 })

// domains / lessons
db.domains.createIndex({ order: 1 })
db.lessons.createIndex({ slug: 1 }, { unique: true })
db.lessons.createIndex({ domain: 1, level: 1 })

// vocabularies
db.vocabularies.createIndex({ word: "text", meaning: "text" })
db.vocabularies.createIndex({ domain: 1, level: 1 })
db.vocabularies.createIndex(
  { word_key: 1 },
  { unique: true, name: "word_key_unique" }
)
// Legacy tuple index (giữ cho DB cũ; unique word_key đã đủ ràng buộc)
db.vocabularies.createIndex(
  { word_key: 1, domain: 1, meaning_key: 1 },
  {
    unique: true,
    partialFilterExpression: {
      word_key: { $type: "string" },
      domain: { $type: "string" },
      meaning_key: { $type: "string" }
    }
  }
)

// enrichment jobs
db.vocab_enrichment_jobs.createIndex({ field: 1, status: 1 })
db.vocab_enrichment_jobs.createIndex({ word_key: 1 })

// exercise bank
db.exercise_items.createIndex(
  { exercise_item_id: 1 },
  { unique: true, partialFilterExpression: { exercise_item_id: { $type: "string" } } }
)
db.exercise_items.createIndex({ vocabulary_id: 1, skill: 1 })
db.exercise_items.createIndex({ domain: 1, level: 1, skill: 1, active: 1 })

// learning sessions
db.learning_sessions.createIndex(
  { session_id: 1 },
  { unique: true, partialFilterExpression: { session_id: { $type: "string" } } }
)
db.learning_sessions.createIndex({ user_id: 1, started_at: -1 })

// answer attempts
db.answer_attempts.createIndex({ user_id: 1, answered_at: -1 })
db.answer_attempts.createIndex({ session_id: 1 })
db.answer_attempts.createIndex(
  { attempt_id: 1 },
  { unique: true, partialFilterExpression: { attempt_id: { $type: "string" } } }
)

// per-user word state (Mastery + FSRS)
db.user_word_states.createIndex({ user_id: 1, vocabulary_id: 1 }, { unique: true })
db.user_word_states.createIndex({ user_id: 1, "fsrs.due_at": 1 })

// lesson progress (theo unit)
db.lesson_progress.createIndex(
  { user_id: 1, lesson_id: 1, unit: 1 },
  {
    unique: true,
    partialFilterExpression: {
      lesson_id: { $type: "string" },
      unit: { $type: "int" }
    },
    name: "uniq_user_lesson_unit"
  }
)
db.lesson_progress.createIndex({ user_id: 1, topic: 1 })

// FSRS review history
db.fsrs_review_logs.createIndex(
  { review_id: 1 },
  { unique: true, partialFilterExpression: { review_id: { $type: "string" } } }
)
db.fsrs_review_logs.createIndex({ user_id: 1, reviewed_at: -1 })

// level assessments
db.level_assessment_attempts.createIndex(
  { attempt_id: 1 },
  { unique: true, partialFilterExpression: { attempt_id: { $type: "string" } } }
)
db.level_assessment_attempts.createIndex(
  { user_id: 1, domain: 1, level: 1, created_at: -1 }
)
db.level_assessment_attempts.createIndex({ expires_at: 1 }, { expireAfterSeconds: 0 })
db.level_assessment_results.createIndex(
  { user_id: 1, domain: 1, level: 1 }, { unique: true }
)

// password reset OTPs
db.password_reset_otps.createIndex({ expires_at: 1 }, { expireAfterSeconds: 0 })
db.password_reset_otps.createIndex({ email: 1, created_at: -1 })

// legacy quiz (TTL)
db.quiz_questions.createIndex({ question_id: 1 }, { unique: true })
db.quiz_questions.createIndex({ expires_at: 1 }, { expireAfterSeconds: 0 })

// legacy flashcards
db.flashcard_progress.createIndex({ user_id: 1, vocabulary_id: 1 }, { unique: true })
```

## 4. Quy tắc xóa / đổi tên

- **Đổi email (admin)**: cập nhật `users._id` và lan sang `user_word_states`,
  `answer_attempts`, `learning_sessions`, `fsrs_review_logs`, `lesson_progress`,
  `quiz_questions`, `flashcard_progress` (danh sách `USER_DATA_COLLECTIONS` trong
  `app/routers/admin_router.py`). Avatar local không bị đổi tên.
- **Xóa user (admin)**: xóa user + dữ liệu ở chính các collection trên và xóa file avatar.
- **Giới hạn hiện tại**: `story_games`, `speaking_exercises`, `level_assessment_attempts`
  và `level_assessment_results` chưa nằm trong `USER_DATA_COLLECTIONS`, nên chưa được
  tự động migrate khi đổi email hoặc xóa qua admin. Cần thêm vào danh sách này ở bước sau.
- **Xóa vocabulary**: dọn `exercise_items`/`user_word_states` liên quan (thực hiện
  trong `vocabulary_service`).
- **Xóa lesson**: chỉ xóa metadata; nếu còn từ vựng thuộc `domain`+`level` → trả `409`.
- **Xóa domain**: không hỗ trợ (chỉ bật/tắt `active`).
