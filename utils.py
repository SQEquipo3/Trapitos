"""Funciones auxiliares reutilizables de la aplicación."""

import hashlib
import hmac
import secrets
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import date, datetime, timedelta

from config import DATE_FMT, DATETIME_FMT


# Número de iteraciones para fortalecer el hash de la contraseña.
ITERATIONS = 600_000


def now_text():
    """Devuelve la fecha y hora actual con el formato configurado."""
    return datetime.now().strftime(DATETIME_FMT)


def today_text():
    """Devuelve la fecha actual con el formato configurado."""
    return date.today().strftime(DATE_FMT)


def date_offset(days):
    """Fecha de hoy desplazada `days` días, con el formato configurado."""
    return (date.today() + timedelta(days=days)).strftime(DATE_FMT)


def dinero(value):
    """Convierte un valor numérico a formato monetario."""
    try:
        return f"${float(value):,.2f}"
    except (ValueError, TypeError):
        return "$0.00"
def a_centavos(value):
    """Convierte pesos a centavos enteros con redondeo comercial."""
    try:
        cantidad = Decimal(str(value or 0))
        if not cantidad.is_finite():
            raise ValueError
        return int(
            (cantidad * 100).quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP
            )
        )
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("El importe no es válido.")


def dinero_centavos(value):
    """Muestra un importe almacenado en centavos como pesos."""
    centavos = int(value or 0)
    pesos = Decimal(centavos) / Decimal(100)
    return f"${pesos:,.2f}"

def hash_password(password):
    """
    Genera un hash seguro de la contraseña utilizando PBKDF2.

    Cada contraseña recibe una sal aleatoria diferente.
    El resultado tiene el formato:
    algoritmo$sal$hash
    """

    # Generar una sal aleatoria de 16 bytes.
    salt = secrets.token_bytes(16)

    # Calcular el hash de la contraseña con PBKDF2-HMAC-SHA256.
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        ITERATIONS
    )

    # Convertir la sal y el hash a hexadecimal para almacenarlos.
    salt_hex = salt.hex()
    hash_hex = password_hash.hex()

    # Guardar algoritmo, sal y hash en una sola cadena.
    return f"pbkdf2_sha256${salt_hex}${hash_hex}"


def verify_password(password, stored_hash):
    """
    Comprueba si una contraseña coincide con el hash almacenado.

    También permite verificar contraseñas antiguas guardadas
    mediante SHA-256 sin sal.
    """

    # Comprobar que los datos recibidos sean válidos.
    if not isinstance(password, str) or not isinstance(stored_hash, str):
        return False

    # Detectar hashes antiguos SHA-256 sin sal.
    if "$" not in stored_hash:
        old_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()

        # Comparar de forma segura el hash antiguo.
        return hmac.compare_digest(old_hash, stored_hash)

    try:
        # Separar el algoritmo, la sal y el hash almacenado.
        algorithm, salt_hex, hash_hex = stored_hash.split("$")

        # Verificar que el algoritmo sea el esperado.
        if algorithm != "pbkdf2_sha256":
            return False

        # Convertir la sal hexadecimal a bytes.
        salt = bytes.fromhex(salt_hex)

        # Convertir el hash almacenado a bytes.
        expected_hash = bytes.fromhex(hash_hex)

        # Validar las longitudes esperadas.
        if len(salt) != 16 or len(expected_hash) != 32:
            return False

        # Calcular nuevamente el hash con la misma sal.
        calculated_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            ITERATIONS
        )

        # Comparar ambos hashes de forma segura.
        return hmac.compare_digest(calculated_hash, expected_hash)

    except (ValueError, TypeError):
        # Si el formato está dañado, la contraseña no es válida.
        return False


def needs_password_rehash(stored_hash):
    """
    Indica si una contraseña necesita actualizarse.

    Los hashes SHA-256 antiguos necesitan migrarse
    al nuevo formato PBKDF2.
    """

    return not (
        isinstance(stored_hash, str)
        and stored_hash.startswith("pbkdf2_sha256$")
    )
