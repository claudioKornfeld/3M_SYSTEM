# 3M_SYSTEM — Sistema de Gestión de Compras Proveedor 3M / Solventum
## Lilis S.A. — Código Proveedor: 1418

---

## Descripción General

Sistema para capturar, parsear y almacenar en base de datos histórica los cuatro documentos
del flujo de compras de 3M / Solventum:

| Documento | Origen | Tabla(s) |
|-----------|--------|----------|
| **PO** (confirmación email) | PDF manual | `T_3M_PO_HEADER`, `T_3M_PO_DETAIL` |
| **Invoice** (factura proveedor) | PDF Solventum | `T_3M_INVOICE_HEADER`, `T_3M_INVOICE_DETAIL` |
| **Packing List** | PDF Solventum | `T_3M_PLIST_HEADER`, `T_3M_PLIST_DETAIL` |
| **FIREX.txt** (Gecom) | TXT exportado | `T_GECOM_FI`, `T_GECOM_FI_DETAIL`, `T_GECOM_RE`, `T_GECOM_RE_DETAIL` |

---

## Estructura del Proyecto

```
3M_SYSTEM/
├── config.py           → Configuración de entorno (dev/prod) y rutas BD
├── db_connector.py     → Conexión SQLite/Access + DDL de tablas
├── parser_firex.py     → Parser FIREX.txt (FI y RE del Gecom)
├── parser_invoice.py   → Parser Invoice PDF 3M
├── parser_plist.py     → Parser Packing List PDF 3M
├── parser_po.py        → Parser PO (email convertido a PDF)
├── main.py             → Orquestador principal
├── README.md           → Este archivo
└── input/              → Carpeta de archivos a procesar
```

---

## Uso

### Inicializar base de datos
```bash
python main.py --init
```

### Cargar un documento individual
```bash
python main.py --firex input/firex.txt
python main.py --invoice input/Invoice.pdf
python main.py --plist input/Packing_List_202.pdf
python main.py --po input/PO.pdf
```

### Cargar todo lo que haya en la carpeta input/
```bash
python main.py --all --dir ./input
```
El sistema detecta el tipo por nombre de archivo:
- Contiene `firex` y termina en `.txt` → FIREX
- Contiene `invoice` → Invoice PDF
- Contiene `packing` o `plist` → Packing List PDF
- Contiene `po` u `order` → PO PDF

### Ver resumen de tablas
```bash
python main.py --report
```

### Re-ejecutar enlaces entre tablas
```bash
python main.py --link
```

---

## Configuración de Entorno

Editar `config.py`:

```python
ENVIRONMENT = "development"   # → SQLite local para pruebas
# ENVIRONMENT = "production"  # → MS Access en producción
```

En producción, cambiar también:
```python
DB_PATH = r"C:\EXTERIOR\PO_Database.accdb"   # desarrollo Windows
# DB_PATH = r"X:\EXTERIOR\PO_Database.accdb" # producción
```

**Requisitos producción:**
- Python con `pyodbc`: `pip install pyodbc`
- Microsoft Access Database Engine (64-bit)

---

## Claves de Cruce entre Documentos

```
T_3M_PO_HEADER.po_number
    ↑ "204 Lilis" / "202 rex"
    └── T_3M_INVOICE_HEADER.po_number
    └── T_3M_PLIST_HEADER.po_number

T_3M_INVOICE_HEADER.delivery_nbr  (Ej: 8112297327)
    └── T_3M_PLIST_HEADER.shipping_ref  [enlace automático]

T_3M_INVOICE_HEADER.invoice_6dig  (últimos 6 del invoice_nbr)
    └── T_GECOM_FI.fi_6dig            [enlace automático]

T_GECOM_FI.fi_6dig
    └── T_GECOM_RE.re_6dig            [enlace automático]
```

---

## Reglas de Negocio Implementadas

1. **Idempotencia**: Cada carga verifica duplicados por clave única. Re-cargar el mismo
   archivo no duplica registros (registra como "duplicada" y continúa).

2. **FIREX duplicados**: El Gecom puede repetir comprobantes en distintos pedidos del
   reporte. Los duplicados se contabilizan pero no se insertan dos veces.

3. **Enlace FI ↔ Invoice**: Los últimos 6 dígitos del `invoice_nbr` de 3M deben coincidir
   con los últimos 6 del número de comprobante FI en Gecom. El enlace se ejecuta
   automáticamente después de cada carga.

4. **Enlace RE ↔ FI**: El RE siempre debe tener el mismo número base que su FI. Se
   detecta por coincidencia de los 6 dígitos.

5. **Sumariado**: Las Invoice y Packing Lists pueden tener múltiples líneas para el mismo
   material. Están almacenadas a nivel de línea individual. Las vistas de consolidación
   quedan para la siguiente etapa de desarrollo.

---

## Tablas de Datos — Detalle

### T_GECOM_FI
| Campo | Descripción |
|-------|-------------|
| `comprobante` | Nro completo Gecom (00943-XXXXXXXX) |
| `fi_6dig` | Últimos 6 dígitos → clave cruce con Invoice 3M |
| `invoice_nbr` | Enlace a `T_3M_INVOICE_HEADER` (auto-completado) |
| `total_comprobante` | Total en ARS del comprobante |

### T_GECOM_FI_DETAIL
| Campo | Descripción |
|-------|-------------|
| `codigo_lilis` | Código interno Lilis (33xxx = estetoscopio, 80xxx = repuesto) |
| `imputacion` | Cuenta contable Gecom (ej: 114900) |
| `precio_unit` | Precio en ARS |

---

## Próximos Pasos (Fase 2)

- Vistas SQL de comparación PO ↔ Invoice ↔ FI ↔ RE por producto
- Detección de diferencias de cantidades (mermas, faltantes en aduana)
- Interfaz de búsqueda por número de PO o Invoice
- Integración con PO_System existente
- Exportación de reportes de discrepancias

---

*Desarrollado para Lilis S.A. — Departamento Exterior*
*Proveedor 1418 — 3M COMPANY USA / Solventum*
