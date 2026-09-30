# AI Workbench V2 compatibility with the validation firewall

The access policy supports a future AI V2 without implementing it. Before prediction freeze, LLM/RAG may retrieve approved evidence and input metadata only; it must never index or retrieve sealed validation outcomes. A supervised ranking head and self-supervised graph encoder train on development data only. Validation cases are inference-only under a frozen protocol, not training, tuning, feature selection or model selection data.

The default graph-pretraining mode is **inductive**: validation nodes, edges and features are excluded from pretraining. If a future study proposes a **transductive** setting in which validation graph structure is visible, that fact must be declared and approved before predictions; no validation labels may be used. This policy grants no AI V2 access and does not authorize validation execution.
