# SmartVOCAB AI — Tài liệu Nhu cầu (Requirements)

> Cập nhật theo phạm vi MVP hiện tại: 3 lĩnh vực, Mastery đa kỹ năng + FSRS,
> RBAC `user`/`admin`. Leitner 5 hộp chỉ còn là dữ liệu legacy.

## 1. Tổng quan

SmartVOCAB AI là nền tảng học từ vựng tiếng Anh thích ứng (adaptive), hỗ trợ:

- Kho từ vựng dùng chung theo 3 lĩnh vực: General English, IT & Technology, Business English.
- Gợi ý từ vựng bằng AI (Google Gemini): phiên âm, nghĩa tiếng Việt, ví dụ, đồng/nghĩa trái.
- Luyện tập 3 kỹ năng: Meaning, Spelling, Context (cloze) và quiz theo bài học.
- Theo dõi **Mastery** từng từ theo 3 kỹ năng độc lập.
- Ôn tập theo lịch **FSRS** (spaced repetition).
- Theo dõi tiến độ: XP, level, streak, thống kê theo lĩnh vực/kỹ năng.
- Trang quản trị `/admin` cho quản lý người dùng, từ vựng, lĩnh vực, bài học, ngân hàng câu hỏi.

## 2. Người dùng (Actors)

| Vai trò | Mô tả |
|---|---|
| Guest | Đăng ký / đăng nhập; chưa vào được khu vực học |
| Learner (`role = user`) | Onboarding, học bài, luyện tập, ôn FSRS, xem tiến độ, quản lý hồ sơ |
| Admin (`role = admin`) | Toàn bộ quyền learner (dùng giao diện admin) + quản trị dữ liệu người dùng, từ vựng, lĩnh vực, bài học, câu hỏi |

- Role lưu trong MongoDB; đăng ký công khai luôn tạo `user`.
- Admin tạo/nâng quyền bằng `backend/scripts/create_admin.py` hoặc qua API admin.

## 3. Chức năng bắt buộc (Must have)

### FR-AUTH — Xác thực & tài khoản
- FR-AUTH-01: Đăng ký (email, username, password); email chuẩn hóa lowercase.
- FR-AUTH-02: Đăng nhập, nhận JWT (`sub` = email, có `token_version`).
- FR-AUTH-03: Lấy/cập nhật hồ sơ hiện tại (`GET/PUT /auth/me`).
- FR-AUTH-04: Onboarding trình độ CEFR + lĩnh vực quan tâm (`POST /auth/onboarding`).
- FR-AUTH-05: Đổi mật khẩu; tăng `token_version` → thu hồi token cũ.
- FR-AUTH-06: Tự đăng xuất phía client khi token hết hạn/không hợp lệ (`401`).
- FR-AUTH-07: Tài khoản bị khóa (`is_active=false`) không đăng nhập được (`403`).

### FR-DOMAIN — Lĩnh vực
- FR-DOMAIN-01: Hiển thị 3 lĩnh vực MVP đang active.
- FR-DOMAIN-02: Từ vựng legacy (`topic`) được map đúng về `domain`.

### FR-VOCAB — Kho từ vựng
- FR-VOCAB-01: Xem danh sách từ vựng (phân trang).
- FR-VOCAB-02: Tìm kiếm theo từ/nghĩa (text index).
- FR-VOCAB-03: Lọc theo `domain`, `level` (A1–C2).
- FR-VOCAB-04: Thêm từ thủ công (learner/admin) và chỉnh sửa.
- FR-VOCAB-05: Xóa từ vựng (chỉ admin).
- FR-VOCAB-06: Gợi ý từ bằng AI (single); sinh hàng loạt (admin).

### FR-LESSON — Bài học
- FR-LESSON-01: Danh sách bài học theo `domain` + `level`, kèm tiến độ/đã hoàn thành.
- FR-LESSON-02: Chi tiết bài học + danh sách từ.
- FR-LESSON-03: Quiz theo bài học (`GET /lessons/{id}/quiz`) và nộp bài
  (`POST /lessons/{id}/quiz/submit`), chấm điểm server-side.

### FR-LEARN — Luyện tập & phiên học
- FR-LEARN-01: Tạo phiên luyện tập theo bài học, chọn kỹ năng và số câu.
- FR-LEARN-02: Nhận câu hỏi (không kèm đáp án) và nộp từng câu trả lời.
- FR-LEARN-03: Chấm điểm server-side, chống trả lời lại cộng điểm (idempotent theo `attempt_id`).
- FR-LEARN-04: Kết thúc phiên, tính %, đạt nếu ≥ 70%; cập nhật hoàn thành bài học.
- FR-LEARN-05: Ôn flashcard theo FSRS: danh sách đến hạn, đánh giá 1–4, thống kê; hỗ trợ 3 chế độ Lật thẻ, Recall (gõ nghĩa) và Cloze (điền từ vào câu ví dụ).
- FR-LEARN-06: Xem kế hoạch học hằng ngày (mục tiêu, từ cần ôn, từ mới, tiến bộ 7 ngày) và bật/tắt nhắc nhở trên trình duyệt.

### FR-PROGRESS — Tiến độ & Mastery
- FR-PROGRESS-01: Xem tổng quan tiến độ (XP, level, streak, số từ học/thuộc, bài hoàn thành).
- FR-PROGRESS-02: Xem tổng hợp theo lĩnh vực/kỹ năng.
- FR-PROGRESS-03: Xem phân rã Mastery theo kỹ năng.
- FR-PROGRESS-04: Xem lịch sử trả lời gần đây.
- FR-PROGRESS-05: Ghi nhận câu trả lời thủ công (`/progress/study-answer`) cho luồng study.

### FR-ADMIN — Quản trị (RBAC)
- FR-ADMIN-01: Dashboard số liệu thật (users, từ vựng, bài học, câu hỏi).
- FR-ADMIN-02: Quản lý người dùng: danh sách/tìm kiếm/lọc role, chi tiết, sửa,
  khóa/mở, reset mật khẩu, đổi role, xóa.
- FR-ADMIN-03: CRUD từ vựng.
- FR-ADMIN-04: Sửa lĩnh vực (tên, mô tả, thứ tự, active); khôi phục mặc định.
- FR-ADMIN-05: Quản lý metadata bài học; xem từ của bài.
- FR-ADMIN-06: Quản lý ngân hàng câu hỏi: xem/sửa/xóa/tạo/tái sinh.
- FR-ADMIN-07: Mọi endpoint `/admin/*` yêu cầu `role = admin` (kiểm tra từ DB).

## 4. Chức năng nâng cao (Could have)

- FR-NB-01: Phát âm từ bằng Web Speech API.
- FR-NB-02: Nhập từ vựng hàng loạt từ CSV/Excel.
- FR-NB-03: Thống kê theo ngày/tuần (heatmap).
- FR-NB-04: Chế độ chơi game ôn tập (quiz, đếm giờ).
- FR-NB-05: Gợi ý câu ví dụ theo ngữ cảnh người dùng.
- FR-NB-06: Refresh token / cookie httpOnly, rate limiting, audit log admin.

## 5. Quy tắc nghiệp vụ

### 5.1 Mastery (thay Leitner ở luồng chính)

Mỗi từ có 3 điểm độc lập 0–100: `meaning`, `spelling`, `context`.

| Sự kiện | Thay đổi |
|---|---|
| Đúng | +10 (mặc định `MASTERY_CORRECT_GAIN`) |
| Đúng có hint | gain × 0.5 (`MASTERY_HINT_FACTOR`) |
| Đúng nhanh (≤ 4000 ms) | +2 (`MASTERY_FAST_BONUS`) |
| Sai | −5 (`MASTERY_WRONG_PENALTY`) |
| Kẹp biên | `[0, 100]` |

- `learned`: một kỹ năng > 0.
- `mastered`: cả 3 kỹ năng ≥ `MASTERY_THRESHOLD` (mặc định 80).
- Chỉ kỹ năng vừa luyện thay đổi.

### 5.2 FSRS (spaced repetition)

- Rating 1–4: Again / Hard / Good / Easy.
- `due_at` do scheduler FSRS tính từ `difficulty` + `stability`.
- Một lần trả lời bài tập **không** tự động là một lần ôn FSRS.
- `retrievability` tính tại thời điểm đọc.

### 5.3 XP / Level / Streak

| Sự kiện | XP |
|---|---|
| Trả lời đúng | +10 |
| Trả lời sai | +2 |
| Hoàn thành bài học | +50 |

- Level suy ra từ ngưỡng XP (`LEVEL_THRESHOLDS`).
- Streak tăng khi học các ngày liên tiếp; reset khi nghỉ > 1 ngày.
- Đạt bài/phiên: ≥ 70%.

## 6. Yêu cầu phi chức năng

| Mã | Loại | Mô tả |
|---|---|---|
| NFR-01 | Performance | API phản hồi < 300ms (trừ AI); text index cho tìm kiếm |
| NFR-02 | Security | bcrypt, JWT HS256 + `token_version`, RBAC server-side, CORS giới hạn |
| NFR-03 | Scalability | MongoDB, API stateless (chạy nhiều instance sau nginx) |
| NFR-04 | Usability | UI responsive, tiếng Việt mặc định |
| NFR-05 | Availability | `/health` trả trạng thái + DB đang dùng; healthcheck Docker |
| NFR-06 | Integrity | `attempt_id`/`review_id` idempotent; chấm điểm chỉ ở server |
| NFR-07 | Data | TTL cho `quiz_questions`; index unique cho trạng thái user/từ |

## 7. Ràng buộc kỹ thuật

- Backend: Python 3.11+, FastAPI, MongoDB Atlas (Motor + PyMongo), `fsrs==6.3.2`.
- Frontend: React 18, Vite 6, React Router 6, Axios.
- AI: Google Gemini (`GEMINI_API_KEY`); cấu hình Cloudflare (`CF_*`) dự phòng, chưa nối.
- Auth: JWT Bearer; role trong MongoDB.
