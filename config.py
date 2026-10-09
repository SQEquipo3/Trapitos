"""Configuración central de la aplicación Mis trapitos."""

# Información de la aplicación
APP_TITLE = "Mis trapitos - Sistema local"
APP_VERSION = "7.0"

# Base de datos
DB_NAME = "mis_trapitos.db"

# Formatos de fecha y hora
DATE_FMT = "%Y-%m-%d"
DATETIME_FMT = "%Y-%m-%d %H:%M:%S"

# Métodos de pago disponibles
PAYMENT_METHODS = (
    "Efectivo",
    "Tarjeta de credito",
    "Tarjeta de debito",
    "Transferencia bancaria",
)