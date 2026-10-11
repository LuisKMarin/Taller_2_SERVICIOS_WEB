"""Evidencias 1, 2 y 17 + comprobación de los 20 minutos de muestreo.

Ejecutar (desde la raíz del proyecto, con el entorno virtual activo):
    python probar_bd.py

Solo LEE la base de datos y el archivo mqtt.log. Genera:
    evidencias/01_recepcion_mqtt.txt      (#1  mensajes recibidos del tópico)
    evidencias/02_17_base_de_datos.txt    (#2  mediciones guardadas, #17 claves foráneas)

Nota: el .gitignore ignora *.log, por eso las evidencias se guardan como .txt.
"""

import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

from app.database.connection import SessionLocal

load_dotenv()

CODIGO = os.getenv("SENSOR_CODIGO", "GAS-005")
RAIZ = Path(__file__).resolve().parent
EVIDENCIAS = RAIZ / "evidencias"
EVIDENCIAS.mkdir(exist_ok=True)


def tabla(filas, columnas) -> str:
    """Formatea filas de la BD como una tabla de texto alineada."""
    datos = [[str(c) for c in columnas]] + [[str(v) for v in f] for f in filas]
    anchos = [max(len(f[i]) for f in datos) for i in range(len(columnas))]
    lineas = ["  ".join(v.ljust(anchos[i]) for i, v in enumerate(f)) for f in datos]
    lineas.insert(1, "  ".join("-" * a for a in anchos))
    return "\n".join(lineas)


# ------------------------------------------------------------------ #1 MQTT
def evidencia_mqtt() -> None:
    """Extrae del mqtt.log la conexión, la suscripción y los primeros mensajes."""
    ruta = RAIZ / "mqtt.log"
    salida = [
        "EVIDENCIA #1 - Recepcion MQTT desde el topico asignado",
        f"Generado: {datetime.now():%Y-%m-%d %H:%M:%S}",
        "Archivo y funcion: app/mqtt/client.py -> _on_connect, _on_message, procesar_mensaje",
        "",
    ]
    if not ruta.exists():
        salida.append("No existe mqtt.log: ejecuta la API (uvicorn app.main:app) y espera mensajes.")
    else:
        lineas = ruta.read_text(encoding="utf-8", errors="replace").splitlines()
        claves = ("Conectado al broker", "Suscrito al", "[RECEPCION]", "[GUARDADO]")
        utiles = [l for l in lineas if any(k in l for k in claves)]
        rechazos = [l for l in lineas if "[RECHAZADO]" in l]
        salida.append(f"Total de mensajes recibidos en el log : {sum('[RECEPCION]' in l for l in lineas)}")
        salida.append(f"Total guardados                       : {sum('[GUARDADO]' in l for l in lineas)}")
        salida.append(f"Total rechazados                      : {len(rechazos)}")
        salida.append("")
        salida.append("--- Primeras lineas relevantes del log ---")
        salida.extend(utiles[:12])
        if rechazos:
            salida.append("")
            salida.append("--- Rechazos reales recibidos del broker ---")
            salida.extend(rechazos[:20])
    (EVIDENCIAS / "01_recepcion_mqtt.txt").write_text("\n".join(salida) + "\n", encoding="utf-8")
    print("\n".join(salida[:8]))


# ------------------------------------------------------ #2 y #17 PostgreSQL
def evidencia_bd() -> None:
    salida = [
        "EVIDENCIAS #2 y #17 - Datos almacenados y claves foraneas en PostgreSQL",
        f"Generado: {datetime.now():%Y-%m-%d %H:%M:%S}   Sensor: {CODIGO}",
        "Archivos: app/crud/medicion.py -> crear_mediciones | app/models/sensor_magnitud.py y"
        " app/models/medicion.py -> ForeignKey",
        "",
    ]
    with SessionLocal() as db:
        resumen = db.execute(
            text(
                """
                SELECT sm.id, sm.magnitud, sm.unidad, sm.valor_minimo, sm.valor_maximo,
                       COUNT(m.id) AS total, MIN(m.timestamp_utc) AS primera,
                       MAX(m.timestamp_utc) AS ultima
                FROM sensor_magnitudes sm
                JOIN sensores s ON s.id = sm.sensor_id
                LEFT JOIN mediciones m ON m.sensor_magnitud_id = sm.id
                WHERE s.codigo = :c
                GROUP BY sm.id, sm.magnitud, sm.unidad, sm.valor_minimo, sm.valor_maximo
                ORDER BY sm.id
                """
            ),
            {"c": CODIGO},
        ).all()

        payloads = db.execute(
            text(
                """
                SELECT COUNT(*), MIN(n), MAX(n), MIN(t), MAX(t) FROM (
                    SELECT m.timestamp_utc AS t, COUNT(*) AS n
                    FROM mediciones m
                    JOIN sensor_magnitudes sm ON sm.id = m.sensor_magnitud_id
                    JOIN sensores s ON s.id = sm.sensor_id
                    WHERE s.codigo = :c GROUP BY m.timestamp_utc
                ) x
                """
            ),
            {"c": CODIGO},
        ).one()

        # tramo continuo mas largo: mediciones seguidas sin huecos de mas de 60 s.
        # (con la primera y la ultima no alcanza: si la API se apago un rato, el resultado engana)
        continuo = db.execute(
            text(
                """
                WITH t AS (
                    SELECT DISTINCT m.timestamp_utc AS t
                    FROM mediciones m
                    JOIN sensor_magnitudes sm ON sm.id = m.sensor_magnitud_id
                    JOIN sensores s ON s.id = sm.sensor_id
                    WHERE s.codigo = :c
                ), g AS (
                    SELECT t, CASE WHEN t - LAG(t) OVER (ORDER BY t) > INTERVAL '60 seconds'
                                   THEN 1 ELSE 0 END AS corte
                    FROM t
                ), b AS (
                    SELECT t, SUM(corte) OVER (ORDER BY t) AS bloque FROM g
                )
                SELECT MIN(t), MAX(t), COUNT(*) FROM b
                GROUP BY bloque ORDER BY MAX(t) - MIN(t) DESC LIMIT 1
                """
            ),
            {"c": CODIGO},
        ).first()

        ultimas = db.execute(
            text(
                """
                SELECT m.id, s.codigo, sm.magnitud, m.valor, sm.unidad,
                       m.timestamp_utc, m.fecha_recepcion, m.sensor_magnitud_id
                FROM mediciones m
                JOIN sensor_magnitudes sm ON sm.id = m.sensor_magnitud_id
                JOIN sensores s ON s.id = sm.sensor_id
                WHERE s.codigo = :c
                ORDER BY m.timestamp_utc DESC, m.id DESC LIMIT 12
                """
            ),
            {"c": CODIGO},
        ).all()

        fks = db.execute(
            text(
                """
                SELECT conrelid::regclass::text AS tabla, conname AS restriccion,
                       pg_get_constraintdef(oid) AS definicion
                FROM pg_constraint
                WHERE contype = 'f'
                  AND conrelid::regclass::text IN ('sensor_magnitudes', 'mediciones')
                ORDER BY 1
                """
            )
        ).all()

        huerfanas = db.execute(
            text(
                "SELECT COUNT(*) FROM mediciones m "
                "LEFT JOIN sensor_magnitudes sm ON sm.id = m.sensor_magnitud_id "
                "WHERE sm.id IS NULL"
            )
        ).scalar_one()

    n_pay, min_n, max_n, primero, ultimo = payloads
    minutos = (ultimo - primero).total_seconds() / 60 if n_pay else 0
    if continuo is not None and continuo[0] is not None:
        c_ini, c_fin, c_n = continuo
        c_min = (c_fin - c_ini).total_seconds() / 60
    else:
        c_ini = c_fin = None
        c_n, c_min = 0, 0.0

    salida.append("== Mediciones por magnitud (catalogo + lo almacenado) ==")
    salida.append(
        tabla(
            resumen,
            ["sm.id", "magnitud", "unidad", "min", "max", "total", "primera_utc", "ultima_utc"],
        )
    )
    salida += [
        "",
        "== Tiempo de muestreo (requisito: al menos 20 minutos) ==",
        f"Payloads guardados (timestamps distintos): {n_pay}",
        f"Filas por payload: minimo {min_n}, maximo {max_n} (una por magnitud, mismo timestamp_utc)",
        f"Primera medicion : {primero}",
        f"Ultima medicion  : {ultimo}",
        f"Duracion total   : {minutos:.1f} minutos (primera a ultima, incluye pausas)",
        f"Tramo continuo   : {c_min:.1f} minutos, {c_n} payloads ({c_ini} -> {c_fin}), sin huecos > 60 s",
        "Resultado        : "
        + (
            "CUMPLE (>= 20 min continuos)"
            if c_min >= 20
            else "NO CUMPLE: deja la API corriendo sin interrupciones hasta superar 20 min"
        ),
        "",
        "== Ultimas 12 mediciones almacenadas (evidencia #2) ==",
        tabla(
            ultimas,
            ["id", "sensor", "magnitud", "valor", "unidad", "timestamp_utc", "fecha_recepcion", "sm_id"],
        ),
        "",
        "== Claves foraneas definidas en PostgreSQL (evidencia #17) ==",
        tabla(fks, ["tabla", "restriccion", "definicion"]),
        "",
        f"Mediciones sin magnitud padre (debe ser 0): {huerfanas}",
        "Relaciones ORM: Sensor 1:N SensorMagnitud 1:N Medicion (relationship + ForeignKey).",
    ]
    (EVIDENCIAS / "02_17_base_de_datos.txt").write_text("\n".join(salida) + "\n", encoding="utf-8")
    print("\n".join(salida))


if __name__ == "__main__":
    evidencia_mqtt()
    print()
    evidencia_bd()
    print(f"\nListo. Archivos guardados en {EVIDENCIAS}")