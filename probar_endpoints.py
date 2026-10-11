"""Evidencias 8 a 16: prueba los endpoints HTTP y guarda el resultado.

1) En una terminal, con la API corriendo:   uvicorn app.main:app
2) En otra terminal (entorno virtual activo): python probar_endpoints.py

Usa solo la libreria estandar para llamar a la API (no agrega dependencias).
Genera: evidencias/08_16_endpoints_http.txt
Variables opcionales: API_URL (por defecto http://127.0.0.1:8000), SENSOR_CODIGO.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib import error, parse, request

from dotenv import load_dotenv

load_dotenv()

BASE = os.getenv("API_URL", "http://127.0.0.1:8000").rstrip("/")
CODIGO = os.getenv("SENSOR_CODIGO", "GAS-005")
EVIDENCIAS = Path(__file__).resolve().parent / "evidencias"
EVIDENCIAS.mkdir(exist_ok=True)

ARCH_SENSOR = "app/api/sensor.py -> {} -> app/crud/sensor.py"
ARCH_MED = "app/api/medicion.py -> mediciones_de_sensor -> app/crud/medicion.py -> get_mediciones_por_sensor"

BLOQUES: list[str] = []
RESULTADOS: list[tuple[str, int, int, bool]] = []


def llamar(ruta: str, params: dict | None = None):
    """GET a la API. Devuelve (url, codigo_http, cuerpo_json)."""
    url = BASE + ruta + ("?" + parse.urlencode(params) if params else "")
    try:
        with request.urlopen(url, timeout=15) as r:
            return url, r.status, json.loads(r.read().decode("utf-8"))
    except error.HTTPError as e:
        cuerpo = e.read().decode("utf-8", errors="replace")
        try:
            cuerpo = json.loads(cuerpo)
        except ValueError:
            pass
        return url, e.code, cuerpo


def resumir(cuerpo) -> str:
    if isinstance(cuerpo, list):
        txt = json.dumps(cuerpo[:3], indent=2, ensure_ascii=False)
        return f"{len(cuerpo)} elemento(s). Primeros 3:\n{txt}"
    txt = json.dumps(cuerpo, indent=2, ensure_ascii=False)
    return txt if len(txt) <= 1500 else txt[:1500] + "\n..."


def probar(num, nombre, ruta, esperado, params=None, verificar=None, donde="", explicacion=""):
    """Ejecuta una solicitud, compara el código HTTP y (opcional) valida el cuerpo."""
    url, codigo, cuerpo = llamar(ruta, params)
    ok = codigo == esperado
    nota = ""
    if ok and verificar is not None:
        ok_cuerpo, nota = verificar(cuerpo)
        ok = ok and ok_cuerpo
    RESULTADOS.append((f"#{num} {nombre}", codigo, esperado, ok))
    BLOQUES.append(
        "\n".join(
            [
                f"--- Prueba #{num}: {nombre} ---",
                f"Solicitud          : GET {url}",
                f"Codigo HTTP        : {codigo} (esperado {esperado}) -> {'OK' if ok else 'FALLO'}",
                *([f"Verificacion       : {nota}"] if nota else []),
                f"Respuesta          : {resumir(cuerpo)}",
                f"Archivo y funcion  : {donde}",
                f"Explicacion        : {explicacion}",
                "",
            ]
        )
    )
    print(f"[{'OK' if ok else 'FALLO'}] #{num} {nombre}: HTTP {codigo} (esperado {esperado})")
    return cuerpo if codigo == 200 else None


def fecha(item: dict) -> datetime:
    return datetime.fromisoformat(item["timestamp_colombia"])


def main() -> None:
    # La API debe estar encendida.
    try:
        _, codigo, _ = llamar("/")
    except error.URLError:
        sys.exit(f"No se pudo conectar con {BASE}. Inicia la API con: uvicorn app.main:app")
    if codigo != 200:
        sys.exit(f"La API respondio {codigo} en '/'. Revisa que este bien iniciada.")

    _, c, sensor = llamar(f"/sensores/por-codigo/{CODIGO}")
    if c != 200:
        sys.exit(f"No existe el sensor {CODIGO} (HTTP {c}). Revisa SENSOR_CODIGO en el .env")
    sid = sensor["id"]

    # ------------------------------------------------ #8 consulta por ID existente
    probar(8, "Listar sensores", "/sensores", 200,
           donde=ARCH_SENSOR.format("listar_sensores"), explicacion="Catalogo completo (solo lectura).")
    probar(8, "Sensor por id existente", f"/sensores/{sid}", 200,
           verificar=lambda b: (b["codigo"] == CODIGO, f"codigo devuelto = {b['codigo']}"),
           donde=ARCH_SENSOR.format("sensor_por_id / obtener_sensor_o_404"),
           explicacion="Busca por clave primaria numerica y muestra fecha_registro en hora de Colombia.")
    probar(8, "Sensor por codigo", f"/sensores/por-codigo/{CODIGO}", 200,
           donde=ARCH_SENSOR.format("sensor_por_codigo"),
           explicacion="El codigo es el sensor_id que llega por MQTT.")
    magnitudes = probar(8, "Magnitudes del sensor", f"/sensores/{sid}/magnitudes", 200,
                        donde="app/api/sensor_magnitud.py -> magnitudes_de_sensor -> app/crud/sensor_magnitud.py",
                        explicacion="Magnitudes, unidades y rangos del sensor.") or []
    if magnitudes:
        probar(8, "Magnitud de sensor por id", f"/sensor-magnitudes/{magnitudes[0]['id']}", 200,
               donde="app/api/sensor_magnitud.py -> sensor_magnitud_por_id",
               explicacion="Una fila de sensor_magnitudes por su clave primaria.")

    historico = probar(10, "Consulta historica (sin filtros)", f"/sensores/{sid}/mediciones", 200,
                       verificar=lambda b: (
                           len(b) > 0 and all(fecha(b[i]) >= fecha(b[i + 1]) for i in range(len(b) - 1)),
                           f"{len(b)} mediciones, de la mas reciente a la mas antigua"),
                       donde=ARCH_MED,
                       explicacion="Todas las mediciones del sensor ordenadas por timestamp_utc descendente.") or []
    if not historico:
        print("\nEl sensor aun no tiene mediciones: deja corriendo la API para recibir datos y repite.")

    # Medición por ID (existente)
    if historico:
        mid = historico[0]["id"]
        probar(8, "Medicion por id existente", f"/mediciones/{mid}", 200,
               verificar=lambda b: (b["id"] == mid, f"id devuelto = {b['id']}"),
               donde="app/api/medicion.py -> medicion_por_id -> app/crud/medicion.py -> get_medicion",
               explicacion="Muestra magnitud y unidad (join con sensor_magnitudes) y la hora en Colombia.")

    # ------------------------------------------------ #9 consulta por ID inexistente (404)
    probar(9, "Sensor con id inexistente", "/sensores/999999", 404,
           donde=ARCH_SENSOR.format("obtener_sensor_o_404"), explicacion="No existe el sensor: HTTPException 404.")
    probar(9, "Medicion con id inexistente", "/mediciones/999999999", 404,
           donde="app/api/medicion.py -> medicion_por_id", explicacion="No existe la medicion: HTTPException 404.")
    probar(9, "Sensor con codigo inexistente", "/sensores/por-codigo/XXX-000", 404,
           donde=ARCH_SENSOR.format("sensor_por_codigo"), explicacion="Codigo no registrado: 404.")
    probar(9, "Magnitud de sensor con id inexistente", "/sensor-magnitudes/999999", 404,
           donde="app/api/sensor_magnitud.py -> sensor_magnitud_por_id", explicacion="No existe: 404.")

    if len(historico) >= 6:
        # -------------------------------------------- #11 rango de fechas / #12 desde > hasta
        hasta = fecha(historico[len(historico) // 3])
        desde = fecha(historico[2 * len(historico) // 3])
        rango = {"desde": desde.isoformat(), "hasta": hasta.isoformat()}
        probar(11, "Consulta por rango de fechas", f"/sensores/{sid}/mediciones", 200, params=rango,
               verificar=lambda b: (
                   len(b) > 0 and all(desde <= fecha(m) <= hasta for m in b),
                   f"{len(b)} mediciones, todas entre desde y hasta"),
               donde=ARCH_MED + " (+ _a_utc)",
               explicacion="Filtra por timestamp_utc; fechas sin zona se interpretan como hora de Colombia.")
        probar(12, "Rango invalido: desde > hasta", f"/sensores/{sid}/mediciones", 400,
               params={"desde": rango["hasta"], "hasta": rango["desde"]},
               donde="app/api/medicion.py -> mediciones_de_sensor (desde_utc > hasta_utc)",
               explicacion="Rango imposible: HTTPException 400 antes de consultar la BD.")

    # ------------------------------------------------ #13 validación HTTP incorrecta (422)
    probar(13, "Id no numerico", "/sensores/abc", 422,
           donde="app/api/sensor.py -> SensorId (Path int, ge=1)", explicacion="FastAPI valida el tipo del parametro.")
    probar(13, "Id fuera de rango (0)", "/sensores/0", 422,
           donde="app/api/sensor.py -> SensorId (Path ge=1)", explicacion="El id debe ser >= 1.")
    probar(13, "limit invalido (0)", f"/sensores/{sid}/mediciones", 422, params={"limit": 0},
           donde="app/api/medicion.py -> mediciones_de_sensor (Query ge=1)", explicacion="limit debe ser >= 1.")
    probar(13, "Fecha con formato invalido", f"/sensores/{sid}/mediciones", 422, params={"desde": "no-es-una-fecha"},
           donde="app/api/medicion.py -> mediciones_de_sensor (Query datetime)",
           explicacion="Pydantic no puede interpretar el texto como fecha.")

    # ------------------------------------------------ #14 última medición
    if historico:
        mas_reciente = fecha(historico[0])
        probar(14, "Ultima medicion", f"/sensores/{sid}/ultima-medicion", 200,
               verificar=lambda b: (
                   len({m["timestamp_colombia"] for m in b}) == 1 and fecha(b[0]) == mas_reciente,
                   f"{len(b)} medicion(es) del instante mas reciente: {b[0]['timestamp_colombia']}"),
               donde="app/api/medicion.py -> ultima_medicion -> app/crud/medicion.py -> get_ultima_lectura",
               explicacion="Una medicion por magnitud, todas del timestamp mas reciente.")

        # -------------------------------------------- #15 últimas N
        n = min(5, len(historico))
        probar(15, f"Ultimas {n} mediciones (limit={n})", f"/sensores/{sid}/mediciones", 200, params={"limit": n},
               verificar=lambda b: (len(b) == n and b == historico[:n], f"devolvio {len(b)} = las {n} mas recientes"),
               donde=ARCH_MED + " (stmt.limit)", explicacion="limit devuelve las ultimas N filas.")

        # -------------------------------------------- #16 filtro por magnitud
        nombres = [m["magnitud"] for m in magnitudes]
        mag = "temperature" if "temperature" in nombres else (nombres[0] if nombres else None)
        if mag:
            probar(16, f"Filtro por magnitud ({mag})", f"/sensores/{sid}/mediciones", 200, params={"magnitud": mag},
                   verificar=lambda b: (
                       len(b) > 0 and all(m["magnitud"] == mag for m in b), f"{len(b)} mediciones, todas de {mag}"),
                   donde=ARCH_MED + " (SensorMagnitud.magnitud == magnitud)",
                   explicacion="Join con sensor_magnitudes y filtro por nombre de magnitud.")
            if len(historico) >= 6:
                probar(16, f"Filtros combinados ({mag} + fechas + limit=3)", f"/sensores/{sid}/mediciones", 200,
                       params={"magnitud": mag, "desde": rango["desde"], "hasta": rango["hasta"], "limit": 3},
                       verificar=lambda b: (
                           0 < len(b) <= 3 and all(m["magnitud"] == mag for m in b),
                           f"{len(b)} mediciones de {mag} dentro del rango"),
                       donde=ARCH_MED, explicacion="Los filtros son opcionales y combinables.")
        probar(16, "Magnitud que el sensor no tiene (pressure)", f"/sensores/{sid}/mediciones", 404,
               params={"magnitud": "pressure"},
               donde="app/api/medicion.py -> mediciones_de_sensor (get_magnitud_de_sensor is None)",
               explicacion="Magnitud inexistente para ese sensor: 404.")

    # ------------------------------------------------ resumen
    codigos = sorted({c for _, c, _, _ in RESULTADOS})
    fallos = [n for n, _, _, ok in RESULTADOS if not ok]
    cabecera = [
        "EVIDENCIAS #8 a #16 - Endpoints FastAPI",
        f"Generado: {datetime.now():%Y-%m-%d %H:%M:%S}   API: {BASE}   Sensor: {CODIGO} (id={sid})",
        f"Codigos HTTP observados: {', '.join(map(str, codigos))}",
        f"Pruebas: {len(RESULTADOS)}   Correctas: {len(RESULTADOS) - len(fallos)}   Con fallo: {len(fallos)}",
        *[f"  FALLO: {n}" for n in fallos],
        "",
    ]
    texto = "\n".join(cabecera + BLOQUES)
    (EVIDENCIAS / "08_16_endpoints_http.txt").write_text(texto, encoding="utf-8")
    print("\n" + "\n".join(cabecera))
    print(f"Guardado en {EVIDENCIAS / '08_16_endpoints_http.txt'}")
    if not set(codigos) >= {200, 400, 404, 422}:
        print("AVISO: faltan codigos por demostrar (se necesitan 200, 400, 404 y 422).")
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()