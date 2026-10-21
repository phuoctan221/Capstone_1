# SmartVOCAB AI — Tài liệu Nhu cầu (Requirements)

## 1. Tổng quan

SmartVOCAB AI là ứng dụng học từ vựng tiếng Anh thông minh, hỗ trợ:

- Quản lý từ vựng cá nhân
- Gợi ý nghĩa, phiên âm, ví dụ bằng AI (Google Gemini)
- Ôn tập theo hệ thống Leitner 5 hộp (spaced repetition)

## 2. Người dùng (Actors)

| Vai trò | Mô tả |
|---|---|
| Guest | Chỉ xem trang chủ, đăng nhập/đăng ký |
| Member | Quản lý từ vựng cá nhân, ôn tập flashcards |

## 3. Chức năng bắt buộc (Must have)

### FR-AUTH — Xác thực
- FR-AUTH-01: Đăng ký tài khoản (email, username, password)
- FR-AUTH-02: Đăng nhập, nhận JWT token
- FR-AUTH-03: Tự động đăng xuất khi token hết hạn
- FR-AUTH-04: Đăng xuất

### FR-VOCAB — Quản lý từ vựng
- FR-VOCAB-01: Xem danh sách từ vựng (phân trang)
- FR-VOCAB-02: Tìm kiếm theo từ hoặc nghĩa
- FR-VOCAB-03: Lọc theo trình độ (A1–C2) và chủ đề
- FR-VOCAB-04: Thêm từ vựng thủ công
- FR-VOCAB-05: Chỉnh sửa, xóa từ vựng
- FR-VOCAB-06: Gợi ý từ vựng bằng AI (sinh meaning, phonetic, example, synonyms...)

### FR-LEARN — Ôn tập
- FR-LEARN-01: Lấy danh sách thẻ đến hạn ôn
- FR-LEARN-02: Ghi nhận kết quả ôn (nhớ / chưa nhớ)
- FR-LEARN-03: Tự động chuyển thẻ giữa 5 hộp theo kết quả
- FR-LEARN-04: Xem thống kê (tổng, đang học, đã thuộc, đến hạn)

## 4. Chức năng nâng cao (Could have)

- FR-NB-01: Phát âm từ bằng Web Speech API
- FR-NB-02: Nhập file CSV/Excel từ vựng hàng loạt
- FR-NB-03: Thống kê theo ngày/tuần (heatmap)
- FR-NB-04: Chế độ chơi game ôn tập (quiz, đếm giờ)
- FR-NB-05: Gợi ý câu ví dụ theo ngữ cảnh người dùng

## 5. Yêu cầu phi chức năng

| Mã | Loại | Mô tả |
|---|---|---|
| NFR-01 | Performance | API phản hồi < 300ms (trừ AI) |
| NFR-02 | Security | Mật khẩu hash bcrypt, JWT HS256, CORS giới hạn |
| NFR-03 | Scalability | MongoDB, API stateless |
| NFR-04 | Usability | UI responsive, tiếng Việt mặc định |
| NFR-05 | Availability | Health check endpoint `/health` |

## 6. Quy tắc nghiệp vụ Leitner

| Hộp | Chu kỳ ôn |
|---|---|
| 1 | 10 phút |
| 2 | 1 giờ |
| 3 | 1 ngày |
| 4 | 3 ngày |
| 5 | 7 ngày (đã thuộc) |

- Ôn đúng: lên 1 hộp (tối đa 5)
- Ôn sai: lùi về hộp 1

## 7. Ràng buộc kỹ thuật

- Backend: Python 3.11+, FastAPI, MongoDB (Motor)
- Frontend: React 18, Vite, React Router 6, Axios
- AI: Google Gemini API
- Auth: JWT Bearer
