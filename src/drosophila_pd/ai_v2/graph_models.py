"""Fixed small development baselines; all fitting uses training-fold labels only."""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ModelOutput:
    validation_scores: np.ndarray
    parameter_count: int
    training_seconds: float
    inference_seconds: float
    training_log: tuple[dict[str, float], ...]
    train_feature_mean: tuple[float, ...] | None = None


def fit_linear_baseline(x: np.ndarray, labels: np.ndarray, train_index: np.ndarray, validation_index: np.ndarray, *, seed: int) -> ModelOutput:
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    start = time.perf_counter()
    scaler = StandardScaler().fit(x[train_index])
    train_x = scaler.transform(x[train_index])
    model = LogisticRegression(C=1.0, class_weight="balanced", max_iter=1000, random_state=seed)
    model.fit(train_x, labels[train_index])
    trained = time.perf_counter()
    scores = model.predict_proba(scaler.transform(x[validation_index]))[:, 1]
    inferred = time.perf_counter()
    return ModelOutput(scores, int(model.coef_.size + model.intercept_.size), trained - start, inferred - trained, (), tuple(float(v) for v in scaler.mean_))


def fit_graphsage(
    node_features: np.ndarray,
    neighbor_features: np.ndarray,
    mask: np.ndarray,
    effects: np.ndarray,
    labels: np.ndarray,
    train_index: np.ndarray,
    validation_index: np.ndarray,
    *,
    include_effect: bool,
    hidden_dim: int,
    dropout: float,
    learning_rate: float,
    epochs: int,
    weight_decay: float,
    seed: int,
) -> ModelOutput:
    import torch
    from torch import nn

    torch.set_num_threads(1)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)
    if hidden_dim < 1 or epochs < 1 or not 0 <= dropout < 1:
        raise ValueError("invalid GraphSAGE configuration")
    device = torch.device("cpu")
    self_x = torch.tensor(node_features, dtype=torch.float32, device=device)
    neighbor_x = torch.tensor(neighbor_features, dtype=torch.float32, device=device)
    mask_x = torch.tensor(mask, dtype=torch.float32, device=device)
    labels_x = torch.tensor(labels, dtype=torch.float32, device=device)
    effect_mean = float(effects[train_index].mean())
    effect_std = float(effects[train_index].std())
    if effect_std == 0:
        effect_std = 1.0
    effect_x = torch.tensor((effects - effect_mean) / effect_std, dtype=torch.float32, device=device)

    class OneLayerMeanGraphSAGE(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.self_linear = nn.Linear(self_x.shape[-1], hidden_dim, bias=True)
            self.neighbor_linear = nn.Linear(neighbor_x.shape[-1], hidden_dim, bias=False)
            self.dropout = nn.Dropout(dropout)
            self.head = nn.Linear(hidden_dim + int(include_effect), 1)

        def forward(self, indices: torch.Tensor) -> torch.Tensor:
            hidden = torch.relu(self.self_linear(self_x[indices]) + self.neighbor_linear(neighbor_x[indices]))
            pooled = (self.dropout(hidden) * mask_x[indices, :, None]).sum(dim=1) / mask_x[indices].sum(dim=1, keepdim=True)
            if include_effect:
                pooled = torch.cat((pooled, effect_x[indices, None]), dim=1)
            return self.head(pooled).squeeze(-1)

    model = OneLayerMeanGraphSAGE().to(device)
    train_tensor = torch.tensor(train_index, dtype=torch.long, device=device)
    validation_tensor = torch.tensor(validation_index, dtype=torch.long, device=device)
    positive = int(labels[train_index].sum())
    negative = len(train_index) - positive
    if positive == 0 or negative == 0:
        raise ValueError("each training fold needs both classes")
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(negative / positive, dtype=torch.float32))
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate, weight_decay=weight_decay)
    log = []
    start = time.perf_counter()
    for epoch in range(epochs):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        loss = loss_fn(model(train_tensor), labels_x[train_tensor])
        loss.backward()
        optimizer.step()
        log.append({"epoch": float(epoch + 1), "train_loss": float(loss.detach().cpu())})
    trained = time.perf_counter()
    model.eval()
    with torch.no_grad():
        scores = torch.sigmoid(model(validation_tensor)).cpu().numpy().astype(np.float64)
    inferred = time.perf_counter()
    return ModelOutput(scores, sum(parameter.numel() for parameter in model.parameters()), trained - start, inferred - trained, tuple(log), (effect_mean, effect_std) if include_effect else None)
