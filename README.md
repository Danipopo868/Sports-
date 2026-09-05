# Analizador deportivo MLB · NFL · NBA

Motor en Python para ejecutarse en GitHub Actions durante tres horas. Es independiente: **no lee ni se conecta con Kalshi** y no realiza apuestas automáticamente.

## Qué hace

- Descarga partidos y cuotas reales de API-Sports.
- Analiza MLB, NFL y NBA cada 15 minutos durante 180 minutos.
- Compara cuotas de varias casas y elimina matemáticamente el margen de la casa.
- Calcula forma reciente, margen de anotación, probabilidad estimada, punto de equilibrio, ventaja y valor esperado.
- Para MLB añade abridores probables, ERA, WHIP, K/9 y producción ofensiva usando el servicio público de estadísticas de MLB.
- Revisa el mercado de ganador y, cuando existen datos completos y cuotas compatibles, las primeras cinco entradas de MLB.
- Entrega como máximo **una selección por deporte**.
- Publica **NO APOSTAR** cuando no hay una ventaja suficiente, faltan datos o la calidad es baja.

## Lo que no promete

No existe una apuesta con 99% de certeza ni una ganancia garantizada. Las probabilidades del reporte son estimaciones del modelo. El sistema no sustituye una calibración histórica rigurosa y no debe arriesgar dinero que no puedas perder.

La versión inicial no calcula todavía el historial exacto de cada bateador contra cada lanzador. Para primeras cinco entradas sí exige abridores confirmados y usa sus estadísticas junto con la ofensiva del equipo contrario; si esos datos faltan, bloquea la recomendación.

## Preparación en GitHub

1. Crea un repositorio nuevo, por ejemplo `sports-predictor`.
2. Descomprime este paquete y sube **todo su contenido** al repositorio.
3. En API-Sports activa los planes gratuitos de **Baseball**, **NFL** y **Basketball**. NBA está incluida dentro de Basketball con estadísticas y cuotas.
4. En el repositorio abre `Settings → Secrets and variables → Actions`.
5. Pulsa `New repository secret`.
6. Usa exactamente este nombre:

   ```text
   API_SPORTS_KEY
   ```

7. Pega tu clave como valor. Nunca la escribas dentro de un archivo del repositorio.

## Ejecutar durante tres horas

1. Abre la pestaña `Actions` del repositorio.
2. Selecciona `Analizar deportes durante 3 horas`.
3. Pulsa `Run workflow`.
4. Selecciona `180` minutos.

El trabajo permite 190 minutos porque la instalación, las pruebas y la creación del reporte necesitan unos minutos adicionales. **El motor analiza durante 180 minutos reales**.

`cancel-in-progress: false` impide que una segunda ejecución cancele la primera. No inicies varias sesiones seguidas con el plan gratuito: podrías consumir el límite diario.

## Ver el resultado

Al terminar, abre la ejecución en GitHub Actions:

- El resumen muestra directamente la mejor selección o `NO APOSTAR` para cada deporte.
- El artefacto `reporte-deportivo` contiene `latest.md`, `latest.json` y el historial de los escaneos.
- El archivo más reciente se copia a `dashboard_data/` para que el panel de Streamlit lo muestre sin consumir consultas adicionales.

Los reportes permanecen disponibles durante 14 días.

## Panel visual con Streamlit

El panel se encuentra en `streamlit_app.py`. Lee únicamente el último reporte generado por GitHub Actions; no necesita la clave de API-Sports y no realiza apuestas.

1. Entra en `https://share.streamlit.io` con GitHub.
2. Pulsa `Create app` y elige este repositorio.
3. Selecciona la rama `main`.
4. En `Main file path`, escribe `streamlit_app.py`.
5. Pulsa `Deploy`.

Después de cada ejecución terminada, GitHub actualiza `dashboard_data/latest.json` y Streamlit refleja el nuevo reporte.

## Matemáticas principales

Para una cuota decimal `c`:

```text
probabilidad de equilibrio = 1 / c
ventaja = probabilidad del modelo - probabilidad de equilibrio
valor esperado = (probabilidad del modelo × c) - 1
```

Antes de recomendar, el motor exige simultáneamente:

- probabilidad estimada mínima de 55%;
- ventaja mínima de 3%;
- valor esperado mínimo de 3%;
- al menos dos casas con ambos lados del mercado;
- un mínimo de cinco partidos recientes por equipo;
- calidad de datos mínima de 60/100.

Puedes cambiar estos límites en `config.json`, pero reducirlos produce más selecciones débiles. Una probabilidad alta sin una cuota favorable no implica una apuesta rentable.

## Consumo del plan gratuito

El motor guarda en memoria los historiales y usa consultas agrupadas cuando el proveedor las admite. Está diseñado para una sesión diaria de tres horas. Si el endpoint de cuotas por fecha no estuviera disponible, consulta cada partido una vez y conserva el resultado para proteger el límite gratuito.

## Prueba rápida local

Con Python 3.12 instalado:

```bash
export API_SPORTS_KEY="tu_clave"
python -m unittest discover -s tests -v
python -m sports_predictor.main --once
```

## Fuentes

- API-Sports: partidos, resultados, estadísticas disponibles y cuotas.
- MLB Stats API: abridores probables y estadísticas oficiales de MLB.

Si una fuente falla, el programa muestra el error y marca `NO APOSTAR`; nunca completa huecos con datos simulados.
