# ERD — SmartVOCAB AI (MongoDB)

## 1. Collections

### users

```json
{
  "_id": "user@example.com",
  "username": "nguyenvana",
  "password_hash": "$2b$12$...",
  "created_at": "ISODate"
}
```

> `_id` dùng email để đơn giản (unique mặc định).

### vocabularies

```json
{
  "_id": ObjectId("..."),
  "word": "ephemeral",
  "phonetic": "ɪˈfem(ə)rəl",
  "part_of_speech": "adjective",
  "meaning": "tạm thời, ngắn ngủi",
  "example": "Fame is often ephemeral.",
  "synonyms": ["fleeting", "transient", "brief"],
  "antonyms": ["permanent", "lasting"],
  "topic": "general",
  "level": "B2",
  "created_at": "ISODate",
  "updated_at": "ISODate"
}
```

### flashcard_progress

```json
{
  "_id": ObjectId("..."),
  "user_id": "user@example.com",
  "vocabulary_id": "657abc...",
  "box": 3,
  "correct_count": 5,
  "wrong_count": 1,
  "next_review": "ISODate",
  "last_reviewed": "ISODate | null"
}
```

## 2. Mối quan hệ

```
┌─────────┐       ┌──────────────────┐       ┌───────────────┐
│  users  │ 1───* │ flashcard_progress│ *───1 │ vocabularies  │
└─────────┘       └──────────────────┘       └───────────────┘
   _id  ◄────────── user_id                    _id
                                              ▲
                                              │
                              flashcard_progress.vocabulary_id
```

| Quan hệ | Kiểu | Khóa |
|---|---|---|
| users → flashcard_progress | 1 : N | `users._id` = `flashcard_progress.user_id` |
| vocabularies → flashcard_progress | 1 : N | `vocabularies._id` = `flashcard_progress.vocabulary_id` |

> `vocabularies` là danh sách chung (không riêng theo user) — có thể nâng cấp
> thêm `owner_id` nếu muốn từ vựng cá nhân hoá.

## 3. Indexes đề xuất

```javascript
// vocabularies
db.vocabularies.createIndex({ word: "text", meaning: "text" })
db.vocabularies.createIndex({ level: 1, topic: 1 })
db.vocabularies.createIndex({ created_at: -1 })

// flashcard_progress
db.flashcard_progress.createIndex(
  { user_id: 1, vocabulary_id: 1 },
  { unique: true }
)
db.flashcard_progress.createIndex({ user_id: 1, next_review: 1 })

// users
db.users.createIndex({ email: 1 }, { unique: true })
```

## 4. Quy tắc xóa

- Xóa `vocabularies` → cascade xóa `flashcard_progress` liên quan (thực hiện
  trong `vocabulary_service.delete_vocabulary` nếu cần).
- Xóa `users` → cascade xóa `flashcard_progress` của user đó.
