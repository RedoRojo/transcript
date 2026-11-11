# Transcripción de Videos (YouTube & Archivos Locales)

Herramienta web moderna y con diseño minimalista para transcribir videos de **YouTube** a partir de un enlace o ID, y **archivos locales de video o audio** utilizando inteligencia artificial con **Whisper (`faster-whisper`)**. Permite visualizar marcas de tiempo sincronizadas con reproducción interactiva y exportar el contenido en múltiples formatos.

## Características

- **Diseño Minimalista**: Estética limpia en tonos neutros (zinc/slate). Soporta **Modo Claro** y **Modo Oscuro** (automático y manual).
- **Doble Origen de Video/Audio**:
  - **YouTube**: Soporta URLs estándar (`youtube.com/watch?v=...`), acortadas (`youtu.be/...`), Shorts (`youtube.com/shorts/...`), incrustadas (`embed`) y IDs directos.
  - **Archivos Locales**: Sube cualquier archivo arrastrando y soltando (Drag & Drop) o especifica directamente una ruta local en disco (MP4, MKV, WebM, AVI, MOV, MP3, WAV, M4A, FLAC, etc.).
- **Motor Whisper Local (`faster-whisper`)**:
  - Transcripción acelerada por CPU con cuantización INT8.
  - Selección de modelos: `base` (recomendado), `tiny` (ultrarrápido), `small` (alta precisión) y `medium`.
  - Detección automática de idioma o selección manual (Español, Inglés, Francés, Alemán, Italiano, Portugués, etc.).
  - Filtro VAD (Voice Activity Detection) para omitir silencios.
- **Reproductor Local Sincronizado**:
  - Para videos locales, incluye un reproductor integrado que salta al segundo exacto al hacer clic en las marcas de tiempo.
- **Doble Modo de Visualización**:
  - *Marcas de Tiempo*: Lista de fragmentos con código de tiempo cliqueable y botón de copia rápida por fragmento.
  - *Texto Continuo*: Párrafos continuos optimizados para lectura fluida o para copiarlo a un modelo de IA.
- **Buscador en Tiempo Real**: Filtrado y resaltado de palabras dentro de la transcripción con contador dinámico de coincidencias.
- **Exportación Multiformato**:
  - `.txt` (Texto plano limpio o con marcas de tiempo)
  - `.pdf` (Documento limpio y profesional con metadatos del video, fecha y paginación)
  - `.srt` (Formato estándar SubRip para edición y reproductores)
  - `.vtt` (Formato estándar WebVTT)
  - `.json` (Estructura de datos para desarrolladores)
  - `.csv` (Formato tabular para hojas de cálculo)
  - `.md` (Markdown con metadatos estructurados)
- **Copia Rápida**: Copiar texto plano o con marcas de tiempo al portapapeles en 1 clic.
- **Historial Local**: Acceso a las transcripciones recientes guardadas localmente en el navegador.

## Requisitos

- Python 3.10 o superior.
- `ffmpeg` instalado en el sistema (`/usr/bin/ffmpeg`).

## Instalación y Ejecución

1. Ejecuta el script de inicio rápido:
   ```bash
   ./run.sh
   ```

   O de forma manual:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   python app.py
   ```

2. Abre tu navegador en [http://localhost:8001](http://localhost:8001) o a través del Hub principal en [http://localhost:8000](http://localhost:8000).
