<!-- audit_governance_v1:start -->
# Decisions log

## audit_governance_v1
- Fecha UTC: 2026-07-04T22:40:19+00:00
- Se lee la columna R del diccionario oficial por posición Excel (`Column2` tras `header=3`) como fuente de verdad para variables obligatorias.
- Variables exploratorias v1: no obligatorias, completitud >= 70 %, no sensibles, no administrativas, no outcomes/biomarcadores/capas posteriores ni scores/riesgo.
- Los archivos en `data/raw/` quedan como solo lectura; esta etapa no construye cohortes ni entrena modelos.
- El entrenamiento queda bloqueado hasta generar y validar `cohort_hp_v1.parquet` limpio.
<!-- audit_governance_v1:end -->

<!-- cohort_derivation_v1:start -->
## cohort_derivation_v1
- Fecha UTC: 2026-07-05T14:17:12+00:00
- `cohort_master_v1` se deriva de la capa limpia y conserva todas las filas maestras.
- `cohort_hp_v1` requiere `H_pylori_heces` binario válido: `Positivo`=1, `Negativo`=0.
- `Indeterminado` no se imputa ni se fuerza a una clase; queda fuera del baseline de factibilidad v1.
- `cohort_biomarkers_v1` exige PGI, PGII y ratio PGI/PGII completos.
- `cohort_endoscopy_placeholder_v1` solo traza registros con endoscopia/OLGA disponible; no congela outcome histológico final.
- No se entrenaron modelos en esta etapa.
<!-- cohort_derivation_v1:end -->

<!-- baseline_models_v1:start -->
## baseline_models_v1
- Fecha UTC: 2026-07-06T02:00:59+00:00
- Se entrenaron baselines de factibilidad sobre `cohort_hp_v1.parquet` con target binario `outcome__H_pylori_heces_binary`.
- Las features se resolvieron desde `feature_registry_v1.csv` mediante `master_column_match` para empatar nombres canónicos con columnas físicas.
- La imputación, escalamiento y one-hot encoding se ajustaron dentro de pipelines de entrenamiento para evitar leakage.
- Se guardaron métricas, calibración básica, modelos y reporte; estos resultados son exploratorios y no clínicamente finales.
<!-- baseline_models_v1:end -->

<!-- model_diagnostics_v1:start -->
## model_diagnostics_v1
- Fecha UTC: 2026-07-06T02:01:55+00:00
- Se compararon modelos adicionales, stepwise forward y explicabilidad SHAP/permutation.
- Stepwise se registra solo como diagnóstico, no como método principal recomendado.
- La interpretación principal es que el rendimiento bajo probablemente combina señal limitada, tamaño muestral pequeño y alta dimensionalidad.
<!-- model_diagnostics_v1:end -->

<!-- technical_modeling_report_v1:start -->
## technical_modeling_report_v1
- Fecha UTC: 2026-07-09T23:04:20+00:00
- Se generó un informe técnico reproducible para equipos de ingeniería de datos, ciencia de datos y analítica.
- El informe consolida auditoría, gobernanza, cohortes, preprocesamiento, modelos entrenados, pruebas, métricas, calibración, matrices de confusión y explicabilidad.
- Se generaron gráficas adicionales en `artifacts/figures/technical_modeling_v1/`.
- La validación estructural del DOCX pasó; el render visual con LibreOffice quedó bloqueado por dependencia externa faltante `liblcms2.2.dylib`.
<!-- technical_modeling_report_v1:end -->

<!-- timbio_hpylori_model_v2:start -->
## timbio_hpylori_model_v2
- Fecha UTC: 2026-09-02T20:07:15+00:00
- La fuente analítica se redefinió como `biomarkers_timbio_with_sociodemographics_v2.xlsx`, limitada a pacientes de Timbío. La fuente permanece local y de solo lectura.
- El outcome provisional es `Resultados_Helicobacter`: `Positivo`=1, `Negativo`=0. Los registros `No Registra` se excluyen; no se imputan outcomes.
- La cohorte contiene 276 pacientes con 89 positivos. La entrada de modelado se derivó sin identificadores directos y se guardó solo localmente en `data/interim/`.
- Las variables obligatorias se leyeron desde la columna R del diccionario. De 63 obligatorias, 57 se autorizaron para el momento prediagnóstico; se excluyeron scores/riesgos derivados, fecha de nacimiento, datos de muestra ausentes, resultados, biomarcadores, endoscopia, histología, administración e identificadores.
- Elastic net, random forest y gradient boosting se compararon con validación cruzada anidada (5 pliegues externos, 3 internos); imputación, categorías raras, one-hot y filtrado de varianza se ajustaron dentro de cada pliegue.
- El resultado v2 no respalda uso clínico: mejor AUC fuera de pliegue=0.516 (IC bootstrap 0.440-0.585), compatible con rendimiento no discriminativo. El stepwise no se utilizó como estrategia principal.
- Se ejecutaron bootstrap de optimismo, calibración, curva de decisión, importancia por permutación y SHAP sobre el modelo final reconstruido. No hubo ganancia operacional sobre tratar a todos en umbrales bajos.
<!-- timbio_hpylori_model_v2:end -->
