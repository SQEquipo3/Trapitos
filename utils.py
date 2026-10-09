"""Funciones auxiliares reutilizables de la aplicación."""

import hashlib
from datetime import date, datetime

from config import DATE_FMT, DATETIME_FMT


def now_text():
    """Devuelve la fecha y hora actual con el formato configurado."""
    return datetime.now().strftime(DATETIME_FMT)


def today_text():
    """Devuelve la fecha actual con el formato configurado."""
    return date.today().strftime(DATE_FMT)


def dinero(value):
    """Convierte un valor numérico a formato monetario."""
    try:
        return f"${float(value):,.2f}"
    except Exception:
        return "$0.00"


def hash_password(password):
    """Genera el hash SHA-256 de una contraseña."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()