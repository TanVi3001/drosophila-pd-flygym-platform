# Chốt và chạy comparison OWNER_REVIEWED_DEMO

Utility `scripts/prepare_ai_v2_owner_demo.py` gom bản proposal hiện có thành
package local để owner đọc và chốt. Preparation sao chép đúng bytes corpus,
rubric case-003 proposal và tài liệu nguồn; audit draft, chuẩn bị worksheet trống
và preview payload bằng adapter thật được chặn trước transport. Không có
Gemini request trong preparation hoặc freeze.

Package hiện chỉ gồm synthetic protocol/software fixtures. Một owner
`owner-le-tan-vi` có thể xác nhận demo nội bộ có AI hỗ trợ;
`independent_review_claim=false`. Xác nhận corpus phần mềm cũ hay một session
synthetic khác không thay thế quyết định cho package protocol này.

Chuẩn bị bằng Python staging từ repo root:

```powershell
$taskPython = 'E:\research-\.venvs\ai-v2-staging-312\Scripts\python.exe'
$taskPack = '.workbench/evidence/protocol_draft_development_v1'
& $taskPython scripts/prepare_ai_v2_owner_demo.py --prepare `
  --corpus "$taskPack/protocol_development_corpus_draft.jsonl" `
  --rubric "$taskPack/protocol_development_rubric_case003_context_proposal_v1.json" `
  --measurement-plan "$taskPack/task3b_measurement_plan_v2.md" `
  --output-dir '.workbench/evidence/owner_demo_comparison_review_v1'
```

Các file đầu vào gốc giữ `DRAFT_NOT_APPROVED`, reviewers rỗng, privacy
`NOT_DECIDED`. Package mới chứa `review_inventory.json` với hash từng artifact
và implementation; `owner_decision_pending.json` là mẫu trống, không phải lời
xác nhận. Nếu code hoặc nội dung đổi, chuẩn bị một version mới để review lại
đúng phần thay đổi. Không ghi đè package cũ.

Hai quyết định nội dung còn chờ trên proposal:

- Case 003 giữ `context.sex="female"`, bỏ feeding_state không xác định;
  `missing_fields` chỉ dùng 4 trường lõi, không thêm feeding_state vào danh sách đó.
- Case 012 chỉ là lexical no-hit diagnostic. Giữ artifact và báo riêng;
  11 case còn lại là mẫu số chất lượng trích xuất protocol.

Model đề xuất vẫn là `gemini-3.1-flash-lite`, provider ID
`openai-compatible:gemini-3.1-flash-lite`, endpoint
`https://generativelanguage.googleapis.com/v1beta/openai/chat/completions`.
Phương án này khớp adapter hiện có. Model/project access và khả năng chấp nhận
JSON mode phải được xác minh trong lượt chạy được owner cho phép; không đổi
model hoặc fallback ngầm giữa batch.

Google công bố [model](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite)
có structured output và phù hợp trích xuất nhẹ. Theo
[pricing](https://ai.google.dev/gemini-api/docs/pricing), standard paid text
input/output lần lượt là USD 0.25/1 triệu và USD 1.50/1 triệu token tại lần
đối chiếu 2026-10-09. Phí thực tế phụ thuộc token và project/quota.
[Compatibility endpoint](https://ai.google.dev/gemini-api/docs/openai) dùng
Gemini API key; gói Gemini Pro/Antigravity không phải thông tin API-tier của
project. Theo [terms](https://ai.google.dev/gemini-api/terms), Unpaid có thể dùng
input/output để cải thiện dịch vụ và có human review; Paid không dùng để cải
thiện sản phẩm nhưng có logging giới hạn cho an toàn/pháp lý. Thời lượng cụ thể
và tier/quota của owner chưa được xác minh.

Owner cần chốt corpus/rubric hash, hai quyết định case, model/endpoint, tier API
thực tế (`PAID` hoặc `UNPAID`), và quyền gửi riêng corpus text/protocol text.
Khi có xác nhận thật, tạo file decision version mới, giữ nguyên lời owner và
timestamp có timezone. Utility không tự biết người đã đọc tài liệu; người điền
decision phải dựa trên xác nhận thực tế.

Baseline đang trống. `manual_worksheet.md` trình bày đủ 12 protocol và các ô
trả lời không chứa gold; `manual_template_pending.json` có 12 dòng PENDING,
reviewer rỗng và elapsed time null. Nếu owner chưa trả lời, được chạy hai nhánh
LLM sau approvals, nhưng manual_template phải báo NOT_MEASURED và
`comparison_complete=false`. Không có thắng/thua đủ ba nhánh khi manual trống.
Owner đã xem reference nên baseline sau này là nội bộ không mù. Câu trả lời và
thời gian tự đo chỉ được ghi khi owner cung cấp; case 012 không cần manual answer.

Sau xác nhận cụ thể, freeze local bằng utility hiện có cho manifest và loader
hiện có cho reference:

```powershell
$taskReview = '.workbench/evidence/owner_demo_comparison_review_v1'
$taskFrozen = '.workbench/evidence/owner_demo_protocol_frozen_v1'
& $taskPython scripts/prepare_ai_v2_owner_demo.py --freeze `
  --review-package $taskReview `
  --decision "$taskReview/owner_decision_confirmed_v1.json" `
  --output-dir $taskFrozen
```

Utility tạo snapshot riêng `ai-v2-assistant-reference-reviewed-1` với status
`APPROVED` theo contract loader, có scope `OWNER_REVIEWED_DEMO`, synthetic và
không độc lập. Không sửa draft gốc, không tạo mode `APPROVED_DEVELOPMENT` hay
reviewer thứ hai. `owner_decision.json` lưu lời xác nhận; manifest ghi thời điểm
tạo manifest riêng với thời điểm owner xác nhận. Một freeze thiếu
`freeze_inventory.json` là chưa hoàn tất, không được dùng làm freeze hợp lệ.

Trước chạy, kiểm tra package và implementation vẫn khớp:

```powershell
& $taskPython scripts/prepare_ai_v2_owner_demo.py --check-frozen --review-package $taskFrozen
if ($LASTEXITCODE -ne 0) { throw 'Frozen package integrity failed' }
```

CHỈNH TAY: tạo Gemini API key ở [AI Studio](https://aistudio.google.com/api-keys),
kiểm tra project tier/quota và nhập key tại máy sau khi chốt quyền gửi. Không
dán key vào chat. Chạy comparator ngoài Docker để đo runtime Python hiện có:

```powershell
$env:WORKBENCH_INTAKE_BASE_URL = 'https://generativelanguage.googleapis.com/v1beta/openai'
$env:WORKBENCH_INTAKE_MODEL = 'gemini-3.1-flash-lite'
$env:WORKBENCH_INTAKE_API_KEY_ENV = 'WORKBENCH_LLM_KEY'
$taskSecret = Read-Host 'Gemini API key (nhap an)' -AsSecureString
$taskPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($taskSecret)
try {
  $env:WORKBENCH_LLM_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($taskPointer)
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($taskPointer)
}
$taskRun = Join-Path '.workbench/ai-v2-comparisons' ('paired-' + [DateTimeOffset]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'))
try {
  & $taskPython scripts/compare_ai_v2_protocols.py `
    --corpus "$taskFrozen/protocol_development_corpus_draft.jsonl" `
    --rubric "$taskFrozen/reference_owner_reviewed.json" `
    --manifest "$taskFrozen/corpus.manifest.json" `
    --manual "$taskFrozen/manual_template_pending.json" `
    --run --allow-provider-calls --output-dir $taskRun
} finally {
  Remove-Item Env:WORKBENCH_LLM_KEY -ErrorAction SilentlyContinue
  $taskSecret.Dispose()
}
```

Một lượt, k=5, temperature=0, timeout=60s, không tự retry hoặc fallback. Các
request previews hiện cho phép tối đa 23 request: 12 no-retrieval và 11 RAG;
RAG case 012 dừng cục bộ nếu không có lexical hit. Vẫn lưu đủ 36 arm/case rows.
Provider errors/abstention/NOT_RUN có trong báo cáo. Vì baseline còn trống,
runner exit code 1 có thể biểu thị comparison chưa đủ ba nhánh; xem artifacts
và status thực tế, không gọi đó là kết quả PASS toàn bộ.

Metrics theo [Task 3B contract](task3b_comparator_measurement_v2.md). Claim
support/unsupported-claim rate cần owner chấm đúng output đã thu và hash;
chưa chấm thì pending/N/A. Report nhãn
`MEASURED_OWNER_REVIEWED_SYNTHETIC_DEMO_NOT_INDEPENDENT` khi có lượt thật;
stub tests chỉ là kiểm thử phần mềm. 12 câu policy/9 chunk phần mềm cũ là bộ
kiểm tra riêng và không được trộn vào bộ protocol.

`HELDOUT_STATUS = LOCKED_NOT_RUN`. Lượt này không approve study, submit job hay
chạy simulation; không commit/push evidence/review/results local.

## Lệnh rút gọn sau khi package đã freeze

`scripts/run_ai_v2_owner_demo.ps1` mặc định chỉ kiểm tra hash và dry-run, không
gọi provider. Chỉ thêm `-Run` khi muốn thực thi; `-PromptForKey` nhập key ẩn tại
máy. Script dùng model/endpoint từ decision đã freeze, kiểm tra integrity trước
khi đọc credential và khôi phục các biến môi trường khi kết thúc. Script không
tự lấy key từ tài khoản Gemini Pro hoặc file secrets.

```powershell
Set-Location 'E:\research-\.workbench\ai-v2-dev'
# Offline, không gửi dữ liệu:
& .\scripts\run_ai_v2_owner_demo.ps1
# Sau approval thực tế, nhập key ở máy để chạy Gemini:
& .\scripts\run_ai_v2_owner_demo.ps1 -Run -PromptForKey
```

Nếu PowerShell chặn script, đọc chính sách trên máy và chỉ dùng cách chạy được
nhóm cho phép; không tự đổi ExecutionPolicy hoặc tắt security controls.
