"""A compact NumPy surrogate for the P159 synthetic fire corpus.

The model is a one-hidden-layer tanh MLP over per-cell fuel, terrain, weather, and
ignition-relative features. It is deliberately small and CPU-only; it is not a replacement
for the FBP growth kernel.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import numpy as np

from .fuel import FireFuelError
from .surrogate import SURROGATE_FUEL_ORDER, SurrogateCorpus, SurrogateSample

MODEL_VERSION: Final[str] = "ws4.fire-surrogate.mlp.v1"
FEATURE_NAMES: Final[tuple[str, ...]] = (
    *(f"fuel_{name}" for name in SURROGATE_FUEL_ORDER),
    "nonfuel",
    "slope",
    "aspect_sin",
    "aspect_cos",
    "wind_speed",
    "wind_direction_sin",
    "wind_direction_cos",
    "ffmc",
    "bui",
    "ignition_distance",
    "bearing_sin",
    "bearing_cos",
)


def _sigmoid(value: np.ndarray) -> np.ndarray:
    """Return a stable logistic sigmoid."""
    clipped = np.clip(value, -60.0, 60.0)
    return np.asarray(1.0 / (1.0 + np.exp(-clipped)), dtype=float)


def sample_features(sample: SurrogateSample) -> np.ndarray:
    """Return the per-cell feature matrix for one sample.

    Parameters
    ----------
    sample : SurrogateSample
        Corpus sample.

    Returns
    -------
    numpy.ndarray
        ``(rows * cols, len(FEATURE_NAMES))`` float matrix.

    Raises
    ------
    FireFuelError
        If a fuel index is outside the corpus order.
    """
    rows, cols = sample.shape
    features = np.zeros((rows, cols, len(FEATURE_NAMES)), dtype=float)
    fuel = np.asarray(sample.fuel_index, dtype=int)
    if bool((fuel < 0).any()) or bool((fuel > len(SURROGATE_FUEL_ORDER)).any()):
        raise FireFuelError("fuel index is outside the surrogate fuel order")
    for index in range(len(SURROGATE_FUEL_ORDER)):
        features[:, :, index] = fuel == index + 1
    features[:, :, len(SURROGATE_FUEL_ORDER)] = fuel == 0
    features[:, :, len(SURROGATE_FUEL_ORDER) + 1] = np.asarray(sample.slope_percent) / 100.0
    aspect = np.radians(np.asarray(sample.aspect_deg))
    features[:, :, len(SURROGATE_FUEL_ORDER) + 2] = np.sin(aspect)
    features[:, :, len(SURROGATE_FUEL_ORDER) + 3] = np.cos(aspect)
    features[:, :, len(SURROGATE_FUEL_ORDER) + 4] = sample.wind_kmh / 50.0
    direction = np.radians(sample.wind_direction_deg)
    features[:, :, len(SURROGATE_FUEL_ORDER) + 5] = np.sin(direction)
    features[:, :, len(SURROGATE_FUEL_ORDER) + 6] = np.cos(direction)
    features[:, :, len(SURROGATE_FUEL_ORDER) + 7] = sample.ffmc / 100.0
    features[:, :, len(SURROGATE_FUEL_ORDER) + 8] = sample.bui / 200.0
    ign_row, ign_col = sample.ignition
    row_grid, col_grid = np.mgrid[0:rows, 0:cols]
    drow = row_grid - ign_row
    dcol = col_grid - ign_col
    distance = np.hypot(drow, dcol)
    max_distance = max(float(np.hypot(rows, cols)), 1.0)
    features[:, :, len(SURROGATE_FUEL_ORDER) + 9] = distance / max_distance
    bearing = np.arctan2(dcol, -drow)
    features[:, :, len(SURROGATE_FUEL_ORDER) + 10] = np.sin(bearing)
    features[:, :, len(SURROGATE_FUEL_ORDER) + 11] = np.cos(bearing)
    return features.reshape(rows * cols, len(FEATURE_NAMES))


@dataclass(frozen=True)
class SurrogateModel:
    """A trained compact fire surrogate.

    Parameters
    ----------
    w1, b1, w2, b2 : numpy.ndarray
        MLP weights and biases.
    hidden_units : int
        Hidden layer width.
    seed : int
        Training seed.
    epochs : int
        Training epochs.
    learning_rate : float
        Adam learning rate.
    train_loss : float
        Final weighted training loss.
    validation_loss : float
        Final weighted validation loss.
    """

    w1: np.ndarray
    b1: np.ndarray
    w2: np.ndarray
    b2: float
    hidden_units: int
    seed: int
    epochs: int
    learning_rate: float
    train_loss: float
    validation_loss: float

    @property
    def version(self) -> str:
        """Return the model version.

        Returns
        -------
        str
            Stable model version.
        """
        return MODEL_VERSION

    @classmethod
    def fit(
        cls,
        corpus: SurrogateCorpus,
        *,
        hidden_units: int = 32,
        epochs: int = 200,
        learning_rate: float = 0.01,
        seed: int = 159,
    ) -> SurrogateModel:
        """Fit the MLP on the corpus training split.

        Parameters
        ----------
        corpus : SurrogateCorpus
            Corpus with train and validation samples.
        hidden_units : int, optional
            Hidden width (default 32).
        epochs : int, optional
            Training epochs (default 200).
        learning_rate : float, optional
            Adam learning rate (default 0.01).
        seed : int, optional
            Weight-initialisation seed (default 159).

        Returns
        -------
        SurrogateModel
            The fitted model.

        Raises
        ------
        FireFuelError
            If the corpus has no train or validation samples, or dimensions are invalid.
        """
        if hidden_units < 1 or epochs < 1 or learning_rate <= 0.0:
            raise FireFuelError("hidden_units, epochs, and learning_rate must be positive")
        train = [sample for sample in corpus.samples if sample.split == "train"]
        validation = [sample for sample in corpus.samples if sample.split == "validation"]
        if not train or not validation:
            raise FireFuelError("corpus needs both train and validation samples")
        x_train, y_train = _training_arrays(train)
        x_val, y_val = _training_arrays(validation)
        rng = np.random.default_rng(seed)
        w1 = rng.normal(0.0, np.sqrt(2.0 / x_train.shape[1]), size=(hidden_units, x_train.shape[1]))
        b1 = np.zeros(hidden_units, dtype=float)
        w2 = rng.normal(0.0, np.sqrt(1.0 / hidden_units), size=hidden_units)
        b2 = 0.0
        positive = float(y_train.sum())
        negative = float(len(y_train) - positive)
        positive_weight = max(1.0, negative / max(positive, 1.0))
        m = [np.zeros_like(w1), np.zeros_like(b1), np.zeros_like(w2), np.zeros_like(b2)]
        v = [np.zeros_like(w1), np.zeros_like(b1), np.zeros_like(w2), np.zeros_like(b2)]
        beta1, beta2, epsilon = 0.9, 0.999, 1e-8
        for epoch in range(1, epochs + 1):
            hidden = np.tanh(x_train @ w1.T + b1)
            prob = _sigmoid(hidden @ w2 + b2)
            sample_weight = np.where(y_train > 0.5, positive_weight, 1.0)
            dz2 = (prob - y_train) * sample_weight / len(y_train)
            dw2 = hidden.T @ dz2
            db2 = float(dz2.sum())
            dh = np.outer(dz2, w2) * (1.0 - hidden**2)
            dw1 = dh.T @ x_train
            db1 = dh.sum(axis=0)
            grads = [dw1, db1, dw2, np.asarray(db2)]
            for index, grad in enumerate(grads):
                m[index] = beta1 * m[index] + (1.0 - beta1) * grad
                v[index] = beta2 * v[index] + (1.0 - beta2) * grad**2
                m_hat = m[index] / (1.0 - beta1**epoch)
                v_hat = v[index] / (1.0 - beta2**epoch)
                if index == 0:
                    w1 -= learning_rate * m_hat / (np.sqrt(v_hat) + epsilon)
                elif index == 1:
                    b1 -= learning_rate * m_hat / (np.sqrt(v_hat) + epsilon)
                elif index == 2:
                    w2 -= learning_rate * m_hat / (np.sqrt(v_hat) + epsilon)
                else:
                    b2 -= float(learning_rate * m_hat / (np.sqrt(v_hat) + epsilon))
        train_loss = _loss(x_train, y_train, w1, b1, w2, b2, positive_weight)
        validation_loss = _loss(x_val, y_val, w1, b1, w2, b2, positive_weight)
        return cls(
            w1=w1,
            b1=b1,
            w2=w2,
            b2=b2,
            hidden_units=hidden_units,
            seed=seed,
            epochs=epochs,
            learning_rate=learning_rate,
            train_loss=train_loss,
            validation_loss=validation_loss,
        )

    def predict_proba(self, sample: SurrogateSample) -> np.ndarray:
        """Return per-cell burn probabilities for one sample.

        Parameters
        ----------
        sample : SurrogateSample
            Sample to predict.

        Returns
        -------
        numpy.ndarray
            Probability grid in ``[0, 1]``, zero for non-fuel cells.
        """
        features = sample_features(sample)
        hidden = np.tanh(features @ self.w1.T + self.b1)
        prob = _sigmoid(hidden @ self.w2 + self.b2)
        grid = prob.reshape(sample.shape)
        return grid * (np.asarray(sample.fuel_index) > 0)

    def predict_mask(self, sample: SurrogateSample, *, threshold: float = 0.5) -> np.ndarray:
        """Return a thresholded burned mask for one sample.

        Parameters
        ----------
        sample : SurrogateSample
            Sample to predict.
        threshold : float, optional
            Probability threshold (default 0.5).

        Returns
        -------
        numpy.ndarray
            Boolean mask, zero outside burnable cells.
        """
        if not 0.0 <= threshold <= 1.0:
            raise FireFuelError("threshold must be between 0 and 1")
        return self.predict_proba(sample) >= threshold

    def to_dict(self) -> dict[str, object]:
        """Return model metadata as a JSON-serializable mapping.

        Returns
        -------
        dict
            Version, architecture, training configuration, and losses.
        """
        return {
            "version": self.version,
            "feature_names": list(FEATURE_NAMES),
            "fuel_order": list(SURROGATE_FUEL_ORDER),
            "hidden_units": self.hidden_units,
            "seed": self.seed,
            "epochs": self.epochs,
            "learning_rate": self.learning_rate,
            "train_loss": self.train_loss,
            "validation_loss": self.validation_loss,
            "parameters": int(self.w1.size + self.b1.size + self.w2.size + 1),
        }

    def save(self, directory: str | Path) -> Path:
        """Save the model weights and metadata.

        Parameters
        ----------
        directory : str or Path
            Destination directory.

        Returns
        -------
        Path
            The metadata path.
        """
        root = Path(directory)
        root.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            str(root / "weights.npz"),
            w1=self.w1,
            b1=self.b1,
            w2=self.w2,
            b2=np.asarray(self.b2),
        )
        metadata = root / "model.json"
        metadata.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return metadata

    @classmethod
    def load(cls, directory: str | Path) -> SurrogateModel:
        """Load a model saved by :meth:`save`.

        Parameters
        ----------
        directory : str or Path
            Model directory.

        Returns
        -------
        SurrogateModel
            Loaded model.

        Raises
        ------
        FireFuelError
            If the metadata or weights are missing.
        """
        root = Path(directory)
        metadata_path = root / "model.json"
        weights_path = root / "weights.npz"
        if not metadata_path.is_file() or not weights_path.is_file():
            raise FireFuelError("surrogate model needs model.json and weights.npz")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        with np.load(weights_path, allow_pickle=False) as weights:
            return cls(
                w1=np.asarray(weights["w1"]),
                b1=np.asarray(weights["b1"]),
                w2=np.asarray(weights["w2"]),
                b2=float(weights["b2"]),
                hidden_units=int(metadata["hidden_units"]),
                seed=int(metadata["seed"]),
                epochs=int(metadata["epochs"]),
                learning_rate=float(metadata["learning_rate"]),
                train_loss=float(metadata["train_loss"]),
                validation_loss=float(metadata["validation_loss"]),
            )


def _training_arrays(samples: list[SurrogateSample]) -> tuple[np.ndarray, np.ndarray]:
    """Return flattened features and labels for a set of samples."""
    features = []
    labels = []
    for sample in samples:
        matrix = sample_features(sample)
        burnable = np.asarray(sample.fuel_index).reshape(-1) > 0
        features.append(matrix[burnable])
        labels.append(np.asarray(sample.burned_mask).reshape(-1)[burnable].astype(float))
    return np.vstack(features), np.concatenate(labels)


def _loss(
    features: np.ndarray,
    labels: np.ndarray,
    w1: np.ndarray,
    b1: np.ndarray,
    w2: np.ndarray,
    b2: float,
    positive_weight: float,
) -> float:
    """Return weighted binary cross-entropy."""
    hidden = np.tanh(features @ w1.T + b1)
    prob = _sigmoid(hidden @ w2 + b2)
    weights = np.where(labels > 0.5, positive_weight, 1.0)
    epsilon = 1e-8
    return float(
        np.mean(
            weights
            * (
                -labels * np.log(np.clip(prob, epsilon, 1.0))
                - (1.0 - labels) * np.log(np.clip(1.0 - prob, epsilon, 1.0))
            )
        )
    )
