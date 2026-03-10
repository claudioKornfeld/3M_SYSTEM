# =============================================================================
# parser_invoice.py  —  Parser de Invoice PDF  (3M Healthcare LATAM/APAC)
# =============================================================================
import re, os, json
from datetime import datetime
import pdfplumber

def _clean(s): return (s or "").strip()
def _num(s):
    if not s: return 0.0
    return float(re.sub(r'[^\d.]', '', str(s)))

def _extract_text(filepath):
    pages = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    return "\n".join(pages)

def parse_invoice(filepath):
    text = _extract_text(filepath)
    lines_raw = text.splitlines()

    header = {
        "invoice_nbr": None, "invoice_6dig": None, "po_number": None,
        "invoice_date": None, "order_date": None, "shipment_date": None,
        "payment_terms": None, "payment_due_date": None, "carrier": None,
        "bill_of_lading": None, "delivery_nbr": None,
        "ship_to_account": None, "ship_to_name": None, "ship_to_address": None,
        "bill_to_account": None, "bill_to_name": None, "bill_to_address": None,
        "incoterms": None, "ship_from": None, "shipment_nbr": None,
        "tracking_nbrs": None, "invoice_value": 0.0, "invoice_total": 0.0,
        "currency": "USD",
        "fecha_carga": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "archivo_origen": os.path.basename(filepath),
    }

    def _find(pattern, default=None):
        m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        return _clean(m.group(1)) if m else default

    # Línea de cabecera principal
    m = re.search(
        r'(\d{10})\s+(\d{2}/\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})\s+(NET \d+ DAYS)\s+'
        r'Received By\s+(\d{2}/\d{2}/\d{4})', text)
    if m:
        header["invoice_nbr"] = m.group(1)
        header["invoice_date"] = m.group(2)
        header["order_date"] = m.group(3)
        header["payment_terms"] = m.group(4)
        header["payment_due_date"] = m.group(5)

    # Bill of lading / Delivery / Carrier / PO
    m = re.search(r'(\d{10})\s+(\d{10})\s+(\d{2}/\d{2}/\d{4})\s+(.+?)\s{2,}(.+?)$', text, re.MULTILINE)
    if m:
        header["bill_of_lading"] = m.group(1)
        header["delivery_nbr"] = m.group(2)
        header["shipment_date"] = m.group(3)
        header["carrier"] = _clean(m.group(4))
        header["po_number"] = _clean(m.group(5))

    # Accounts
    m = re.search(r'Ship to:\s+Account Nbr\s+(\d+)\s+Bill to:\s+Account Nbr\s+(\d+)', text)
    if m:
        header["ship_to_account"] = m.group(1)
        header["bill_to_account"] = m.group(2)

    header["ship_to_name"] = "GAVA IFC USA INC / LILIS SA" if "GAVA IFC" in text else None
    header["bill_to_name"] = "LILIS SA"
    header["incoterms"] = _find(r'Incoterms:\s*(.+?)(?:\s{2,}|Shipment|$)')
    header["ship_from"] = _find(r'Ship From:\s*(.+?)(?:\s{2,}|$)')
    header["shipment_nbr"] = _find(r'Shipment Nbr:\s*(\d+)')
    header["tracking_nbrs"] = _find(r'Pro/Parcel Tracking Nbr:\s*(.+?)(?:\n\n|\Z)', "")

    iv = _find(r'Invoice Value\s+([\d,\.]+)')
    it = _find(r'Invoice Total\s+([\d,\.]+)')
    header["invoice_value"] = _num(iv) if iv else 0.0
    header["invoice_total"] = _num(it) if it else 0.0
    if header["invoice_nbr"]:
        header["invoice_6dig"] = header["invoice_nbr"][-6:]

    # --- Líneas de detalle ---
    # "100 7100212849 3M™ Littmann® ... desc  3  63.0360  189.11"
    line_start = re.compile(
        r'^(\d{3,4})\s+(71\d{8})\s+(3M.+?)\s+(\d+)\s+([\d\.]+)\s+([\d\.]+)\s*$')

    detail_lines = []
    i = 0
    while i < len(lines_raw):
        line = lines_raw[i].strip()
        ms = line_start.match(line)
        if ms:
            cust_line = ms.group(1)
            material_id = ms.group(2)
            desc1 = ms.group(3).strip()
            qty = float(ms.group(4))
            precio = float(ms.group(5))
            importe = float(ms.group(6))

            upc = catalog_id = vendor_line = uom = contrato = batch = ""
            desc_extra = []
            j = i + 1

            while j < len(lines_raw):
                nxt = lines_raw[j].strip()
                if not nxt or "3M Healthcare" in nxt or nxt.startswith("Page"):
                    j += 1
                    continue
                if line_start.match(nxt):
                    break

                # "10 00707387789565 texto EA"
                mc = re.match(r'^(\d{1,3})\s+(00\d{12})\s+(.*?)\s+(EA|KIT|CS)\s*$', nxt)
                if mc:
                    vendor_line = mc.group(1)
                    upc = mc.group(2)
                    et = mc.group(3).strip()
                    uom = mc.group(4)
                    if et: desc_extra.append(et)
                    j += 1; continue

                if re.match(r'^[\w]{3,7}$', nxt) and not nxt.startswith("71"):
                    if not catalog_id:
                        catalog_id = nxt
                    j += 1; continue

                if re.match(r'^71\d{8}\s', nxt) or re.match(r'^71\d{8}$', nxt):
                    j += 1; continue

                if "Contract Nbr" in nxt:
                    contrato = re.sub(r'Contract Nbr[:\s]*', '', nxt).strip()
                    j += 1; continue
                if "Batch Nbr" in nxt:
                    batch = re.sub(r'Batch Nbr[:\s]*', '', nxt).strip()
                    j += 1; continue

                desc_extra.append(nxt)
                j += 1

            descripcion = desc1
            if desc_extra:
                descripcion += " " + " ".join(desc_extra)

            detail_lines.append({
                "cust_line_nbr": cust_line, "vendor_line": vendor_line,
                "material_id": material_id, "upc": upc,
                "catalog_id": catalog_id, "descripcion": descripcion.strip(),
                "cantidad": qty, "unidad": uom or "EA",
                "precio_unit": precio, "importe": importe,
                "contrato": contrato, "batch_nbr": batch,
            })
            i = j
        else:
            i += 1

    print(f"[Invoice] {header['invoice_nbr']} | PO: {header['po_number']} | "
          f"Total: {header['invoice_total']} {header['currency']} | Líneas: {len(detail_lines)}")
    return {"header": header, "lines": detail_lines}


def load_invoice_to_db(conn, parsed):
    cur = conn.cursor()
    h = parsed["header"]
    if not h.get("invoice_nbr"):
        print("[Invoice→DB] ERROR: invoice_nbr vacío, saltando.")
        return False
    try:
        cur.execute("""
            INSERT INTO T_3M_INVOICE_HEADER
                (invoice_nbr, invoice_6dig, po_number, invoice_date, order_date,
                 shipment_date, payment_terms, payment_due_date, carrier,
                 bill_of_lading, delivery_nbr, ship_to_account, ship_to_name,
                 ship_to_address, bill_to_account, bill_to_name, bill_to_address,
                 incoterms, ship_from, shipment_nbr, tracking_nbrs,
                 invoice_value, invoice_total, currency, fecha_carga, archivo_origen)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (h["invoice_nbr"], h["invoice_6dig"], h["po_number"],
              h["invoice_date"], h["order_date"], h["shipment_date"],
              h["payment_terms"], h["payment_due_date"], h["carrier"],
              h["bill_of_lading"], h["delivery_nbr"],
              h["ship_to_account"], h["ship_to_name"], h["ship_to_address"],
              h["bill_to_account"], h["bill_to_name"], h["bill_to_address"],
              h["incoterms"], h["ship_from"], h["shipment_nbr"], h["tracking_nbrs"],
              h["invoice_value"], h["invoice_total"], h["currency"],
              h["fecha_carga"], h["archivo_origen"]))

        for ln in parsed["lines"]:
            cur.execute("""
                INSERT INTO T_3M_INVOICE_DETAIL
                    (invoice_nbr, cust_line_nbr, vendor_line, material_id, upc,
                     catalog_id, descripcion, cantidad, unidad, precio_unit,
                     importe, contrato, batch_nbr)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (h["invoice_nbr"], ln["cust_line_nbr"], ln["vendor_line"],
                  ln["material_id"], ln["upc"], ln["catalog_id"],
                  ln["descripcion"], ln["cantidad"], ln["unidad"],
                  ln["precio_unit"], ln["importe"], ln["contrato"], ln["batch_nbr"]))

        conn.commit()
        print(f"[Invoice→DB] {h['invoice_nbr']} cargada: {len(parsed['lines'])} líneas.")
        return True
    except Exception as e:
        conn.rollback()
        if "UNIQUE" in str(e).upper():
            print(f"[Invoice→DB] {h['invoice_nbr']} ya existe (duplicada).")
        else:
            print(f"[Invoice→DB] ERROR: {e}")
        return False

if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "input/Invoice.pdf"
    result = parse_invoice(path)
    print("\nCABECERA:")
    for k, v in result["header"].items(): print(f"  {k}: {v}")
    print(f"\nDETALLE ({len(result['lines'])} líneas):")
    for ln in result["lines"]: print(" ", ln)
