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

## Admin (RBAC)

Mọi endpoint `/admin/*` yêu cầu JWT hợp lệ **và** `role = "admin"` lưu trong MongoDB.
Token hợp lệ nhưng role `user` trả `403` với `{"detail": "Admin privileges required"}`.
Đăng ký công khai luôn tạo `role = "user"`; không có cơ chế nâng quyền theo email.
Tạo/nâng quyền admin bằng `backend/scripts/create_admin.py`.

### `GET /admin/stats`

Thống kê thật từ MongoDB: số tài khoản (admin/người học, 5 tài khoản mới nhất), từ vựng theo lĩnh vực/cấp độ,
bài học có dữ liệu, câu hỏi theo kỹ năng và trạng thái.

### `GET /admin/users`

Query: `search?`, `role?` (`user` | `admin`), `page=1`, `page_size=50`.

```json
{ "total": 12, "page": 1, "page_size": 50, "items": [ { "...UserOut" } ] }
```

Không trả `password_hash`.

### `PUT /admin/users/{user_id}/role`

Body: `{ "role": "admin" }` hoặc `{ "role": "user" }`.

- `400`: role không hợp lệ, tự thu quyền admin của chính mình, hoặc thu quyền admin cuối cùng.
- `404`: không tìm thấy tài khoản.

### `GET /admin/vocabularies`

Query: `domain?`, `level?`, `search?`, `page=1`, `page_size=50`.
Response giống `GET /vocabulary`.

- `POST /admin/vocabularies`: tạo từ vựng (`201`).
- `PUT /admin/vocabularies/{vocab_id}`: cập nhật từ vựng.
- `DELETE /admin/vocabularies/{vocab_id}`: xóa từ vựng (`204`).

### Domains

- `GET /admin/domains`: danh sách 3 lĩnh vực, gồm cả lĩnh vực đang tạm ẩn.
- `PUT /admin/domains/{slug}`: sửa `name`, `name_vi`, `description`, `order`, `active`.
- `POST /admin/domains/ensure`: khôi phục lĩnh vực mặc định bị thiếu, không ghi đè tùy chỉnh.

### Lessons

- `GET /admin/lessons`: bài học nhóm theo lĩnh vực + cấp độ từ kho từ vựng.
- `POST /admin/lessons`: tạo/cập nhật metadata bài học (idempotent theo `domain-level`).
- `PUT /admin/lessons/{lesson_id}`: sửa `title`, `description`, `order`.
- `DELETE /admin/lessons/{lesson_id}`: xóa metadata; trả `409` nếu bài còn từ vựng.
- `GET /admin/lessons/{lesson_id}/words`: danh sách từ vựng của bài (phân trang).

### Exercises

- `GET /admin/exercises`: query `lesson_id?`, `domain?`, `level?`, `skill?`, `active?`, `search?`, `page`, `page_size`.
- `GET /admin/exercises/{item_id}`: chi tiết một câu hỏi.
- `POST /admin/exercises`: tạo câu hỏi thủ công (`201`).
- `PUT /admin/exercises/{item_id}`: sửa prompt/options/đáp án/trạng thái.
- `DELETE /admin/exercises/{item_id}`: xóa câu hỏi (`204`).
- `POST /admin/exercises/regenerate?lesson_id=...`: sinh lại ngân hàng câu hỏi cho bài học.

## Mã lỗi dùng chung

| Mã | Ý nghĩa |
|---|---|
| 401 | Chưa đăng nhập / token sai / hết hạn |
| 403 | Đã đăng nhập nhưng không đủ quyền (API `/admin/*` yêu cầu role `admin`) |
| 404 | Không tìm thấy tài nguyên |
| 409 | Dữ liệu trùng lặp |
| 422 | Dữ liệu gửi lên không hợp lệ (validation) |
| 502 | Lỗi dịch vụ AI |
