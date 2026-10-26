
# Capstone_1
# SmartVocab AI
Adaptive English Vocabulary Learning Platform

## Technology Stack
- ReactJS + Vite
- Python + FastAPI
- MongoDB

## Team
5 members

## Development
Agile Scrum - 8 Sprints

Ứng dụng học từ vựng tiếng Anh thông minh — gợi ý từ vựng bằng AI (Google Gemini)
và ôn tập theo hệ thống Leitner 5 hộp (spaced repetition).

## Tính năng

- Đăng ký / đăng nhập bằng JWT
- Quản lý từ vựng: thêm, sửa, xóa, tìm kiếm, lọc theo trình độ (A1–C2) và chủ đề
- Gợi ý từ vựng bằng AI: phiên âm, nghĩa tiếng Việt, ví dụ, đồng/nghĩa trái
- Ôn tập flashcards theo Leitner 5 hộp với thống kê học tập

## Cấu trúc dự án

```
SmartVOCAB/
├── frontend/     # React 18 + Vite (src/components, pages, services)
├── backend/      # FastAPI + MongoDB (app/core, db, models, routers, services, scripts)
├── docs/         # requirements.md, architecture.md, erd.md, api-spec.md
└── data/         # sample_vocabulary.json
```

## Yêu cầu hệ thống

- Python 3.11+
- Node.js 18+
- MongoDB Atlas — dùng chung một cluster cho cả team, **không cần cài Docker hay MongoDB local**
- API key Google Gemini (tùy chọn — cho tính năng AI gợi ý)

## Chạy dự án

### Cách nhanh nhất

Double-click `start.bat`. Script sẽ tự:

1. Kiểm tra Python/Node đã cài chưa
2. Tạo `backend/.env` từ `.env.example` nếu chưa có
3. Tạo virtualenv + cài `requirements.txt` (nếu chưa có)
4. `npm install` (nếu chưa có `node_modules`)
5. Mở Backend (`:8000`) và Frontend (`:5173`), tự mở trình duyệt khi backend sẵn sàng

### Thủ công

```bash
# 1. Backend
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

pip install -r requirements.txt
copy .env.example .env          # Windows — rồi điền MONGO_URI + GEMINI_API_KEY
# cp .env.example .env          # macOS/Linux

uvicorn app.main:app --reload --port 8000
```

Swagger UI: http://localhost:8000/docs

```bash
# 2. Frontend
cd frontend
npm install
npm run dev
```

App: http://localhost:5173 (proxy `/api` → backend `:8000`)

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

4. Chạy `start.bat` hoặc `uvicorn` + `npm run dev` như trên.

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
| `GEMINI_API_KEY` | API key Google Gemini (để bật AI) |
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
