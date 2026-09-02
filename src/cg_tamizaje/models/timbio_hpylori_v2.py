"""Leakage-controlled internal validation for the Timbio H. pylori v2 cohort."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
import yaml
from sklearn.base import clone
from sklearn.calibration import calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.feature_selection import VarianceThreshold
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, confusion_matrix, f1_score, roc_auc_score, roc_curve
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from cg_tamizaje.paths import ROOT


VERSION = "v2"
ARTIFACTS = ROOT / "artifacts"
METRICS_DIR = ARTIFACTS / "metrics"
MODELS_DIR = ARTIFACTS / "models"
FIGURES_DIR = ARTIFACTS / "figures" / "timbio_hpylori_v2"
REPORTS_DIR = ARTIFACTS / "reports"
REGISTRY_DIR = ARTIFACTS / "model_registry"
INTERIM_DIR = ROOT / "data" / "interim"
MANIFEST_DIR = ROOT / "data" / "manifests"


@dataclass
class RunArtifacts:
    results: pd.DataFrame
    feature_registry: pd.DataFrame
    calibration: pd.DataFrame
    decision_curve: pd.DataFrame
    report_path: Path
    selected_model: str


def normalized(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value).strip().lower())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "", text)


def normalized_label(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value).strip().upper())
    return "".join(char for char in text if not unicodedata.combining(char))


def load_config(config_path: Path) -> dict[str, Any]:
    with config_path.open() as handle:
        return yaml.safe_load(handle)


def load_cohort(config: dict[str, Any]) -> pd.DataFrame:
    source = ROOT / config["input"]["path"]
    df = pd.read_excel(source)
    municipality = config["input"]["municipality_column"]
    target_municipality = normalized_label(config["input"]["municipality_value"])
    df = df.loc[df[municipality].map(normalized_label).eq(target_municipality)].copy()
    outcome = config["input"]["outcome_column"]
    positive = normalized_label(config["input"]["positive_value"])
    negative = normalized_label(config["input"]["negative_value"])
    labels = df[outcome].map(normalized_label)
    df["outcome__resultados_helicobacter_binary"] = labels.map({positive: 1, negative: 0})
    return df.loc[df["outcome__resultados_helicobacter_binary"].notna()].copy()


def build_feature_registry(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    source = ROOT / config["input"]["dictionary_path"]
    dictionary = pd.read_excel(
        source,
        sheet_name=config["input"]["dictionary_sheet"],
        header=int(config["input"]["dictionary_header_row"]),
    )
    mandatory = dictionary.iloc[:, int(config["input"]["mandatory_column_position"]) - 1].eq(1)
    dictionary = dictionary.loc[mandatory].copy()
    available = {normalized(column): str(column) for column in df.columns}
    excluded_names = {normalized(name) for name in config["feature_policy"]["excluded_canonical_variables"]}
    patterns = [re.compile(pattern, re.IGNORECASE) for pattern in config["feature_policy"]["excluded_patterns"]]
    rows: list[dict[str, Any]] = []
    for _, record in dictionary.iterrows():
        canonical = str(record["Variable canónica"])
        source_name = str(record["Nombre variable BD"])
        candidates = [canonical, source_name, str(record["ID metadato fuente"])]
        raw_column = next((available[normalized(value)] for value in candidates if normalized(value) in available), None)
        reason = ""
        eligible = False
        if raw_column is None:
            reason = "mandatory_not_present_in_v2_source"
        elif normalized(canonical) in excluded_names or normalized(source_name) in excluded_names:
            reason = "excluded_by_pre_prediction_policy"
        elif any(pattern.search(normalized(raw_column)) for pattern in patterns):
            reason = "excluded_sensitive_post_outcome_or_derived"
        elif raw_column and df[raw_column].notna().sum() < int(config["feature_policy"]["min_non_missing_predictor_observations"]):
            reason = "excluded_insufficient_observed_values_for_cv"
        else:
            eligible = True
            reason = "mandatory_pre_prediction_authorized"
        completeness = float(df[raw_column].notna().mean()) if raw_column else np.nan
        rows.append(
            {
                "variable_canonical": canonical,
                "source_variable": source_name,
                "raw_column": raw_column or "",
                "mandatory_dictionary_column_r": True,
                "model_eligible": eligible,
                "completeness": completeness,
                "dtype_observed": str(df[raw_column].dtype) if raw_column else "",
                "reason": reason,
            }
        )
    registry = pd.DataFrame(rows)
    if registry["model_eligible"].sum() == 0:
        raise ValueError("No authorized mandatory predictors found after governance rules.")
    return registry


def prepare_model_input(df: pd.DataFrame, registry: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    features = registry.loc[registry["model_eligible"], "raw_column"].tolist()
    X = df[features].copy().replace({"": np.nan, "NA": np.nan, "N/A": np.nan, "null": np.nan})
    y = df["outcome__resultados_helicobacter_binary"].astype(int).copy()
    return X, y, features


def make_preprocessor(X: pd.DataFrame) -> ColumnTransformer:
    numeric = X.select_dtypes(include=["number", "bool"]).columns.tolist()
    categorical = [column for column in X.columns if column not in numeric]
    numeric_steps: list[tuple[str, Any]] = [("imputer", SimpleImputer(strategy="median", keep_empty_features=True)), ("scaler", StandardScaler())]
    categorical_steps: list[tuple[str, Any]] = [
        ("imputer", SimpleImputer(strategy="constant", fill_value="__MISSING__", keep_empty_features=True)),
        ("onehot", OneHotEncoder(handle_unknown="ignore", min_frequency=0.03, sparse_output=False)),
    ]
    return ColumnTransformer(
        [("numeric", Pipeline(numeric_steps), numeric), ("categorical", Pipeline(categorical_steps), categorical)],
        remainder="drop",
        verbose_feature_names_out=True,
    )


def model_specifications(seed: int) -> dict[str, tuple[Any, dict[str, list[Any]]]]:
    return {
        "elastic_net_logistic": (
            LogisticRegression(solver="saga", class_weight="balanced", max_iter=8000, random_state=seed),
            {"model__C": [0.1, 1.0], "model__l1_ratio": [0.2, 0.8]},
        ),
        "random_forest": (
            RandomForestClassifier(class_weight="balanced", n_estimators=300, random_state=seed, n_jobs=1),
            {"model__max_depth": [3, None], "model__min_samples_leaf": [5, 10]},
        ),
        "gradient_boosting": (
            GradientBoostingClassifier(random_state=seed),
            {"model__n_estimators": [100, 200], "model__learning_rate": [0.05], "model__max_depth": [1, 2], "model__min_samples_leaf": [10], "model__subsample": [0.8]},
        ),
    }


def make_pipeline(X: pd.DataFrame, estimator: Any) -> Pipeline:
    return Pipeline(
        [("preprocess", make_preprocessor(X)), ("variance", VarianceThreshold(0.0)), ("model", estimator)]
    )


def calibration_parameters(y: np.ndarray, probabilities: np.ndarray) -> tuple[float, float]:
    clipped = np.clip(probabilities, 1e-6, 1 - 1e-6)
    logit = np.log(clipped / (1 - clipped)).reshape(-1, 1)
    model = LogisticRegression(penalty=None, solver="lbfgs", max_iter=1000).fit(logit, y)
    return float(model.intercept_[0]), float(model.coef_[0, 0])


def choose_threshold(y: np.ndarray, probabilities: np.ndarray, thresholds: list[float], sensitivity_target: float) -> float:
    candidates: list[tuple[float, float]] = []
    for threshold in thresholds:
        predicted = (probabilities >= threshold).astype(int)
        tn, fp, fn, tp = confusion_matrix(y, predicted, labels=[0, 1]).ravel()
        sensitivity = tp / (tp + fn) if tp + fn else 0.0
        specificity = tn / (tn + fp) if tn + fp else 0.0
        if sensitivity >= sensitivity_target:
            candidates.append((specificity, threshold))
    if candidates:
        return max(candidates)[1]
    return max(thresholds, key=lambda threshold: np.mean((probabilities >= threshold).astype(int) == y))


def bootstrap_auc_ci(y: np.ndarray, probabilities: np.ndarray, seed: int, iterations: int) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    indices = np.arange(len(y))
    values = []
    for _ in range(iterations):
        sample = rng.choice(indices, size=len(indices), replace=True)
        if len(np.unique(y[sample])) == 2:
            values.append(roc_auc_score(y[sample], probabilities[sample]))
    return tuple(np.quantile(values, [0.025, 0.975]).tolist())


def metrics_row(name: str, y: np.ndarray, probabilities: np.ndarray, config: dict[str, Any], features: list[str]) -> dict[str, Any]:
    threshold = choose_threshold(y, probabilities, config["validation"]["decision_thresholds"], config["validation"]["sensitivity_target"])
    predicted = (probabilities >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, predicted, labels=[0, 1]).ravel()
    auc_low, auc_high = bootstrap_auc_ci(y, probabilities, config["random_state"], config["validation"]["auc_ci_bootstrap_iterations"])
    intercept, slope = calibration_parameters(y, probabilities)
    return {
        "model_name": name,
        "version": VERSION,
        "n_patients": int(len(y)),
        "n_positive": int(y.sum()),
        "prevalence": float(y.mean()),
        "n_raw_predictors": len(features),
        "auc_oof": float(roc_auc_score(y, probabilities)),
        "auc_oof_ci_low": auc_low,
        "auc_oof_ci_high": auc_high,
        "brier_oof": float(brier_score_loss(y, probabilities)),
        "calibration_intercept_oof": intercept,
        "calibration_slope_oof": slope,
        "threshold_selected_oof": threshold,
        "sensitivity_oof": float(tp / (tp + fn)),
        "specificity_oof": float(tn / (tn + fp)),
        "f1_oof": float(f1_score(y, predicted, zero_division=0)),
        "tp_oof": int(tp),
        "fp_oof": int(fp),
        "tn_oof": int(tn),
        "fn_oof": int(fn),
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def nested_cv(X: pd.DataFrame, y: pd.Series, features: list[str], config: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Pipeline]]:
    seed = int(config["random_state"])
    outer = StratifiedKFold(n_splits=int(config["validation"]["outer_folds"]), shuffle=True, random_state=seed)
    inner = StratifiedKFold(n_splits=int(config["validation"]["inner_folds"]), shuffle=True, random_state=seed + 1)
    result_rows: list[dict[str, Any]] = []
    oof_rows: list[pd.DataFrame] = []
    tuning_rows: list[dict[str, Any]] = []
    fitted: dict[str, Pipeline] = {}
    for model_name, (estimator, grid) in model_specifications(seed).items():
        probabilities = np.full(len(X), np.nan)
        for fold, (train_idx, test_idx) in enumerate(outer.split(X, y), start=1):
            print(f"{model_name}: outer fold {fold}/{outer.get_n_splits()}", flush=True)
            pipeline = make_pipeline(X.iloc[train_idx], clone(estimator))
            search = GridSearchCV(pipeline, grid, scoring="roc_auc", cv=inner, n_jobs=1, refit=True, error_score="raise")
            search.fit(X.iloc[train_idx], y.iloc[train_idx])
            probabilities[test_idx] = search.predict_proba(X.iloc[test_idx])[:, 1]
            tuning_rows.append({"model_name": model_name, "outer_fold": fold, "inner_best_auc": search.best_score_, "best_params": json.dumps(search.best_params_, sort_keys=True)})
        result_rows.append(metrics_row(model_name, y.to_numpy(), probabilities, config, features))
        oof_rows.append(pd.DataFrame({"row_index": X.index, "model_name": model_name, "y_true": y.to_numpy(), "probability_oof": probabilities}))
        full_search = GridSearchCV(make_pipeline(X, clone(estimator)), grid, scoring="roc_auc", cv=outer, n_jobs=1, refit=True, error_score="raise")
        full_search.fit(X, y)
        fitted[model_name] = full_search.best_estimator_
        joblib.dump(full_search.best_estimator_, MODELS_DIR / f"timbio_hpylori_{model_name}_{VERSION}.joblib")
        tuning_rows.append({"model_name": model_name, "outer_fold": "full_data_refit", "inner_best_auc": full_search.best_score_, "best_params": json.dumps(full_search.best_params_, sort_keys=True)})
    return pd.DataFrame(result_rows).sort_values("auc_oof", ascending=False), pd.concat(oof_rows, ignore_index=True), pd.DataFrame(tuning_rows), fitted


def calibration_table(oof: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for name, group in oof.groupby("model_name"):
        observed, predicted = calibration_curve(group["y_true"], group["probability_oof"], n_bins=5, strategy="quantile")
        rows.append(pd.DataFrame({"model_name": name, "bin": np.arange(1, len(observed) + 1), "observed_rate": observed, "mean_predicted_probability": predicted}))
    return pd.concat(rows, ignore_index=True)


def decision_curve(y: np.ndarray, probabilities: np.ndarray, model_name: str, thresholds: list[float]) -> pd.DataFrame:
    prevalence = y.mean()
    rows = []
    for threshold in thresholds:
        predicted = probabilities >= threshold
        tp = int(np.sum((predicted == 1) & (y == 1)))
        fp = int(np.sum((predicted == 1) & (y == 0)))
        weight = threshold / (1 - threshold)
        rows.extend(
            [
                {"model_name": model_name, "strategy": "model", "threshold": threshold, "net_benefit": tp / len(y) - fp / len(y) * weight},
                {"model_name": model_name, "strategy": "treat_all", "threshold": threshold, "net_benefit": prevalence - (1 - prevalence) * weight},
                {"model_name": model_name, "strategy": "treat_none", "threshold": threshold, "net_benefit": 0.0},
            ]
        )
    return pd.DataFrame(rows)


def bootstrap_optimism(model: Pipeline, X: pd.DataFrame, y: pd.Series, seed: int, iterations: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    apparent = model.predict_proba(X)[:, 1]
    apparent_auc = roc_auc_score(y, apparent)
    apparent_brier = brier_score_loss(y, apparent)
    rows = []
    for iteration in range(1, iterations + 1):
        sample = rng.choice(np.arange(len(X)), size=len(X), replace=True)
        y_boot = y.iloc[sample]
        if y_boot.nunique() < 2:
            continue
        boot_model = clone(model).fit(X.iloc[sample], y_boot)
        boot_pred = boot_model.predict_proba(X.iloc[sample])[:, 1]
        original_pred = boot_model.predict_proba(X)[:, 1]
        rows.append(
            {
                "iteration": iteration,
                "auc_optimism": roc_auc_score(y_boot, boot_pred) - roc_auc_score(y, original_pred),
                "brier_optimism": brier_score_loss(y, original_pred) - brier_score_loss(y_boot, boot_pred),
                "apparent_auc": apparent_auc,
                "apparent_brier": apparent_brier,
            }
        )
    return pd.DataFrame(rows)


def shap_importance(model: Pipeline, X: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
    transformed = model.named_steps["preprocess"].transform(X)
    names = model.named_steps["preprocess"].get_feature_names_out()
    support = model.named_steps["variance"].get_support()
    transformed = transformed[:, support]
    names = names[support]
    estimator = model.named_steps["model"]
    sample = transformed[: min(200, len(transformed))]
    if isinstance(estimator, LogisticRegression):
        values = shap.LinearExplainer(estimator, sample).shap_values(sample)
    else:
        values = shap.TreeExplainer(estimator).shap_values(sample)
    values = np.asarray(values)
    if values.ndim == 3:
        values = values[:, :, 1] if values.shape[-1] == 2 else values[1]
    importance = np.mean(np.abs(values), axis=0)
    table = pd.DataFrame({"encoded_feature": names, "mean_abs_shap": importance}).sort_values("mean_abs_shap", ascending=False)
    table["source_feature"] = table["encoded_feature"].str.replace(r"^(numeric|categorical)__", "", regex=True).str.split("_").str[0]
    return table


def make_figures(results: pd.DataFrame, oof: pd.DataFrame, calibration: pd.DataFrame, decision: pd.DataFrame, shap_table: pd.DataFrame) -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    plot = results.sort_values("auc_oof")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.barh(plot["model_name"], plot["auc_oof"], color="#1f6f8b")
    ax.errorbar(plot["auc_oof"], plot["model_name"], xerr=[plot["auc_oof"] - plot["auc_oof_ci_low"], plot["auc_oof_ci_high"] - plot["auc_oof"]], fmt="none", color="#17202a", capsize=3)
    ax.axvline(0.5, color="#9b1c31", linestyle="--", linewidth=1)
    ax.set(xlabel="AUC ROC fuera de pliegue", title="Comparación interna: validación cruzada anidada")
    fig.tight_layout(); fig.savefig(FIGURES_DIR / "auc_comparison_v2.png", dpi=180); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 5))
    for name, group in oof.groupby("model_name"):
        fpr, tpr, _ = roc_curve(group["y_true"], group["probability_oof"])
        auc = roc_auc_score(group["y_true"], group["probability_oof"])
        ax.plot(fpr, tpr, label=f"{name} (AUC={auc:.3f})")
    ax.plot([0, 1], [0, 1], "--", color="gray"); ax.set(xlabel="1 - especificidad", ylabel="sensibilidad", title="Curvas ROC fuera de pliegue")
    ax.legend(fontsize=8); fig.tight_layout(); fig.savefig(FIGURES_DIR / "roc_oof_v2.png", dpi=180); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 5))
    for name, group in calibration.groupby("model_name"):
        ax.plot(group["mean_predicted_probability"], group["observed_rate"], marker="o", label=name)
    ax.plot([0, 1], [0, 1], "--", color="gray"); ax.set(xlabel="probabilidad media predicha", ylabel="frecuencia observada", title="Calibración fuera de pliegue")
    ax.legend(fontsize=8); fig.tight_layout(); fig.savefig(FIGURES_DIR / "calibration_oof_v2.png", dpi=180); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 4.5))
    for strategy, group in decision.groupby("strategy"):
        ax.plot(group["threshold"], group["net_benefit"], marker="o", label=strategy)
    ax.axhline(0, color="gray", linewidth=1); ax.set(xlabel="umbral de riesgo", ylabel="beneficio neto", title="Análisis de curva de decisión: modelo ganador")
    ax.legend(); fig.tight_layout(); fig.savefig(FIGURES_DIR / "decision_curve_v2.png", dpi=180); plt.close(fig)

    top = shap_table.head(15).sort_values("mean_abs_shap")
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(top["encoded_feature"], top["mean_abs_shap"], color="#c65d3a")
    ax.set(xlabel="media de |SHAP|", title="Explicabilidad del modelo final: importancia global")
    fig.tight_layout(); fig.savefig(FIGURES_DIR / "shap_importance_v2.png", dpi=180); plt.close(fig)


def markdown_report(results: pd.DataFrame, registry: pd.DataFrame, bootstrap: pd.DataFrame, selected: str, config: dict[str, Any]) -> str:
    winner = results.loc[results["model_name"].eq(selected)].iloc[0]
    corrected_auc = winner["auc_oof"] - bootstrap["auc_optimism"].mean()
    corrected_brier = winner["brier_oof"] + bootstrap["brier_optimism"].mean()
    visible = results[["model_name", "auc_oof", "auc_oof_ci_low", "auc_oof_ci_high", "brier_oof", "calibration_slope_oof", "threshold_selected_oof", "sensitivity_oof", "specificity_oof", "f1_oof"]].round(3)
    table = "| " + " | ".join(visible.columns) + " |\n|" + "|".join(["---"] * len(visible.columns)) + "|\n"
    table += "\n".join("| " + " | ".join(str(value) for value in row) + " |" for row in visible.itertuples(index=False, name=None))
    return f"""# Modelo de factibilidad de H. pylori en Timbío v2

## Diseño y población

Fuente analítica: `biomarkers_timbio_with_sociodemographics_v2.xlsx`, filtrada a Timbío. El outcome provisional es `Resultados_Helicobacter`; se conservaron solo `Positivo` y `Negativo`. La cohorte analítica contiene {int(winner['n_patients'])} pacientes, con {int(winner['n_positive'])} positivos ({winner['prevalence']:.1%}).

## Gobernanza y prevención de leakage

El diccionario oficial aportó {len(registry)} variables obligatorias de la columna R. Se autorizaron {int(registry['model_eligible'].sum())} predictores prediagnóstico. Se excluyeron explícitamente identificadores, variables sensibles, fechas, resultados de H. pylori, biomarcadores, endoscopia, histología, scores y riesgos derivados. La imputación, codificación, filtrado de varianza y tuning están dentro de cada pliegue de remuestreo.

## Validación

Se compararon elastic net, random forest y gradient boosting mediante validación cruzada anidada ({config['validation']['outer_folds']} pliegues externos, {config['validation']['inner_folds']} pliegues internos), con AUC como métrica de tuning. El modelo seleccionado se sometió a bootstrap interno ({len(bootstrap)} réplicas) para estimar optimismo.

## Resultados

Modelo seleccionado por AUC fuera de pliegue: **{selected}**. AUC={winner['auc_oof']:.3f} (IC bootstrap {winner['auc_oof_ci_low']:.3f}-{winner['auc_oof_ci_high']:.3f}); Brier={winner['brier_oof']:.3f}; pendiente de calibración={winner['calibration_slope_oof']:.3f}. La corrección bootstrap por optimismo produjo AUC={corrected_auc:.3f} y Brier={corrected_brier:.3f}.

El umbral descriptivo seleccionado en predicciones fuera de pliegue fue {winner['threshold_selected_oof']:.2f}, dirigido a sensibilidad de al menos {config['validation']['sensitivity_target']:.0%}; su sensibilidad fue {winner['sensitivity_oof']:.3f} y especificidad {winner['specificity_oof']:.3f}. Este umbral requiere validación adicional antes de uso clínico.

{table}

## Interpretación y límites

Los resultados son una evaluación interna de factibilidad, no validación clínica ni externa. El tamaño de muestra y el número de eventos siguen siendo limitados. La explicación SHAP describe el comportamiento del modelo final entrenado correctamente; no establece causalidad ni sustituye el rendimiento, la calibración o la validación externa.

## Reproducción

Ejecutar `python scripts/run_timbio_hpylori_model_v2.py` desde el entorno `.venv-model-v2`. Las fuentes crudas se leen sin modificación; la copia de modelado desidentificada, las matrices, métricas, figuras, modelo y reportes se generan con sufijo `_v2`.
"""


def run(config_path: Path | None = None) -> RunArtifacts:
    config = load_config(config_path or ROOT / "configs" / "timbio_hpylori_model_v2.yaml")
    for path in [METRICS_DIR, MODELS_DIR, FIGURES_DIR, REPORTS_DIR, REGISTRY_DIR, INTERIM_DIR, MANIFEST_DIR]:
        path.mkdir(parents=True, exist_ok=True)
    cohort = load_cohort(config)
    registry = build_feature_registry(cohort, config)
    X, y, features = prepare_model_input(cohort, registry)
    deidentified = X.copy(); deidentified["Resultados_Helicobacter"] = y.map({1: "Positivo", 0: "Negativo"})
    deidentified.to_parquet(INTERIM_DIR / "timbio_hpylori_model_input_deidentified_v2.parquet", index=False)
    deidentified.to_excel(INTERIM_DIR / "timbio_hpylori_model_input_deidentified_v2.xlsx", index=False)
    registry.to_csv(MANIFEST_DIR / "feature_registry_timbio_hpylori_v2.csv", index=False)
    results, oof, tuning, fitted = nested_cv(X, y, features, config)
    calibration = calibration_table(oof)
    selected = results.iloc[0]["model_name"]
    selected_oof = oof.loc[oof["model_name"].eq(selected)]
    decision = decision_curve(y.to_numpy(), selected_oof["probability_oof"].to_numpy(), selected, config["validation"]["decision_thresholds"])
    bootstrap = bootstrap_optimism(fitted[selected], X, y, int(config["random_state"]), int(config["validation"]["bootstrap_iterations"]))
    shap_table = shap_importance(fitted[selected], X, y)
    permutation = permutation_importance(fitted[selected], X, y, scoring="roc_auc", n_repeats=30, random_state=int(config["random_state"]), n_jobs=1)
    permutation_table = pd.DataFrame({"feature": X.columns, "importance_mean_auc_drop": permutation.importances_mean, "importance_std": permutation.importances_std}).sort_values("importance_mean_auc_drop", ascending=False)
    make_figures(results, oof, calibration, decision, shap_table)
    results.to_csv(REGISTRY_DIR / "model_results_timbio_hpylori_v2.csv", index=False)
    oof.to_csv(METRICS_DIR / "model_oof_predictions_timbio_hpylori_v2.csv", index=False)
    tuning.to_csv(METRICS_DIR / "model_tuning_trace_timbio_hpylori_v2.csv", index=False)
    calibration.to_csv(METRICS_DIR / "model_calibration_timbio_hpylori_v2.csv", index=False)
    decision.to_csv(METRICS_DIR / "decision_curve_timbio_hpylori_v2.csv", index=False)
    bootstrap.to_csv(METRICS_DIR / "bootstrap_optimism_timbio_hpylori_v2.csv", index=False)
    shap_table.to_csv(METRICS_DIR / "shap_importance_timbio_hpylori_v2.csv", index=False)
    permutation_table.to_csv(METRICS_DIR / "permutation_importance_timbio_hpylori_v2.csv", index=False)
    report_path = REPORTS_DIR / "model_feasibility_timbio_hpylori_v2.md"
    report_text = markdown_report(results, registry, bootstrap, selected, config)
    report_path.write_text(report_text)
    (ROOT / "reports" / "model_feasibility_timbio_hpylori_v2.md").write_text(report_text)
    return RunArtifacts(results, registry, calibration, decision, report_path, selected)
