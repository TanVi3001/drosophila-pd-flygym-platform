# Graph learning setting — AI V2 development

`GRAPH_SETTING = TRANSDUCTIVE_STRUCTURE_LABEL_ISOLATED`

FlyWire-630 is one directed connectivity graph. The adapter calculates label-blind node features from the complete public graph, including topology around neurons belonging to validation folds. For each target neuron, its incoming-neighbor mean is formed from presynaptic nodes. The one-layer GraphSAGE encoder sees these fixed, unlabeled neighborhood features at training and inference time. All learned GraphSAGE weights, the linear heads, the class weights and the effect feature scaling are fitted using only the four training folds. Validation-fold labels enter metrics only after predictions are made; no early stopping or hyperparameter selection uses them.

This is transductive structure access with fold-label isolation. It does **not** test transfer to an unseen connectome or a newly collected experiment. The Task 0 future-pretraining contract remains inductive by default; this separate Task 1 graph-signal experiment declares its transductive setting explicitly. No GraphMAE pretraining has been run.

`VALIDATION_LABELS_USED_FOR_TRAINING = FALSE`. The internal 32-case set and any external-validation outcomes were not used or evaluated.
