# Kiến trúc Hệ thống — SmartVOCAB AI

## 1. Tổng quan kiến trúc

Kiến trúc Client–Server với REST API, 3 lớp:

```
┌─────────────────────────────────────────────┐
│                FRONTEND (React)             │
│   Pages → Components → Services (Axios)     │
└──────────────────────┬──────────────────────┘
                       │ HTTP/JSON (JWT Bearer)
┌──────────────────────▼──────────────────────┐
│              BACKEND (FastAPI)              │
│  Routers → Services → DB (Motor/MongoDB)    │
│                    ↘ AI Service → Gemini    │
└──────────────────────┬──────────────────────┘
                       │
              ┌────────▼────────┐
              │    MongoDB      │
              │ smartvocab DB   │
              └─────────────────┘
```

## 2. Cấu trúc thư mục

```
smartvocab-ai/
├── frontend/          # React + Vite
│   ├── src/
│   │   ├── components/    # UI dùng lại (Navbar, Flashcard, ...)
│   │   ├── pages/         # Route-level pages
│   │   ├── services/      # Axios API layer
│   │   ├── App.jsx
│   │   └── main.jsx
│   └── package.json
├── backend/           # FastAPI
│   ├── app/
│   │   ├── main.py        # App entry, CORS, router mount
│   │   ├── core/          # config.py (pydantic-settings)
│   │   ├── db/            # mongodb.py (Motor async client)
│   │   ├── models/        # Pydantic schemas
│   │   ├── routers/       # API endpoints
│   │   └── services/      # Business logic
│   └── requirements.txt
├── docs/              # Tài liệu thiết kế
├── data/              # Dữ liệu mẫu
└── README.md
```

## 3. Luồng xác thực

```
Client                     Backend
  │  POST /auth/login        │
  │ ────────────────────────►│ verify bcrypt
  │  {access_token, user}    │ sign JWT (HS256)
  │ ◄────────────────────────│
  │                          │
  │  GET /vocabulary         │
  │  Authorization: Bearer   │
  │ ────────────────────────►│ decode JWT → get_current_user
  │  {items, total}          │
  │ ◄────────────────────────│
```

## 4. Luồng AI Generate

```
User nhập "ephemeral"
  → POST /vocabulary/ai-generate {word}
  → ai_service gọi Gemini API (JSON mode, temp 0.2)
  → Parse JSON: phonetic, meaning, example, synonyms...
  → Trả về form đã điền sẵn
  → User bấm "Lưu từ vựng" → POST /vocabulary
```

Fallback: nếu thiếu `GEMINI_API_KEY`, endpoint trả 502 kèm thông báo.

## 5. Leitner Spaced Repetition

```
            ┌──────────┐
   correct  │ Box 5    │ 7 ngày
            │ (master) │──────────┐
            └──────────┘          │
                 ▲                ▼
            ┌──────────┐   ┌──────────┐
            │ Box 4    │   │ Box 3    │ 1 ngày
            │ 3 ngày   │   │          │
            └──────────┘   └──────────┘
                 ▲                ▼
            ┌──────────┐   ┌──────────┐
            │ Box 2    │   │ Box 1    │ 10 phút
            │ 1 giờ    │   │          │
            └──────────┘   └──────────┘
                 ▲                ▲
                 └── wrong ───────┘
```

- Đúng → lên 1 hộp, `next_review = now + interval[box]`
- Sai → lùi về hộp 1
- Chỉ hiển thị thẻ có `next_review <= now`

## 6. Công nghệ

| Thành phần | Lựa chọn | Lý do |
|---|---|---|
| Web framework | FastAPI | Async, type hints, OpenAPI tự sinh |
| DB | MongoDB | Schema linh hoạt cho từ vựng |
| ORM-like | Motor | Driver async chính thức cho MongoDB |
| Auth | JWT + bcrypt | Stateless, chuẩn ngành |
| AI | Gemini 1.5 Flash | Nhanh, rẻ, JSON mode |
| Frontend | React + Vite | Dev server nhanh, bundle nhỏ |
| HTTP client | Axios | Interceptor cho JWT & 401 |

## 7. Chiến lược triển khai

- **Dev**: MongoDB Atlas (cluster dùng chung cho cả team) + `uvicorn --reload` + `npm run dev`
- **Prod**: Uvicorn/Gunicorn sau Nginx, MongoDB Atlas, frontend build tĩnh trên CDN
- **Secrets**: qua `.env`, không commit lên git
