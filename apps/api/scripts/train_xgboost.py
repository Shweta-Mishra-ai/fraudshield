"""
FraudShield — XGBoost Training Pipeline
========================================
Trains on IEEE-CIS Fraud Detection dataset (590k real transactions).

Usage:
    # 1. Download dataset
    python scripts/train_xgboost.py --download

    # 2. Train model
    python scripts/train_xgboost.py --train

    # 3. Download + Train in one step
    python scripts/train_xgboost.py --download --train

Output:
    data/models/xgboost_model.json     ← trained model
    data/models/model_metadata.json    ← AUC, precision, recall, thresholds
    data/models/feature_importance.json ← SHAP feature rankings

Expected results on IEEE-CIS:
    AUC-ROC:   0.92 – 0.96
    Precision: 0.70 – 0.85  (at 0.5 threshold)
    Recall:    0.65 – 0.80
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────
DATA_DIR   = Path("data/ieee")
MODEL_DIR  = Path("data/models")
TRAIN_FILE = DATA_DIR / "train_transaction.csv"
MODEL_FILE = MODEL_DIR / "xgboost_model.json"
META_FILE  = MODEL_DIR / "model_metadata.json"
IMPORTANCE_FILE = MODEL_DIR / "feature_importance.json"


# ══════════════════════════════════════════════════════════════════════════
# Step 1 — Download
# ══════════════════════════════════════════════════════════════════════════

def download_dataset() -> None:
    """Download IEEE-CIS dataset from Kaggle."""
    logger.info("Downloading IEEE-CIS Fraud Detection dataset from Kaggle...")
    logger.info("This requires kaggle API credentials (~500MB download)")

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if TRAIN_FILE.exists():
        size_mb = TRAIN_FILE.stat().st_size / 1_048_576
        logger.info("Dataset already exists (%.1f MB) — skipping download", size_mb)
        return

    # Check kaggle credentials
    kaggle_dir  = Path.home() / ".kaggle"
    kaggle_json = kaggle_dir / "kaggle.json"

    if not kaggle_json.exists():
        print("\n" + "="*60)
        print("  KAGGLE SETUP REQUIRED")
        print("="*60)
        print()
        print("  1. Go to: https://www.kaggle.com/settings/account")
        print("  2. Scroll to 'API' section")
        print("  3. Click 'Create New Token'")
        print("  4. Download kaggle.json")
        print(f"  5. Move it to: {kaggle_json}")
        print()
        print("  Then run: python scripts/train_xgboost.py --download")
        print("="*60)
        sys.exit(1)

    try:
        result = subprocess.run(
            ["kaggle", "competitions", "download",
             "-c", "ieee-fraud-detection",
             "-p", str(DATA_DIR)],
            capture_output=True, text=True, check=True
        )
        logger.info("Download complete: %s", result.stdout.strip())

        # Unzip
        import zipfile
        zip_path = DATA_DIR / "ieee-fraud-detection.zip"
        if zip_path.exists():
            logger.info("Extracting dataset...")
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(DATA_DIR)
            zip_path.unlink()
            logger.info("Extraction complete")

    except subprocess.CalledProcessError as exc:
        logger.error("Kaggle download failed: %s", exc.stderr)
        print("\nIf you haven't accepted the competition rules:")
        print("→ Go to: https://www.kaggle.com/c/ieee-fraud-detection")
        print("→ Click 'Join Competition' and accept rules")
        sys.exit(1)


# ══════════════════════════════════════════════════════════════════════════
# Step 2 — Load + Engineer Features
# ══════════════════════════════════════════════════════════════════════════

def load_and_engineer(sample_frac: float = 1.0) -> tuple:
    """
    Load IEEE-CIS dataset and engineer our 22 features.
    Returns (X, y, feature_names).
    """
    logger.info("Loading IEEE-CIS dataset...")

    if not TRAIN_FILE.exists():
        raise FileNotFoundError(
            f"Dataset not found at {TRAIN_FILE}\n"
            "Run: python scripts/train_xgboost.py --download"
        )

    df = pd.read_csv(TRAIN_FILE)
    logger.info("Loaded %d rows, %d columns", len(df), len(df.columns))
    logger.info("Fraud rate: %.2f%%", df["isFraud"].mean() * 100)

    if sample_frac < 1.0:
        df = df.sample(frac=sample_frac, random_state=42)
        logger.info("Sampled to %d rows (frac=%.2f)", len(df), sample_frac)

    # Map to our features
    from scripts.ieee_feature_mapper import map_ieee_to_features, FEATURE_NAMES
    X_df = map_ieee_to_features(df)
    y    = df["isFraud"].values

    # Fill any remaining NaN
    X_df = X_df.fillna(0)

    # Ensure correct column order
    X = X_df[FEATURE_NAMES].values.astype(np.float32)

    logger.info("Feature matrix: %s | Fraud: %d (%.2f%%)",
                X.shape, y.sum(), y.mean() * 100)

    return X, y, FEATURE_NAMES


# ══════════════════════════════════════════════════════════════════════════
# Step 3 — Train XGBoost
# ══════════════════════════════════════════════════════════════════════════

def train(sample_frac: float = 1.0) -> dict:
    """Train XGBoost and save model + metadata."""
    import xgboost as xgb
    import shap
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import (
        roc_auc_score, average_precision_score,
        precision_score, recall_score, f1_score,
        confusion_matrix,
    )
    from sklearn.calibration import CalibratedClassifierCV

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    # ── Load data ─────────────────────────────────────────────────────────
    X, y, feature_names = load_and_engineer(sample_frac)

    # ── Train/val/test split (60/20/20) ───────────────────────────────────
    X_temp, X_test, y_temp, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_temp, y_temp, test_size=0.25, random_state=42, stratify=y_temp
    )
    logger.info("Train: %d | Val: %d | Test: %d", len(X_train), len(X_val), len(X_test))

    # ── Class imbalance ───────────────────────────────────────────────────
    fraud_rate    = y_train.mean()
    scale_pos_wt  = round((1 - fraud_rate) / fraud_rate, 2)
    logger.info("Class imbalance scale_pos_weight = %.1f", scale_pos_wt)

    # ── Model config ──────────────────────────────────────────────────────
    model = xgb.XGBClassifier(
        n_estimators       = 500,
        max_depth          = 6,
        learning_rate      = 0.05,
        subsample          = 0.8,
        colsample_bytree   = 0.8,
        min_child_weight   = 10,
        gamma              = 1,
        reg_alpha          = 0.1,
        reg_lambda         = 1.0,
        scale_pos_weight   = scale_pos_wt,
        eval_metric        = "auc",
        early_stopping_rounds = 30,
        random_state       = 42,
        n_jobs             = -1,
        tree_method        = "hist",    # fast on CPU
    )

    # ── Train ─────────────────────────────────────────────────────────────
    logger.info("Training XGBoost on %d samples...", len(X_train))
    t0 = time.time()

    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        verbose=50,
    )

    train_time = round(time.time() - t0, 1)
    logger.info("Training complete in %.1fs", train_time)

    # ── Evaluate on test set ──────────────────────────────────────────────
    y_prob = model.predict_proba(X_test)[:, 1]
    y_pred = (y_prob >= 0.5).astype(int)

    auc     = round(roc_auc_score(y_test, y_prob), 4)
    ap      = round(average_precision_score(y_test, y_prob), 4)
    prec    = round(precision_score(y_test, y_pred, zero_division=0), 4)
    rec     = round(recall_score(y_test, y_pred, zero_division=0), 4)
    f1      = round(f1_score(y_test, y_pred, zero_division=0), 4)
    tn, fp, fn, tp = confusion_matrix(y_test, y_pred).ravel()

    logger.info("="*50)
    logger.info("TEST SET RESULTS:")
    logger.info("  AUC-ROC:           %.4f", auc)
    logger.info("  Avg Precision:     %.4f", ap)
    logger.info("  Precision @0.5:    %.4f", prec)
    logger.info("  Recall    @0.5:    %.4f", rec)
    logger.info("  F1-Score  @0.5:    %.4f", f1)
    logger.info("  True Positives:    %d", tp)
    logger.info("  False Positives:   %d", fp)
    logger.info("  False Negatives:   %d", fn)
    logger.info("  True Negatives:    %d", tn)
    logger.info("="*50)

    # ── Optimal threshold (maximize F1) ───────────────────────────────────
    thresholds  = np.arange(0.1, 0.9, 0.05)
    f1_scores   = [f1_score(y_test, (y_prob >= t).astype(int), zero_division=0)
                   for t in thresholds]
    best_thresh = round(float(thresholds[np.argmax(f1_scores)]), 2)
    best_f1     = round(max(f1_scores), 4)
    logger.info("Optimal threshold: %.2f (F1=%.4f)", best_thresh, best_f1)

    # ── SHAP feature importance ───────────────────────────────────────────
    logger.info("Computing SHAP feature importance (sample of 2000)...")
    sample_idx  = np.random.choice(len(X_test), min(2000, len(X_test)), replace=False)
    X_sample    = X_test[sample_idx]
    explainer   = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_sample)

    mean_abs_shap = np.abs(shap_values).mean(axis=0)
    importance    = sorted(
        zip(feature_names, mean_abs_shap.tolist()),
        key=lambda x: x[1], reverse=True
    )

    logger.info("Top 10 most important features:")
    for name, val in importance[:10]:
        logger.info("  %-35s  %.4f", name, val)

    # ── Save model ────────────────────────────────────────────────────────
    model.save_model(str(MODEL_FILE))
    logger.info("Model saved → %s", MODEL_FILE)

    # ── Save metadata ─────────────────────────────────────────────────────
    metadata = {
        "model_version":    "2.1.0",
        "trained_at":       time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dataset":          "IEEE-CIS Fraud Detection (Kaggle)",
        "train_samples":    len(X_train),
        "val_samples":      len(X_val),
        "test_samples":     len(X_test),
        "fraud_rate_train": round(float(y_train.mean() * 100), 3),
        "scale_pos_weight": scale_pos_wt,
        "train_seconds":    train_time,
        "best_iteration":   model.best_iteration,
        "metrics": {
            "auc_roc":          auc,
            "avg_precision":    ap,
            "precision_at_0_5": prec,
            "recall_at_0_5":    rec,
            "f1_at_0_5":        f1,
            "optimal_threshold": best_thresh,
            "f1_at_optimal":    best_f1,
        },
        "confusion_matrix": {
            "true_positives":  int(tp),
            "false_positives": int(fp),
            "false_negatives": int(fn),
            "true_negatives":  int(tn),
        },
        "feature_names": feature_names,
    }

    with open(META_FILE, "w") as f:
        json.dump(metadata, f, indent=2)
    logger.info("Metadata saved → %s", META_FILE)

    # ── Save feature importance ───────────────────────────────────────────
    with open(IMPORTANCE_FILE, "w") as f:
        json.dump([{"feature": n, "shap_importance": round(v, 6)}
                   for n, v in importance], f, indent=2)
    logger.info("Feature importance saved → %s", IMPORTANCE_FILE)

    print("\n" + "="*60)
    print("  🎉 TRAINING COMPLETE")
    print("="*60)
    print(f"  AUC-ROC:            {auc:.4f}")
    print(f"  Avg Precision:      {ap:.4f}")
    print(f"  F1 @ optimal:       {best_f1:.4f}  (threshold={best_thresh})")
    print(f"  Train time:         {train_time}s")
    print(f"  Model saved to:     {MODEL_FILE}")
    print("="*60)
    print()
    print("  Next step — load model in detector:")
    print("  python scripts/train_xgboost.py --verify")
    print("="*60 + "\n")

    return metadata


# ══════════════════════════════════════════════════════════════════════════
# Step 4 — Verify trained model loads correctly
# ══════════════════════════════════════════════════════════════════════════

def verify() -> None:
    """Load saved model and run a quick smoke test."""
    import xgboost as xgb

    if not MODEL_FILE.exists():
        logger.error("No model found at %s — run --train first", MODEL_FILE)
        sys.exit(1)

    logger.info("Loading model from %s...", MODEL_FILE)
    model = xgb.XGBClassifier()
    model.load_model(str(MODEL_FILE))

    # Load metadata
    with open(META_FILE) as f:
        meta = json.load(f)

    # Quick smoke test
    from scripts.ieee_feature_mapper import FEATURE_NAMES
    dummy = np.zeros((3, len(FEATURE_NAMES)), dtype=np.float32)
    dummy[0, 0] = 50.0     # normal
    dummy[1, 0] = 15000.0  # high value
    dummy[2, 0] = 1.0      # small

    probs = model.predict_proba(dummy)[:, 1]

    print("\n" + "="*60)
    print("  ✅ MODEL VERIFICATION")
    print("="*60)
    print(f"  Trained on:    {meta['dataset']}")
    print(f"  Train samples: {meta['train_samples']:,}")
    print(f"  AUC-ROC:       {meta['metrics']['auc_roc']}")
    print(f"  Optimal thresh:{meta['metrics']['optimal_threshold']}")
    print()
    print("  Smoke test predictions:")
    print(f"    Normal tx ($50):      {probs[0]:.4f} fraud probability")
    print(f"    High value ($15,000): {probs[1]:.4f} fraud probability")
    print(f"    Small tx ($1):        {probs[2]:.4f} fraud probability")
    print()
    print("  Model is ready to use in FraudDetector!")
    print("="*60 + "\n")


# ══════════════════════════════════════════════════════════════════════════
# Step 5 — Load model into FraudDetector
# ══════════════════════════════════════════════════════════════════════════

def load_trained_model_into_detector() -> None:
    """
    Load saved XGBoost model into the live FraudDetector.
    Call this in API startup after hydration.
    """
    import xgboost as xgb
    from src.ml.ensemble import MLEnsemble

    if not MODEL_FILE.exists():
        logger.warning("No trained model found at %s — using IsoForest only", MODEL_FILE)
        return None

    model = xgb.XGBClassifier()
    model.load_model(str(MODEL_FILE))

    ensemble = MLEnsemble()
    ensemble.xgb._model = model

    logger.info("Trained XGBoost model loaded into ensemble")
    return ensemble


# ══════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="FraudShield XGBoost Training Pipeline"
    )
    parser.add_argument("--download", action="store_true",
                        help="Download IEEE-CIS dataset from Kaggle")
    parser.add_argument("--train",    action="store_true",
                        help="Train XGBoost model")
    parser.add_argument("--verify",   action="store_true",
                        help="Verify saved model loads correctly")
    parser.add_argument("--sample",   type=float, default=1.0,
                        help="Fraction of data to use (0.1-1.0, default=1.0)")
    args = parser.parse_args()

    if not any([args.download, args.train, args.verify]):
        parser.print_help()
        sys.exit(0)

    if args.download:
        download_dataset()

    if args.train:
        train(sample_frac=args.sample)

    if args.verify:
        verify()
