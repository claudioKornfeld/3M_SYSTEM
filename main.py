#!/usr/bin/env python3
# =============================================================================
# main.py  —  Orquestador principal del 3M_SYSTEM
#
# Uso:
#   python main.py --init                     # Inicializa / verifica la BD
#   python main.py --firex firex.txt          # Carga FIREX.txt
#   python main.py --invoice Invoice.pdf      # Carga Invoice
#   python main.py --plist Packing_List.pdf   # Carga Packing List
#   python main.py --po PO.pdf                # Carga PO
#   python main.py --aduana Despacho.pdf        # Carga Despacho de Aduana
#   python main.py --all --dir ./input        # Carga todo lo que haya en carpeta
#   python main.py --report                   # Resumen de tablas
#   python main.py --link                     # Re-enlazar documentos
# =============================================================================

import argparse
import os
import sys

from config import DB_TYPE, DB_PATH
from parser_firex   import parse_firex
from parser_invoice import parse_invoice
from parser_plist   import parse_plist
from parser_po      import parse_po
from parser_aduana  import parse_aduana


# ---------------------------------------------------------------------------
# Obtener backend según entorno
# ---------------------------------------------------------------------------

def _get_backend():
    """
    Retorna un objeto 'backend' con métodos comunes para ambos entornos.
    En desarrollo: envuelve una conexión SQLite con funciones equivalentes.
    En producción: usa AccessConnector directamente.
    """
    if DB_TYPE == "sqlite":
        return _SQLiteBackend()
    else:
        from access_connector import AccessConnector
        ac = AccessConnector()
        ac.conectar()
        return _AccessBackend(ac)


# ---------------------------------------------------------------------------
# Backend SQLite (desarrollo)
# ---------------------------------------------------------------------------

class _SQLiteBackend:
    def __init__(self):
        import sqlite3
        from db_connector import create_tables
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row
        create_tables(self.conn)

    def close(self):
        self.conn.close()

    def load_firex(self, parsed, archivo):
        from parser_firex import load_firex_to_db
        load_firex_to_db(self.conn, parsed, archivo)

    def load_invoice(self, parsed):
        from parser_invoice import load_invoice_to_db
        load_invoice_to_db(self.conn, parsed)

    def load_plist(self, parsed):
        from parser_plist import load_plist_to_db
        load_plist_to_db(self.conn, parsed)

    def load_po(self, parsed):
        from parser_po import load_po_to_db
        load_po_to_db(self.conn, parsed)

    def load_aduana(self, parsed):
        from parser_aduana import load_aduana_to_db
        load_aduana_to_db(self.conn, parsed)

    def link_documents(self):
        cur = self.conn.cursor()
        n = 0

        # FI ↔ Invoice  (via invoice_6dig)
        cur.execute("""
            UPDATE T_GECOM_FI SET invoice_nbr = (
                SELECT invoice_nbr FROM T_3M_INVOICE_HEADER
                WHERE invoice_6dig = T_GECOM_FI.fi_6dig LIMIT 1
            ) WHERE invoice_nbr IS NULL
        """)
        n += cur.rowcount

        # PList ↔ Invoice  (delivery_nbr = shipping_ref)
        cur.execute("""
            UPDATE T_3M_PLIST_HEADER SET invoice_nbr = (
                SELECT invoice_nbr FROM T_3M_INVOICE_HEADER
                WHERE delivery_nbr = T_3M_PLIST_HEADER.shipping_ref LIMIT 1
            ) WHERE invoice_nbr IS NULL
        """)
        n += cur.rowcount

        # RE ↔ FI  (via re_6dig = fi_6dig)
        cur.execute("""
            UPDATE T_GECOM_RE SET fi_comprobante = (
                SELECT comprobante FROM T_GECOM_FI
                WHERE fi_6dig = T_GECOM_RE.re_6dig LIMIT 1
            ) WHERE fi_comprobante IS NULL
        """)
        n += cur.rowcount

        # Invoice ↔ PO  (recuperar po_number desde PList cuando el parser no lo capturó)
        cur.execute("""
            UPDATE T_3M_INVOICE_HEADER SET po_number = (
                SELECT po_number FROM T_3M_PLIST_HEADER
                WHERE shipping_ref = T_3M_INVOICE_HEADER.delivery_nbr
                  AND po_number IS NOT NULL LIMIT 1
            ) WHERE (po_number IS NULL OR po_number = '')
              AND delivery_nbr IS NOT NULL
        """)
        n += cur.rowcount

        # PList ↔ PO  (recuperar po_number desde Invoice cuando PList no lo tiene)
        cur.execute("""
            UPDATE T_3M_PLIST_HEADER SET po_number = (
                SELECT po_number FROM T_3M_INVOICE_HEADER
                WHERE delivery_nbr = T_3M_PLIST_HEADER.shipping_ref
                  AND po_number IS NOT NULL LIMIT 1
            ) WHERE (po_number IS NULL OR po_number = '')
              AND invoice_nbr IS NOT NULL
        """)
        n += cur.rowcount

        self.conn.commit()
        print(f"[LINKS] {n} relaciones actualizadas.")

    def report(self):
        cur = self.conn.cursor()
        tables = [
            "T_3M_PO_HEADER", "T_3M_PO_DETAIL",
            "T_3M_INVOICE_HEADER", "T_3M_INVOICE_DETAIL",
            "T_3M_PLIST_HEADER", "T_3M_PLIST_DETAIL",
            "T_GECOM_FI", "T_GECOM_FI_DETAIL",
            "T_GECOM_RE", "T_GECOM_RE_DETAIL",
            "T_ADUANA_DESPACHO",
        ]
        print("\n" + "=" * 60)
        print("  RESUMEN  —  3M_SYSTEM (SQLite dev)")
        print("=" * 60)
        for t in tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {t}")
                print(f"  {t:<35} {cur.fetchone()[0]:>6} registros")
            except Exception as e:
                print(f"  {t:<35} ERROR: {e}")
        print("=" * 60 + "\n")

    def init(self):
        print(f"[INIT] SQLite lista: {DB_PATH}")


# ---------------------------------------------------------------------------
# Backend Access (producción)
# ---------------------------------------------------------------------------

class _AccessBackend:
    def __init__(self, ac):
        self.ac = ac

    def close(self):
        self.ac.desconectar()

    def load_firex(self, parsed, archivo):
        fi_ok = fi_dup = re_ok = re_dup = 0
        for doc in parsed["fi"]:
            if self.ac.insertar_fi(doc["header"], doc["lines"]):
                fi_ok += 1
            else:
                fi_dup += 1
        for doc in parsed["re"]:
            if self.ac.insertar_re(doc["header"], doc["lines"]):
                re_ok += 1
            else:
                re_dup += 1
        print(f"[FIREX→Access] FI: {fi_ok} nuevas, {fi_dup} dup | RE: {re_ok} nuevas, {re_dup} dup")

    def load_invoice(self, parsed):
        h = parsed["header"]
        if self.ac.insertar_invoice_header(h):
            self.ac.insertar_invoice_detail(h["invoice_nbr"], parsed["lines"])
            print(f"[Invoice→Access] {h['invoice_nbr']} cargada: {len(parsed['lines'])} líneas.")

    def load_plist(self, parsed):
        h = parsed["header"]
        if self.ac.insertar_plist_header(h):
            self.ac.insertar_plist_detail(h["shipping_ref"], parsed["lines"])
            print(f"[PList→Access] {h['shipping_ref']} cargada: {len(parsed['lines'])} líneas.")

    def load_po(self, parsed):
        h = parsed["header"]
        if self.ac.insertar_po_header(h):
            self.ac.insertar_po_detail(h["po_number"], parsed["lines"])
            print(f"[PO→Access] '{h['po_number']}' cargada: {len(parsed['lines'])} líneas.")

    def load_aduana(self, parsed):
        if self.ac.insertar_aduana(parsed):
            print(f"[Aduana→Access] {parsed['nr_despacho']} cargada.")

    def link_documents(self):
        self.ac.enlazar_documentos()

    def report(self):
        self.ac.resumen_tablas()

    def init(self):
        resultado = self.ac.inicializar_tablas_3m()
        print(f"[INIT] Tablas creadas:    {resultado['creadas']    or '—'}")
        print(f"[INIT] Tablas existentes: {resultado['existentes'] or '—'}")


# ---------------------------------------------------------------------------
# Procesamiento de carpeta
# ---------------------------------------------------------------------------

def _process_dir(backend, directory):
    print(f"\n[ALL] Procesando directorio: {directory}")
    for fname in sorted(os.listdir(directory)):
        fpath = os.path.join(directory, fname)
        fl    = fname.lower()
        if fl.endswith(".txt") and "firex" in fl:
            data = parse_firex(fpath)
            backend.load_firex(data, fname)
        elif fl.endswith(".pdf"):
            if "invoice" in fl:
                data = parse_invoice(fpath)
                backend.load_invoice(data)
            elif "packing" in fl or "plist" in fl:
                data = parse_plist(fpath)
                backend.load_plist(data)
            elif "po" in fl or "order" in fl:
                data = parse_po(fpath)
                backend.load_po(data)
            elif "aduana" in fl or "ic04" in fl or "despacho" in fl:
                data = parse_aduana(fpath)
                backend.load_aduana(data)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="3M_SYSTEM — Carga de documentos 3M/Solventum a base de datos"
    )
    parser.add_argument("--init",    action="store_true", help="Inicializar BD")
    parser.add_argument("--firex",   metavar="FILE",      help="Cargar FIREX.txt")
    parser.add_argument("--invoice", metavar="FILE",      help="Cargar Invoice PDF")
    parser.add_argument("--plist",   metavar="FILE",      help="Cargar Packing List PDF")
    parser.add_argument("--po",      metavar="FILE",      help="Cargar PO PDF")
    parser.add_argument("--aduana",  metavar="FILE",      help="Cargar Despacho de Aduana PDF")
    parser.add_argument("--all",     action="store_true", help="Cargar todo en --dir")
    parser.add_argument("--dir",     metavar="DIR",       default="./input")
    parser.add_argument("--report",  action="store_true", help="Mostrar resumen de tablas")
    parser.add_argument("--link",    action="store_true", help="Re-enlazar documentos")
    args = parser.parse_args()

    backend = _get_backend()

    try:
        if args.init:
            backend.init()

        if args.firex:
            data = parse_firex(args.firex)
            backend.load_firex(data, os.path.basename(args.firex))

        if args.invoice:
            data = parse_invoice(args.invoice)
            backend.load_invoice(data)

        if args.plist:
            data = parse_plist(args.plist)
            backend.load_plist(data)

        if args.po:
            data = parse_po(args.po)
            backend.load_po(data)

        if args.aduana:
            data = parse_aduana(args.aduana)
            backend.load_aduana(data)

        if args.all:
            _process_dir(backend, args.dir)

        # Enlazar siempre después de una carga
        if any([args.firex, args.invoice, args.plist, args.po, args.aduana, args.all]):
            backend.link_documents()

        if args.link:
            backend.link_documents()

        if args.report or not any(vars(args).values()):
            backend.report()

    finally:
        backend.close()


if __name__ == "__main__":
    main()
