# =============================================================================
# db_connector.py  —  Conector unificado SQLite (dev) / Access (prod)
#
# En desarrollo : SQLite local, sin dependencias de Windows
# En producción : access_connector.py → C:\EXTERIOR\PO_DataBase.accdb
# =============================================================================

import sqlite3
from config import DB_TYPE, DB_PATH


# ---------------------------------------------------------------------------
# Conexión SQLite (solo para desarrollo / pruebas)
# ---------------------------------------------------------------------------

def get_connection():
    """
    Retorna una conexión activa según el entorno configurado en config.py.
    En producción usa access_connector.AccessConnector.
    """
    if DB_TYPE == "sqlite":
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    else:
        # En producción, usar AccessConnector directamente en main.py
        raise RuntimeError(
            "En producción usar AccessConnector de access_connector.py, "
            "no get_connection()."
        )


# ---------------------------------------------------------------------------
# DDL SQLite (solo para desarrollo)
# ---------------------------------------------------------------------------

DDL_SQLITE = [
    """CREATE TABLE IF NOT EXISTS T_3M_PO_HEADER (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        po_number TEXT NOT NULL, order_date TEXT,
        sold_to_account TEXT, sold_to_name TEXT, sold_to_address TEXT,
        ship_to_account TEXT, ship_to_name TEXT, ship_to_address TEXT,
        delivery_method TEXT, requested_delivery TEXT, ultimate_country TEXT,
        payment_method TEXT, subtotal REAL,
        fecha_carga TEXT, archivo_origen TEXT, UNIQUE(po_number))""",

    """CREATE TABLE IF NOT EXISTS T_3M_PO_DETAIL (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        po_number TEXT NOT NULL, linea INTEGER,
        catalog_3m TEXT, stock_3m TEXT, upc TEXT, descripcion TEXT,
        cantidad REAL, unidad TEXT, precio_unit REAL, total_linea REAL,
        contrato TEXT)""",

    """CREATE TABLE IF NOT EXISTS T_3M_INVOICE_HEADER (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_nbr TEXT NOT NULL, invoice_6dig TEXT, po_number TEXT,
        invoice_date TEXT, order_date TEXT, shipment_date TEXT,
        payment_terms TEXT, payment_due_date TEXT, carrier TEXT,
        bill_of_lading TEXT, delivery_nbr TEXT,
        ship_to_account TEXT, ship_to_name TEXT, ship_to_address TEXT,
        bill_to_account TEXT, bill_to_name TEXT, bill_to_address TEXT,
        incoterms TEXT, ship_from TEXT, shipment_nbr TEXT, tracking_nbrs TEXT,
        invoice_value REAL, invoice_total REAL, currency TEXT,
        fecha_carga TEXT, archivo_origen TEXT, UNIQUE(invoice_nbr))""",

    """CREATE TABLE IF NOT EXISTS T_3M_INVOICE_DETAIL (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_nbr TEXT NOT NULL, cust_line_nbr TEXT, vendor_line TEXT,
        material_id TEXT, upc TEXT, catalog_id TEXT, descripcion TEXT,
        cantidad REAL, unidad TEXT, precio_unit REAL, importe REAL,
        contrato TEXT, batch_nbr TEXT)""",

    """CREATE TABLE IF NOT EXISTS T_3M_PLIST_HEADER (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        shipping_ref TEXT NOT NULL, po_number TEXT, invoice_nbr TEXT,
        ship_from_loc TEXT, wave_nbr TEXT, order_date TEXT, ship_date TEXT,
        ship_to_name TEXT, ship_to_address TEXT,
        charge_to_name TEXT, charge_to_address TEXT,
        total_pieces INTEGER, total_weight REAL,
        fecha_carga TEXT, archivo_origen TEXT, UNIQUE(shipping_ref))""",

    """CREATE TABLE IF NOT EXISTS T_3M_PLIST_DETAIL (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        shipping_ref TEXT NOT NULL, line_nbr TEXT,
        order_qty REAL, shipped_qty REAL, bill_unit TEXT,
        upc TEXT, material_id TEXT, descripcion TEXT,
        tot_line_weight REAL, total_pieces INTEGER, lot_info TEXT)""",

    """CREATE TABLE IF NOT EXISTS T_GECOM_FI (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo TEXT DEFAULT 'fi', comprobante TEXT NOT NULL,
        fecha TEXT, proveedor_cod TEXT, proveedor_nom TEXT,
        lista TEXT, fi_6dig TEXT, invoice_nbr TEXT,
        total_comprobante REAL, fecha_carga TEXT, archivo_origen TEXT,
        UNIQUE(comprobante))""",

    """CREATE TABLE IF NOT EXISTS T_GECOM_FI_DETAIL (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        comprobante TEXT NOT NULL, codigo_lilis TEXT, imputacion TEXT,
        descripcion TEXT, cantidad REAL, precio_unit REAL, total_linea REAL)""",

    """CREATE TABLE IF NOT EXISTS T_GECOM_RE (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo TEXT DEFAULT 're', comprobante TEXT NOT NULL,
        fecha TEXT, proveedor_cod TEXT, proveedor_nom TEXT,
        re_6dig TEXT, fi_comprobante TEXT,
        fecha_carga TEXT, archivo_origen TEXT, UNIQUE(comprobante))""",

    """CREATE TABLE IF NOT EXISTS T_GECOM_RE_DETAIL (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        comprobante TEXT NOT NULL, codigo_lilis TEXT,
        descripcion TEXT, cantidad REAL)""",
]


def create_tables(conn):
    """Crea tablas SQLite si no existen (solo en desarrollo)."""
    cur = conn.cursor()
    for ddl in DDL_SQLITE:
        cur.execute(ddl)
    conn.commit()
    print("[DB] Tablas SQLite verificadas/creadas.")


def init_database():
    conn = get_connection()
    create_tables(conn)
    conn.close()
    print(f"[DB] Base de datos inicializada: {DB_PATH}")


if __name__ == "__main__":
    init_database()
