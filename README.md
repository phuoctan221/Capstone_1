
# Capstone_1
# SmartVocab AI
Adaptive English Vocabulary Learning Platform

## Technology Stack
- ReactJS 18 + Vite 6
- Python + FastAPI
- MongoDB
- Google Gemini (chính) / Cloudflare Workers AI (dự phòng) / Mistral (story game)
- Speechace hoặc Chivox (chấm phát âm), Free Dictionary API + Datamuse (kiểm tra từ)

## Team
5 members

## Development
Agile Scrum - 8 Sprints

Ứng dụng học từ vựng tiếng Anh thông minh — gợi ý từ vựng bằng AI (Google Gemini)
và ôn tập theo lịch FSRS (spaced repetition) dựa trên độ thành thạo từng từ.

## Tính năng

- Đăng ký / đăng nhập bằng JWT; mật khẩu băm, email chuẩn hóa chữ thường
- Phân quyền RBAC: `user` và `admin`; role do MongoDB quyết định. Frontend làm mới tài khoản qua `/auth/me` khi khởi động, backend luôn kiểm tra lại và trả `401`/`403`
- Người học: onboarding trình độ/sở thích, dashboard, bài học 3 lĩnh vực (General English, IT & Technology, Business English)
- Luyện tập 3 dạng câu hỏi (Meaning, Spelling, Context) và ôn tập flashcards theo FSRS với 3 chế độ Lật thẻ / Recall / Cloze
- Theo dõi tiến độ: độ thành thạo từ, XP, streak, thống kê theo lĩnh vực/kỹ năng
- Gợi ý từ vựng bằng AI: phiên âm, nghĩa tiếng Việt, ví dụ, đồng/nghĩa trái
- Luyện nói với từ đã học hoặc từ tự nhập; kiểm tra từ bằng Free Dictionary API + Datamuse, chấm phát âm qua Speechace/Chivox
- Trợ lý học tập AI (`ChatWidget`) và AI Story game: truyện có từ đã học, bản dịch và 3 câu hỏi hiểu bài
- Đánh giá trình độ theo lĩnh vực/cấp độ; đạt bài đánh giá sẽ mở cấp độ tiếp theo
- Quên mật khẩu qua OTP email; upload avatar trong hồ sơ
- Trang quản trị `/admin`: dashboard số liệu thật, quản lý người dùng, từ vựng, lĩnh vực, bài học và ngân hàng câu hỏi

## Cấu trúc dự án

```
SmartVOCAB/
├── frontend/     # React 18 + Vite (src/components, pages, services)
├── backend/      # FastAPI + MongoDB (app/core, db, models, routers, services, scripts)
├── docs/         # requirements.md, architecture.md, erd.md, api-spec.md, deployment.md,
│                 # story-game.md, speaking-word-validation.md
└── data/         # sample_vocabulary.json
```

## Thành viên mới: clone và chạy dự án

### 1. Cần cài những gì

| Công cụ | Phiên bản | Bắt buộc | Dùng để |
|---|---|---|---|
| Git | mới nhất | Có | clone, pull, push |
| Python | 3.11+ | Có | chạy backend FastAPI |
| Node.js + npm | 18+ (khuyến nghị 20 LTS) | Có | chạy frontend React/Vite |
| Docker Desktop | mới nhất | Không | chạy toàn bộ bằng container |
| MongoDB | — | Không | dùng Atlas chung, **không cài local** |
| Google Gemini API key | — | Không | bật tính năng gợi ý từ vựng AI |

Kiểm tra nhanh:

```bash
git --version
python --version      # macOS/Linux có thể là python3
node --version
npm --version
docker --version      # chỉ cần nếu chạy bằng Docker
```

### 2. Clone và tạo nhánh làm việc

```bash
git clone https://github.com/phuoctan221/Capstone_1.git
cd Capstone_1

git switch tan                  # nhánh phát triển hiện tại
git switch -c feature/<ten-ban> # tạo nhánh riêng trước khi sửa code
```

- `main`: nhánh ổn định
- `tan`: nhánh phát triển chính của nhóm
- `backup-tan-before-merge`: **chỉ để backup, không commit/push vào**
- Làm việc trên `feature/...` rồi mở PR vào `tan`.

### 3. Tạo `backend/.env`

Lấy `MONGO_URI` từ team lead qua chat/nhóm (không commit chuỗi này). Sau đó:

```bash
cd backend
copy .env.example .env          # Windows (cmd)
# cp .env.example .env          # macOS/Linux
```

Điền tối thiểu:

```ini
MONGO_URI="mongodb+srv://<user>:<password>@<cluster>.mongodb.net/capstone1?authSource=admin"
MONGO_DB_NAME="capstone1"
JWT_SECRET="<chuoi-ngau-nhien>"
GEMINI_API_KEY="<key-rieng-cua-ban>"   # có thể để trống nếu chưa dùng AI
```

Sinh `JWT_SECRET`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

> Muốn thử nghiệm DB riêng mà không ảnh hưởng nhóm: tạo `backend/.env.local` để override `MONGO_URI` (file này cũng bị ignore).

### 4. Chạy local (khuyến nghị khi code)

Terminal 1 — backend:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

- Swagger: http://localhost:8000/docs
- Health: http://localhost:8000/health

Terminal 2 — frontend:

```bash
cd frontend
npm ci
npm run dev
```

Mở http://localhost:5173 (Vite proxy `/api` → `http://localhost:8000`).

### 5. Hoặc chạy bằng Docker

```bash
# backend/.env phải tồn tại trước
docker compose up -d --build
docker compose ps
```

Mở http://localhost:8080. Chi tiết và xử lý sự cố: xem mục **Chạy bằng Docker** bên dưới.

### 6. Nạp dữ liệu từ vựng (tùy chọn)

DB dùng chung đã có sẵn kho từ. Chỉ chạy khi cần dựng lại dữ liệu hoặc thêm từ mới.

```bash
cd backend

# 1) CSV -> MongoDB (resumable, tự tạo unique word_key)
.venv\Scripts\python.exe scripts\import_english_vocab_pipeline.py --limit 10   # thử 10 từ
.venv\Scripts\python.exe scripts\import_english_vocab_pipeline.py             # toàn bộ CSV

# 2) Làm giàu: IPA, synonyms/antonyms, topic/domain, review_status
.venv\Scripts\python.exe scripts\enrich_vocabularies.py --dry-run --sample 50
.venv\Scripts\python.exe scripts\enrich_vocabularies.py --apply --fields all --rpm 60
.venv\Scripts\python.exe scripts\enrich_vocabularies.py --apply --fields phonetic --words apple,book

# 3) Seed domains + lessons + ngân hàng câu hỏi
.venv\Scripts\python.exe scripts\seed_mvp.py --apply --allow-shared
```

- `enrich_vocabularies.py` chỉ điền trường đang trống, không ghi đè `meaning`/`example`; tự backup vào `backend/data/enrichment_backup_*.json` trước khi ghi.
- IPA lấy từ dictionaryapi.dev (mặc định 60 rpm); topic phân loại bằng Gemini theo 3 lĩnh vực MVP, fallback keyword. Tiến độ lưu ở `vocab_enrichment_jobs` nên có thể dừng và chạy lại.
- `seed_mvp.py` chỉ tạo từ còn thiếu, giữ nguyên dữ liệu đã làm giàu. Dùng `--skip-vocabulary` khi chỉ muốn dựng lại lessons/exercise bank sau khi đổi `domain`.
- Bộ mẫu nhỏ: `scripts\import_sample_vocabulary.py` (xem mục **Dữ liệu mẫu**).

### 7. Checklist sau khi chạy

- [ ] `GET /health` trả `"status":"ok"` và đúng database
- [ ] Mở frontend, thấy trang đăng nhập
- [ ] Đăng ký / đăng nhập được
- [ ] Thêm / sửa / xóa một từ vựng
- [ ] (Nếu có key) thử gợi ý từ vựng AI, trò chuyện với trợ lý và tạo truyện ở `/games/story`
- [ ] Ở `/speaking`, kiểm tra một từ và thử chấm phát âm (cần key Speechace hoặc Chivox)
- [ ] Viết lại mật khẩu qua `/forgot-password` (cần cấu hình SMTP)
- [ ] Tạo tài khoản admin (xem mục dưới) và mở được `/admin`

### 8. Tài khoản admin

Đăng ký công khai **luôn** tạo role `user`. Không có cơ chế tự động nâng quyền theo email.
Tạo admin đầu tiên bằng script (chạy trong `backend/`, dùng đúng `MONGO_URI` trong `.env`):

```bash
# Tạo mới hoặc nâng quyền; mật khẩu nhập ẩn qua getpass
.venv\Scripts\python.exe scripts\create_admin.py --email admin@example.com

# Chỉ nâng quyền một tài khoản đã đăng ký
.venv\Scripts\python.exe scripts\create_admin.py --email admin@example.com --promote-only

# Đặt lại mật khẩu admin
.venv\Scripts\python.exe scripts\create_admin.py --email admin@example.com --reset-password
```

Có thể truyền mật khẩu qua biến môi trường `SMARTVOCAB_ADMIN_PASSWORD` (không truyền qua tham số dòng lệnh).
Với Docker, dùng `docker compose exec api1 python scripts/create_admin.py --email admin@example.com`.

Sau khi đăng nhập bằng tài khoản admin, giao diện quản trị nằm tại `/admin`; người dùng thường chỉ thấy `/dashboard`.
API `/admin/*` đều yêu cầu role `admin` và trả `403` cho tài khoản khác.

Giao diện được tách theo vai trò:

- **Người học** dùng `Navbar` và các trang `/dashboard`, `/learn`, `/progress`, `/flashcards`, `/speaking`, `/games/story`, `/vocabulary`, `/profile`; ngoài ra có `/assessments/:domain/:level`, `/settings/learning` và `/forgot-password`.
- **Admin** dùng `AdminLayout` tại `/admin` (tổng quan, người dùng, từ vựng, lĩnh vực, bài học, câu hỏi).
- Admin mở đường dẫn người học sẽ được chuyển về `/admin`; người học mở `/admin` sẽ bị chuyển về `/dashboard`.
- Khi token hết hạn hoặc không hợp lệ, frontend xóa phiên và đưa về `/login`; quyền thực tế luôn do backend kiểm tra.

### 9. Kiểm thử backend

```bash
cd backend
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Bộ test dùng MongoDB Atlas thật qua `backend/tests/support.py` (database `capstone1_mvp_test`),
vì vậy cần `MONGO_URI` hợp lệ và mạng ổn định. Có thể chạy riêng từng nhóm, ví dụ
`python -m unittest tests.test_story tests.test_speaking tests.test_word_validation tests.test_chivox tests.test_assessment`.
Frontend chưa có unit test tự động; kiểm tra bằng `npm run build` và hai script browser thủ công trong `frontend/tests/`.

### 10. Lỗi thường gặp

| Lỗi | Cách xử lý |
|---|---|
| `Chua cau hinh MONGO_URI` | Chưa tạo hoặc chưa điền `backend/.env` |
| `MongoDB xac thuc that bai` | Sai user/password hoặc IP chưa whitelist trên Atlas; chạy `python scripts/check_mongo.py` |
| `ModuleNotFoundError: app` | Phải đứng trong thư mục `backend/` khi chạy `uvicorn` |
| Port bận (`EADDRINUSE`) | Đổi port hoặc tắt process đang dùng 5173/8000/8080 |
| `npm ci` lỗi | Kiểm tra Node ≥ 18 (`node -v`), xóa `node_modules` rồi chạy lại |
| CORS error | Thêm origin frontend vào `CORS_ORIGINS` trong `backend/.env` |
| Docker: `failed to connect to the docker API` | Mở Docker Desktop và chờ engine chạy |

### 11. Quy ước Git

- `git pull --ff-only` trước khi bắt đầu làm.
- Không commit: `backend/.env`, `.env.local`, `.venv/`, `node_modules/`, `dist/`, file dump/keyfile.
- Không force-push; không push trực tiếp vào `main` hoặc `backup-tan-before-merge`.
- Commit message ngắn, rõ: `feat: ...`, `fix: ...`, `docs: ...`.

### 12. Giới hạn còn lại (MVP)

- Role được cache trong `localStorage` để hiển thị UI; đây chỉ là gợi ý. Backend đọc role từ MongoDB ở mọi request nên sửa `localStorage` không cấp được quyền.
- JWT đang lưu trong `localStorage`, chưa có refresh token/rotation. Phù hợp MVP; nếu triển khai công khai nên chuyển sang cookie `httpOnly` + `Secure`.
- Chưa có rate limiting, audit log thao tác admin hoặc khóa tài khoản.
- Ba lĩnh vực là cố định theo MVP; admin sửa được tên/mô tả/thứ tự/trạng thái nhưng không tạo hoặc xóa lĩnh vực.
- Câu hỏi được sinh tự động từ từ vựng; admin có thể tạo/sửa/xóa/tắt/tái tạo cả qua UI lẫn API. Đáp án luôn nằm ở server.
- Xóa bài học chỉ xóa metadata; phải xóa hoặc chuyển từ vựng trước, nếu không backend trả `409`.
- Test backend cần MongoDB Atlas; khi không kết nối được, test được skip thay vì fail. Frontend chưa có unit test tự động, hiện kiểm tra bằng `npm run build`.
- Luyện nói cần mạng và key Speechace hoặc Chivox; story game cần `MISTRAL_API_KEY`, còn quên mật khẩu cần cấu hình SMTP. Các luồng học chính vẫn chạy khi thiếu các key này.
- Docker Phase A chưa có TLS và chạy `api1`/`api2` trên cùng một host; Phase B (replica set 3 node) chưa bật.
- Đổi/xóa user qua admin chưa lan sang dữ liệu story/speaking/assessment (chỉ các collection học tập lõi); xem `docs/erd.md`.

## MongoDB Atlas — database dùng chung

Cả team dùng chung **một cluster Atlas**, nên không ai phải cài MongoDB local hay mở Docker.

### Thành viên mới cần làm gì

1. Lấy connection string từ team lead (gửi qua kênh chat/nhóm dự án — **không commit vào git**):

   ```
   mongodb+srv://<user>:<password>@<cluster>.mongodb.net/capstone1?authSource=admin
   ```

2. Tạo file cấu hình:

   ```bash
   cd backend
   copy .env.example .env      # Windows
   # cp .env.example .env      # macOS/Linux
   ```

3. Điền vào `backend/.env`:

   ```ini
   MONGO_URI="mongodb+srv://<user>:<password>@<cluster>.mongodb.net/capstone1?authSource=admin"
   MONGO_DB_NAME="capstone1"
   GEMINI_API_KEY="<key-ca-nhan-ban>"     # mỗi người dùng key riêng để tránh tranh chấp quota
   JWT_SECRET="<chuoi-ngau-nhien-cua-ban>"
   ```

4. Chạy `uvicorn` + `npm run dev` (xem mục **Thành viên mới**), hoặc `docker compose up -d --build`.

> `backend/.env` đã nằm trong `.gitignore` — không ai push file này lên git.

### Điều kiện phía Atlas (team lead thiết lập một lần)

| Mục | Yêu cầu |
|---|---|
| Network Access → IP Access List | Cho phép IP của từng thành viên. Với cluster dev, dùng `0.0.0.0/0` cho tiện (đã ghi chú ở mục Security) |
| Database Access | User dùng chung phải có role `readWrite` trên database `capstone1` |
| Authentication Database | Nếu connection string có `?authSource=admin` thì user phải được tạo trong database `admin` |

### Chẩn đoán kết nối

```bash
cd backend
.venv\Scripts\python.exe scripts\check_mongo.py
```

Script kiểm tra lần lượt DNS/SRV → TCP/TLS → xác thực SCRAM → quyền trên database → index,
và chỉ ra chính xác lớp nào đang hỏng kèm hướng khắc phục.

### Trỏ sang cluster / database khác khi phát triển

`backend/app/core/config.py` đọc config theo thứ tự ưu tiên:

```
1. Biến môi trường hệ thống   (MONGO_URI=... trong terminal)
2. backend/.env.local          (override cục bộ — xóa file này để dùng .env)
3. backend/.env                (config dùng chung)
4. Giá trị mặc định trong Settings
```

Nhờ vậy bạn có thể trỏ cluster chính trong `.env` mà vẫn dev trên cluster cá nhân qua `backend/.env.local`.
Backend luôn in ra database đang dùng khi khởi động, và `/health` trả về thông tin này.

## Biến môi trường (`backend/.env`)

| Biến | Mô tả |
|---|---|
| `MONGO_URI` | Chuỗi kết nối MongoDB Atlas (`mongodb+srv://...`) |
| `MONGO_DB_NAME` | Tên database (`capstone1`) |
| `MONGO_TIMEOUT_MS` | Timeout chọn server (mặc định 10000 ms) |
| `JWT_SECRET` | Chuỗi bí mật ký JWT |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Thời hạn JWT (mặc định 1440) |
| `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_RPM` | Gợi ý từ/trợ lý/phân tích lỗi; model mặc định `gemini-3.8-flash` |
| `MISTRAL_API_KEY`, `MISTRAL_MODEL` | AI Story game; model mặc định `mistral-small-latest` |
| `CF_ACCOUNT_ID`, `CF_API_TOKEN`, `CF_MODEL`, `CF_RPM` | Cloudflare Workers AI, fallback khi Gemini lỗi |
| `DICTIONARY_RPM` | Giới hạn gọi dictionaryapi.dev khi kiểm tra từ |
| `SPEECHACE_API_KEY`, `SPEECHACE_URL`, `SPEECHACE_DIALECT` | Chấm phát âm qua Speechace |
| `PRONUNCIATION_PROVIDER`, `CHIVOX_API_KEY`, `FFMPEG_PATH` | Đổi sang Chivox và cấu hình ffmpeg |
| `AVATAR_MAX_BYTES` | Dung lượng tối đa ảnh đại diện (mặc định 2 MB) |
| `SMTP_*`, `PASSWORD_RESET_*` | Gửi OTP quên mật khẩu; xem `backend/.env.example` |
| `ASSESSMENT_*` | Số câu, ngưỡng đạt, TTL và cooldown của bài đánh giá |
| `MASTERY_*`, `SESSION_MAX_QUESTIONS`, `MIN_LESSON_WORDS` | Ngưỡng Mastery và giới hạn engine bài tập |
| `CORS_ORIGINS` | Danh sách origin được phép |

## Dữ liệu mẫu

Script nạp bộ từ vựng mẫu vào MongoDB (tự đọc `MONGO_URI` / `MONGO_DB_NAME` từ `backend/.env`):

```bash
cd backend
.venv\Scripts\python.exe scripts\import_sample_vocabulary.py            # thêm mới / cập nhật
.venv\Scripts\python.exe scripts\import_sample_vocabulary.py --dry-run  # chỉ kiểm tra, không ghi
.venv\Scripts\python.exe scripts\import_sample_vocabulary.py --mode replace   # xóa collection rồi nạp lại
```

Các chế độ: `upsert` (mặc định), `insert-only` (bỏ qua từ đã có), `replace` (xóa `vocabularies` rồi nạp lại).
Script tự gán `created_at` / `updated_at` còn thiếu trong file JSON và tạo text index cho `word` + `meaning`.

Nếu đã cài `mongoimport` thì vẫn dùng được cách cũ:

```bash
mongoimport --uri "mongodb+srv://<user>:<password>@<cluster>.mongodb.net/capstone1?authSource=admin" \
  --collection vocabularies \
  --jsonArray \
  --file data/sample_vocabulary.json
```

## Chạy bằng Docker (Phase A — giữ MongoDB Atlas)

Kiến trúc: `nginx` phục vụ SPA + cân bằng tải `/api` tới **2 backend** (`api1`, `api2`), cả hai dùng chung `backend/.env` và kết nối Atlas hiện tại.

```
Browser :8080 ──► web (nginx) ──► api1 / api2 (FastAPI) ──► MongoDB Atlas
                    │ /            (SPA + fallback)
                    └ /api/*       (least_conn, strip /api)
```

### Yêu cầu

- Docker Desktop (Docker Engine + Docker Compose v2) đang chạy
- `backend/.env` có `MONGO_URI` trỏ Atlas (Phase A **không** di chuyển dữ liệu)

### Cấu trúc container

| Service | Vai trò | Cổng host |
|---|---|---|
| `web` | Nginx: serve React build + cân bằng tải `/api` | `8080` (đổi bằng `WEB_PORT`) |
| `api1`, `api2` | FastAPI + Motor, dùng chung `backend/.env` | không mở ra host |
| `smartvocab` | Network nội bộ giữa các container | — |

### Lần đầu chạy

```bash
# 1. Chuẩn bị env — CHỈ copy khi chưa có, không ghi đè .env thật
# Windows (cmd)
if not exist backend\.env copy backend\.env.example backend\.env
# macOS/Linux
[ -f backend/.env ] || cp backend/.env.example backend/.env

# rồi điền MONGO_URI / JWT_SECRET / GEMINI_API_KEY trong backend/.env
# .env.docker.example là bản tham khảo cho Docker + Phase B

# 2. Build và chạy
docker compose up -d --build

# 3. Kiểm tra
docker compose ps
curl http://localhost:8080/healthz
curl http://localhost:8080/api/health     # Windows PowerShell: curl.exe ...
```

Mở app tại **http://localhost:8080**.

### Lệnh thường dùng

```bash
docker compose ps                      # trạng thái + healthcheck
docker compose logs -f api1            # log backend
docker compose logs -f web             # log nginx
docker compose restart api1            # restart 1 service
docker compose up -d --build           # rebuild sau khi sửa code
docker compose down                    # dừng, GIỮ dữ liệu Atlas
```

Đổi cổng web (khi 8080 bị chiếm):

```powershell
$env:WEB_PORT=9090; docker compose up -d
# bash: WEB_PORT=9090 docker compose up -d
```

### Kiểm tra nhanh

- `web` healthy: `curl http://localhost:8080/healthz` → `ok`
- API + MongoDB: `curl http://localhost:8080/api/health` → `"status":"ok"`
- Trang đăng nhập render tại `/login`, gọi API qua `/api/...`
- Tài khoản admin vào `/admin`; tài khoản `user` vào `/dashboard` và bị chặn khỏi `/admin`

### Xử lý sự cố

| Lỗi | Cách xử lý |
|---|---|
| `failed to connect to the docker API` | Mở Docker Desktop, chờ engine chạy rồi thử lại |
| `THESE PACKAGES DO NOT MATCH THE HASHES` khi `pip install` | Lỗi mạng/tải dở; chạy lại `docker compose build api1` |
| `port is already allocated` | Đổi `WEB_PORT` như trên |
| `api1`/`api2` unhealthy | `docker compose logs api1`; kiểm tra `MONGO_URI` trong `backend/.env` |
| Sửa code nhưng app không đổi | `docker compose up -d --build` |
| Nginx không thấy `api1/api2` sau khi recreate | `docker compose restart web` |

> **Dữ liệu:** Phase A dùng Atlas nên `docker compose down` không làm mất dữ liệu. **Không** chạy `docker compose down -v` — sẽ xóa volume MongoDB khi chuyển sang Phase B. Không commit `backend/.env`, keyfile hay file dump.

Chi tiết rollback, bảo toàn dữ liệu và lộ trình Replica Set: [docs/deployment.md](docs/deployment.md).

## Tài liệu thiết kế

- [Nhu cầu hệ thống](docs/requirements.md)
- [Kiến trúc](docs/architecture.md)
- [ERD](docs/erd.md)
- [API Specification](docs/api-spec.md)
- [Triển khai Docker](docs/deployment.md)
- [AI Story game](docs/story-game.md)
- [Kiểm tra từ khi luyện nói](docs/speaking-word-validation.md)
