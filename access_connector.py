#!/usr/bin/env python3
"""
=============================================================================
access_connector.py  —  Conector Access para 3M_SYSTEM
=============================================================================
Adaptado del conector original del PO_System.
Diferencias respecto al original:
  - Sin dependencia de GestorRutas ni logger externo
  - Logger interno simple (consola + archivo de log)
  - Ruta de BD tomada directamente de config.py
  - Agrega las tablas del 3M_SYSTEM a las existentes del PO_System
  - Función inicializar_tablas_3m() para crear solo las tablas nuevas,
    sin tocar ninguna tabla existente del PO_System

BD:
  Desarrollo : C:\\EXTERIOR\\PO_DataBase.accdb
  Producción : C:\\EXTERIOR\\PO_DataBase.accdb   ← misma ruta, distinta máquina
=============================================================================
"""

import logging
import pandas as pd
import pyodbc
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Ruta de la base de datos
# ---------------------------------------------------------------------------
# DESARROLLO y PRODUCCIÓN apuntan al mismo nombre de archivo.
# En producción el archivo estará en X:\EXTERIOR\ (unidad de red).
# Cambiar aquí cuando se pase a producción:

DB_PATH_DEV  = Path(r"C:\EXTERIOR\PO_DataBase.accdb")
DB_PATH_PROD = Path(r"X:\EXTERIOR\PO_DataBase.accdb")

# Switch: cambiar a "production" para producción
_ENVIRONMENT = "development"

DB_PATH = DB_PATH_DEV if _ENVIRONMENT == "development" else DB_PATH_PROD


# ---------------------------------------------------------------------------
# Logger interno simple
# ---------------------------------------------------------------------------

def _build_logger(name: str = "3M_ACCESS") -> logging.Logger:
    """Logger que escribe en consola y en 3M_SYSTEM.log"""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # ya inicializado

    logger.setLevel(logging.INFO)

    fmt = logging.Formatter("%(asctime)s  %(levelname)-7s  %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")

    # Consola
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # Archivo (en el mismo directorio que este script)
    try:
        log_path = Path(__file__).parent / "3M_SYSTEM.log"
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except Exception:
        pass  # Si no puede escribir el log, continúa sin él

    return logger


# ---------------------------------------------------------------------------
# Nombres de tablas — PO_System (existentes, NO tocar)
# ---------------------------------------------------------------------------
TABLAS_PO = {
    'maestro':         'tbl_ProductoProveedor',
    'purchase_orders': 'tbl_PurchaseOrders',
    'po_detalle':      'tbl_PO_Detalle',
    'proveedores':     'tbl_Proveedores',
    'auditoria':       'tbl_Auditoria',
}

# ---------------------------------------------------------------------------
# Nombres de tablas — 3M_SYSTEM (nuevas)
# ---------------------------------------------------------------------------
TABLAS_3M = {
    'po_hdr':      'T_3M_PO_HEADER',
    'po_det':      'T_3M_PO_DETAIL',
    'inv_hdr':     'T_3M_INVOICE_HEADER',
    'inv_det':     'T_3M_INVOICE_DETAIL',
    'plist_hdr':   'T_3M_PLIST_HEADER',
    'plist_det':   'T_3M_PLIST_DETAIL',
    'fi_hdr':      'T_GECOM_FI',
    'fi_det':      'T_GECOM_FI_DETAIL',
    're_hdr':      'T_GECOM_RE',
    're_det':      'T_GECOM_RE_DETAIL',
}

# ---------------------------------------------------------------------------
# DDL de las tablas 3M (sintaxis Access / Jet SQL)
# COUNTER = autonumérico  |  MEMO = texto largo  |  TEXT(n) = texto corto
# ---------------------------------------------------------------------------
DDL_3M = [
    (
        'T_3M_PO_HEADER',
        """
        CREATE TABLE T_3M_PO_HEADER (
            [id]                COUNTER     PRIMARY KEY,
            [po_number]         TEXT(50)    ,
            [order_date]        TEXT(50),
            [sold_to_account]   TEXT(20),
            [sold_to_name]      TEXT(200),
            [sold_to_address]   MEMO,
            [ship_to_account]   TEXT(20),
            [ship_to_name]      TEXT(200),
            [ship_to_address]   MEMO,
            [delivery_method]   TEXT(100),
            [requested_delivery] TEXT(20),
            [ultimate_country]  TEXT(100),
            [payment_method]    TEXT(100),
            [subtotal]          DOUBLE,
            [fecha_carga]       TEXT(30),
            [archivo_origen]    TEXT(200)
        )
        """
    ),
    (
        'T_3M_PO_DETAIL',
        """
        CREATE TABLE T_3M_PO_DETAIL (
            [id]            COUNTER   PRIMARY KEY,
            [po_number]     TEXT(50)  ,
            [linea]         INTEGER,
            [catalog_3m]    TEXT(20),
            [stock_3m]      TEXT(20),
            [upc]           TEXT(20),
            [descripcion]   MEMO,
            [cantidad]      DOUBLE,
            [unidad]        TEXT(10),
            [precio_unit]   DOUBLE,
            [total_linea]   DOUBLE,
            [contrato]      TEXT(50)
        )
        """
    ),
    (
        'T_3M_INVOICE_HEADER',
        """
        CREATE TABLE T_3M_INVOICE_HEADER (
            [id]                COUNTER     PRIMARY KEY,
            [invoice_nbr]       TEXT(20)    ,
            [invoice_6dig]      TEXT(10),
            [po_number]         TEXT(50),
            [invoice_date]      TEXT(20),
            [order_date]        TEXT(20),
            [shipment_date]     TEXT(20),
            [payment_terms]     TEXT(50),
            [payment_due_date]  TEXT(20),
            [carrier]           TEXT(100),
            [bill_of_lading]    TEXT(20),
            [delivery_nbr]      TEXT(20),
            [ship_to_account]   TEXT(20),
            [ship_to_name]      TEXT(200),
            [ship_to_address]   MEMO,
            [bill_to_account]   TEXT(20),
            [bill_to_name]      TEXT(200),
            [bill_to_address]   MEMO,
            [incoterms]         TEXT(100),
            [ship_from]         TEXT(200),
            [shipment_nbr]      TEXT(20),
            [tracking_nbrs]     MEMO,
            [invoice_value]     DOUBLE,
            [invoice_total]     DOUBLE,
            [currency]          TEXT(10),
            [fecha_carga]       TEXT(30),
            [archivo_origen]    TEXT(200)
        )
        """
    ),
    (
        'T_3M_INVOICE_DETAIL',
        """
        CREATE TABLE T_3M_INVOICE_DETAIL (
            [id]            COUNTER   PRIMARY KEY,
            [invoice_nbr]   TEXT(20)  ,
            [cust_line_nbr] TEXT(10),
            [vendor_line]   TEXT(10),
            [material_id]   TEXT(20),
            [upc]           TEXT(20),
            [catalog_id]    TEXT(20),
            [descripcion]   MEMO,
            [cantidad]      DOUBLE,
            [unidad]        TEXT(10),
            [precio_unit]   DOUBLE,
            [importe]       DOUBLE,
            [contrato]      TEXT(50),
            [batch_nbr]     TEXT(100)
        )
        """
    ),
    (
        'T_3M_PLIST_HEADER',
        """
        CREATE TABLE T_3M_PLIST_HEADER (
            [id]                COUNTER     PRIMARY KEY,
            [shipping_ref]      TEXT(20)    ,
            [po_number]         TEXT(50),
            [invoice_nbr]       TEXT(20),
            [ship_from_loc]     TEXT(20),
            [wave_nbr]          TEXT(20),
            [order_date]        TEXT(20),
            [ship_date]         TEXT(20),
            [ship_to_name]      TEXT(200),
            [ship_to_address]   MEMO,
            [charge_to_name]    TEXT(200),
            [charge_to_address] MEMO,
            [total_pieces]      INTEGER,
            [total_weight]      DOUBLE,
            [fecha_carga]       TEXT(30),
            [archivo_origen]    TEXT(200)
        )
        """
    ),
    (
        'T_3M_PLIST_DETAIL',
        """
        CREATE TABLE T_3M_PLIST_DETAIL (
            [id]              COUNTER   PRIMARY KEY,
            [shipping_ref]    TEXT(20)  ,
            [line_nbr]        TEXT(10),
            [order_qty]       DOUBLE,
            [shipped_qty]     DOUBLE,
            [bill_unit]       TEXT(10),
            [upc]             TEXT(20),
            [material_id]     TEXT(20),
            [descripcion]     MEMO,
            [tot_line_weight] DOUBLE,
            [total_pieces]    INTEGER,
            [lot_info]        MEMO
        )
        """
    ),
    (
        'T_GECOM_FI',
        """
        CREATE TABLE T_GECOM_FI (
            [id]                  COUNTER     PRIMARY KEY,
            [tipo]                TEXT(5),
            [comprobante]         TEXT(20)    ,
            [fecha]               TEXT(10),
            [proveedor_cod]       TEXT(10),
            [proveedor_nom]       TEXT(100),
            [lista]               TEXT(20),
            [fi_6dig]             TEXT(10),
            [invoice_nbr]         TEXT(20),
            [total_comprobante]   DOUBLE,
            [fecha_carga]         TEXT(30),
            [archivo_origen]      TEXT(200)
        )
        """
    ),
    (
        'T_GECOM_FI_DETAIL',
        """
        CREATE TABLE T_GECOM_FI_DETAIL (
            [id]            COUNTER   PRIMARY KEY,
            [comprobante]   TEXT(20)  ,
            [codigo_lilis]  TEXT(10),
            [imputacion]    TEXT(10),
            [descripcion]   TEXT(200),
            [cantidad]      DOUBLE,
            [precio_unit]   DOUBLE,
            [total_linea]   DOUBLE
        )
        """
    ),
    (
        'T_GECOM_RE',
        """
        CREATE TABLE T_GECOM_RE (
            [id]              COUNTER     PRIMARY KEY,
            [tipo]            TEXT(5),
            [comprobante]     TEXT(20)    ,
            [fecha]           TEXT(10),
            [proveedor_cod]   TEXT(10),
            [proveedor_nom]   TEXT(100),
            [re_6dig]         TEXT(10),
            [fi_comprobante]  TEXT(20),
            [fecha_carga]     TEXT(30),
            [archivo_origen]  TEXT(200)
        )
        """
    ),
    (
        'T_GECOM_RE_DETAIL',
        """
        CREATE TABLE T_GECOM_RE_DETAIL (
            [id]            COUNTER   PRIMARY KEY,
            [comprobante]   TEXT(20)  ,
            [codigo_lilis]  TEXT(10),
            [descripcion]   TEXT(200),
            [cantidad]      DOUBLE
        )
        """
    ),
]


# ============================================================================
# HELPERS PRIVADOS
# ============================================================================

def _safe_float(valor):
    if valor is None:
        return None
    try:
        import math
        f = float(valor)
        return None if math.isnan(f) else f
    except (ValueError, TypeError):
        return None


def _safe_int(valor):
    if valor is None:
        return None
    try:
        return int(float(valor))
    except (ValueError, TypeError):
        return None


# ============================================================================
# CLASE PRINCIPAL
# ============================================================================

class AccessConnector:
    """
    Conector bidireccional para PO_DataBase.accdb — 3M_SYSTEM.

    Uso básico:
        db = AccessConnector()
        db.conectar()
        db.inicializar_tablas_3m()      # solo primera vez
        ...
        db.desconectar()

    O como context manager:
        with AccessConnector() as db:
            db.inicializar_tablas_3m()
    """

    def __init__(self, logger=None):
        self.logger = logger or _build_logger()
        self.conn   = None
        self._ruta_bd = DB_PATH

    # ------------------------------------------------------------------ #
    # CONEXIÓN
    # ------------------------------------------------------------------ #

    def conectar(self):
        """
        Abre la conexión con la BD Access.

        Returns:
            bool: True si la conexión fue exitosa

        Raises:
            FileNotFoundError: si no existe el .accdb
            pyodbc.Error:      si falla el driver ODBC
        """
        if not self._ruta_bd.exists():
            raise FileNotFoundError(
                f"No se encuentra la base de datos: {self._ruta_bd}\n"
                f"Verifique que el archivo exista y que la ruta sea correcta.\n"
                f"Ruta configurada: {self._ruta_bd}"
            )

        self.logger.info(f"Conectando a: {self._ruta_bd.name} ...")

        try:
            conn_str = (
                r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
                f"DBQ={self._ruta_bd};"
            )
            self.conn = pyodbc.connect(conn_str)
            self.logger.info(f"  ✔ Conexión establecida: {self._ruta_bd.name}")
            return True

        except pyodbc.Error as e:
            self.logger.error(f"  ✘ Error al conectar: {e}")
            self.logger.error(
                "  ℹ Verifique que estén instalados los drivers de Access "
                "(Microsoft Access Database Engine 64-bit)"
            )
            raise

    def desconectar(self):
        if self.conn:
            self.conn.close()
            self.conn = None
            self.logger.info("  ✔ Conexión cerrada")

    def _verificar_conexion(self):
        if self.conn is None:
            raise ConnectionError("No hay conexión activa. Llamar a conectar() primero.")

    # ------------------------------------------------------------------ #
    # INICIALIZACIÓN DE TABLAS 3M
    # ------------------------------------------------------------------ #

    def inicializar_tablas_3m(self):
        """
        Crea las tablas del 3M_SYSTEM en la BD Access si no existen aún.
        NO toca ninguna tabla existente del PO_System.

        Returns:
            dict: {'creadas': [...], 'existentes': [...]}
        """
        self._verificar_conexion()

        cursor = self.conn.cursor()

        # Obtener tablas existentes
        tablas_existentes = {
            row.table_name
            for row in cursor.tables(tableType='TABLE')
        }

        creadas    = []
        existentes = []

        for nombre, sql_create in DDL_3M:
            if nombre in tablas_existentes:
                cursor.execute(f"SELECT COUNT(*) FROM [{nombre}]")
                n = cursor.fetchone()[0]
                self.logger.info(f"  ℹ  {nombre}: ya existe ({n} registros)")
                existentes.append(nombre)
            else:
                try:
                    cursor.execute(sql_create)
                    self.conn.commit()
                    self.logger.info(f"  ✔ {nombre}: creada")
                    creadas.append(nombre)
                except Exception as e:
                    self.logger.error(f"  ✘ Error al crear {nombre}: {e}")
                    raise

        cursor.close()

        self.logger.info("")
        self.logger.info(f"  Tablas creadas:    {creadas    or '—'}")
        self.logger.info(f"  Tablas existentes: {existentes or '—'}")

        return {'creadas': creadas, 'existentes': existentes}

    # ------------------------------------------------------------------ #
    # OPERACIONES GENÉRICAS
    # ------------------------------------------------------------------ #

    def leer_tabla(self, nombre_tabla, where=None):
        """Lee una tabla (o filtro WHERE) y devuelve DataFrame."""
        self._verificar_conexion()
        sql = f"SELECT * FROM [{nombre_tabla}]"
        if where:
            sql += f" WHERE {where}"
        try:
            df = pd.read_sql(sql, self.conn)
            self.logger.info(f"  ✔ {nombre_tabla}: {len(df)} registros leídos")
            return df
        except Exception as e:
            self.logger.error(f"  ✘ Error al leer {nombre_tabla}: {e}")
            raise

    def ejecutar_query(self, sql, params=None):
        """Ejecuta SELECT y devuelve DataFrame."""
        self._verificar_conexion()
        try:
            df = pd.read_sql(sql, self.conn, params=params) if params \
                 else pd.read_sql(sql, self.conn)
            return df
        except Exception as e:
            self.logger.error(f"  ✘ Error en query: {e}\n  SQL: {sql}")
            raise

    def ejecutar_comando(self, sql, params=None):
        """Ejecuta INSERT/UPDATE/DELETE. Retorna filas afectadas."""
        self._verificar_conexion()
        cursor = self.conn.cursor()
        try:
            if params and isinstance(params[0], (list, tuple)):
                cursor.executemany(sql, params)
            elif params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            self.conn.commit()
            return cursor.rowcount
        except Exception as e:
            self.conn.rollback()
            self.logger.error(f"  ✘ Error ejecutando comando: {e}\n  SQL: {sql}")
            raise
        finally:
            cursor.close()

    # ------------------------------------------------------------------ #
    # INSERT CON CONTROL DE DUPLICADOS
    # ------------------------------------------------------------------ #

    def _existe(self, tabla: str, campo_clave: str, valor: str) -> bool:
        """Retorna True si el valor ya existe en la tabla."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                f"SELECT COUNT(*) FROM [{tabla}] WHERE [{campo_clave}] = ?",
                (valor,)
            )
            n = cursor.fetchone()[0]
            cursor.close()
            return n > 0
        except Exception:
            return False

    # ------------------------------------------------------------------ #
    # CARGA DE DOCUMENTOS 3M
    # ------------------------------------------------------------------ #

    def insertar_po_header(self, h: dict) -> bool:
        if self._existe('T_3M_PO_HEADER', 'po_number', h['po_number']):
            self.logger.info(f"  ℹ PO '{h['po_number']}' ya existe, saltando.")
            return False
        self.ejecutar_comando("""
            INSERT INTO [T_3M_PO_HEADER]
                (po_number, [order_date],
                 sold_to_account, sold_to_name, sold_to_address,
                 ship_to_account, ship_to_name, ship_to_address,
                 delivery_method, requested_delivery, ultimate_country,
                 payment_method, subtotal, fecha_carga, archivo_origen)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (h['po_number'], h['order_date'],
              h['sold_to_account'], h['sold_to_name'], h['sold_to_address'],
              h['ship_to_account'], h['ship_to_name'], h['ship_to_address'],
              h['delivery_method'], h['requested_delivery'], h['ultimate_country'],
              h['payment_method'], _safe_float(h['subtotal']),
              h['fecha_carga'], h['archivo_origen']))
        return True

    def insertar_po_detail(self, po_number: str, lines: list):
        for ln in lines:
            self.ejecutar_comando("""
                INSERT INTO [T_3M_PO_DETAIL]
                    (po_number, linea, catalog_3m, stock_3m, upc,
                     descripcion, cantidad, unidad, precio_unit, total_linea, contrato)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (po_number, _safe_int(ln['linea']),
                  ln['catalog_3m'], ln['stock_3m'], ln['upc'],
                  ln['descripcion'], _safe_float(ln['cantidad']),
                  ln['unidad'], _safe_float(ln['precio_unit']),
                  _safe_float(ln['total_linea']), ln['contrato']))

    def insertar_invoice_header(self, h: dict) -> bool:
        if not h.get('invoice_nbr'):
            self.logger.warning("  ⚠ Invoice sin invoice_nbr, saltando.")
            return False
        if self._existe('T_3M_INVOICE_HEADER', 'invoice_nbr', h['invoice_nbr']):
            self.logger.info(f"  ℹ Invoice {h['invoice_nbr']} ya existe, saltando.")
            return False
        self.ejecutar_comando("""
            INSERT INTO [T_3M_INVOICE_HEADER]
                (invoice_nbr, invoice_6dig, po_number, invoice_date, [order_date],
                 shipment_date, payment_terms, payment_due_date, [carrier],
                 bill_of_lading, delivery_nbr,
                 ship_to_account, ship_to_name, ship_to_address,
                 bill_to_account, bill_to_name, bill_to_address,
                 [incoterms], ship_from, shipment_nbr, tracking_nbrs,
                 invoice_value, invoice_total, [currency], fecha_carga, archivo_origen)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (h['invoice_nbr'], h['invoice_6dig'], h['po_number'],
              h['invoice_date'], h['order_date'], h['shipment_date'],
              h['payment_terms'], h['payment_due_date'], h['carrier'],
              h['bill_of_lading'], h['delivery_nbr'],
              h['ship_to_account'], h['ship_to_name'], h['ship_to_address'],
              h['bill_to_account'], h['bill_to_name'], h['bill_to_address'],
              h['incoterms'], h['ship_from'], h['shipment_nbr'], h['tracking_nbrs'],
              _safe_float(h['invoice_value']), _safe_float(h['invoice_total']),
              h['currency'], h['fecha_carga'], h['archivo_origen']))
        return True

    def insertar_invoice_detail(self, invoice_nbr: str, lines: list):
        for ln in lines:
            self.ejecutar_comando("""
                INSERT INTO [T_3M_INVOICE_DETAIL]
                    (invoice_nbr, cust_line_nbr, vendor_line, material_id, upc,
                     catalog_id, descripcion, cantidad, unidad,
                     precio_unit, [importe], contrato, batch_nbr)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (invoice_nbr, ln['cust_line_nbr'], ln['vendor_line'],
                  ln['material_id'], ln['upc'], ln['catalog_id'],
                  ln['descripcion'], _safe_float(ln['cantidad']), ln['unidad'],
                  _safe_float(ln['precio_unit']), _safe_float(ln['importe']),
                  ln['contrato'], ln['batch_nbr']))

    def insertar_plist_header(self, h: dict) -> bool:
        if self._existe('T_3M_PLIST_HEADER', 'shipping_ref', h['shipping_ref']):
            self.logger.info(f"  ℹ PList {h['shipping_ref']} ya existe, saltando.")
            return False
        self.ejecutar_comando("""
            INSERT INTO [T_3M_PLIST_HEADER]
                (shipping_ref, po_number, invoice_nbr, ship_from_loc, wave_nbr,
                 [order_date], [ship_date], ship_to_name, ship_to_address,
                 charge_to_name, charge_to_address,
                 total_pieces, total_weight, fecha_carga, archivo_origen)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (h['shipping_ref'], h['po_number'], h['invoice_nbr'],
              h['ship_from_loc'], h['wave_nbr'],
              h['order_date'], h['ship_date'],
              h['ship_to_name'], h['ship_to_address'],
              h['charge_to_name'], h['charge_to_address'],
              _safe_int(h['total_pieces']), _safe_float(h['total_weight']),
              h['fecha_carga'], h['archivo_origen']))
        return True

    def insertar_plist_detail(self, shipping_ref: str, lines: list):
        for ln in lines:
            self.ejecutar_comando("""
                INSERT INTO [T_3M_PLIST_DETAIL]
                    (shipping_ref, [line_nbr], order_qty, shipped_qty, [bill_unit],
                     upc, material_id, descripcion,
                     tot_line_weight, total_pieces, lot_info)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (shipping_ref, ln['line_nbr'],
                  _safe_float(ln['order_qty']), _safe_float(ln['shipped_qty']),
                  ln['bill_unit'], ln['upc'], ln['material_id'],
                  ln['descripcion'], _safe_float(ln['tot_line_weight']),
                  _safe_int(ln['total_pieces']), ln['lot_info']))

    def insertar_fi(self, h: dict, lines: list) -> bool:
        if self._existe('T_GECOM_FI', 'comprobante', h['comprobante']):
            return False  # duplicado silencioso, es normal en FIREX
        self.ejecutar_comando("""
            INSERT INTO [T_GECOM_FI]
                (tipo, comprobante, fecha, proveedor_cod, proveedor_nom,
                 lista, fi_6dig, invoice_nbr, total_comprobante,
                 fecha_carga, archivo_origen)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (h['tipo'], h['comprobante'], h['fecha'],
              h['proveedor_cod'], h['proveedor_nom'],
              h['lista'], h['fi_6dig'], h['invoice_nbr'],
              _safe_float(h['total_comprobante']),
              h['fecha_carga'], h['archivo_origen']))
        for ln in lines:
            self.ejecutar_comando("""
                INSERT INTO [T_GECOM_FI_DETAIL]
                    (comprobante, codigo_lilis, imputacion, descripcion,
                     cantidad, precio_unit, total_linea)
                VALUES (?,?,?,?,?,?,?)
            """, (h['comprobante'], ln['codigo_lilis'], ln['imputacion'],
                  ln['descripcion'], _safe_float(ln['cantidad']),
                  _safe_float(ln['precio_unit']), _safe_float(ln['total_linea'])))
        return True

    def insertar_re(self, h: dict, lines: list) -> bool:
        if self._existe('T_GECOM_RE', 'comprobante', h['comprobante']):
            return False
        # Buscar FI asociada
        fi_comp = None
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT comprobante FROM [T_GECOM_FI] WHERE fi_6dig = ?",
                (h['fi_6dig'],)
            )
            row = cursor.fetchone()
            if row:
                fi_comp = row[0]
            cursor.close()
        except Exception:
            pass

        self.ejecutar_comando("""
            INSERT INTO [T_GECOM_RE]
                (tipo, comprobante, fecha, proveedor_cod, proveedor_nom,
                 re_6dig, fi_comprobante, fecha_carga, archivo_origen)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (h['tipo'], h['comprobante'], h['fecha'],
              h['proveedor_cod'], h['proveedor_nom'],
              h['fi_6dig'], fi_comp,
              h['fecha_carga'], h['archivo_origen']))
        for ln in lines:
            self.ejecutar_comando("""
                INSERT INTO [T_GECOM_RE_DETAIL]
                    (comprobante, codigo_lilis, descripcion, cantidad)
                VALUES (?,?,?,?)
            """, (h['comprobante'], ln['codigo_lilis'],
                  ln['descripcion'], _safe_float(ln['cantidad'])))
        return True

    # ------------------------------------------------------------------ #
    # ENLAZAR DOCUMENTOS (re-run seguro, idempotente)
    # ------------------------------------------------------------------ #

    def enlazar_documentos(self):
        """
        Actualiza los campos de enlace entre tablas:
          - T_GECOM_FI.invoice_nbr      ← match por invoice_6dig
          - T_3M_PLIST_HEADER.invoice_nbr ← match por delivery_nbr = shipping_ref
          - T_GECOM_RE.fi_comprobante   ← match por re_6dig = fi_6dig
        Seguro de re-ejecutar: solo actualiza los que tienen NULL.
        """
        self._verificar_conexion()
        cursor = self.conn.cursor()
        n_total = 0

        # Invoice ↔ PO (cuando el parser no pudo capturar po_number del PDF)
        cursor.execute(
            "SELECT invoice_nbr, delivery_nbr FROM [T_3M_INVOICE_HEADER] "
            "WHERE (po_number IS NULL OR po_number = '')"
        )
        invoices_sin_po = cursor.fetchall()
        for inv_nbr, delivery_nbr in invoices_sin_po:
            if not delivery_nbr:
                continue
            # El PO se puede recuperar via PList que comparte el mismo delivery
            cursor.execute(
                "SELECT po_number FROM [T_3M_PLIST_HEADER] WHERE shipping_ref = ?",
                (delivery_nbr,)
            )
            row = cursor.fetchone()
            if row and row[0]:
                cursor.execute(
                    "UPDATE [T_3M_INVOICE_HEADER] SET po_number = ? WHERE invoice_nbr = ?",
                    (row[0], inv_nbr)
                )
                n_total += 1

        # PList ↔ PO (cuando el Packing List tampoco tiene po_number)
        cursor.execute(
            "SELECT shipping_ref FROM [T_3M_PLIST_HEADER] "
            "WHERE (po_number IS NULL OR po_number = '') AND invoice_nbr IS NOT NULL"
        )
        plists_sin_po = cursor.fetchall()
        for (sref,) in plists_sin_po:
            cursor.execute(
                "SELECT po_number FROM [T_3M_INVOICE_HEADER] WHERE delivery_nbr = ?",
                (sref,)
            )
            row = cursor.fetchone()
            if row and row[0]:
                cursor.execute(
                    "UPDATE [T_3M_PLIST_HEADER] SET po_number = ? WHERE shipping_ref = ?",
                    (row[0], sref)
                )
                n_total += 1

        # FI ↔ Invoice
        cursor.execute("SELECT comprobante, fi_6dig FROM [T_GECOM_FI] WHERE invoice_nbr IS NULL")
        fis = cursor.fetchall()
        for comp, dig6 in fis:
            cursor.execute(
                "SELECT invoice_nbr FROM [T_3M_INVOICE_HEADER] WHERE invoice_6dig = ?", (dig6,)
            )
            row = cursor.fetchone()
            if row:
                cursor.execute(
                    "UPDATE [T_GECOM_FI] SET invoice_nbr = ? WHERE comprobante = ?",
                    (row[0], comp)
                )
                n_total += 1

        # PList ↔ Invoice (delivery_nbr = shipping_ref)
        cursor.execute("SELECT shipping_ref FROM [T_3M_PLIST_HEADER] WHERE invoice_nbr IS NULL")
        plists = cursor.fetchall()
        for (sref,) in plists:
            cursor.execute(
                "SELECT invoice_nbr FROM [T_3M_INVOICE_HEADER] WHERE delivery_nbr = ?", (sref,)
            )
            row = cursor.fetchone()
            if row:
                cursor.execute(
                    "UPDATE [T_3M_PLIST_HEADER] SET invoice_nbr = ? WHERE shipping_ref = ?",
                    (row[0], sref)
                )
                n_total += 1

        # RE ↔ FI
        cursor.execute("SELECT comprobante, re_6dig FROM [T_GECOM_RE] WHERE fi_comprobante IS NULL")
        res = cursor.fetchall()
        for comp, dig6 in res:
            cursor.execute(
                "SELECT comprobante FROM [T_GECOM_FI] WHERE fi_6dig = ?", (dig6,)
            )
            row = cursor.fetchone()
            if row:
                cursor.execute(
                    "UPDATE [T_GECOM_RE] SET fi_comprobante = ? WHERE comprobante = ?",
                    (row[0], comp)
                )
                n_total += 1

        self.conn.commit()
        cursor.close()
        self.logger.info(f"  ✔ Enlace entre documentos: {n_total} relaciones actualizadas")
        return n_total

    # ------------------------------------------------------------------ #
    # AUDITORÍA (hereda del PO_System si la tabla existe)
    # ------------------------------------------------------------------ #

    def _registrar_auditoria(self, accion, tabla='', id_registro='',
                              detalle='', usuario='3M_SYSTEM'):
        """Registra en tbl_Auditoria del PO_System si existe."""
        try:
            cursor = self.conn.cursor()
            tablas = {r.table_name for r in cursor.tables(tableType='TABLE')}
            if 'tbl_Auditoria' not in tablas:
                cursor.close()
                return
            cursor.execute("""
                INSERT INTO [tbl_Auditoria]
                    (fecha_hora, accion, tabla_afectada, id_registro, usuario, detalle)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (datetime.now(), accion, tabla, str(id_registro), usuario, detalle))
            self.conn.commit()
            cursor.close()
        except Exception as e:
            self.logger.warning(f"  ⚠ No se pudo registrar auditoría: {e}")

    # ------------------------------------------------------------------ #
    # RESUMEN DE TABLAS
    # ------------------------------------------------------------------ #

    def resumen_tablas(self):
        """Imprime conteo de registros de todas las tablas 3M."""
        self._verificar_conexion()
        cursor = self.conn.cursor()
        print("\n" + "=" * 60)
        print("  RESUMEN  —  3M_SYSTEM en Access")
        print("=" * 60)
        for nombre in [t for _, t in TABLAS_3M.items()]:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM [{nombre}]")
                n = cursor.fetchone()[0]
                print(f"  {nombre:<35} {n:>6} registros")
            except Exception as e:
                print(f"  {nombre:<35} ERROR: {e}")
        print("=" * 60 + "\n")
        cursor.close()

    # ------------------------------------------------------------------ #
    # CONTEXT MANAGER
    # ------------------------------------------------------------------ #

    def __enter__(self):
        self.conectar()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.desconectar()
        return False

    def __str__(self):
        estado = "conectado" if self.conn else "desconectado"
        bd = self._ruta_bd.name if self._ruta_bd else "—"
        return f"AccessConnector(bd={bd}, estado={estado})"


# ============================================================================
# TEST / DEMO  —  ejecutar directamente en Windows con la BD real
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  TEST  —  AccessConnector  3M_SYSTEM")
    print("=" * 60)
    print()

    try:
        with AccessConnector() as db:

            print("--- Inicializando tablas 3M ---")
            resultado = db.inicializar_tablas_3m()
            print(f"  Creadas:    {resultado['creadas']    or '—'}")
            print(f"  Existentes: {resultado['existentes'] or '—'}")
            print()

            print("--- Resumen de tablas ---")
            db.resumen_tablas()

    except FileNotFoundError as e:
        print(f"\n⚠  Archivo .accdb no encontrado:\n   {e}")
        print(f"\n   Ruta configurada: {DB_PATH}")
        print("   Verifique que exista C:\\EXTERIOR\\PO_DataBase.accdb")
        raise SystemExit(1)

    except pyodbc.Error as e:
        print(f"\n⚠  Error de conexión ODBC: {e}")
        print("   Requiere: Microsoft Access Database Engine (64-bit)")
        raise SystemExit(1)
