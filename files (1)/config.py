# =============================================================================
# 3M_SYSTEM - Configuración Central
# Proveedor: 3M / Solventum  (Código Lilis: 1418)
# =============================================================================

import os

# ---------------------------------------------------------------------------
# ENTORNO: cambiar a "production" para usar Access real
# ---------------------------------------------------------------------------
ENVIRONMENT = "development"   # "development" | "production"

# ---------------------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------------------
if ENVIRONMENT == "development":
    DB_TYPE = "sqlite"
    DB_PATH = os.path.join(os.path.dirname(__file__), "PO_Database_dev.db")
else:
    DB_TYPE = "access"
    DB_PATH = r"C:\EXTERIOR\PO_Database.accdb"          # desarrollo en Windows
    # DB_PATH = r"X:\EXTERIOR\PO_Database.accdb"        # producción

# ---------------------------------------------------------------------------
# Proveedor 3M
# ---------------------------------------------------------------------------
SUPPLIER_CODE = "1418"
SUPPLIER_NAME = "3M COMPANY USA"

# ---------------------------------------------------------------------------
# Directorios de entrada (ajustar según entorno)
# ---------------------------------------------------------------------------
INPUT_DIR = os.path.join(os.path.dirname(__file__), "input")
os.makedirs(INPUT_DIR, exist_ok=True)

print(f"[CONFIG] Entorno: {ENVIRONMENT} | DB: {DB_TYPE} → {DB_PATH}")
