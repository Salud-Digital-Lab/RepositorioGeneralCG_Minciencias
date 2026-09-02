# Informe de modelado TRIPOD+AI v2: H. pylori en Timbío

Generado: 2026-09-02T20:32:22+00:00 UTC.

## Dictamen ejecutivo

Esta segunda iteración corrige los problemas metodológicos señalados en la revisión previa: fuente local sin publicar, entrada de modelado desidentificada, exclusión explícita de leakage, preprocesamiento dentro de los pliegues, validación cruzada anidada, bootstrap de optimismo, calibración y análisis de decisión. Aun con estas correcciones, no se observó discriminación clínica útil para el desenlace `Resultados_Helicobacter`. El mejor modelo fue `random_forest` con AUC fuera de pliegue 0.516 (IC bootstrap 0.440-0.585); el intervalo cruza 0.5. El desempeño corregido por optimismo fue AUC=0.379. Por tanto, el modelo no debe usarse para decisión clínica ni priorización de pacientes.

## 1. Pregunta y fuente de datos

Población: pacientes de Timbío de `biomarkers_timbio_with_sociodemographics_v2.xlsx`.

Outcome provisional: `Resultados_Helicobacter`, con `Positivo`=1 y `Negativo`=0. Se excluyeron los registros `No Registra`. La cohorte analítica final tuvo 276 pacientes y 89 positivos (32.2%).

La elección de `Resultados_Helicobacter` responde a la indicación de esta iteración. Frente a `H_pylori_heces`, hubo 276 coincidencias informativas y un positivo adicional en `H_pylori_heces`; este detalle debe mantenerse documentado si el outcome cambia en una futura iteración.

## 2. Correcciones implementadas respecto a la revisión metodológica

- La fuente se trató como solo lectura y se creó una matriz de modelado sin identificadores directos en `data/interim/`.
- La política de predictores partió de las 63 variables obligatorias de la columna R del diccionario oficial.
- Se autorizaron 57 predictores prediagnóstico. Se excluyeron datos sensibles, resultados, biomarcadores, endoscopia, histología, scores y riesgos derivados.
- Imputación, manejo de faltantes, agrupación de categorías raras, one-hot encoding y filtrado de varianza se ajustaron exclusivamente dentro de cada pliegue.
- Se compararon elastic net, random forest y gradient boosting bajo el mismo esquema de validación cruzada anidada.
- El stepwise no se usó como estrategia de selección.
- SHAP se calculó únicamente sobre el modelo final reconstruido bajo este pipeline corregido.

Variables obligatorias no elegibles:
- `data_datos_ubicacion_riesgo_class`: excluded_by_pre_prediction_policy
- `data_muestra_resultado`: mandatory_not_present_in_v2_source
- `clas_riesgo_cancer`: excluded_by_pre_prediction_policy
- `fecha_nacimiento`: excluded_by_pre_prediction_policy
- `riesgo`: excluded_by_pre_prediction_policy
- `consumo_agua`: excluded_insufficient_observed_values_for_cv

## 3. Validación y evaluación

Se usaron 5 pliegues externos estratificados y 3 pliegues internos para tuning por AUC. Las métricas principales se calcularon sobre predicciones fuera de pliegue. El modelo ganador se ajustó sobre la cohorte completa y se sometió a 200 réplicas bootstrap para estimar optimismo.

No se fijó el umbral en 0.5. Se exploraron umbrales entre 0.05 y 0.50; para obtener al menos 80% de sensibilidad, el umbral descriptivo del modelo ganador fue 0.40. Esto logró sensibilidad 0.944, pero especificidad 0.080, por lo que derivaría casi toda la población y no es operacionalmente útil.

## 4. Comparación de modelos

| model_name | auc_oof | auc_oof_ci_low | auc_oof_ci_high | brier_oof | calibration_slope_oof | threshold_selected_oof | sensitivity_oof | specificity_oof |
|---|---|---|---|---|---|---|---|---|
| random_forest | 0.516 | 0.440 | 0.585 | 0.245 | 0.551 | 0.400 | 0.944 | 0.080 |
| gradient_boosting | 0.513 | 0.442 | 0.579 | 0.228 | 0.151 | 0.200 | 0.865 | 0.171 |
| elastic_net_logistic | 0.502 | 0.426 | 0.573 | 0.260 | 0.119 | 0.400 | 0.831 | 0.150 |

El random forest tuvo la mayor AUC fuera de pliegue, pero su magnitud fue mínima y compatible con azar. Gradient boosting tuvo menor Brier aparente fuera de pliegue, aunque su pendiente de calibración fue muy baja. Ningún modelo proporciona evidencia suficiente de utilidad predictiva.

## 5. Calibración, bootstrap y utilidad clínica

Para el modelo ganador: Brier fuera de pliegue=0.245; intercepto de calibración=-0.711; pendiente=0.551. La pendiente inferior a 1 indica sobreajuste. El bootstrap de optimismo estimó AUC corregida=0.379 y Brier corregido=0.302.

En la curva de decisión, el beneficio neto del modelo fue igual a “tratar a todos” en umbrales 0.05-0.30. A 0.35 fue -0.031 y a 0.40 fue -0.111; ambos no sostienen una estrategia de tamización selectiva. El umbral más bajo tuvo beneficio neto 0.287, idéntico a tratar a todos.

## 6. Explicabilidad del modelo final

SHAP describe qué variables influyen en las probabilidades del random forest final, no evidencia de causalidad ni de desempeño útil. Las diez variables codificadas con mayor importancia global fueron:

- `numeric__imc`: media |SHAP|=0.023
- `numeric__peso`: media |SHAP|=0.020
- `numeric__edad_hoy`: media |SHAP|=0.018
- `categorical__pared_Ladrillo`: media |SHAP|=0.011
- `numeric__talla`: media |SHAP|=0.008
- `categorical__salero_mesa_Si`: media |SHAP|=0.008
- `categorical__estado_civil_Casado(a)`: media |SHAP|=0.008
- `categorical__data-factor_riesgo-sintomas_Ninguno`: media |SHAP|=0.007
- `categorical__piso_Cerámica`: media |SHAP|=0.007
- `categorical__salero_mesa_No`: media |SHAP|=0.007

Estas señales son exploratorias. Dado que el AUC externo interno es cercano a 0.5, no deben convertirse en un score ni interpretarse como factores de riesgo confirmados.

## 7. Limitaciones y siguiente fase

- El tamaño de la cohorte es limitado: 89 eventos para 57 predictores base, antes de la expansión por categorías.
- La fuente integrada contiene biomarcadores y resultados posteriores, pero fueron excluidos deliberadamente de este modelo clínico-social base.
- La ausencia de señal puede reflejar que la infección activa no está suficientemente determinada por los predictores disponibles, errores de medición, heterogeneidad o selección de la población.
- Este análisis no reemplaza la futura fase de biomarcadores ni el desenlace histológico/endoscópico.

La siguiente iteración debe definir una pregunta separada para biomarcadores o para endoscopia/histología, con temporalidad clara, tamaño muestral suficiente y validación externa o temporal. No se recomienda optimizar más modelos sobre esta misma matriz para buscar una mejora marginal.

## 8. Reproducción y artefactos

- Configuración: `configs/timbio_hpylori_model_v2.yaml`
- Ejecución: `scripts/run_timbio_hpylori_model_v2.py`
- Registro de predictores: `data/manifests/feature_registry_timbio_hpylori_v2.csv`
- Matriz de entrada desidentificada: `data/interim/timbio_hpylori_model_input_deidentified_v2.parquet`
- Resultados, predicciones fuera de pliegue, bootstrap, calibración, curva de decisión, SHAP y figuras: `artifacts/` con sufijo `_v2`.
