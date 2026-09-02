# RepositorioGeneralCG_Minciencias

Snapshot de evaluación técnica de la Actividad 1.2.2 del Proyecto 110661: **Estrategia territorial para la identificación de factores de riesgo que contribuyen a la prevención del cáncer gástrico en una población del departamento del Cauca**.

## Propósito

Este repositorio fue preparado como **espejo público de evaluación** para revisores de Minciencias y otros evaluadores autorizados del proyecto. Contiene únicamente código reproducible, configuración, gobernanza de variables, métricas agregadas, figuras y documentación técnica asociada a la versión v2 del análisis de factibilidad para predecir resultado de *Helicobacter pylori* en pacientes tamizados de Timbío.

No es el repositorio operativo de desarrollo y no se actualiza automáticamente con cada cambio del repositorio fuente. Su objetivo es permitir una inspección estable, abierta y trazable de la evidencia que respalda el informe de la Actividad 1.2.2.

## Acceso

Una vez configurada la visibilidad del repositorio como **Public**, cualquier evaluador podrá consultar su contenido directamente desde el navegador, sin crear una cuenta de GitHub y sin solicitar permisos.

URL del espejo de evaluación:

https://github.com/Salud-Digital-Lab/RepositorioGeneralCG_Minciencias

La consulta pública de este espejo **no concede acceso** al repositorio operativo de desarrollo ni a los datos de investigación.

## Snapshot congelado

- Repositorio fuente: `DigitalHealthCauca/RepositorioGeneralCG`
- Commit fuente de referencia: `59c51804196b9b216818b62aa0cf5ad36e5169a7`
- Fecha del snapshot: 2026-09-02
- Cohorte analítica: 276 participantes de Timbío con resultado válido
- Positivos para `Resultados_Helicobacter`: 89 (32,2 %)
- Predictores prediagnóstico autorizados: 57
- Modelos comparados: regresión logística Elastic Net, Random Forest y Gradient Boosting
- Validación: validación cruzada anidada 5×3 + bootstrap interno de optimismo
- Resultado principal: Random Forest con AUC fuera de pliegue ≈ 0,516; desempeño compatible con discriminación no útil para priorización clínica

## Cómo empezar la revisión

1. Lea `docs/GUIA_EVALUADOR_MINCIENCIAS.md`.
2. Revise `docs/MAPA_T1_T4.md` para relacionar cada artefacto con las tareas T01–T04.
3. Consulte `configs/timbio_hpylori_model_v2.yaml` para verificar las reglas de cohorte, exclusiones y validación.
4. Revise `data/manifests/feature_registry_timbio_hpylori_v2.csv` para comprobar qué variables fueron elegibles o excluidas.
5. Inspeccione `src/cg_tamizaje/models/timbio_hpylori_v2.py` y `scripts/run_timbio_hpylori_model_v2.py`.
6. Revise los resultados agregados en `artifacts/` y el informe en `docs/informe_modelado_tripod_ai_v2.md`.
7. Consulte `docs/ACCESO_EVALUADORES_MINCIENCIAS.md` para conocer el alcance del acceso público y las restricciones de información.

## Protección de información

Este espejo público **no contiene** bases crudas, cohortes por paciente, identificadores, predicciones individuales ni modelos serializados entrenados. Los datos clínicos y los archivos de trabajo permanecen en almacenamiento institucional/autorizado y no se publican en GitHub.

La apertura de este espejo corresponde exclusivamente a código, documentación y resultados agregados previamente revisados. La publicación del espejo **no implica la publicación de datos clínicos**, ni autoriza el acceso a las fuentes originales.

## Estructura

- `configs/`: configuración versionada de ejecución.
- `scripts/`: puntos de entrada reproducibles.
- `src/`: lógica del pipeline de modelado.
- `data/manifests/`: registro de variables y decisiones de elegibilidad, sin datos por paciente.
- `artifacts/model_registry/`: resultados comparativos agregados.
- `artifacts/metrics/`: calibración, bootstrap, curva de decisión, SHAP, importancia por permutación y trazas de tuning.
- `artifacts/figures/`: figuras derivadas del modelo v2.
- `artifacts/reports/`: reporte resumido de factibilidad.
- `docs/`: bitácora de decisiones, informe TRIPOD+AI y guía de evaluación.

## Nota de interpretación

Este snapshot demuestra que el pipeline metodológico y la trazabilidad fueron implementados, pero el rendimiento predictivo obtenido no justifica usar el modelo v2 para decisiones clínicas o priorización de pacientes. La ausencia de utilidad clínica forma parte del resultado técnico y se reporta de manera explícita.
