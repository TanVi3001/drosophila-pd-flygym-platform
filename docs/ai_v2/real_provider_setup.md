# Gemini provider cho demo development — chưa kích hoạt

## Trạng thái đã kiểm tra

Ngày kiểm tra tài liệu: 2026-10-07. Đây là hướng dẫn chuẩn bị, không phải
biên bản owner đã duyệt hoặc kết quả inference.

- Đã tách bộ 12 câu hỏi phần mềm khỏi bộ 12 protocol synthetic.
- Runner có chế độ `retrieval-only` và `rag-draft`, lưu output/error/provenance.
- Bộ protocol mới có 6 chunk; audit chỉ xác nhận cấu trúc.
- Rubric mới vẫn `DRAFT_NOT_APPROVED`, reviewer rỗng, privacy `NOT_DECIDED`.
- Xác nhận corpus phần mềm trước đây không áp dụng cho bộ protocol mới.
- Owner đã chọn hướng Gemini thay cho OpenAI; exact model và data policy còn
  cần chốt. Chưa cấp quyền sharing hoặc gọi model.

## Cấu hình đề xuất, không phải cấu hình đang chạy

| Mục | Đề xuất |
| --- | --- |
| Provider | Gemini Developer API qua compatibility endpoint của Google |
| Model ứng viên hiện tại (chưa owner chọn) | `gemini-3.1-flash-lite`; xem file quyết định draft gắn với hash package protocol trước khi chốt |
| Base URL cho adapter | `https://generativelanguage.googleapis.com/v1beta/openai` |
| Endpoint đầy đủ phải ghi trong approval | `https://generativelanguage.googleapis.com/v1beta/openai/chat/completions` |
| Provider ID phải khớp chính xác | `openai-compatible:gemini-3.1-flash-lite` nếu owner chấp nhận đúng model ứng viên này |
| Prompt hiện tại | `protocol-rag-intake-1` |
| Dạng output adapter hiện tại | JSON mode `json_object`, không phải strict JSON Schema; exact request chưa được live-verified với Google |
| Credential trong server | Biến môi trường `WORKBENCH_LLM_KEY` |
| Phạm vi | `OWNER_REVIEWED_DEMO`, synthetic, không độc lập |

Lý do chọn làm **ứng viên để owner cân nhắc**, không phải lựa chọn đã được chốt:
task demo là trích các trường protocol ngắn. Google mô tả
[Gemini 3.1 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite)
là model stable chi phí thấp cho tác vụ nhẹ/data extraction và liệt kê structured
outputs. Bảng giá Google hiện ghi mức standard Paid là $0.25/1M text input và
$1.50/1M output; mức Unpaid hiển thị miễn phí nhưng có chính sách dùng dữ liệu
khác bên dưới. Đây không phải kết luận model tốt nhất cho sinh học; model access
và quota trên project của owner chưa kiểm tra. Không dùng `latest` hay fallback
tự động khi lỗi.

Adapter hiện dùng Chat Completions, `temperature=0` và `response_format` kiểu
`json_object`. Google có
[compatibility endpoint](https://ai.google.dev/gemini-api/docs/openai) dùng bearer
Gemini API key và response envelope tương thích; trang chính thức minh họa cả
structured output qua schema/Pydantic. Tuy vậy, code hiện tại chỉ gửi JSON mode,
không gửi JSON Schema chính thức; chưa có provider call xác nhận đúng payload
này được Gemini chấp nhận. Tên class/provider ID vẫn là
`OpenAICompatibleIntakeProvider` / `openai-compatible:*`: đây là tên định dạng
giao thức, không có nghĩa request được gửi tới OpenAI. URL thật là Google.
Không live-test model, endpoint hay tham số; nếu sau này được owner cho phép
smoke-test và provider báo không hỗ trợ, ghi lỗi rồi version thay đổi trước một
lượt đo mới, không silently đổi giữa batch. JSON hợp lệ cũng không đảm bảo nội
dung đúng; vẫn kiểm tra schema/citations ở local.

## Google AI Pro / Antigravity khác Gemini API

[Google AI Pro](https://one.google.com/about/google-ai-plans/) có quyền lợi cho
Gemini/Antigravity và có thể có Cloud credits tùy eligibility. Không suy ra
quota API không giới hạn hoặc credits đã được kích hoạt từ việc đã mua Pro.
Antigravity là công cụ hỗ trợ build; không dùng session/cookie/token IDE làm
key cho Workbench. Runtime này cần Gemini API key của một project AI Studio.

**CHỈNH TAY:** vào [AI Studio API keys](https://aistudio.google.com/api-keys),
đăng nhập cùng tài khoản, chọn/tạo project, tạo API key. Kiểm tra Plan,
model access, quota, billing và credits thực tế. Không tạo project/bật billing
thay owner. Nếu cần, xem [hướng dẫn key](https://ai.google.dev/gemini-api/docs/api-key)
và [billing](https://ai.google.dev/gemini-api/docs/billing).

## Quyết định owner còn cần chốt

1. Đọc nguồn, 6 chunk và đủ 12 case trong
   `.workbench/evidence/protocol_draft_development_v1/` theo README của bộ này.
   Xác nhận gold fields, trường thiếu và citation đúng cho demo synthetic.
2. Chốt exact Gemini model/endpoint và API project/plan. Chọn Gemini không
   tự duyệt model đề xuất hoặc quyền gửi dữ liệu.
3. Xác nhận riêng cho phép gửi cả `protocol_text` và các excerpt truy xuất cùng
   định danh/citation của chúng tới endpoint đã chọn. Xác nhận quyền sử dụng
   nội dung đó. Không gửi gold/reference/rubric, review record hoặc benchmark.
4. Có Gemini API key và quyền truy cập/quota. Chỉ nhập key cục bộ.

**Privacy phải review lại cho Google**, không tái sử dụng quyết định OpenAI.
Theo [Gemini API Additional Terms](https://ai.google.dev/gemini-api/terms.md),
Unpaid Services có thể dùng input/output để cung cấp, cải thiện và phát triển
sản phẩm; human reviewers có thể đọc/xử lý input/output. Không gửi dữ liệu
confidential, personal hoặc sensitive vào nhánh đó. Với Paid Services, prompt và
response không được dùng để cải thiện sản phẩm nhưng vẫn được log trong một
khoảng thời gian giới hạn cho safety/security và legal/regulatory; điều khoản
được xem không nêu thời lượng cụ thể trong đoạn này. Paid Service được xác định
theo điều kiện project/account/billing của Google, không theo suy đoán từ gói
Google AI Pro hoặc Antigravity. Trạng thái project của owner chưa được kiểm tra.
Khuyến nghị project Paid khi dùng tài liệu nội bộ/private; chỉ dùng Free cho
synthetic không confidential sau khi owner xác nhận rõ điều kiện dữ liệu.
Không chọn Free/Paid thay owner hoặc bật quyền chia sẻ để vượt gate.

Một owner đủ cho demo nội bộ; báo cáo phải ghi AI-assisted, synthetic và
`independent_review_claim=false`. Không ghi owner đã đọc/đồng ý nếu chưa có
xác nhận. Không yêu cầu lab bên ngoài cho bước demo này.

## Sau khi có xác nhận thực tế

Tạo một package local version mới (không ghi đè draft hoặc freeze cũ) gồm:

- Copy byte-for-byte corpus/source đã được owner duyệt.
- Review record: reviewer, thời điểm có timezone, quyết định từng case và
  quyền chia sẻ gắn exact model/provider/endpoint.
- Reference snapshot mới `ai-v2-assistant-reference-reviewed-1`, APPROVED,
  reviewer thật, privacy đã duyệt; giữ synthetic/claim scope/gold/cases.
  Rubric draft gốc giữ nguyên.
- Manifest qua `scripts/create_rag_manifest.py`: outcome-free, DEVELOPMENT,
  reviewer, hash corpus, source allowlist, hai sharing flags và exact binding.
  Utility chỉ ghi lời xác nhận, không thay thế review.

Kiểm tra hash, schema và chạy collector `--mode rag-draft --allow-provider-calls
--dry-run` với corpus/reference/manifest mới trước khi đổi runtime. Dry-run
không gọi mạng, không xác minh API key hoặc tài khoản provider.

### Nhập key bằng PowerShell, chỉ sau khi chọn provider

Token staging hiện tại khác API key của model. Không lấy token 43 ký tự của
Workbench để nhập làm Gemini API key. Không in ENV, không chạy `docker inspect`
hoặc `docker compose config` để chia sẻ output chứa secrets.

```powershell
Set-Location 'E:\research-\.workbench\ai-v2-dev'

# CHỈNH TAY: nhập API key tại máy; không gửi key vào chat hoặc file repo.
$taskProviderSecret = Read-Host 'Nhap Gemini API key (an)' -AsSecureString
$taskSecretPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($taskProviderSecret)
try {
  $env:WORKBENCH_LLM_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($taskSecretPtr)
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($taskSecretPtr)
  Remove-Variable taskProviderSecret, taskSecretPtr
}

# CHỈNH TAY: chỉ giữ cấu hình này nếu owner đã chọn đúng model/endpoint này.
$env:WORKBENCH_INTAKE_BASE_URL = 'https://generativelanguage.googleapis.com/v1beta/openai'
$env:WORKBENCH_INTAKE_MODEL = 'gemini-3.5-flash-lite'
$env:WORKBENCH_INTAKE_API_KEY_ENV = 'WORKBENCH_LLM_KEY'
$env:WORKBENCH_ALLOW_UNGROUNDED_INTAKE = 'false'

# Chỉ hiện true/false, không hiện credential.
(-not [string]::IsNullOrWhiteSpace($env:WORKBENCH_LLM_KEY))
```

Các lệnh trên không tự gửi dữ liệu nhưng sẽ cấu hình ENV cho lần recreate
kế tiếp. Chưa chạy recreate khi thiếu reviewed package mới. Compose đã hỗ trợ
các biến này; không cần nới auth, sharing gate hoặc mở cổng public.
Docker administrators có thể đọc ENV; đây chỉ là staging local, không phải
production secret management.

### Thay runtime và thu output, chỉ với package đã duyệt

1. Trong cùng PowerShell có token staging và key, đặt `WORKBENCH_RAG_HOST_DIR`
   trỏ package mới; `WORKBENCH_RAG_MANIFEST` là đường dẫn manifest mới bên trong
   `/opt/workbench/evidence/`. Không mount draft rubric thành manifest.
2. Recreate service qua compose staging; giữ named volume, không dùng `down -v`.
   Kiểm tra container healthy và `/v1/ai/rag/status` bằng bearer token.
3. Status phải khớp corpus/manifest hash, hai sharing flags và
   `provider_identity_matches_approval=true`, `provider_ready=true`.
   Readiness là cấu hình, chưa chứng minh model đã đáp lời thành công.
4. Chạy collector theo [output_collection.md](output_collection.md) với
   `--mode rag-draft --allow-provider-calls --timeout 60`, exact manifest,
   reviewed reference mới và thư mục output mới ngoài package inputs.
   Không chạy một smoke draft trùng rồi bỏ output trước batch đo chính thức.
5. Giữ tất cả 12 case kể cả error/abstain/not-run. Không auto retry timeout:
   provider có thể đã chạy và tính phí trước khi client nhận lỗi.
6. Xem provenance model/prompt/corpus và raw draft; không sửa gold theo output.
   Case no-hit không gọi provider là đúng. Generation success không đồng nghĩa
   với trích đúng nội dung hoặc có biological validity.

Runner chỉ thu RAG outputs, chưa tự thu hai comparator manual/no-retrieval,
human claim annotations hoặc chấm toàn bộ metric. Một lượt model thật không
tự chứng minh RAG tốt hơn baseline. Bộ synthetic này cũng chưa đánh giá khả
năng đọc tài liệu sinh học. Giữ các giới hạn đó trong report cuối.

Không có eval, simulation, held-out hoặc sharing activation được thực hiện
chỉ bởi việc tạo tài liệu này. `HELDOUT_STATUS = LOCKED_NOT_RUN`.
