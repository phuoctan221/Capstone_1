# API Specification — SmartVOCAB AI

Base URL: `http://localhost:8000`
Tất cả endpoint trừ `/auth` và `/health` yêu cầu header:

```
Authorization: Bearer <access_token>
```

---

## Health

### `GET /health`

```json
{ "status": "ok", "app": "SmartVOCAB AI" }
```

---

## Auth

### `POST /auth/register`

Body:

```json
{
  "email": "user@example.com",
  "username": "nguyenvana",
  "password": "secret123"
}
```

Responses:
- `201 Created`:

```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "user": { "id": "user@example.com", "email": "user@example.com", "username": "nguyenvana" }
}
```

- `409 Conflict`: `"Email already registered"`

### `POST /auth/login`

Body: `{ "email": "...", "password": "..." }`

Responses:
- `200 OK`: giống trên
- `401 Unauthorized`: `"Incorrect email or password"`

---

## Vocabulary

### `GET /vocabulary`

Query params: `topic?`, `level?`, `search?`, `page=1`, `page_size=20`

Response:

```json
{
  "total": 42,
  "page": 1,
  "page_size": 20,
  "items": [ { "...VocabularyOut" } ]
}
```

### `GET /vocabulary/{id}`

`200`: VocabularyOut · `404`: Not found

### `POST /vocabulary`

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
  "level": "B2"
}
```

`201 Created`: VocabularyOut

### `PUT /vocabulary/{id}`

Body: bất kỳ trường nào cần cập nhật · `200`: VocabularyOut

### `DELETE /vocabulary/{id}`

`204 No Content`

### `POST /vocabulary/ai-generate`

Body:

```json
{ "word": "ubiquitous", "target_language": "vi" }
```

Response `200`:

```json
{
  "word": "ubiquitous",
  "phonetic": "juːˈbɪkwɪtəs",
  "part_of_speech": "adjective",
  "meaning": "có mặt ở khắp nơi",
  "example": "Smartphones are ubiquitous nowadays.",
  "synonyms": ["omnipresent", "pervasive"],
  "antonyms": ["rare", "scarce"],
  "topic": "technology",
  "level": "C1"
}
```

`502 Bad Gateway`: AI lỗi / thiếu API key

---

## Learning

### `GET /learning/due`

Response: mảng flashcard_progress đến hạn

```json
[
  {
    "id": "...",
    "user_id": "user@example.com",
    "vocabulary_id": "657abc...",
    "box": 2,
    "correct_count": 3,
    "wrong_count": 1,
    "next_review": "2026-10-21T10:00:00Z",
    "last_reviewed": "2026-10-21T09:00:00Z"
  }
]
```

### `POST /learning/review`

Body:

```json
{ "vocabulary_id": "657abc...", "remembered": true }
```

Response: progress đã cập nhật (box, next_review mới)

### `GET /learning/stats`

```json
{ "total_words": 50, "mastered": 12, "learning": 38, "due_today": 7 }
```

---

## Mã lỗi dùng chung

| Mã | Ý nghĩa |
|---|---|
| 401 | Chưa đăng nhập / token sai / hết hạn |
| 404 | Không tìm thấy tài nguyên |
| 409 | Dữ liệu trùng lặp |
| 422 | Dữ liệu gửi lên không hợp lệ (validation) |
| 502 | Lỗi dịch vụ AI |
