# =============================================================================
# parser_po.py  —  Parser del PDF de confirmación de PO (email Solventum)
# =============================================================================

import re
import os
from datetime import datetime
import pdfplumber


def _clean(s):
    return (s or "").strip()

def _num(s):
    if not s:
        return 0.0
    # Soporta "$ 1,423.92" → 1423.92
    return float(re.sub(r'[^\d.]', '', str(s).replace(',', '')))


def _extract_text(filepath: str) -> str:
    pages = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    return "\n".join(pages)


def parse_po(filepath: str) -> dict:
    """
    Parsea la confirmación de PO de 3M (email convertido a PDF).
    Retorna dict con 'header' y 'lines'.
    """
    text = _extract_text(filepath)

    header = {
        "po_number":          None,
        "order_date":         None,
        "sold_to_account":    None,
        "sold_to_name":       None,
        "sold_to_address":    None,
        "ship_to_account":    None,
        "ship_to_name":       None,
        "ship_to_address":    None,
        "delivery_method":    None,
        "requested_delivery": None,
        "ultimate_country":   None,
        "payment_method":     None,
        "subtotal":           0.0,
        "fecha_carga":        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "archivo_origen":     os.path.basename(filepath),
    }

    detail_lines = []

    def _find(pattern, default=None):
        m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        return _clean(m.group(1)) if m else default

    # --- PO Number ---
    header["po_number"] = _find(r'Purchase Order Number\s+([\w\s]+?)(?:\n|Product)')
    if not header["po_number"]:
        header["po_number"] = _find(r'Order Confirmation\s+([\w\s]+?)(?:\n)')

    # Limpiar
    if header["po_number"]:
        header["po_number"] = header["po_number"].strip()

    # --- Fecha del email / order ---
    header["order_date"] = _find(r'Enviado el:.*?(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})')
    if not header["order_date"]:
        header["order_date"] = _find(r'(?:Sent|Date):\s*([^\n]+)')

    # --- Delivery ---
    header["delivery_method"]    = _find(r'Delivery Method\s+([^\n]+?)(?:\n|Attention)')
    header["requested_delivery"] = _find(r'Requested Delivery:\s*([\d/]+)')
    header["ultimate_country"]   = _find(r'Country\s+([A-Za-z]+)')
    header["payment_method"]     = _find(r'Order Payment Method\s+([^\n]+?)(?:\n|Purchase)')

    # --- Sold-to ---
    m = re.search(
        r'Sold-to Address:\s*\n([^\n]+)\n(\d+)\n([^\n]+)\n([^\n]+)\n([^\n]+)',
        text, re.IGNORECASE
    )
    if m:
        header["sold_to_name"]    = _clean(m.group(3))
        header["sold_to_account"] = _clean(m.group(2))
        header["sold_to_address"] = _clean(m.group(4)) + " | " + _clean(m.group(5))

    # --- Ship-to ---
    m = re.search(
        r'Ship-to Address:\s*\n(\d+)\n([^\n]+)\n([^\n]+)\n([^\n]+)\n([^\n]+)',
        text, re.IGNORECASE
    )
    if m:
        header["ship_to_account"] = _clean(m.group(1))
        header["ship_to_name"]    = _clean(m.group(2)) + " / " + _clean(m.group(3))
        header["ship_to_address"] = _clean(m.group(4)) + " | " + _clean(m.group(5))

    # --- Subtotal ---
    sub = _find(r'(?:Subtotal|Order Total):\s*\$?\s*([\d,\.]+)')
    header["subtotal"] = _num(sub) if sub else 0.0

    # --- Líneas de detalle ---
    # Patrón en el texto del email:
    # <linea_num>
    # 3M™ Littmann® ... descripción ...
    # Contract #: CXXXXX
    # Your Catalog Number:
    # 3M Catalog Number: XXXX
    # 3M Stock Number: XXXXXXXXXX
    # UPC#: XXXXXXXXXXXXXXX
    # <qty> Each $ <precio> per Each $ <total>

    # Dividir el texto en bloques por número de línea
    # Los números de línea en PO son enteros simples (1,2,3...)
    line_block_pattern = re.compile(
        r'^\s*(\d{1,2})\s*\n'              # Número de línea
        r'(3M™.+?)\n'                       # Descripción (primera línea)
        r'(.*?)'                            # resto del bloque
        r'(\d+)\s+Each\s+\$\s*([\d,\.]+)\s+per\s+Each\s+\$\s*([\d,\.]+)',
        re.MULTILINE | re.DOTALL
    )

    for m in line_block_pattern.finditer(text):
        linea   = int(m.group(1))
        desc1   = _clean(m.group(2))
        middle  = m.group(3)
        qty     = _num(m.group(4))
        precio  = _num(m.group(5))
        total   = _num(m.group(6))

        # Extraer datos del bloque intermedio
        cat_3m  = None
        stock_3m = None
        upc     = None
        contrato = None

        for bl in middle.splitlines():
            bl = bl.strip()
            cm = re.search(r'3M Catalog\s+Number:\s*(\S+)', bl)
            if cm:
                cat_3m = cm.group(1)
            sm = re.search(r'3M Stock\s+Number:\s*(\d+)', bl)
            if sm:
                stock_3m = sm.group(1)
            um = re.search(r'UPC#:\s*(\d+)', bl)
            if um:
                upc = um.group(1)
            co = re.search(r'Contract #:\s*(\S+)', bl)
            if co:
                contrato = co.group(1)

        # Juntar descripción completa
        desc_lines = [desc1]
        for bl in middle.splitlines():
            bl = bl.strip()
            if bl and not any(bl.startswith(x) for x in [
                "Contract", "Your Catalog", "3M Catalog", "3M Stock", "UPC#"
            ]):
                if "Each/Case" in bl or "inch" in bl:
                    desc_lines.append(bl)

        descripcion = " ".join(desc_lines).strip()

        detail_lines.append({
            "linea":       linea,
            "catalog_3m":  cat_3m,
            "stock_3m":    stock_3m,
            "upc":         upc,
            "descripcion": descripcion,
            "cantidad":    qty,
            "unidad":      "Each",
            "precio_unit": precio,
            "total_linea": total,
            "contrato":    contrato,
        })

    # Fallback si no encontró líneas con el patrón complejo
    if not detail_lines:
        # Patrón más simple
        simple_pattern = re.compile(
            r'(\d{1,2})\s+3M™([^\n]+)\n'
        )
        for m in simple_pattern.finditer(text):
            detail_lines.append({
                "linea":       int(m.group(1)),
                "catalog_3m":  None,
                "stock_3m":    None,
                "upc":         None,
                "descripcion": "3M™" + m.group(2).strip(),
                "cantidad":    None,
                "unidad":      "Each",
                "precio_unit": None,
                "total_linea": None,
                "contrato":    None,
            })

    print(f"[PO] {header['po_number']} | Subtotal: {header['subtotal']} | "
          f"Líneas: {len(detail_lines)}")

    return {"header": header, "lines": detail_lines}


# ---------------------------------------------------------------------------
# Carga en base de datos
# ---------------------------------------------------------------------------

def load_po_to_db(conn, parsed: dict):
    cur = conn.cursor()
    h = parsed["header"]

    try:
        cur.execute("""
            INSERT INTO T_3M_PO_HEADER
                (po_number, order_date,
                 sold_to_account, sold_to_name, sold_to_address,
                 ship_to_account, ship_to_name, ship_to_address,
                 delivery_method, requested_delivery, ultimate_country,
                 payment_method, subtotal,
                 fecha_carga, archivo_origen)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            h["po_number"], h["order_date"],
            h["sold_to_account"], h["sold_to_name"], h["sold_to_address"],
            h["ship_to_account"], h["ship_to_name"], h["ship_to_address"],
            h["delivery_method"], h["requested_delivery"], h["ultimate_country"],
            h["payment_method"], h["subtotal"],
            h["fecha_carga"], h["archivo_origen"]
        ))

        for ln in parsed["lines"]:
            cur.execute("""
                INSERT INTO T_3M_PO_DETAIL
                    (po_number, linea, catalog_3m, stock_3m, upc,
                     descripcion, cantidad, unidad,
                     precio_unit, total_linea, contrato)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                h["po_number"], ln["linea"], ln["catalog_3m"], ln["stock_3m"],
                ln["upc"], ln["descripcion"], ln["cantidad"], ln["unidad"],
                ln["precio_unit"], ln["total_linea"], ln["contrato"]
            ))

        conn.commit()
        print(f"[PO→DB] '{h['po_number']}' cargada: {len(parsed['lines'])} líneas.")
        return True

    except Exception as e:
        conn.rollback()
        if "UNIQUE" in str(e).upper():
            print(f"[PO→DB] '{h['po_number']}' ya existe (duplicada).")
        else:
            print(f"[PO→DB] ERROR: {e}")
        return False


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "../input/PO.pdf"
    result = parse_po(path)
    print("\nCABECERA:")
    for k, v in result["header"].items():
        print(f"  {k}: {v}")
    print(f"\nDETALLE ({len(result['lines'])} líneas):")
    for ln in result["lines"]:
        print(" ", ln)
