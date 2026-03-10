# =============================================================================
# parser_firex.py  —  Parser del archivo FIREX.txt (Detalle Comprobantes Gecom)
# Extrae: FI (Facturas de Importación) y RE (Remitos de Entrada)
#
# Estructura definida en Estructura_Firex.xlsx (posiciones base-1):
#
# CABECERA:
#   TipoDoc   col  1, ancho  2  → "fi" / "re"
#   (skip)    col  3, ancho  2
#   Sucursal  col  5, ancho  5  → "00943"
#   (skip)    col 10, ancho  1
#   NroDoc    col 11, ancho  8  → "02871435"
#   (skip)    col 19, ancho  7
#   Fecha     col 26, ancho  8  → "26/02/25"
#   (skip)    col 34, ancho  7
#   NroProv   col 41, ancho  4  → "1418"
#   (skip)    col 45, ancho  1
#   NomProv   col 46, ancho 29  → "3M COMPANY USA              "
#   (skip)    col 75, ancho 58  → resto (Lista, etc.)
#
# DETALLE:
#   (skip)    col  1, ancho  1  → ":"
#   CodProd   col  2, ancho  5  → "33131" / "80054"
#   (skip)    col  7, ancho 28
#   NomProd   col 35, ancho 40  → descripción del producto
#   Cantidad  col 75, ancho 15  → "          30,00"
#   (skip)    col 90, ancho 43  → precio y total (no requeridos en RE)
# =============================================================================

import re
import os
from datetime import datetime


def _parse_qty(s: str) -> float:
    """'          30,00' → 30.0"""
    s = s.strip()
    if not s:
        return 0.0
    return float(s.replace('.', '').replace(',', '.'))


def _parse_amount(s: str) -> float:
    """'    30.275,00' → 30275.0"""
    s = s.strip()
    if not s:
        return 0.0
    return float(s.replace('.', '').replace(',', '.'))


def _extract_header(line: str) -> dict | None:
    """
    Intenta parsear una línea de cabecera usando posiciones fijas.
    Retorna dict o None si no corresponde.
    """
    if len(line) < 50:
        return None

    tipo    = line[0:2].strip().lower()
    if tipo not in ('fi', 're'):
        return None

    sucursal = line[4:9].strip()    # col 5, ancho 5  (base-0: 4:9)
    nro_doc  = line[10:18].strip()  # col 11, ancho 8 (base-0: 10:18)
    fecha    = line[25:33].strip()  # col 26, ancho 8 (base-0: 25:33)
    nro_prov = line[40:44].strip()  # col 41, ancho 4 (base-0: 40:44)
    nom_prov = line[45:74].strip()  # col 46, ancho 29 (base-0: 45:74)
    resto    = line[74:].strip()    # col 75 en adelante (Lista, etc.)

    if not nro_doc or not fecha:
        return None

    # Extraer Lista del resto: "- Vd:        - Lista: 9999"
    lista = ""
    m = re.search(r'Lista:\s*(\S*)', resto)
    if m:
        lista = m.group(1).strip()

    comprobante = f"{sucursal}-{nro_doc}"
    numero_puro = sucursal + nro_doc   # sin guión para calcular los 6 dígitos
    fi_6dig     = numero_puro[-6:]

    return {
        "tipo":           tipo,
        "comprobante":    comprobante,
        "sucursal":       sucursal,
        "nro_doc":        nro_doc,
        "fecha":          fecha,
        "proveedor_cod":  nro_prov,
        "proveedor_nom":  nom_prov,
        "lista":          lista,
        "fi_6dig":        fi_6dig,
        "invoice_nbr":    None,
        "total_comprobante": None,
        "fecha_carga":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "archivo_origen": "",
    }


def _extract_detail(line: str) -> dict | None:
    """
    Parsea una línea de detalle usando posiciones fijas.
    Retorna dict o None si no es línea de detalle.
    """
    if len(line) < 50:
        return None

    # La línea debe empezar con ':'
    if line[0] != ':':
        return None

    cod_prod  = line[1:6].strip()     # col 2, ancho 5  (base-0: 1:6)
    # col 7-34 se salta (imputacion puede estar ahí, la extraemos igual)
    imputacion = line[6:34].strip()   # por si acaso guardamos el bloque intermedio
    # extraer código de imputación (6 dígitos) si existe
    m_imput = re.search(r'\b(\d{6})\b', imputacion)
    imput_cod = m_imput.group(1) if m_imput else ""

    nom_prod  = line[34:74].strip()   # col 35, ancho 40 (base-0: 34:74)
    cantidad_raw = line[74:89] if len(line) > 74 else ""  # col 75, ancho 15
    resto_raw    = line[89:] if len(line) > 89 else ""    # col 90 en adelante

    # Ignorar líneas sin código de producto (líneas de nota)
    if not cod_prod:
        return None

    # Parsear cantidad
    try:
        cantidad = _parse_qty(cantidad_raw)
    except Exception:
        cantidad = 0.0

    # Parsear precio y total del resto (solo FI los tiene)
    precio_unit = 0.0
    total_linea = 0.0
    if resto_raw.strip():
        # Formato: "        30.275,00         605.500,00:"
        numeros = re.findall(r'[\d\.]+,\d{2}', resto_raw)
        if len(numeros) >= 2:
            precio_unit = _parse_amount(numeros[0])
            total_linea = _parse_amount(numeros[1])
        elif len(numeros) == 1:
            precio_unit = _parse_amount(numeros[0])

    return {
        "codigo_lilis":  cod_prod,
        "imputacion":    imput_cod,
        "descripcion":   nom_prod,
        "cantidad":      cantidad,
        "precio_unit":   precio_unit,
        "total_linea":   total_linea,
    }


# ---------------------------------------------------------------------------
# Parser principal
# ---------------------------------------------------------------------------

# Total de comprobante: línea con solo un número grande, muy indentado
RE_TOTAL = re.compile(r'^\s{50,}([\d\.]+,\d{2})\s*$')

# Líneas a ignorar completamente
RE_IGNORE = re.compile(
    r'LILIS S\.A\.|DETALLE\s+COMPROBANTES|Desde\s+\d|'
    r'C[oó]digo.*Med.*Col|-----+|\(\s*\d'
)


def parse_firex(filepath: str, supplier_code: str = "1418") -> dict:
    """
    Lee FIREX.txt y retorna:
    { "fi": [ {header:{...}, lines:[...]} ], "re": [...] }
    Solo incluye comprobantes del proveedor indicado.
    """
    result   = {"fi": [], "re": []}
    current  = None
    last_total = None
    archivo  = os.path.basename(filepath)

    def _flush(doc, total_val):
        if doc is None:
            return
        doc["header"]["total_comprobante"] = total_val
        result[doc["header"]["tipo"]].append(doc)

    with open(filepath, encoding="latin-1") as f:
        for raw in f:
            line = raw.rstrip('\n')  # conservar espacios internos

            # Ignorar líneas de página / separadores
            if RE_IGNORE.search(line):
                continue

            # ¿Total de comprobante?
            tm = RE_TOTAL.match(line)
            if tm:
                last_total = _parse_amount(tm.group(1))
                continue

            # ¿Cabecera de comprobante?
            hdr = _extract_header(line)
            if hdr:
                _flush(current, last_total)
                last_total = None
                if hdr["proveedor_cod"] != supplier_code:
                    current = None
                    continue
                hdr["archivo_origen"] = archivo
                current = {"header": hdr, "lines": []}
                continue

            if current is None:
                continue

            # ¿Línea de detalle?
            det = _extract_detail(line)
            if det:
                current["lines"].append(det)

    _flush(current, last_total)

    print(f"[FIREX] Parseados: {len(result['fi'])} FI  |  {len(result['re'])} RE")
    return result


# ---------------------------------------------------------------------------
# Carga en base de datos
# ---------------------------------------------------------------------------

def load_firex_to_db(conn, parsed: dict, archivo_origen: str = "firex.txt"):
    cur = conn.cursor()
    fi_ok = fi_dup = re_ok = re_dup = 0

    # --- FI ---
    for doc in parsed["fi"]:
        h = doc["header"]
        try:
            cur.execute("""
                INSERT INTO T_GECOM_FI
                    (tipo, comprobante, fecha, proveedor_cod, proveedor_nom,
                     lista, fi_6dig, invoice_nbr, total_comprobante,
                     fecha_carga, archivo_origen)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                h["tipo"], h["comprobante"], h["fecha"],
                h["proveedor_cod"], h["proveedor_nom"],
                h["lista"], h["fi_6dig"], h["invoice_nbr"],
                h["total_comprobante"],
                h["fecha_carga"], h["archivo_origen"]
            ))
            for ln in doc["lines"]:
                cur.execute("""
                    INSERT INTO T_GECOM_FI_DETAIL
                        (comprobante, codigo_lilis, imputacion, descripcion,
                         cantidad, precio_unit, total_linea)
                    VALUES (?,?,?,?,?,?,?)
                """, (
                    h["comprobante"], ln["codigo_lilis"], ln["imputacion"],
                    ln["descripcion"], ln["cantidad"],
                    ln["precio_unit"], ln["total_linea"]
                ))
            fi_ok += 1
        except Exception as e:
            if "UNIQUE" in str(e).upper():
                fi_dup += 1
            else:
                print(f"  [FI ERROR] {h['comprobante']}: {e}")

    # --- RE ---
    for doc in parsed["re"]:
        h = doc["header"]
        fi_comp = None
        try:
            cur.execute(
                "SELECT comprobante FROM T_GECOM_FI WHERE fi_6dig=?", (h["fi_6dig"],)
            )
            row = cur.fetchone()
            if row:
                fi_comp = row[0]
        except Exception:
            pass

        try:
            cur.execute("""
                INSERT INTO T_GECOM_RE
                    (tipo, comprobante, fecha, proveedor_cod, proveedor_nom,
                     re_6dig, fi_comprobante, fecha_carga, archivo_origen)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                h["tipo"], h["comprobante"], h["fecha"],
                h["proveedor_cod"], h["proveedor_nom"],
                h["fi_6dig"], fi_comp,
                h["fecha_carga"], h["archivo_origen"]
            ))
            for ln in doc["lines"]:
                cur.execute("""
                    INSERT INTO T_GECOM_RE_DETAIL
                        (comprobante, codigo_lilis, descripcion, cantidad)
                    VALUES (?,?,?,?)
                """, (
                    h["comprobante"], ln["codigo_lilis"],
                    ln["descripcion"], ln["cantidad"]
                ))
            re_ok += 1
        except Exception as e:
            if "UNIQUE" in str(e).upper():
                re_dup += 1
            else:
                print(f"  [RE ERROR] {h['comprobante']}: {e}")

    conn.commit()
    print(f"[FIREX→DB] FI: {fi_ok} nuevas, {fi_dup} duplicadas | "
          f"RE: {re_ok} nuevas, {re_dup} duplicadas")


# ---------------------------------------------------------------------------
# Test con volcado de primeros registros
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "input/firex.txt"
    data = parse_firex(path)

    print("\n=== Primeras 3 FI ===")
    for doc in data["fi"][:3]:
        h = doc["header"]
        print(f"  {h['comprobante']}  {h['fecha']}  prov={h['proveedor_cod']}  "
              f"lista={h['lista']}  total={h['total_comprobante']}  6dig={h['fi_6dig']}")
        for ln in doc["lines"][:3]:
            print(f"    cod={ln['codigo_lilis']}  imput={ln['imputacion']}  "
                  f"desc={ln['descripcion'][:35]}  qty={ln['cantidad']}  "
                  f"precio={ln['precio_unit']}  total={ln['total_linea']}")

    print("\n=== Primeros 3 RE ===")
    for doc in data["re"][:3]:
        h = doc["header"]
        print(f"  {h['comprobante']}  {h['fecha']}  prov={h['proveedor_cod']}  "
              f"6dig={h['fi_6dig']}")
        for ln in doc["lines"][:3]:
            print(f"    cod={ln['codigo_lilis']}  "
                  f"desc={ln['descripcion'][:35]}  qty={ln['cantidad']}")
