# Mapa de evidencia T01–T04

| Tarea | Evidencia principal en este repositorio | Qué permite verificar |
|---|---|---|
| T01. Exploración y comprensión de datos | `docs/decisions_log.md`, `data/manifests/feature_registry_timbio_hpylori_v2.csv`, configuración YAML | Definición de cohorte, outcome, disponibilidad y elegibilidad de variables |
| T02. Preparación y transformación de datos | `scripts/join_timbio_biomarkers_sociodemographics.py`, `src/cg_tamizaje/models/timbio_hpylori_v2.py` | Integración, desidentificación, imputación, codificación, manejo de categorías raras y prevención de leakage |
| T03. Selección y evaluación de variables | `feature_registry_timbio_hpylori_v2.csv`, importancia por permutación y SHAP | Exclusiones por política temporal, variables autorizadas y análisis exploratorio de importancia |
| T04. Entrenamiento, validación y evaluación | `run_timbio_hpylori_model_v2.py`, `model_results_timbio_hpylori_v2.csv`, calibración, bootstrap, curva de decisión e informe TRIPOD+AI | Comparación de modelos, tuning, AUC, Brier, calibración, sensibilidad, especificidad, optimismo y utilidad clínica |

## Nota
Las tareas T01–T04 están integradas en un único pipeline reproducible. Esta organización evita separar artificialmente fases que dependen unas de otras y permite rastrear cada decisión desde la configuración hasta los resultados agregados.
