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


def _extract_detail_lines_by_coords(filepath: str) -> list:
    """
    Extrae lineas de detalle usando coordenadas de palabras.
    El PDF de confirmacion de PO tiene dos columnas:
      - Columna izquierda  (x < COL_SPLIT): nro de linea + descripcion
      - Columna derecha    (x >= COL_SPLIT): Your Catalog / 3M Catalog / Stock / UPC / qty / precio / total
    Todas las paginas de detalle se unifican en un unico espacio de coordenadas
    sumando el offset Y acumulado, para manejar bloques cortados entre paginas.
    """
    COL_SPLIT = 185

    detail_lines = []

    with pdfplumber.open(filepath) as pdf:
        all_left  = []
        all_right = []
        y_offset  = 0.0

        for page in pdf.pages[1:]:
            words = page.extract_words()
            if not words:
                y_offset += page.height
                continue
            for w in words:
                y = float(w['top']) + y_offset
                entry = dict(w, top=y)
                if w['x0'] < COL_SPLIT:
                    all_left.append(entry)
                else:
                    all_right.append(entry)
            y_offset += page.height

        product_starts = []
        for w in all_left:
            if re.match(r'^\d{1,2}$', w['text']) and w['x0'] < 40:
                product_starts.append((int(w['text']), float(w['top'])))

        if not product_starts:
            return detail_lines

        subtotal_words = [w for w in all_left if w['text'].startswith('Subtotal')]
        y_footer = float(subtotal_words[0]['top']) if subtotal_words else 9999

        for idx, (linea_num, y_start) in enumerate(product_starts):
            y_end = min(
                product_starts[idx + 1][1] if idx + 1 < len(product_starts) else 9999,
                y_footer
            )

            desc_words = [
                w for w in all_left
                if y_start <= w['top'] < y_end
                and not re.match(r'^\d{1,2}$', w['text'])
            ]
            descripcion = " ".join(
                w['text'] for w in sorted(desc_words, key=lambda w: (w['top'], w['x0']))
            )

            data_words = [w for w in all_right if y_start <= w['top'] < y_end]
            data_lines_raw = {}
            for w in data_words:
                y_key = round(w['top'] / 3) * 3
                data_lines_raw.setdefault(y_key, []).append(w)
            data_lines_text = [
                " ".join(w['text'] for w in sorted(data_lines_raw[yk], key=lambda w: w['x0']))
                for yk in sorted(data_lines_raw)
            ]

            cat_3m   = None
            stock_3m = None
            upc      = None
            contrato = None
            qty      = None
            unidad   = "Each"
            precio   = None
            total    = None
            upc_next = False

            for i, line in enumerate(data_lines_text):
                line_s = line.strip()

                if upc_next:
                    if re.match(r'^\d{10,}$', line_s):
                        upc = line_s
                    upc_next = False
                    continue

                if re.match(r'^UPC#:$', line_s):
                    upc_next = True
                    continue
                m = re.search(r'UPC#:\s*(\d+)', line_s)
                if m:
                    upc = m.group(1)
                    continue

                m = re.search(
                    r'(\d+)\s+(Kit|Each|BX|CS|PK|DZ)\s+\$\s*([\d,\.]+)\s+per\s+(?:Kit|Each|BX|CS|PK|DZ)\s+\$\s*([\d,\.]+)',
                    line_s
                )
                if m:
                    qty = _num(m.group(1)); unidad = m.group(2)
                    precio = _num(m.group(3)); total = _num(m.group(4))
                    continue
                m = re.search(
                    r'(\d+)\s+(Kit|Each|BX|CS|PK|DZ)\s+\$\s*([\d,\.]+)\s+per\s+\$\s*([\d,\.]+)',
                    line_s
                )
                if m:
                    qty = _num(m.group(1)); unidad = m.group(2)
                    precio = _num(m.group(3)); total = _num(m.group(4))
                    continue

                # 3M Catalog Number — el valor siempre está en la linea siguiente (nunca inline fiable)
                # porque pdfplumber mezcla "Each" de la columna de qty en esa misma fila.
                if re.search(r'3M Catalog\s+Number:', line_s):
                    if i + 1 < len(data_lines_text):
                        nxt = data_lines_text[i + 1].strip()
                        # Aceptar: alfanumérico corto, no una palabra clave del PDF
                        if re.match(r'^[\w]{1,10}$', nxt) and not re.search(
                            r'^(3M|Stock|Number|UPC|Each|Kit|BX|CS|PK|DZ|Your|Catalog|Per)$', nxt, re.I
                        ):
                            cat_3m = nxt
                    continue

                m = re.search(r'Number:\s*(\d{10})', line_s)
                if m:
                    stock_3m = m.group(1)
                    continue

                m = re.search(r'Contract #:\s*(\S+)', line_s)
                if m:
                    contrato = m.group(1)
                    continue

            if qty is None and precio is None:
                continue

            detail_lines.append({
                "linea":       linea_num,
                "catalog_3m":  cat_3m,
                "stock_3m":    stock_3m,
                "upc":         upc,
                "descripcion": descripcion.strip(),
                "cantidad":    qty,
                "unidad":      unidad,
                "precio_unit": precio,
                "total_linea": total,
                "contrato":    contrato,
            })

    return detail_lines


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
    header["delivery_method"]    = _find(r'Delivery Method\s+(.+?)(?:\s+Requested Delivery:|\n)')
    header["requested_delivery"] = _find(r'Requested Delivery:\s*([\d/]+)')
    header["ultimate_country"]   = _find(r'Country\s+([A-Za-z]+)')
    header["payment_method"]     = _find(r'Order Payment Method\s+([^\n]+?)(?:\s+Purchase|\n)')

    # --- Sold-to y Ship-to: usar coordenadas (layout de 2 columnas en pág. 1) ---
    with pdfplumber.open(filepath) as _pdf:
        _page1 = _pdf.pages[0]
        _words = _page1.extract_words()
        _COL   = 300   # separación sold-to (izq) / ship-to (der)

        # Encontrar y_start de cada bloque de direcciones
        _sold_y = next((float(w['top']) for w in _words if w['text'] == 'Sold-to'), None)
        _ship_y = next((float(w['top']) for w in _words if w['text'] == 'Ship-to'), None)
        _ship_section_y = next((float(w['top']) for w in _words if w['text'] == 'Shipping'), 9999)

        def _addr_lines(x_min, x_max, y_min, y_max):
            """Agrupa palabras en líneas de texto dentro de una región."""
            region = [w for w in _words
                      if x_min <= w['x0'] < x_max
                      and y_min <= float(w['top']) < y_max]
            rows = {}
            for w in region:
                y_key = round(float(w['top']) / 3) * 3
                rows.setdefault(y_key, []).append(w)
            return [
                " ".join(w['text'] for w in sorted(rows[yk], key=lambda w: w['x0']))
                for yk in sorted(rows)
            ]

        if _sold_y:
            lines = _addr_lines(0, _COL, _sold_y + 5, _ship_section_y)
            # lines: [supplier_name, account_num, customer_name, address1, city_zip]
            # Ejemplo: ['Solventum Export United States', '16258871', 'LILIS SA', '2302 AVENIDA CORDOBA PASTEUR 796', 'CABA, null', 'C1028AAP']
            nums = [l for l in lines if re.match(r'^\d+$', l.strip())]
            if nums:
                header["sold_to_account"] = nums[0]
            # Nombre del cliente = primera línea que no sea la del proveedor ni un número
            name_lines = [l for l in lines if not re.match(r'^\d+$', l.strip())
                          and 'Solventum' not in l]
            if name_lines:
                header["sold_to_name"] = name_lines[0]
            if len(name_lines) > 1:
                header["sold_to_address"] = " | ".join(name_lines[1:])

        if _ship_y:
            lines = _addr_lines(_COL, 9999, _ship_y + 5, _ship_section_y)
            nums = [l for l in lines if re.match(r'^\d+$', l.strip())]
            if nums:
                header["ship_to_account"] = nums[0]
            name_lines = [l for l in lines if not re.match(r'^\d+$', l.strip())]
            if len(name_lines) >= 2:
                header["ship_to_name"] = name_lines[0] + " / " + name_lines[1]
            if len(name_lines) > 2:
                header["ship_to_address"] = " | ".join(name_lines[2:])

    # --- Subtotal ---
    sub = _find(r'(?:Subtotal|Order Total):\s*\$?\s*([\d,\.]+)')
    header["subtotal"] = _num(sub) if sub else 0.0

    # --- Líneas de detalle ---
    # El PDF de confirmación de PO tiene layout de 2 columnas en la página de detalle.
    # pdfplumber mezcla las columnas al extraer texto plano, por lo que se usa
    # extracción por coordenadas de palabras (_extract_detail_lines_by_coords).
    detail_lines = _extract_detail_lines_by_coords(filepath)

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
