# Aplicación Flask de ejemplo

Esta es una aplicación muy sencilla de Flask que muestra una tabla almacenada en una base de datos SQLite.

## Requisitos

- Python 3.10+
- Dependencias listadas en `requirements.txt`

Instala las dependencias ejecutando:

```bash
pip install -r requirements.txt
```

## Uso

Inicializa la base de datos y ejecuta el servidor de desarrollo con:

```bash
flask --app app run --debug
```

Después abre <http://127.0.0.1:5000> en tu navegador para ver la tabla de empleados.
