# Modelo de factibilidad de H. pylori en Timbío v2

## Diseño y población

Fuente analítica: `biomarkers_timbio_with_sociodemographics_v2.xlsx`, filtrada a Timbío. El outcome provisional es `Resultados_Helicobacter`; se conservaron solo `Positivo` y `Negativo`. La cohorte analítica contiene 276 pacientes, con 89 positivos (32.2%).

## Gobernanza y prevención de leakage

El diccionario oficial aportó 63 variables obligatorias de la columna R. Se autorizaron 57 predictores prediagnóstico. Se excluyeron explícitamente identificadores, variables sensibles, fechas, resultados de H. pylori, biomarcadores, endoscopia, histología, scores y riesgos derivados. La imputación, codificación, filtrado de varianza y tuning están dentro de cada pliegue de remuestreo.

## Validación

Se compararon elastic net, random forest y gradient boosting mediante validación cruzada anidada (5 pliegues externos, 3 pliegues internos), con AUC como métrica de tuning. El modelo seleccionado se sometió a bootstrap interno (200 réplicas) para estimar optimismo.

## Resultados

Modelo seleccionado por AUC fuera de pliegue: **random_forest**. AUC=0.516 (IC bootstrap 0.440-0.585); Brier=0.245; pendiente de calibración=0.551. La corrección bootstrap por optimismo produjo AUC=0.379 y Brier=0.302.

El umbral descriptivo seleccionado en predicciones fuera de pliegue fue 0.40, dirigido a sensibilidad de al menos 80%; su sensibilidad fue 0.944 y especificidad 0.080. Este umbral requiere validación adicional antes de uso clínico.

| model_name | auc_oof | auc_oof_ci_low | auc_oof_ci_high | brier_oof | calibration_slope_oof | threshold_selected_oof | sensitivity_oof | specificity_oof | f1_oof |
|---|---|---|---|---|---|---|---|---|---|
| random_forest | 0.516 | 0.44 | 0.585 | 0.245 | 0.551 | 0.4 | 0.944 | 0.08 | 0.487 |
| gradient_boosting | 0.513 | 0.442 | 0.579 | 0.228 | 0.151 | 0.2 | 0.865 | 0.171 | 0.48 |
| elastic_net_logistic | 0.502 | 0.426 | 0.573 | 0.26 | 0.119 | 0.4 | 0.831 | 0.15 | 0.46 |

## Interpretación y límites

Los resultados son una evaluación interna de factibilidad, no validación clínica ni externa. El tamaño de muestra y el número de eventos siguen siendo limitados. La explicación SHAP describe el comportamiento del modelo final entrenado correctamente; no establece causalidad ni sustituye el rendimiento, la calibración o la validación externa.

## Reproducción

Ejecutar `python scripts/run_timbio_hpylori_model_v2.py` desde el entorno `.venv-model-v2`. Las fuentes crudas se leen sin modificación; la copia de modelado desidentificada, las matrices, métricas, figuras, modelo y reportes se generan con sufijo `_v2`.
