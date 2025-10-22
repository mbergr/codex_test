# Practicelog

Aplicación Flask + SQLite para registrar sesiones de práctica musical.

## Requisitos

- Python 3.10+

## Instalación y ejecución

```bash
python -m venv .venv
source .venv/bin/activate  # En Windows usa .venv\\Scripts\\activate
pip install -r requirements.txt
flask --app app run --debug
```

La base de datos `data/practice.db` se crea automáticamente en el primer arranque.

## Funcionalidades

- Dashboard con racha, minutos semanales y top de temas.
- Registro de nuevas sesiones con temas dinámicos y etiquetas.
- Historial filtrable por texto, tema, etiqueta y rango de fechas.
- Detalle de sesión con notas por tema y adición rápida vía htmx.
- Analíticas por rango (7/30 días) incluyendo distribución por etiquetas.
- Exportación JSON/CSV e importación desde JSON.
- API JSON (`/api/sessions`, `/api/dashboard`).

## Datos de ejemplo

Ejecuta el script `sample_data.py` para poblar cinco sesiones de muestra:

```bash
python sample_data.py
```

## Notas

- Tailwind, HTMX y Chart.js se cargan vía CDN para simplificar la ejecución local.
- El formulario valida datos clave usando Pydantic antes de guardar.
