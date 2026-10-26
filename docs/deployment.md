# Triển khai Docker — SmartVOCAB AI

## 1. Kiến trúc Phase A (hiện tại)

```
Browser
  │  :8080
  ▼
┌──────────────────────────────────────────────┐
│ web (nginx:1.27-alpine)                      │
│  /            → React build (SPA fallback)   │
│  /api/*       → upstream api1 / api2         │
│  /healthz     → 200 ok                       │
└───────────────┬──────────────────────────────┘
        least_conn│
        ┌─────────┴─────────┐
        ▼                   ▼
   ┌─────────┐         ┌─────────┐
   │ api1    │         │ api2    │   FastAPI + Motor
   │ :8000   │         │ :8000   │   (JWT stateless)
   └────┬────┘         └────┬────┘
        └─────────┬─────────┘
                  ▼
        MongoDB Atlas (shared cluster)
```

- JWT stateless nên round-robin/least_conn **không cần sticky session**.
- Cả `api1`, `api2` đọc cùng `backend/.env`; **không có secret nào nằm trong image**.
- Nginx strip tiền tố `/api` (`/api/vocabulary` → `/vocabulary`), khớp Vite proxy khi dev.
- Phase A **không di chuyển dữ liệu**: vẫn dùng Atlas, không ghi/xóa dữ liệu Atlas ngoài việc backend tạo index idempotent lúc khởi động.

## 2. Chạy Phase A

```bash
copy .env.docker.example backend\.env
# điền MONGO_URI (Atlas), JWT_SECRET, GEMINI_API_KEY

docker compose up -d --build
docker compose ps
```

Kiểm tra:

```bash
curl http://localhost:8080/healthz          # ok
curl http://localhost:8080/api/health       # JSON: status, database, mongo
docker compose logs -f api1
docker compose logs -f web
```

- App: http://localhost:8080
- Đổi cổng: `WEB_PORT=9090 docker compose up -d` (PowerShell: `$env:WEB_PORT=9090; docker compose up -d`)
- Swagger trực tiếp (nếu cần): `docker compose exec api1 python -c "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:8000/docs').status)"` hoặc map port tạm.

## 3. Vận hành & rollback

```bash
docker compose restart api1
docker compose logs --tail=200 api2
docker compose down            # dừng, KHÔNG xóa volume
docker compose up -d --build   # rebuild sau khi sửa code
```

Rollback code: quay lại branch/commit trước đó rồi `docker compose up -d --build`.
Vì Phase A dùng Atlas, `docker compose down` **không ảnh hưởng dữ liệu**.

> Không chạy `docker compose down -v` khi đã chuyển sang Phase B (sẽ xóa volume MongoDB).

## 4. Biến môi trường

Compose đọc `backend/.env` qua `env_file`. Mẫu đầy đủ ở `.env.docker.example`.

| Biến | Ghi chú |
|---|---|
| `MONGO_URI` | Phase A: `mongodb+srv://...` của Atlas |
| `MONGO_DB_NAME` | `capstone1` |
| `JWT_SECRET` | Chuỗi ngẫu nhiên, không commit |
| `GEMINI_API_KEY` | Key riêng từng người |
| `CORS_ORIGINS` | JSON array; same-origin qua nginx nên thường không cần đổi |

Backend có thêm `retryWrites=True`, `appname`, timeout kết nối trong `app/db/mongodb.py` để phù hợp cả Atlas lẫn replica set.

## 5. Giới hạn đã biết

- `api1` và `api2` chạy **cùng một máy** → tăng khả năng chịu lỗi process, không chống hỏng host.
- Nginx resolve `api1`/`api2` lúc khởi động. Nếu container API bị tạo lại và đổi IP, chạy `docker compose restart web`.
- Log đang ghi ra stdout; muốn lưu file dài hạn cần thêm driver logging/volume.

## 6. Chuẩn bị Phase B — MongoDB Replica Set 3 node

Chưa bật. Khi được duyệt, bổ sung service `mongo1..3` + `mongo-init` với:

- `--replSet rs0 --bind_ip_all --keyFile /etc/mongo/keyfile`
- Named volume riêng `mongo_data1..3`
- Keyfile 600, không commit (đã ignore `mongo-keyfile`)
- `deploy/mongo/init-replica.sh` chạy **bên trong `mongo1`** (localhost exception) để `rs.initiate` và tạo app user
- URI: `mongodb://mongo1:27017,mongo2:27017,mongo3:27017/capstone1?replicaSet=rs0&retryWrites=true&w=majority`

### Quy trình chuyển dữ liệu an toàn

1. **Backup Atlas** (không sửa Atlas):
   ```bash
   mongodump --uri "$MONGO_URI" --out backups/atlas-$(date +%Y%m%d)
   ```
2. Đếm document các collection chính (`users`, `vocabularies`, `flashcard_progress`, `lesson_progress`).
3. Khởi động `mongo1..3`, chạy `init-replica.sh`, chờ `rs.status()` có PRIMARY.
4. `mongorestore --uri "mongodb://...replicaSet=rs0" backups/atlas-...`
5. So sánh số document; chạy `api1` với URI mới; test `/api/health` + đăng nhập.
6. Giữ Atlas nguyên trạng để rollback (chỉ cần đổi lại `MONGO_URI`).

### Kiểm tra failover

```bash
docker compose exec mongo1 mongosh --quiet --eval "rs.status().members.map(m => [m.name, m.stateStr])"
docker compose stop mongo1          # driver tự bầu primary mới
curl http://localhost:8080/api/health
docker compose start mongo1
```

## 7. Bảo mật

- Không commit `backend/.env`, keyfile, dump.
- `.dockerignore` loại `.env`, `.venv`, `node_modules`, `__pycache__`.
- Container backend chạy user không phải root.
- Nếu public internet: thêm TLS (Caddy/Traefik hoặc certbot) trước nginx, giới hạn CORS, và IP access list Atlas.
