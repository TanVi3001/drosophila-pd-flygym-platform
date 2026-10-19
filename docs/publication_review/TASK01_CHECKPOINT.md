# TASK 01 — Checkpoint

Trạng thái: CLOSED (2026-10-19). Người dùng chấp nhận audit và hướng Workbench methods. Không phê duyệt scientific validity/publication readiness/protocol mới; không independent review. Chưa thực hiện Task02.

## Môi trường và bảo toàn
- Tool CWD `E:\Task` không phải repo. Repo xác minh từ bàn giao: `E:\research-\.workbench\ai-v2-dev`.
- Branch `feature/evidence-audit-review`; HEAD `03b91b598eb63a72840cacd9dd7bb5fed7ebd4b1`.
- Ban đầu untracked: `PROJECT_PAPER_MASTER_CONTEXT_VI_2026-10-19.md`, `scripts/_verify_plos018_deep.py`; giữ nguyên.
- Đã đọc root AGENTS; không tìm thấy AGENTS bổ sung dưới docs/src hoặc các ancestor đã kiểm tra. Hai deliverables chưa tồn tại lúc bắt đầu.

## Đã đọc / findings có nguồn
- Handoff không phải measurement.
- `docs/workbench_active_scope.md` toàn bộ: methods track; human mapping review pending; mô tả partial held-out score preparation và summary bằng effect-only. Không mở artifact held-out được dẫn trong tài liệu.
- `docs/workbench_publication_roadmap.md`: gates A–E kế hoạch; MN9 pilot smoke; operator riêng.
- `docs/workbench_q1_manuscript_protocol.md`: P@5 common denominator; response-presence không phải causal; seeds không phải flies.
- `docs/workbench/evidence_gated_prioritization.md`, Public mapping registry → cuối: pending review; approval bound hashes; LCB/stability/budget policy là cơ chế được mô tả, cần đối chiếu code.
- `docs/ai_v2/task1c_go_no_go.md` toàn bộ: GRAPH_SIGNAL_UNSUPPORTED trong development; 74 mappings pending theo tài liệu, chưa xác minh record hiện tại. LOCKED_NOT_RUN chỉ thuộc track đó, không giải quyết lịch sử Workbench.

## Cụm đọc 2 / đối chiếu
- Code `service.py`: approve_support_assessment, _require_support_freeze, select_study; `selection.py`: SelectionPolicy/select_candidates; AI facade transitions. Có hash gates, LCB/budget/abstention; chưa runtime/toàn call paths. Contract support-gated-1.
- Summary Task1C development xác nhận decision unsupported, ΔAP -0.1151465, ΔP@5 0, pending 74 trong artifact lịch sử, không phải registry hiện tại.
- Paired synthetic metrics run 20261009T131833878Z: 11 cases, comparison_complete=false, owner-reviewed-not-independent, prompt-v2, raw/processed VALID 11/11 hai LLM arms. Không adjudicate provenance mâu thuẫn handoff §10.
- PLOS draft-v2 readiness:24–26 báo overlap case v1, không phải kiểm corpus v2. Không mở corpus/case/gold; chưa kiểm review hiện tại.
- Đã đọc v0.1/master §10.
- Web 19/10: NeuroMechFly official homepage; v2 2024 DOI 10.1038/s41592-024-02497-y (abstract); AiiDA 2020 DOI 10.1038/s41597-020-00638-4 (abstract/provenance/workflows); ALCE 2023 DOI 10.18653/v1/2023.emnlp-main.398 (abstract/metadata); Shiu 2024 DOI 10.1038/s41586-024-07763-9 (abstract). Không tải supplementary/datasets. Novelty mới được đối chiếu sơ bộ, không systematic; không suy feature vắng mặt từ abstract.

## Chưa xác minh
Novelty cơ chế so với toàn bộ prior art; runtime; review hiện tại; label provenance/circularity/cluster identity, exposure history, version reconciliation. 9 REVIEWED/11 PENDING và PLOS chưa approved/frozen/run: theo bàn giao, chưa xác minh hiện tại.

## File đã ghi / bước tiếp
Đã ghi nhận chấp nhận; đóng Task01. Workbench reliability là claim mục tiêu; ranking có điều kiện. Đã sửa exposure, v1/v2 overlap, CI, denominator/cluster, learning effects; reviewer string không xác thực người/độc lập. Chỉ hai deliverables ngoài hai untracked ban đầu. Task02 cần chỉ dẫn riêng; chưa thực hiện.

## Cấm
Không mở held-out/sealed (kể cả load gián tiếp); không chạy test/evaluator/benchmark/simulator/provider. Không sửa code/config/gold/corpus/review/approval/frozen artifacts; không Git state changes, subagent hoặc Task02. Khi tiếp tục: đọc AGENTS/checkpoint/report, đối chiếu HEAD/status trước.