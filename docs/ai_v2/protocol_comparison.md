# So sánh template / LLM / LLM + RAG trên development

> **Cập nhật 2026-10-07:** phần mô tả lịch sử bên dưới là policy v1 và đã bị
> thay thế. Không dùng mẫu số 12-case hay kết luận “chưa có Precision@5/schema
> metric” ở phần cũ để diễn giải implementation hiện tại. Quy tắc hiện hành là
> 11 protocol-extraction cases + case 012 diagnostic riêng, cùng Precision@5 và
> raw/post-sanitization schema-valid metrics. Xem [Task 3B measurement plan v2](task3b_comparator_measurement_v2.md).

## Current contract — Task 3B

- Giữ 12 artifacts; chỉ 11 protocol case được đưa vào quality aggregates.
  Case 012 (`no_lexical_evidence_probe`) báo riêng status, retrieval hits,
  provider attempted/called, abstention và schema status; gold rỗng không được
  biến thành điểm 0.
- Precision@5 là gold-set relevance: macro mean của
  `|returned top-5 ∩ gold IDs| / |actual unique returned hits|` trên protocol
  cases có gold IDs. Fewer-than-5 dùng số hit thực; zero-hit với gold không rỗng
  là 0; empty-gold và nhánh không retrieval là N/A. Chunk ngoài gold là
  **unjudged**, không mặc định irrelevant.
- Raw response schema được kiểm tra trước sanitizer; processed Workbench draft
  được kiểm tra riêng sau sanitizer. Báo cả valid/response, valid/produced và
  valid/all-11-case cùng status counts. Lỗi, no response, provider-not-called,
  abstention và not-run không bị lược bỏ. Schema validity không phải field
  accuracy.
- Không có provider thật trong lượt Task 3B. Corpus/rubric/baseline vẫn pending;
  không freeze, không sharing approval, không Gemini request.

## Historical v1 material (superseded; retained for provenance)

## Phạm vi và trạng thái

Công cụ đã implement; chưa có lượt Gemini thật hoặc kết quả chất lượng AI thật.
Bộ mới 12 protocol / 6 chunk vẫn là synthetic, `DRAFT_NOT_APPROVED`. Không
chuyển draft thành APPROVED, cấp sharing hoặc bịa review để chạy script.
Owner là reviewer duy nhất được phép cho demo nội bộ, không độc lập.

Kiểm tra cấu trúc gần nhất (2026-10-07, Python 3.12):
`STRUCTURE_ONLY_NO_REQUESTS`, 12 cases, `retrieval_k=5`,
`live_run_approved=false`, `reference_status=DRAFT_NOT_APPROVED`,
`HELDOUT_STATUS=LOCKED_NOT_RUN`. Đây **không** phải lần chạy Gemini hay phép đo
ba nhánh; vì vậy chưa có Recall@5/độ đúng/latency thực để so sánh.

Hai file đầu vào cũ 12 câu hỏi phần mềm / 9 chunk không dùng cho task này:
schema đầu ra policy Q&A không khớp protocol draft.

Entry point: `scripts/compare_ai_v2_protocols.py`.
Đây là **experiment harness chạy trong Python local**, gọi provider trực tiếp
qua adapter đã có, không phải đo deployment/Docker UI. Nó không bật endpoint
ungrounded của staging, tạo StudySpec, approve mapping hoặc chạy job/simulation.

## Protocol so sánh v1 — chốt trước output

| Nhánh | Input thực sự | Output |
| --- | --- | --- |
| `manual_template` | Người điền cùng protocol vào worksheet trống; không nhìn gold hoặc dùng retrieval | Fields, missing fields, citations, reviewer ID và thời gian tự đo |
| `llm_no_retrieval` | Protocol + `approved_evidence=[]` | Output model thô + draft được sanitize |
| `llm_rag` | Cùng protocol + tối đa 5 evidence truy xuất từ corpus đã duyệt | Output thô + draft RAG / no-hit abstention |

Hai nhánh AI gọi **cùng `extract_with_evidence`**, cùng system prompt
`protocol-rag-intake-1`, provider/model/endpoint, temperature hiện có và output
format. Không dùng prompt legacy `extract` có nội dung khác để làm baseline.
Không gửi gold, rubric, review record hoặc comparator output vào model.

Thứ tự case giữ nguyên; thứ tự hai nhánh AI luân phiên no-retrieval/RAG rồi
RAG/no-retrieval theo ordinal. Không retry tự động, không tự đổi model/prompt.
RAG no-hit không gọi model, còn nhánh no-retrieval vẫn thử đọc protocol.
Provider cấu hình drift sẽ ghi lỗi và dừng các lời gọi tiếp theo.
Model ID là cấu hình request, không phải chứng nhận backend revision bất biến.

Đây là so sánh **hai workflow**, không phải causal ablation chỉ khác retrieval:
RAG còn có no-hit gate và validation citation theo các chunk đã lấy.
Vì vậy lưu/chấm citation thô trước guardrail và citation được chấp nhận riêng.
Không tuyên bố lợi ích retrieval đã tách hoàn toàn khỏi guardrail.

Policy version `paired-protocol-comparison-1`, code hashes, corpus/rubric/manifest
hash, k=5 và thứ tự chạy được lưu trước lượt gọi đầu tiên. Không chỉnh gold,
normalization, k hoặc tham số sau khi xem output. Thay đổi protocol phải version
mới và báo rõ; không chạm V1 locked scientific score hoặc benchmark.

## Metrics và mẫu số

| Metric | Cách tính / giới hạn |
| --- | --- |
| Recall@5 | Chỉ RAG; macro `gold chunk được lấy / gold chunk cần`. Case gold rỗng không thuộc mẫu số. Retrieval fail/not-run đóng góp 0; provider fail sau retrieval vẫn giữ hits đã lấy |
| Field exact accuracy | Mỗi required field trên tất cả case; error/not-run không được điểm kể cả gold=null. Abstention hợp lệ vẫn được chấm. Có thêm accuracy chỉ trên gold non-null để không che khuất việc trích field bằng điểm missing/null |
| Missing detection | Micro TP/FP/FN, precision/recall/F1 của workflow. Failure giữ gold positives trong FN; không biến error thành abstain. Runtime tự tính missing_fields; raw_missing_declaration tách riêng câu trả lời missing của model, mẫu số là generation attempts (không gồm no-hit skip), để không gán việc sanitizer sửa lỗi thành năng lực model |
| Raw citation source precision | Citation model/human đưa ra trỏ tới source+chunk tồn tại trong approved corpus / tất cả citation thô, kể cả citation sai định dạng |
| Raw citation gold precision | Citation thô khớp gold pair / tất cả citation; chỉ là proxy relevance theo reference, không chứng minh support |
| Accepted citation source precision | Sau runtime guardrail; báo riêng, không thay số liệu citation thô |
| Unsupported claim rate | UNSUPPORTED / (SUPPORTED + UNSUPPORTED), dựa review người; UNCERTAIN tách riêng. Báo cả review coverage và pending, không ghi 0 khi chưa review |
| Completion/error/not-run | Counts và tỷ lệ trên đủ N case mỗi nhánh. Completion là nhận draft hợp lệ, không phải protocol đã đủ thông tin hoặc nghiên cứu đã hoàn thành |
| Runtime success | COMPLETED + ABSTAINED / N, phân biệt với draft completion; có fully_specified_protocol_count riêng |
| Latency | Mean/median/p95 nearest-rank, có mẫu số. Model đo retrieval + generation trong process, gồm failed attempts; không đo startup/setup/artifact IO. Manual time tự đo, không giả định so sánh thời gian này hoàn toàn tương đương |

N/A/null khác 0. Không retrieval thì Recall@5 là N/A, không phải thua RAG.
Nhánh hoàn toàn NOT_RUN có quality metrics NOT_MEASURED, không được trình bày
như một baseline đã đo. Exact mismatch có thể chỉ là paraphrase; raw exact-match
không được gọi là semantic correctness. Report này chưa có confidence intervals,
statistical significance hoặc bằng chứng RAG tốt hơn baseline.

## Bước 1 — tạo worksheet thủ công và kiểm tra cấu trúc

Các lệnh này chạy được với draft, không cần API key, không gọi provider:

```powershell
Set-Location 'E:\research-\.workbench\ai-v2-dev'
$taskPython = 'E:\research-\.venvs\ai-v2-staging-312\Scripts\python.exe'
$taskPack = '.workbench/evidence/protocol_draft_development_v1'

& $taskPython scripts/compare_ai_v2_protocols.py `
  --corpus "$taskPack/protocol_development_corpus_draft.jsonl" `
  --rubric "$taskPack/protocol_development_rubric_draft.json" --dry-run

& $taskPython scripts/compare_ai_v2_protocols.py `
  --corpus "$taskPack/protocol_development_corpus_draft.jsonl" `
  --rubric "$taskPack/protocol_development_rubric_draft.json" `
  --create-manual-template '.workbench/ai-v2-comparison-prep/manual-template-v1.json'
```

Existing file bị từ chối; dùng version mới, không ghi đè. Worksheet chỉ có
protocol + chỗ điền trống, không có gold. **CHỈNH TAY:** điền fields bằng lời
trong protocol, missing_fields (4 trường lõi), citations chỉ khi có nguồn biết
thật; ghi reviewer ID, elapsed_seconds tự đo. PENDING để nguyên case chưa làm.
Không cho AI hoặc script chép gold vào worksheet rồi gọi đó là manual baseline.
Nếu owner đã xem gold để duyệt, đây không phải blinded human baseline: ghi rõ
nguy cơ nhớ đáp án/reference contamination. Nếu dùng phép đo này, label phải là
internal non-blinded template comparator, không phải independent human study.

## Bước 2 — freeze package và chạy cùng Gemini

Chỉ thực hiện sau khi owner duyệt corpus/gold và xác nhận data policy cho exact
Gemini model/endpoint/project tier. [Gemini setup](real_provider_setup.md) phân
biệt Pro/Antigravity với API key. Utility manifest chỉ ghi lời xác nhận, không
thay thế review. Giữ draft gốc; chuẩn bị reviewed snapshot/manifest version mới.

**CHỈNH TAY:** dùng các đường dẫn thật của package đã duyệt, không copy
placeholder hoặc tự ghi reviewer/approval chưa có. Cùng PowerShell chứa
WORKBENCH_INTAKE_BASE_URL, WORKBENCH_INTAKE_MODEL,
WORKBENCH_INTAKE_API_KEY_ENV=WORKBENCH_LLM_KEY và key nhập kín:

```powershell
# Placeholder: thay bằng package đã được owner duyệt, không phải draft hiện tại.
$taskCorpus = '<reviewed-corpus.jsonl>'
$taskRubric = '<reviewed-protocol-reference.json>'
$taskManifest = '<matching-reviewed-manifest.json>'
$taskRun = Join-Path '.workbench/ai-v2-comparisons' `
  ('paired-' + [DateTimeOffset]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'))

& $taskPython scripts/compare_ai_v2_protocols.py `
  --corpus $taskCorpus --rubric $taskRubric --manifest $taskManifest `
  --manual '.workbench/ai-v2-comparison-prep/manual-template-v1.json' `
  --run --allow-provider-calls --output-dir $taskRun
```

Worksheet hash phải khớp corpus/reference đã freeze. Nếu draft rubric đổi
metadata khi tạo reviewed snapshot, tạo worksheet mới theo reviewed reference
rồi điền/import quyết định thủ công thật; không chỉnh hash để bỏ qua kiểm tra.
Key không nằm trong CLI/file; provider ID+endpoint phải khớp manifest và rubric.
Chưa approval hoặc thiếu key thì BLOCKED trước generation. Không bật sharing
tự động. Không cần mở public port hoặc bỏ auth của staging.

Thư mục run mới chứa run_config, cases/ từng arm-case, case_outputs,
retrieval log, claim_review_template, metrics.json, report.md, final run_manifest
với checksum artifacts. Mỗi case có error/status/raw/draft/evidence/timing.
Không có final manifest là run bị gián đoạn, không phải completed.

## Bước 3 — chấm phát biểu và xuất report offline

Copy `claim_review_template.json` sang file mới nằm ngoài run directory, giữ
nguyên case_outputs_sha256, claim_id, text, field_path, system/case IDs.
**CHỈNH TAY:** với từng scalar assertion trong raw output, đối chiếu protocol và
approved corpus; chọn SUPPORTED / UNSUPPORTED / UNCERTAIN, ghi reviewer ID thật
và reason. Giữ PENDING nếu chưa chấm; không nhờ LLM tự xác nhận claim support.
Một scalar không nhất thiết là một biological claim; đây là unit operational v1.
Citation/missing_fields không được đếm thành assertion. Không sửa raw output.

```powershell
# Các đường dẫn bên dưới trỏ file thật sau lượt chạy, không phải fixture tests.
& $taskPython scripts/compare_ai_v2_protocols.py `
  --corpus $taskCorpus --rubric $taskRubric `
  --report-only $taskRun --claim-reviews '<completed-claim-reviews.json>' `
  --output-dir '<new-report-directory-outside-run-and-input-packages>'
```

Report-only kiểm tra toàn bộ artifact hashes và corpus/rubric identity; annotations
phải bind output bytes. Nó không gọi provider, không cần key, không ghi đè run.
Report mới có metrics/report + report_manifest hash và nguồn run/review hash.

Không có support review thì metrics chất lượng cấu trúc vẫn tính được; riêng
unsupported rate là PENDING/N/A, không fake giá trị. Nếu thiếu manual outputs,
report ghi comparison_complete=false. Synthetic real-model runs vẫn chỉ là
MEASURED_OWNER_REVIEWED_SYNTHETIC_DEMO_NOT_INDEPENDENT; test stub thì
SOFTWARE_TEST_STUB_RESULTS. Không nâng thành real scientific/biological eval.

`HELDOUT_STATUS = LOCKED_NOT_RUN`. Không commit/push local evidence/review/results.
