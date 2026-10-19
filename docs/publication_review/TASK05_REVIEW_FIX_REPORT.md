# Task05 — Áp dụng bản sửa review và kiểm tra trên Windows

Ngày: 2026-10-19, Asia/Saigon (UTC+07:00).

Trạng thái: **Đã sửa R01–R04 và kiểm tra phạm vi engineering: 43 passed.**
Independent engineering review của oracle vẫn `PENDING_INDEPENDENT_ENGINEERING_REVIEW`.

## Nguồn và kiểm tra trước sửa

- Repo: `E:\research-\.workbench\ai-v2-dev`.
- Branch: `feature/evidence-audit-review`; HEAD: `03b91b598eb63a72840cacd9dd7bb5fed7ebd4b1`.
- Gói do owner cung cấp: `C:\Users\Le Tan Vi\Downloads\task05_review_fix.zip`.
- SHA-256 gói review: `eb771f8cfe2edc2ea0a6c82d9f1cd3acd26e9378b46c0b2f41c40a780f0cf104`.
- Đã kiểm tra đủ 11 entries trong `package_files.json`: đúng SHA-256 và size.
- Hai file hiện hữu cần sửa khớp chính xác before hashes trong manifest; test regression mới chưa tồn tại.
- Đã đọc root AGENTS và kiểm tra các thư mục cha liên quan; không thấy AGENTS bổ sung áp dụng.
- Các thay đổi sẵn có của `service.py` và các file ngoài phạm vi được giữ nguyên.
- Backup trước sửa: `task05_artifacts/review-fix-windows-v1/before/`.

Các hướng dẫn trong archive được đối chiếu như nội dung review. Việc chỉnh repo
thực hiện bằng patch sau khi kiểm tra source; không chạy installer/apply script của archive.

## Thay đổi thực tế

| Finding | Thay đổi | Bằng chứng |
|---|---|---|
| R01: hash source mới nhưng loader có thể chạy `.pyc` cũ | `pure_modules` đọc snapshot bytes một lần cho models/support, dùng cùng bytes cho cache identity và `compile`/execution | Regression tạo bytecode timestamp/size hợp lệ cho OLD, thay source cùng size/mtime thành NEW; trước sửa chạy OLD, sau sửa chạy NEW |
| R02: lỗi import để lại module khởi tạo dở | Khi execution lỗi, xóa package/models/support của namespace vừa tạo rồi re-raise | Hai lần load failed source đều raise, không để lại partial namespace |
| R03: hai object cùng JSON gây duplicate path | Attachment path chứa cả role và digest | Context/policy cùng digest vẫn có path riêng và recompute khớp; importer tiếp tục từ chối duplicate path |
| R04: export ghi trước khi validate/serialize hoàn tất | Kiểm tra snapshot bindings và serialize toàn bộ trước khi tạo thư mục sidecar | Bundle mismatch bị từ chối; NaN gây đúng lỗi JSON serialization; cả hai giữ nguyên bundle và không để lại sidecar |

Implementation của `decision_package.py` và thay đổi parametrization integration
khớp bản review khi chuẩn hóa newline/trailing blank lines. Byte hashes trên Windows
khác hash after trong archive do định dạng dòng; hash bytes thực tế được ghi trong
`task05_artifacts/review-fix-windows-v1/verification-summary.json`.

Integration mở rộng từ S01/S02/S05 sang đủ S01–S06 của ledger hiện có. Cả sáu
đi qua actual service/store/export, copy package, xóa workspace fixture gốc,
rồi recompute bằng trusted code trong process `-I -B` có dependency guard.
Không bổ sung thuật toán quyết định hoặc đổi support policy.

## Chỉnh test so với gói review

Trong regression serialization của archive, bundle được tạo từ S01 nhưng snapshots
lại lấy S02. Với exporter mới, test có thể pass vì `BUNDLE_STUDY_MISMATCH` trước
khi chạm serialization. Bản áp dụng dùng đúng snapshots của bundle và yêu cầu
exception chứa `Out of range float values`, nên kiểm tra đúng lỗi NaN.

Bổ sung một regression cho `DUPLICATE_PATH` để xác nhận importer vẫn từ chối
manifest có hai role trỏ cùng đường dẫn. Tổng final là 43 thay vì 42 tests trong
receipt Linux của archive.

## Verification thực tế

Môi trường: Windows 11, CPython 3.12.10, pytest 9.1.1.
Python: `E:\research-\.venvs\ai-v2-staging-312\Scripts\python.exe`.

| Lượt | Tests | Passed | Failed | Errors / skips | Exit |
|---|---:|---:|---:|---:|---:|
| Baseline hai file cũ | 34 | 34 | 0 | 0 / 0 | 0 |
| Regressions trên code trước sửa | 6 | 1 | 5 | 0 / 0 | 1 (expected reproduction) |
| Final ba file | 43 | 43 | 0 | 0 / 0 | 0 |

Final command từ repo root:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:TASK05_ARTIFACTS = (Resolve-Path 'docs/publication_review/task05_artifacts/review-fix-windows-v1').Path
& 'E:\research-\.venvs\ai-v2-staging-312\Scripts\python.exe' -m pytest --noconftest -q -p no:cacheprovider tests/test_workbench_support_package_integration.py tests/test_workbench_decision_package.py tests/test_workbench_decision_package_review.py --junitxml="$env:TASK05_ARTIFACTS/final.xml"
```

Final stdout: `43 passed in 9.90s`. JUnit suite time: 9.534 seconds.
`git diff --check`: exit 0. Các source/test mới chưa tracked được kiểm tra
thêm trailing whitespace: PASS.

Artifacts mới trong `task05_artifacts/review-fix-windows-v1/`:

- `baseline.xml`, `regressions-before.xml`, `final.xml`.
- `S01-result.json` đến `S06-result.json`.
- `verification-summary.json` và backup hai file trước sửa.

Đối soát sáu result files: `RECOMPUTED`, `integrity_closure=VALID`,
`original_agreement=true`, `operational_authority=false` cho cả 6/6.
Các expected tuple và control non-priority assertions được kiểm tra trong tests.

## Bảo toàn lịch sử và giới hạn

- Ledger gốc vẫn SHA-256 `f75cb973b5c577f1bc230c44c05e9f02958b2e0ebdc810a348c2ddf2d99eb034`.
- `task05_review_packet.zip` gốc vẫn SHA-256 `2811759c30c4afc3778f662ca8e541b2dedd5bde7c69a975a60ca746c4e15aed`.
- Task04/Task05 receipts cũ và oracle giữ nguyên. `build_packet.py` hiện có xây packet lịch sử với summary 34 tests; không rerun nó để mô tả bản fix mới.
- Code identity đã đổi. Sidecar pin code cũ có thể bị từ chối `CODE_MISMATCH`; tạo fixture package mới khi cần kiểm tra code mới, giữ nguyên historical identities.
- Preflight không được replay; dependency guard không phải OS sandbox. Chưa kiểm tra full suite, package initializers, HTTP/UI hoặc live backend.
- Integration dùng fixture store đóng SQLite connections. Production Windows connection lifecycle vẫn là giới hạn đã ghi ở Task05 gốc.
- Chưa chứng minh atomicity trước mọi disk I/O failure/filesystem race hoặc runtime mutation đồng thời.
- Đây là kiểm tra phần mềm do AI thực hiện. Oracle chưa được người engineering độc lập review; chưa có scientific validation hoặc comparative added-value evidence.

Lượt này không gọi provider/simulator, không approve study hoặc submit job,
không đọc held-out/sealed outcomes, không sửa benchmark và không commit/push.
Task06 chưa được thực hiện.
