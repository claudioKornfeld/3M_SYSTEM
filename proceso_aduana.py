#!/usr/bin/env python3
"""
=============================================================================
proceso_aduana.py  —  Inicialización e inserción de Despachos de Aduana
=============================================================================
3M_SYSTEM  |  Lilis S.A.  |  Departamento Exterior

USO:
    python proceso_aduana.py --init
        Crea T_ADUANA_DESPACHO en PO_DataBase.accdb (si no existe).

    python proceso_aduana.py --file 25_001_IC04_210290_X.pdf
        Parsea UN archivo y lo inserta.

    python proceso_aduana.py --dir .\\input
        Parsea todos los PDF de aduana en una carpeta e inserta los nuevos.

    python proceso_aduana.py --init --dir .\\input
        Inicializa la tabla Y carga todos los archivos de la carpeta.

    python proceso_aduana.py --report
        Muestra cuántos registros hay en T_ADUANA_DESPACHO.

    python proceso_aduana.py --help
        Muestra esta ayuda.

Idempotente: si un despacho (nr_despacho) ya está en la tabla, se omite
sin error. Se puede correr múltiples veces sin duplicar datos.

Detección de archivos de aduana en --dir:
    Nombre contiene 'IC04' o 'aduana' (case-insensitive) y termina en .pdf

Requiere:
    pip install pdfplumber pandas pyodbc

    Microsoft Access Database Engine 64-bit (para producción)
    access_connector.py y parser_aduana.py en el mismo directorio.
=============================================================================
"""

import sys
import argparse
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers de salida
# ---------------------------------------------------------------------------

def _sep(char="=", n=62):
    print(char * n)

def _titulo(msg):
    _sep()
    print(f"  {msg}")
    _sep()
    print()

def _ok(msg):   print(f"  ✔  {msg}")
def _skip(msg): print(f"  ℹ  {msg}")
def _err(msg):  print(f"  ✘  {msg}")
def _warn(msg): print(f"  ⚠  {msg}")


# ---------------------------------------------------------------------------
# Acción: --init
# ---------------------------------------------------------------------------

def cmd_init(db):
    """Crea T_ADUANA_DESPACHO (y las demás tablas 3M si faltan)."""
    print("Inicializando tablas 3M...")
    print()
    resultado = db.inicializar_tablas_3m()
    print()
    creadas    = resultado.get("creadas",    [])
    existentes = resultado.get("existentes", [])

    if "T_ADUANA_DESPACHO" in creadas:
        _ok("T_ADUANA_DESPACHO creada exitosamente.")
    elif "T_ADUANA_DESPACHO" in existentes:
        _skip("T_ADUANA_DESPACHO ya existía — sin cambios.")
    else:
        _warn("T_ADUANA_DESPACHO no aparece en el resultado.")

    print()
    return True


# ---------------------------------------------------------------------------
# Acción: procesar un PDF de aduana
# ---------------------------------------------------------------------------

def _procesar_pdf(db, filepath: Path) -> str:
    """
    Parsea un PDF de aduana e intenta insertarlo en la BD.
    Retorna: 'insertado' | 'duplicado' | 'error_parser' | 'error_db'
    """
    from parser_aduana import parse_aduana

    print(f"  Procesando: {filepath.name}")

    # 1 — Parsear
    try:
        datos = parse_aduana(str(filepath))
    except Exception as e:
        _err(f"Error al parsear '{filepath.name}': {e}")
        return "error_parser"

    nr = datos.get("nr_despacho") or "?"
    print(f"    nr_despacho:      {nr}")
    print(f"    oficializacion:   {datos.get('oficializacion')}")
    print(f"    vendedor:         {datos.get('vendedor')}")
    print(f"    fob_total:        {datos.get('fob_total')}")

    # 2 — Insertar
    try:
        insertado = db.insertar_aduana(datos)
    except Exception as e:
        _err(f"Error al insertar '{nr}': {e}")
        return "error_db"

    if insertado:
        _ok(f"'{nr}' insertado.")
        return "insertado"
    else:
        _skip(f"'{nr}' ya existe — omitido.")
        return "duplicado"


# ---------------------------------------------------------------------------
# Acción: --file
# ---------------------------------------------------------------------------

def cmd_file(db, filepath_str: str):
    """Carga un único PDF de aduana."""
    filepath = Path(filepath_str)
    if not filepath.exists():
        _err(f"Archivo no encontrado: {filepath}")
        return False
    if not filepath.suffix.lower() == ".pdf":
        _err(f"El archivo no es PDF: {filepath}")
        return False

    print()
    resultado = _procesar_pdf(db, filepath)
    print()
    return resultado in ("insertado", "duplicado")


# ---------------------------------------------------------------------------
# Acción: --dir
# ---------------------------------------------------------------------------

def _es_aduana(path: Path) -> bool:
    """Detecta si un PDF es de aduana por su nombre."""
    name = path.name.lower()
    return path.suffix.lower() == ".pdf" and (
        "ic04" in name or "aduana" in name
    )


def cmd_dir(db, dir_str: str):
    """Carga todos los PDF de aduana de una carpeta."""
    directorio = Path(dir_str)
    if not directorio.is_dir():
        _err(f"Directorio no encontrado: {directorio}")
        return False

    pdfs = sorted(p for p in directorio.iterdir() if _es_aduana(p))

    if not pdfs:
        _warn(f"No se encontraron archivos de aduana en: {directorio}")
        _warn("  (Buscando PDF con 'IC04' o 'aduana' en el nombre)")
        return True

    print(f"  Archivos encontrados: {len(pdfs)}")
    print()

    contadores = {"insertado": 0, "duplicado": 0, "error_parser": 0, "error_db": 0}

    for pdf in pdfs:
        resultado = _procesar_pdf(db, pdf)
        contadores[resultado] += 1
        print()

    # Resumen
    _sep("-")
    print(f"  RESUMEN  |  {directorio.name}")
    _sep("-")
    print(f"  Insertados:      {contadores['insertado']}")
    print(f"  Ya existían:     {contadores['duplicado']}")
    print(f"  Errores parser:  {contadores['error_parser']}")
    print(f"  Errores BD:      {contadores['error_db']}")
    _sep("-")
    print()

    return (contadores["error_parser"] + contadores["error_db"]) == 0


# ---------------------------------------------------------------------------
# Acción: --report
# ---------------------------------------------------------------------------

def cmd_report(db):
    """Muestra conteo de registros en T_ADUANA_DESPACHO."""
    try:
        df = db.leer_tabla("T_ADUANA_DESPACHO")
        print()
        _sep("-")
        print(f"  T_ADUANA_DESPACHO  —  {len(df)} registros")
        _sep("-")
        if not df.empty:
            cols = ["nr_despacho", "oficializacion", "vendedor", "fob_total", "divisa"]
            cols_presentes = [c for c in cols if c in df.columns]
            print()
            print(df[cols_presentes].to_string(index=False))
        print()
    except Exception as e:
        _err(f"No se pudo leer T_ADUANA_DESPACHO: {e}")
        _warn("  ¿Ya se ejecutó --init?")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="proceso_aduana.py — Carga de Despachos de Aduana al 3M_SYSTEM",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python proceso_aduana.py --init
  python proceso_aduana.py --file 25_001_IC04_210290_X.pdf
  python proceso_aduana.py --dir .\\input
  python proceso_aduana.py --init --dir .\\input
  python proceso_aduana.py --report
        """
    )
    parser.add_argument("--init",   action="store_true",
                        help="Crear T_ADUANA_DESPACHO si no existe")
    parser.add_argument("--file",   metavar="PDF",
                        help="Cargar un único PDF de aduana")
    parser.add_argument("--dir",    metavar="CARPETA",
                        help="Cargar todos los PDF de aduana de una carpeta")
    parser.add_argument("--report", action="store_true",
                        help="Mostrar registros en T_ADUANA_DESPACHO")

    args = parser.parse_args()

    # Si no se pasó nada, mostrar ayuda
    if not any([args.init, args.file, args.dir, args.report]):
        parser.print_help()
        sys.exit(0)

    # Verificar que los módulos necesarios estén disponibles
    try:
        from access_connector import AccessConnector
    except ImportError as e:
        _err(f"No se pudo importar access_connector: {e}")
        _err("  Verificar que access_connector.py esté en el mismo directorio.")
        sys.exit(1)

    _titulo("proceso_aduana.py  —  3M_SYSTEM  |  Lilis S.A.")

    # Conectar a la BD
    try:
        db = AccessConnector()
        db.conectar()
    except FileNotFoundError as e:
        _err(str(e))
        sys.exit(1)
    except Exception as e:
        _err(f"Error de conexión: {e}")
        sys.exit(1)

    exito = True

    try:
        # --init
        if args.init:
            print("[ INICIALIZAR TABLAS ]")
            print()
            if not cmd_init(db):
                exito = False

        # --file
        if args.file:
            print("[ CARGAR ARCHIVO ]")
            if not cmd_file(db, args.file):
                exito = False

        # --dir
        if args.dir:
            print("[ CARGAR CARPETA ]")
            print()
            if not cmd_dir(db, args.dir):
                exito = False

        # --report
        if args.report:
            print("[ REPORTE ]")
            cmd_report(db)

    finally:
        db.desconectar()

    _sep()
    if exito:
        _ok("Proceso finalizado sin errores.")
    else:
        _warn("Proceso finalizado con errores. Revisar salida arriba.")
    _sep()
    print()

    sys.exit(0 if exito else 1)


if __name__ == "__main__":
    main()
