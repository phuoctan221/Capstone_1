# Kiến trúc Hệ thống — SmartVOCAB AI

> Cập nhật theo mã nguồn hiện tại (FastAPI + React + MongoDB Atlas + Mastery/FSRS).
> Tài liệu cũ mô tả Leitner 5 hộp và `flashcard_progress` là luồng chính; hiện
> `flashcard_progress` chỉ còn là dữ liệu legacy, luồng chính dùng **Mastery + FSRS**.
> Ngoài luồng học lõi, codebase còn có speaking, story game, AI chat, level assessment
> và self-service password reset; xem chi tiết ở [api-spec.md](api-spec.md).

## 1. Tổng quan kiến trúc

**Client–Server, REST API, layered monolith** (một backend FastAPI, không phải microservices).
Ba lớp chính: Presentation (React SPA) → Application (FastAPI routers/services) → Data (MongoDB Atlas).
Dịch vụ AI (Google Gemini) là dependency ngoài.

```
┌──────────────────────────────────────────────────────────────┐
│ FRONTEND — React 18 + Vite (SPA)                             │
│  pages/ → components/ → services/(Axios) → hooks/constants   │
│  React Router: route theo role (user / admin) + guard        │
│  Trang phụ: /speaking, /games/story, /assessments, ChatWidget │
│  JWT trong localStorage, interceptor gắn Bearer, 401 → login │
└───────────────────────────┬──────────────────────────────────┘
                            │ HTTP/JSON  (dev: Vite proxy /api)
┌───────────────────────────▼──────────────────────────────────┐
│ BACKEND — FastAPI (async)                                    │
│  routers/  →  services/  →  db/ (Motor async)                │
│  models/ Pydantic · core/config.py (pydantic-settings)       │
│  auth: JWT HS256 + bcrypt, RBAC role đọc từ MongoDB          │
│  ai_service ─► Gemini (chính) / Cloudflare Workers AI (fallback) │
│  mistral_service ─► Mistral (story) · speechace/chivox (nói) │
│  word_validation ─► dictionaryapi.dev + Datamuse             │
└───────────────────────────┬──────────────────────────────────┘
                            │ Motor / MongoDB wire protocol
┌───────────────────────────▼──────────────────────────────────┐
│ DATA — MongoDB Atlas, database `capstone1`                   │
│  users · domains · lessons · vocabularies · exercise_items   │
│  learning_sessions · answer_attempts · user_word_states      │
│  lesson_progress · fsrs_review_logs · quiz_questions         │
│  story_games · speaking_exercises · level_assessment_*        │
│  password_reset_otps · ai_rate_limits                        │
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
│   │   ├── components/       # Navbar, AdminLayout, Flashcard, ChatWidget...
│   │   ├── pages/            # Learn, Speaking, StoryGame, Assessment, Admin...
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
│   │   ├── models/           # Pydantic schemas (incl. story, speaking, chat, assessment)
│   │   ├── routers/          # API endpoints (incl. story, speaking, chat, assessment)
│   │   └── services/         # business logic (incl. mistral, word_validation, chivox)
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

Router hiện có: `/auth`, `/vocabulary` (+ alias GET `/vocabularies`), `/domains`,
`/lessons`, `/learning`, `/progress`, `/admin`, `/speaking`, `/games/story`,
`/chat`, `/assessments`. Mọi router trừ `/auth/register|login` và 3 endpoint reset
mật khẩu đều dùng `Depends(get_current_user)`; riêng `/admin` dùng `require_admin`
ở cấp router. `/uploads` là static mount cho avatar.

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
- Quên mật khẩu: OTP 6 chữ số lưu dạng hash HMAC trong `password_reset_otps`, gửi qua SMTP;
  TTL/cooldown/giới hạn số lần thử nằm ở `settings.PASSWORD_RESET_*`. Xác nhận thành công
  tăng `token_version`.
- Avatar upload lưu file dưới `backend/uploads` (mount `/uploads` ở `main.py`) và ghi
  `avatar_url` vào user. Dùng `AVATAR_MAX_BYTES` để giới hạn dung lượng.

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

### 5.6 Level assessment

`POST /assessments` tạo attempt server-owned (`level_assessment_attempts`, TTL theo
`ASSESSMENT_EXPIRE_MINUTES`) với tối đa `ASSESSMENT_QUESTION_COUNT` câu từ
`exercise_items`. `POST /assessments/attempts/{id}/submit` chấm điểm server-side,
idempotent theo `attempt_id`, lưu result của lần nộp đầu tiên. Đạt
`ASSESSMENT_PASS_PERCENT` → ghi `level_assessment_results` và mở cấp độ tiếp theo
(hoặc nâng `placement_levels`/`learning_level` nếu là placement target). Trạng thái
cho UI Level-Up Hub ở `GET /progress/assessment-status`.

### 5.7 Luyện nói & kiểm tra từ

```
POST /speaking/check-word → dictionaryapi.dev (cache 24h, ≤1000 từ/worker)
                          → Datamuse (gợi ý) → đối chiếu lại từ điển trước khi trả
POST /speaking/exercises  → validate custom_words → lưu speaking_exercises
POST .../items/{i}/score  → audio thô → Speechace/Chivox → lưu results[i]
```

Không có AI sinh định nghĩa; từ không có trong từ điển chỉ được coi là "chưa xác nhận".
Giới hạn request dùng chung collection `ai_rate_limits` (bucket 1 phút, TTL 1 giờ).

### 5.8 Story game & AI chat

- Story game (`/games/story`): chọn 1–7 từ đã học, gọi Mistral JSON mode, validate schema
  (`GeneratedStory`), bắt buộc xuất hiện đúng từ đã chọn, lưu `story_games`; 503 nếu provider
  lỗi. Truyện mẫu là dữ liệu tĩnh, không cần key. Xem [story-game.md](story-game.md).
- AI chat (`POST /chat/messages`): `ChatWidget` gửi kèm tối đa 8 lượt history và ngữ cảnh
  trang/intent/text được chọn; trả lời kèm gợi ý và action link. Chia sẻ rate limit 10/phút.

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
- `ai_service._call_ai()` ưu tiên Gemini; khi Gemini lỗi và có `CF_ACCOUNT_ID` +
  `CF_API_TOKEN` sẽ fallback sang Cloudflare Workers AI. Story game dùng riêng
  `mistral_service`, không đi qua fallback này.

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
| `story_games` | Truyện đã tạo, kèm quiz và lần nộp đầu tiên |
| `speaking_exercises` | Bài luyện nói + kết quả chấm phát âm theo `results[index]` |
| `level_assessment_attempts` | Attempt đánh giá trình độ (TTL `expires_at`) |
| `level_assessment_results` | Kết quả đã đạt theo user/domain/level |
| `password_reset_otps` | OTP hash, TTL, cooldown và số lần thử |
| `ai_rate_limits` | Bucket 1 phút cho AI/speaking/story (TTL 1 giờ) |
| `flashcard_progress` | Legacy Leitner (giữ để tương thích dữ liệu) |

Kho từ vựng được nạp bằng `scripts/import_english_vocab_pipeline.py` (CSV → MongoDB)
và làm giàu bằng `scripts/enrich_vocabularies.py` (IPA từ dictionaryapi.dev,
topic bằng Gemini/keyword, chuẩn hóa `review_status`). Script chỉ điền trường
trống, có backup, lưu tiến độ trong `vocab_enrichment_jobs` và chạy lại an toàn.
`vocab_raw_cache` / `vocab_enrichment_jobs` do script quản lý, không nằm trong
`ensure_indexes()` của backend.

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
| AI | Google Gemini (httpx) → Cloudflare Workers AI | JSON mode, retry + quota handling, fallback |
| Story AI | Mistral (`mistral-small-latest`) | JSON mode, schema validation |
| Pronunciation | Speechace / Chivox (+ ffmpeg) | Chấm audio server-side |
| Dictionary | dictionaryapi.dev + Datamuse | Cache 24h, verify gợi ý |
| Email | SMTP (`SMTP_*`) | OTP quên mật khẩu |
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
