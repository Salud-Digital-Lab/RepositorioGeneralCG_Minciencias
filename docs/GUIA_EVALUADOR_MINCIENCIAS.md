# Guía para evaluadores de Minciencias

## Objetivo de esta guía

Este documento orienta la inspección técnica del snapshot de evaluación correspondiente a la Actividad 1.2.2 del Proyecto 110661.

El espejo está preparado para consulta pública. Una vez configurada su visibilidad como **Public**, la revisión puede realizarse desde cualquier navegador, sin cuenta de GitHub y sin acceso a datos crudos ni información identificable de participantes.

URL:
https://github.com/Salud-Digital-Lab/RepositorioGeneralCG_Minciencias

## Ruta de revisión recomendada

### 1. Comprender el alcance
Leer primero `README.md` y `docs/informe_modelado_tripod_ai_v2.md`.

Punto central: la versión v2 evalúa la factibilidad metodológica de predecir resultado de *H. pylori* en 276 participantes tamizados de Timbío. El análisis no constituye todavía un modelo clínico utilizable.

### 2. Verificar la cohorte y la gobernanza de variables
Revisar:
- `configs/timbio_hpylori_model_v2.yaml`
- `data/manifests/feature_registry_timbio_hpylori_v2.csv`
- `docs/decisions_log.md`

Aspectos a comprobar:
- municipio restringido a Timbío;
- outcome `Resultados_Helicobacter`;
- exclusión de registros `No Registra`;
- 63 variables obligatorias evaluadas;
- 57 predictores prediagnóstico autorizados;
- exclusión explícita de identificadores, resultados, biomarcadores, endoscopia, histología, scores y riesgos derivados.

### 3. Verificar prevención de leakage
En `src/cg_tamizaje/models/timbio_hpylori_v2.py` comprobar que:
- imputación se ajusta dentro del pipeline;
- variables categóricas se codifican dentro del pipeline;
- categorías infrecuentes se gestionan con `min_frequency=0.03`;
- escalado y filtrado de varianza ocurren dentro del remuestreo;
- el tuning se ejecuta dentro de los pliegues internos.

### 4. Verificar entrenamiento y validación
Revisar:
- `scripts/run_timbio_hpylori_model_v2.py`
- `src/cg_tamizaje/models/timbio_hpylori_v2.py`
- `artifacts/metrics/model_tuning_trace_timbio_hpylori_v2.csv`

El esquema utilizado fue validación cruzada anidada:
- 5 pliegues externos estratificados;
- 3 pliegues internos estratificados;
- AUC como métrica de tuning;
- 200 réplicas bootstrap para optimismo;
- 1000 réplicas bootstrap para intervalo de confianza del AUC.

### 5. Revisar resultados
Consultar:
- `artifacts/model_registry/model_results_timbio_hpylori_v2.csv`
- `artifacts/metrics/model_calibration_timbio_hpylori_v2.csv`
- `artifacts/metrics/decision_curve_timbio_hpylori_v2.csv`
- `artifacts/metrics/shap_importance_timbio_hpylori_v2.csv`
- `artifacts/metrics/permutation_importance_timbio_hpylori_v2.csv`
- `artifacts/figures/timbio_hpylori_v2/`

El mejor modelo por AUC fuera de pliegue fue Random Forest, con AUC aproximadamente 0,516. El intervalo de confianza incluye 0,5, por lo que el resultado es compatible con discriminación no útil.

### 6. Interpretar correctamente el resultado
El objetivo del snapshot es demostrar:
1. existencia de un pipeline reproducible;
2. control de leakage;
3. trazabilidad de predictores;
4. comparación homogénea entre algoritmos;
5. validación interna explícita;
6. documentación de calibración, utilidad clínica y explicabilidad.

No debe interpretarse que un modelo con AUC cercana a 0,5 puede emplearse clínicamente. La ausencia de utilidad predictiva en esta cohorte es un resultado técnico válido.

## Descarga opcional

El evaluador puede revisar todo en línea. Si desea una copia local:
- usar **Code > Download ZIP**, o
- ejecutar:
  `git clone https://github.com/Salud-Digital-Lab/RepositorioGeneralCG_Minciencias.git`

No se requiere cuenta de GitHub para descargar o clonar un repositorio público.

## Qué no está incluido
Por confidencialidad y gobierno de datos no se incluyen:
- bases crudas;
- identificadores;
- matriz por paciente;
- predicciones individuales;
- modelos serializados entrenados;
- archivos de linkage.

La ausencia de estos elementos no impide auditar la lógica del pipeline y sus resultados agregados.
