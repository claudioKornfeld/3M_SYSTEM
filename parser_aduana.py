# =============================================================================
# parser_aduana.py  —  Parser de Despacho de Aduana ARCA (IC04)
# Integrado al 3M_SYSTEM
#
# Extrae SOLO de página 1 los campos solicitados:
#   NrDespacho, Oficialización, Agente Transporte, Vendedor,
#   Fecha Arribo, Embalaje, Total Bultos, Peso Bruto,
#   Cond. Venta, FOB Total, Divisa, Flete Total,
#   Información Complementaria
#
# Tabla generada: T_ADUANA_DESPACHO (1 fila por despacho)
# =============================================================================

import re
import os
from datetime import datetime
import pdfplumber


def _band(words, y0, y1, x0=0, x1=9999):
    """Palabras dentro del rectángulo, ordenadas por X."""
    return sorted(
        [w for w in words
         if y0 <= w['top'] <= y1 and x0 <= w['x0'] <= x1],
        key=lambda w: w['x0']
    )

def _txt(words, y0, y1, x0=0, x1=9999):
    """Texto concatenado de las palabras en el rectángulo."""
    return " ".join(w['text'] for w in _band(words, y0, y1, x0, x1)).strip()

def _num(s):
    """'171 .412,83' → 171412.83  (formato argentino)."""
    s = re.sub(r'[^\d,\.]', '', str(s or ""))
    if not s:
        return 0.0
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    try:
        return float(s)
    except Exception:
        return 0.0


def parse_aduana(filepath: str) -> dict:

    result = {
        "nr_despacho":         None,
        "oficializacion":      None,
        "agente_transporte":   None,
        "vendedor":            None,
        "fecha_arribo":        None,
        "embalaje":            None,
        "total_bultos":        None,
        "peso_bruto":          None,
        "cond_venta":          None,
        "fob_total":           None,
        "divisa":              None,
        "flete_total":         None,
        "info_complementaria": None,
        "fecha_carga":         datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "archivo_origen":      os.path.basename(filepath),
    }

    # Extraer palabras de página 1 dentro del context manager
    with pdfplumber.open(filepath) as pdf:
        words = pdf.pages[0].extract_words()

    # ── NrDespacho — desde nombre de archivo (más confiable que OCR) ─────────
    fn = os.path.basename(filepath)
    m = re.search(r'(\d{2})[\s_](\d{3})[\s_][A-Za-z]{2}0?4[\s_](\d{6})[\s_]([A-Z])', fn, re.IGNORECASE)
    if m:
        result["nr_despacho"] = m.group(1) + m.group(2) + "IC04" + m.group(3) + m.group(4)

    # ── Oficialización — y≈80-90 zona cabecera, o pie de página ──────────────
    # En el pie aparece "OFIC¡ALIZADO 07 /10/2025"
    # Buscar en toda la página la primera ocurrencia de DD/MM/YYYY
    for y_approx in [83, 745, 750, 755]:
        raw = _txt(words, y_approx - 4, y_approx + 6)
        m2 = re.search(r'(\d{2})\s*/\s*(\d{2})\s*/\s*(20\d{2})', raw)
        if m2:
            result["oficializacion"] = f"{m2.group(1)}/{m2.group(2)}/{m2.group(3)}"
            break
    if not result["oficializacion"]:
        # Scan completo
        ys = sorted(set(round(w['top']) for w in words))
        for y in ys:
            raw = _txt(words, y - 2, y + 4)
            if re.search(r'OFIC', raw, re.IGNORECASE):
                m2 = re.search(r'(\d{2})\s*/\s*(\d{2})\s*/\s*(20\d{2})', raw)
                if m2:
                    result["oficializacion"] = f"{m2.group(1)}/{m2.group(2)}/{m2.group(3)}"
                    break

    # ── Agente Transporte — y≈124-132, x≈40-220 ────────────────────────────
    # El escáner convierte la "S" de "CARGO S A" en el dígito "5" (mismo glifo).
    # Reconstruimos reemplazando dígito suelto de 1 caracter (x<80) por "S".
    agente_tokens = []
    for w in _band(words, 122, 132, 40, 220):
        tok = w['text']
        if re.fullmatch(r'\d', tok) and w['x0'] < 80:
            tok = 'S'
        agente_tokens.append(tok)
    result["agente_transporte"] = " ".join(agente_tokens).strip() or None

    # ── Vendedor — y≈126-128, x≈305-430 ─────────────────────────────────────
    # "]M HEALÍHCARE LATAM"  →  "3M HEALTHCARE LATAM"
    vend = _txt(words, 122, 132, 300, 430)
    vend = re.sub(r'^[\]|l]M\b', '3M', vend)
    vend = vend.replace("HEALÍHCARE", "HEALTHCARE").replace("LATAM", "LATAM")
    result["vendedor"] = vend or None

    # ── Fecha Arribo — y≈164, x≈230-310 ─────────────────────────────────────
    # "27/09t2025" (OCR usa 't' en lugar de '/')
    raw_fecha = _txt(words, 160, 170, 230, 310)
    m2 = re.search(r'(\d{2})[/t](\d{2})[/t](20\d{2})', raw_fecha)
    if m2:
        result["fecha_arribo"] = f"{m2.group(1)}/{m2.group(2)}/{m2.group(3)}"

    # ── Embalaje — y≈186, x≈40-120 ───────────────────────────────────────────
    result["embalaje"] = _txt(words, 183, 192, 40, 120) or None

    # ── Total Bultos — el "5" está en x≈64, y≈124 (entre CARGO y A) ─────────
    raw_bultos = _txt(words, 122, 132, 62, 68)
    if raw_bultos and re.fullmatch(r'\d+', raw_bultos.strip()):
        result["total_bultos"] = int(raw_bultos.strip())
    else:
        # Fallback más amplio
        raw_bultos = _txt(words, 122, 132, 58, 75)
        nums = re.findall(r'^\d+$', raw_bultos.strip())
        if nums:
            result["total_bultos"] = int(nums[0])

    # ── Peso Bruto — y≈186, x≈140-225 ────────────────────────────────────────
    # "693,000"
    raw_peso = _txt(words, 183, 192, 140, 225)
    if raw_peso:
        result["peso_bruto"] = _num(raw_peso.split()[0])

    # ── Cond. Venta — y≈207, x≈180-225 ──────────────────────────────────────
    result["cond_venta"] = _txt(words, 204, 212, 180, 225) or None

    # ── FOB Total — y≈207-209, x≈245-370 ────────────────────────────────────
    # "171 .412,83"  (OCR parte el número con espacio)
    raw_fob = _txt(words, 204, 215, 245, 370)
    m2 = re.search(r'([\d\s\.]+,\d{2})', raw_fob)
    if m2:
        result["fob_total"] = _num(re.sub(r'\s', '', m2.group(1)))

    # ── Divisa FOB — y≈207-209, x≈355-410 ───────────────────────────────────
    raw_div = _txt(words, 204, 215, 355, 410)
    if re.search(r'\bDOL\b', raw_div):
        result["divisa"] = "DOL"
    elif re.search(r'\bEUR\b', raw_div):
        result["divisa"] = "EUR"

    # ── Flete Total — y≈207-210, x≈415-450 ──────────────────────────────────
    # "21 0,00"  →  OCR parte en "21" + "0,00" = 210.00
    raw_flete = _txt(words, 204, 215, 415, 450)
    result["flete_total"] = _num(re.sub(r'\s', '', raw_flete)) if raw_flete else 0.0

    # ── Información Complementaria — y≈238-252 ───────────────────────────────
    # Línea 1 (y≈238-243): "cotiz = 1.430,000000  DOMICIL.ESTABLEC = Pasteur 796 ..."
    # Línea 2 (y≈247-250): "Peso Guía = 693,000  Nros. Facturas: 9434... ..."
    info1 = _txt(words, 234, 244, 130, 560)
    info2 = _txt(words, 244, 256, 40, 560)
    # Limpiar info2: extraer solo números de factura de 10 dígitos puros
    # (el OCR genera tokens como "}4347OA3ZO" que son basura del escáner)
    if info2:
        peso_m = re.search(r'Peso\s+\w+\s*=\s*([\d,\.]+)', info2)
        facturas = re.findall(r'\b(\d{10})\b', info2)
        parts2 = []
        if peso_m:
            parts2.append(f"Peso Guia = {peso_m.group(1)}")
        if facturas:
            parts2.append("Nros. Facturas: " + " ".join(facturas))
        if parts2:
            info2 = "  ".join(parts2)
    info_parts = [p for p in [info1, info2] if p]
    result["info_complementaria"] = " | ".join(info_parts) or None

    print(
        f"[Aduana] {result['nr_despacho']} | "
        f"Ofic: {result['oficializacion']} | "
        f"Arribo: {result['fecha_arribo']} | "
        f"FOB: {result['fob_total']} {result['divisa']} | "
        f"Flete: {result['flete_total']} | "
        f"Bultos: {result['total_bultos']} | "
        f"Peso: {result['peso_bruto']}"
    )
    return result


# ---------------------------------------------------------------------------
# DDL SQLite (desarrollo)
# ---------------------------------------------------------------------------

DDL_SQLITE = [
    """CREATE TABLE IF NOT EXISTS T_ADUANA_DESPACHO (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        nr_despacho          TEXT NOT NULL,
        oficializacion       TEXT,
        agente_transporte    TEXT,
        vendedor             TEXT,
        fecha_arribo         TEXT,
        embalaje             TEXT,
        total_bultos         INTEGER,
        peso_bruto           REAL,
        cond_venta           TEXT,
        fob_total            REAL,
        divisa               TEXT,
        flete_total          REAL,
        info_complementaria  TEXT,
        fecha_carga          TEXT,
        archivo_origen       TEXT,
        UNIQUE(nr_despacho))""",
]

# DDL Access (para incluir en access_connector.py)
DDL_ACCESS = (
    "CREATE TABLE T_ADUANA_DESPACHO ("
    "id AUTOINCREMENT PRIMARY KEY, "
    "nr_despacho TEXT(30) NOT NULL, "
    "oficializacion TEXT(12), "
    "agente_transporte TEXT(80), "
    "vendedor TEXT(80), "
    "fecha_arribo TEXT(12), "
    "embalaje TEXT(20), "
    "total_bultos INTEGER, "
    "peso_bruto DOUBLE, "
    "cond_venta TEXT(10), "
    "fob_total CURRENCY, "
    "divisa TEXT(5), "
    "flete_total CURRENCY, "
    "info_complementaria MEMO, "
    "fecha_carga TEXT(22), "
    "archivo_origen TEXT(100))"
)


# ---------------------------------------------------------------------------
# Carga en SQLite (desarrollo)
# ---------------------------------------------------------------------------

def load_aduana_to_db(conn, parsed: dict) -> bool:
    cur = conn.cursor()
    did = parsed.get("nr_despacho")
    if not did:
        print("[Aduana→DB] ERROR: nr_despacho vacío.")
        return False
    try:
        cur.execute("""
            INSERT INTO T_ADUANA_DESPACHO
                (nr_despacho, oficializacion, agente_transporte, vendedor,
                 fecha_arribo, embalaje, total_bultos, peso_bruto,
                 cond_venta, fob_total, divisa, flete_total,
                 info_complementaria, fecha_carga, archivo_origen)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            parsed["nr_despacho"],  parsed["oficializacion"],
            parsed["agente_transporte"], parsed["vendedor"],
            parsed["fecha_arribo"], parsed["embalaje"],
            parsed["total_bultos"], parsed["peso_bruto"],
            parsed["cond_venta"],   parsed["fob_total"],
            parsed["divisa"],       parsed["flete_total"],
            parsed["info_complementaria"],
            parsed["fecha_carga"],  parsed["archivo_origen"],
        ))
        conn.commit()
        print(f"[Aduana→DB] {did} insertado correctamente.")
        return True
    except Exception as e:
        conn.rollback()
        if "UNIQUE" in str(e).upper():
            print(f"[Aduana→DB] {did} ya existe (duplicado).")
        else:
            print(f"[Aduana→DB] ERROR: {e}")
        return False


# ---------------------------------------------------------------------------
# CLI / Test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "input/aduana.pdf"
    r = parse_aduana(path)
    print("\n── RESULTADO ──────────────────────────────────────────")
    for k, v in r.items():
        if k != "fecha_carga":
            print(f"  {k.upper():<26}: {v}")
