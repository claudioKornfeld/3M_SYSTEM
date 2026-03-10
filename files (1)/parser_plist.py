# =============================================================================
# parser_plist.py  —  Parser de Packing List PDF  (3M / Solventum)
# =============================================================================

import re
import os
import json
from datetime import datetime
import pdfplumber


def _clean(s):
    return (s or "").strip()

def _num(s):
    try:
        return float(_clean(s))
    except Exception:
        return 0.0


def _extract_text(filepath: str) -> str:
    pages = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    return "\n".join(pages)


def parse_plist(filepath: str) -> dict:
    """
    Parsea un Packing List PDF de Solventum / 3M.
    Retorna dict con 'header' y 'lines'.
    """
    text = _extract_text(filepath)

    header = {
        "shipping_ref":     None,
        "po_number":        None,
        "invoice_nbr":      None,   # se enlaza luego por shipping_ref = delivery_nbr
        "ship_from_loc":    None,
        "wave_nbr":         None,
        "order_date":       None,
        "ship_date":        None,
        "ship_to_name":     None,
        "ship_to_address":  None,
        "charge_to_name":   None,
        "charge_to_address": None,
        "total_pieces":     None,
        "total_weight":     None,
        "fecha_carga":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "archivo_origen":   os.path.basename(filepath),
    }

    detail_lines = []

    def _find(pattern, default=None):
        m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        return _clean(m.group(1)) if m else default

    # --- Cabecera ---
    header["shipping_ref"]  = _find(r'SHIPPING REFERENCE #:\s*(\d+)')
    header["po_number"]     = _find(r'P\.O\. NUMBER\s+([\w\s]+?)(?:\n|SHIP FROM)')
    header["ship_from_loc"] = _find(r'SHIP FROM LOC:\s*(\w+)')
    header["wave_nbr"]      = _find(r'WAVE #:\s*(\S+)')
    header["order_date"]    = _find(r'CUSTOMER ORDER DATE:\s*([\d/]+)')
    header["ship_date"]     = _find(r'SHIP DATE:\s*([\d/]+)')

    # Piezas y peso totales
    m_pieces = re.search(r'Pieces:\s*([\d]+)', text)
    m_weight = re.search(r'Weight:\s*([\d\.]+)', text)
    if m_pieces:
        header["total_pieces"] = int(m_pieces.group(1))
    if m_weight:
        header["total_weight"] = float(m_weight.group(1))

    # Limpiar PO number (puede tener trailing spaces)
    if header["po_number"]:
        header["po_number"] = header["po_number"].strip()

    # Ship To
    m = re.search(
        r'SHIP TO:\s*\n(.*?)\n(.*?)\n(.*?)\n(.*?)\n',
        text, re.IGNORECASE
    )
    if m:
        header["ship_to_name"]    = _clean(m.group(1)) + " " + _clean(m.group(2))
        header["ship_to_address"] = _clean(m.group(3)) + " | " + _clean(m.group(4))

    # Charge To
    m = re.search(
        r'CHARGE TO:\s*\n(.*?)\n(.*?)\n(.*?)\n(.*?)\n',
        text, re.IGNORECASE
    )
    if m:
        header["charge_to_name"]    = _clean(m.group(1))
        header["charge_to_address"] = (
            _clean(m.group(2)) + " | " + _clean(m.group(3)) + " | " + _clean(m.group(4))
        )

    # --- Líneas de detalle ---
    # Formato en el texto extraído (por página, columnas mezcladas):
    # 000100 3.00 3.00 EA 5-07-07387-78956-0 3M™ ... descripción  2.84  1.00
    # 70-2011-8518-1
    # 7100212849
    # Lot #: 13018395

    line_pattern = re.compile(
        r'^(?P<line_nbr>\d{6})\s+'
        r'(?P<order_qty>[\d\.]+)\s+'
        r'(?P<shipped_qty>[\d\.]+)\s+'
        r'(?P<bill_unit>\w+)\s+'
        r'(?P<upc>[\d\-]+)\s+'
        r'(?P<desc>.+?)\s+'
        r'(?P<weight>[\d\.]+)\s+'
        r'(?P<pieces>[\d\.]+)\s*$',
        re.MULTILINE
    )

    matches = list(line_pattern.finditer(text))

    for i, m in enumerate(matches):
        line_nbr    = m.group("line_nbr")
        order_qty   = _num(m.group("order_qty"))
        shipped_qty = _num(m.group("shipped_qty"))
        bill_unit   = m.group("bill_unit")
        upc         = m.group("upc")
        desc        = _clean(m.group("desc"))
        weight      = _num(m.group("weight"))
        pieces      = int(_num(m.group("pieces")))

        # Bloque siguiente hasta próxima línea o fin
        start = m.end()
        end   = matches[i+1].start() if i+1 < len(matches) else len(text)
        block = text[start:end].strip()

        # Extraer material_id y lotes del bloque
        material_id = None
        lots_list   = []

        for bl in block.splitlines():
            bl = bl.strip()
            if not bl:
                continue
            # Material ID: 10 dígitos comenzando con 7100
            if re.match(r'^71\d{8}$', bl):
                material_id = bl
                continue
            # Lot #: XXXXXXXX  o  Lot #: XXXXXXXX QTY: N
            lm = re.match(r'Lot #:\s*(\d+)(?:\s+QTY:\s*(\d+))?', bl)
            if lm:
                lot_entry = {"lot": lm.group(1)}
                if lm.group(2):
                    lot_entry["qty"] = int(lm.group(2))
                lots_list.append(lot_entry)

        detail_lines.append({
            "line_nbr":        line_nbr,
            "order_qty":       order_qty,
            "shipped_qty":     shipped_qty,
            "bill_unit":       bill_unit,
            "upc":             upc,
            "material_id":     material_id,
            "descripcion":     desc,
            "tot_line_weight": weight,
            "total_pieces":    pieces,
            "lot_info":        json.dumps(lots_list) if lots_list else None,
        })

    print(f"[PList] Ref: {header['shipping_ref']} | PO: {header['po_number']} | "
          f"Piezas: {header['total_pieces']} | Peso: {header['total_weight']} | "
          f"Líneas: {len(detail_lines)}")

    return {"header": header, "lines": detail_lines}


# ---------------------------------------------------------------------------
# Carga en base de datos
# ---------------------------------------------------------------------------

def load_plist_to_db(conn, parsed: dict):
    cur = conn.cursor()
    h = parsed["header"]

    try:
        cur.execute("""
            INSERT INTO T_3M_PLIST_HEADER
                (shipping_ref, po_number, invoice_nbr, ship_from_loc, wave_nbr,
                 order_date, ship_date,
                 ship_to_name, ship_to_address,
                 charge_to_name, charge_to_address,
                 total_pieces, total_weight,
                 fecha_carga, archivo_origen)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            h["shipping_ref"], h["po_number"], h["invoice_nbr"],
            h["ship_from_loc"], h["wave_nbr"],
            h["order_date"], h["ship_date"],
            h["ship_to_name"], h["ship_to_address"],
            h["charge_to_name"], h["charge_to_address"],
            h["total_pieces"], h["total_weight"],
            h["fecha_carga"], h["archivo_origen"]
        ))

        for ln in parsed["lines"]:
            cur.execute("""
                INSERT INTO T_3M_PLIST_DETAIL
                    (shipping_ref, line_nbr, order_qty, shipped_qty, bill_unit,
                     upc, material_id, descripcion,
                     tot_line_weight, total_pieces, lot_info)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                h["shipping_ref"], ln["line_nbr"],
                ln["order_qty"], ln["shipped_qty"], ln["bill_unit"],
                ln["upc"], ln["material_id"], ln["descripcion"],
                ln["tot_line_weight"], ln["total_pieces"], ln["lot_info"]
            ))

        conn.commit()
        print(f"[PList→DB] {h['shipping_ref']} cargada: {len(parsed['lines'])} líneas.")
        return True

    except Exception as e:
        conn.rollback()
        if "UNIQUE" in str(e).upper():
            print(f"[PList→DB] {h['shipping_ref']} ya existe (duplicada).")
        else:
            print(f"[PList→DB] ERROR: {e}")
        return False


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "../input/Packing_List.pdf"
    result = parse_plist(path)
    print("\nCABECERA:")
    for k, v in result["header"].items():
        print(f"  {k}: {v}")
    print(f"\nDETALLE ({len(result['lines'])} líneas):")
    for ln in result["lines"]:
        print(" ", ln)
