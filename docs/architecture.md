# Kiến trúc Hệ thống — SmartVOCAB AI

> Cập nhật theo mã nguồn hiện tại (FastAPI + React + MongoDB Atlas + Mastery/FSRS).
> Tài liệu cũ mô tả Leitner 5 hộp và `flashcard_progress` là luồng chính; hiện
> `flashcard_progress` chỉ còn là dữ liệu legacy, luồng chính dùng **Mastery + FSRS**.

## 1. Tổng quan kiến trúc

**Client–Server, REST API, layered monolith** (một backend FastAPI, không phải microservices).
Ba lớp chính: Presentation (React SPA) → Application (FastAPI routers/services) → Data (MongoDB Atlas).
Dịch vụ AI (Google Gemini) là dependency ngoài.

```
┌──────────────────────────────────────────────────────────────┐
│ FRONTEND — React 18 + Vite (SPA)                             │
│  pages/ → components/ → services/(Axios) → hooks/constants   │
│  React Router: route theo role (user / admin) + guard        │
│  JWT trong localStorage, interceptor gắn Bearer, 401 → login │
└───────────────────────────┬──────────────────────────────────┘
                            │ HTTP/JSON  (dev: Vite proxy /api)
┌───────────────────────────▼──────────────────────────────────┐
│ BACKEND — FastAPI (async)                                    │
│  routers/  →  services/  →  db/ (Motor async)                │
│  models/ Pydantic · core/config.py (pydantic-settings)       │
│  auth: JWT HS256 + bcrypt, RBAC role đọc từ MongoDB          │
│  ai_service ───────────────► Google Gemini API (ngoài)       │
└───────────────────────────┬──────────────────────────────────┘
                            │ Motor / MongoDB wire protocol
┌───────────────────────────▼──────────────────────────────────┐
│ DATA — MongoDB Atlas, database `capstone1`                   │
│  users · domains · lessons · vocabularies · exercise_items   │
│  learning_sessions · answer_attempts · user_word_states      │
│  lesson_progress · fsrs_review_logs · quiz_questions         │
│  flashcard_progress (legacy)                                 │
└──────────────────────────────────────────────────────────────┘
```

**Triển khai Docker (Phase A):** nginx serve SPA + reverse proxy + cân bằng tải `/api`
tới 2 container FastAPI (`api1`, `api2`); cả hai dùng chung MongoDB Atlas. Xem
[deployment.md](deployment.md).

## 2. Cấu trúc thư mục

```
Capstone_1/
├── frontend/                 # React 18 + Vite
│   ├── src/
│   │   ├── components/       # Navbar, AdminLayout, Flashcard, form...
│   │   ├── pages/            # trang theo route (Learn, Practice, Admin...)
│   │   ├── services/         # lớp gọi API (Axios) theo domain
│   │   ├── hooks/            # useAuth
│   │   ├── constants/        # domains, helper role
│   │   ├── App.jsx           # khai báo route + guard
│   │   └── main.jsx
│   ├── nginx.conf
│   └── package.json
├── backend/                  # FastAPI
│   ├── app/
│   │   ├── main.py           # app entry, lifespan, CORS, mount routers
│   │   ├── core/             # config.py, domains.py
│   │   ├── db/               # mongodb.py (Motor client + index)
│   │   ├── models/           # Pydantic schemas
│   │   ├── routers/          # API endpoints
│   │   └── services/         # business logic
│   ├── scripts/              # seed, migrate, create_admin, check_mongo...
│   ├── tests/                # unittest
│   ├── requirements.txt
│   └── Dockerfile
├── docs/                     # tài liệu thiết kế
├── data/                     # dữ liệu mẫu
├── deploy/                   # script hạ tầng (Mongo replica set Phase B)
├── docker-compose.yml
└── README.md
```

## 3. Các lớp backend

| Lớp | Vị trí | Trách nhiệm |
|---|---|---|
| Entry / middleware | `app/main.py` | Tạo `FastAPI`, CORS, `lifespan` (kết nối Mongo, seed domain), mount router, `/health` |
| Config | `app/core/config.py` | `pydantic-settings`, ưu tiên env hệ thống → `.env.local` → `.env` |
| Domain constants | `app/core/domains.py` | 3 lĩnh vực MVP + map `topic` legacy → `domain` |
| Data access | `app/db/mongodb.py` | `AsyncIOMotorClient`, ping, `ensure_indexes()` idempotent |
| API / controller | `app/routers/*` | Validate request (Pydantic), phân quyền, gọi service |
| Business logic | `app/services/*` | Auth, vocabulary, lesson, exercise, session, mastery, FSRS, progress, AI |
| Schemas | `app/models/*` | Request/response Pydantic |

Router hiện có: `/auth`, `/vocabulary` (+ alias `/vocabularies`), `/domains`,
`/lessons`, `/learning`, `/progress`, `/admin`.

## 4. Xác thực & phân quyền

```
Client                       Backend
  │ POST /auth/login          │
  │ ─────────────────────────►│ bcrypt verify (passlib)
  │ {access_token, user}      │ JWT HS256: {sub=email, ver, exp}
  │ ◄─────────────────────────│
  │ GET /progress             │
  │ Authorization: Bearer ... │
  │ ─────────────────────────►│ decode → đọc user từ MongoDB
  │                           │ kiểm tra token_version + is_active
  │ {…}                       │ role lấy từ DB (không tin client)
  │ ◄─────────────────────────│
```

- `users._id` = email (lowercase). JWT `sub` = email.
- `token_version` tăng khi đổi/reset mật khẩu → vô hiệu hóa token cũ.
- `is_active = false` → `403 Account is locked`.
- RBAC: chỉ giá trị `role === "admin"` mới có quyền; mọi `/admin/*` gắn
  `Depends(require_admin)`; token hợp lệ nhưng role `user` → `403`.
- Đăng ký công khai luôn tạo `role = "user"`. Tạo admin qua `scripts/create_admin.py`.

## 5. Luồng học tập (Mastery + FSRS)

### 5.1 Phiên luyện tập (exercise session)

```
POST /learning/sessions {lesson_id, skills, count}
  → lấy từ vựng của lesson (theo domain + level)
  → exercise_service.ensure_exercise_bank() sinh/ cập nhật exercise_items
  → chọn câu theo skill, tạo learning_sessions (status=active)
GET  /learning/sessions/{id}/exercises   → trả câu hỏi (KHÔNG kèm đáp án)
POST /learning/sessions/{id}/answers     → chấm điểm server-side
  → cập nhật Mastery của kỹ năng vừa luyện + XP/streak
  → ghi answer_attempts (idempotent theo attempt_id)
POST /learning/sessions/{id}/finish      → tổng kết, pass nếu ≥ 70%
  → cập nhật lesson_progress khi pass
```

### 5.2 Mastery (3 kỹ năng độc lập)

Mỗi từ có 3 điểm 0–100: `meaning`, `spelling`, `context` (`user_word_states.mastery`).

| Sự kiện | Điểm |
|---|---|
| Trả lời đúng | `+MASTERY_CORRECT_GAIN` (mặc định +10) |
| Đúng có dùng hint | gain × `MASTERY_HINT_FACTOR` (×0.5) |
| Đúng nhanh (≤ `MASTERY_FAST_MS`) | +`MASTERY_FAST_BONUS` (+2) |
| Trả lời sai | −`MASTERY_WRONG_PENALTY` (−5) |
| Kẹp giá trị | `[0, 100]` |

- `learned`: có ít nhất một kỹ năng > 0.
- `mastered`: cả 3 kỹ năng ≥ `MASTERY_THRESHOLD` (mặc định 80).
- Chỉ kỹ năng được luyện mới thay đổi; hai kỹ năng còn lại giữ nguyên.

### 5.3 FSRS (spaced repetition)

Dùng package `fsrs==6.3.2` (`app/services/fsrs_service.py`):

```
GET  /learning/due      → các user_word_states có fsrs.due_at <= now
POST /learning/review   → rating 1..4 (again/hard/good/easy)
  → schedule_review() cập nhật difficulty/stability/due_at
  → ghi fsrs_review_logs (review_id idempotent)
GET  /learning/stats    → total / mastered / learning / due_today
```

> Một `answer_attempt` **không** tự động là một lần FSRS review. FSRS chỉ cập nhật
> khi gọi `/learning/review` (ôn flashcard). `retrievability` được tính tại thời
> điểm đọc. `flashcard_progress` (Leitner box) là dữ liệu cũ, không còn là luồng chính.

Trang `/flashcards` có 3 chế độ ôn: **Lật thẻ** (mặc định), **Recall** (gõ nghĩa
trước khi xem đáp án) và **Cloze** (dùng câu `example`, che từ rồi gõ lại, có xử lý
biến thể số nhiều/đuôi từ). Cả 3 đều kết thúc bằng đánh giá FSRS 1–4; việc so khớp
đáp án chỉ mang tính phản hồi phía client, không thay đổi Mastery hay XP.

### 5.4 Vòng học hằng ngày

`GET /learning/daily` (`app/services/daily_service.py`) là endpoint **chỉ đọc**,
tổng hợp trạng thái học trong ngày theo múi giờ người học (`tz_offset`):

```
user_word_states (due_at <= now)  → due_count + due_preview
answer_attempts + fsrs_review_logs → số từ khác nhau đã học hôm nay / 7 ngày
vocabularies chưa có state         → từ mới ưu tiên interests + learning_level
progress (goal, streak)            → tasks + goal_met
```

- `studied_today` đếm distinct `vocabulary_id`, không phải số câu trả lời.
- `week` gồm 7 ngày địa phương (cũ → hôm nay) để vẽ biểu đồ tiến bộ.
- Frontend: `DailyPlanCard` trên Dashboard, kèm nhắc nhở in-app và browser
  Notification (opt-in qua `localStorage`); không có cron/worker nên nhắc nhở chỉ
  chạy khi người học mở ứng dụng.

### 5.5 XP / Streak / Level

- Đúng: +10 XP; sai: +2 XP; hoàn thành lesson: +50 XP (`progress_service`).
- Level suy ra từ ngưỡng XP (`LEVEL_THRESHOLDS`).
- Streak tăng khi học ngày liên tiếp (`last_study_date`).

## 6. Luồng AI Generate

```
User nhập "ephemeral"
  → POST /vocabulary/ai-generate {word, target_language}
  → ai_service gọi Gemini generateContent (JSON mode, temp thấp, retry)
  → parse JSON: phonetic, part_of_speech, meaning, example, synonyms...
  → trả form đã điền sẵn; user bấm lưu → POST /vocabulary
```

- `POST /vocabulary/ai-generate-batch` (admin): sinh/suggest nhiều từ, có thể `save`.
- Thiếu `GEMINI_API_KEY` → lỗi cấu hình; quota hết → `AIQuotaError` (không retry).
- Cấu hình `CF_*` (Cloudflare Workers AI) được giữ để tương thích `.env` nhưng
  hiện **chưa được nối** vào `ai_service`; production dùng Gemini.

## 7. Dữ liệu (tóm tắt)

| Collection | Vai trò |
|---|---|
| `users` | Tài khoản, role, onboarding, XP/streak, `token_version`, `is_active` |
| `domains` | 3 lĩnh vực MVP (metadata chỉnh được, không tạo/xóa) |
| `lessons` | Metadata bài học theo `domain` + `level` |
| `vocabularies` | Kho từ vựng dùng chung (1 document / `word_key`; có IPA, synonyms/antonyms, topic/domain) |
| `vocab_raw_cache` | Cache phản hồi dictionary API khi import |
| `vocab_enrichment_jobs` | Tiến độ làm giàu dữ liệu (phonetic/topic), resumable |
| `exercise_items` | Ngân hàng câu hỏi (meaning/spelling/context), đáp án server-side |
| `learning_sessions` | Phiên luyện tập |
| `answer_attempts` | Lịch sử trả lời (idempotent theo `attempt_id`) |
| `user_word_states` | Mastery + trạng thái FSRS theo từng user/từ |
| `lesson_progress` | Hoàn thành bài học theo user/lesson |
| `fsrs_review_logs` | Lịch sử ôn FSRS |
| `quiz_questions` | Câu hỏi quiz tạm thời (TTL `expires_at`) |
| `flashcard_progress` | Legacy Leitner (giữ để tương thích dữ liệu) |

Kho từ vựng được nạp bằng `scripts/import_english_vocab_pipeline.py` (CSV → MongoDB)
và làm giàu bằng `scripts/enrich_vocabularies.py` (IPA từ dictionaryapi.dev,
topic bằng Gemini/keyword, chuẩn hóa `review_status`). Script chỉ điền trường
trống, có backup, lưu tiến độ trong `vocab_enrichment_jobs` và chạy lại an toàn.

Chi tiết schema/index: [erd.md](erd.md).

## 8. Công nghệ

| Thành phần | Lựa chọn | Ghi chú |
|---|---|---|
| Web framework | FastAPI 0.115 | Async, type hints, OpenAPI tự sinh |
| ASGI server | Uvicorn | Chạy sau nginx khi Docker |
| DB | MongoDB Atlas | Schema linh hoạt, dùng chung cho team |
| Driver | Motor 3.6 + PyMongo | Async chính thức |
| Auth | JWT (python-jose) + bcrypt | Stateless, `token_version` để thu hồi |
| Spaced repetition | `fsrs==6.3.2` | Thay Leitner ở luồng chính |
| AI | Google Gemini (httpx) | JSON mode, retry + quota handling |
| Frontend | React 18 + Vite 6 | SPA, code-split theo route |
| Routing | React Router 6 | Guard theo role/onboarding |
| HTTP client | Axios | Interceptor JWT + xử lý 401 |

## 9. Chiến lược triển khai

- **Dev**: MongoDB Atlas (cluster dùng chung) + `uvicorn --reload` + `npm run dev`
  (Vite proxy `/api` → `:8000`).
- **Docker Phase A**: nginx (SPA + LB `/api`) → `api1`/`api2` FastAPI → Atlas.
  JWT stateless nên không cần sticky session.
- **Phase B (chưa bật)**: MongoDB replica set 3 node trong Docker.
- **Secrets**: qua `.env` / `.env.local`, không commit; `.dockerignore` loại `.env`.
