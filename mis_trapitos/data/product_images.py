"""Copias de fotos y referencias portables, relativas a mis_trapitos_imagenes."""

import logging
from pathlib import Path, PurePosixPath, PureWindowsPath
from uuid import uuid4

from PIL import Image, ImageOps


IMAGE_DIR = "mis_trapitos_imagenes"
_FORMATS = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".gif": "GIF",
            ".ppm": "PPM", ".pgm": "PPM"}


def image_directory():
    """Carpeta junto a la aplicación; no depende del directorio de ejecución."""
    return Path(__file__).resolve().parents[2] / IMAGE_DIR


def _clean_path(path):
    return str(path or "").strip().strip('"')


def _managed_reference(path):
    """Reconoce referencias nuevas y rutas antiguas de Windows o POSIX."""
    base = image_directory().resolve()
    native = Path(path)
    if native.is_absolute():
        try:
            return native.resolve().relative_to(base)
        except ValueError:
            pass
    portable = PurePosixPath(path.replace("\\", "/"))
    parts = portable.parts
    if IMAGE_DIR in parts:
        # Una copia restaurada puede conservar la raíz del equipo anterior.
        folder_index = len(parts) - 1 - parts[::-1].index(IMAGE_DIR)
        parts = parts[folder_index + 1:]
    elif portable.is_absolute() or PureWindowsPath(path).drive:
        return None
    if not parts or ".." in parts:
        return None
    relative = Path(*parts)
    if relative.is_absolute() or not (base / relative).resolve().is_relative_to(base):
        return None
    return relative


def resolve_image_path(path):
    """Resuelve primero la copia administrada; admite originales para importarlos."""
    path = _clean_path(path)
    if not path:
        return ""
    relative = _managed_reference(path)
    if relative is not None:
        candidate = image_directory() / relative
        if candidate.is_file():
            return str(candidate.resolve())
    native = Path(path)
    if native.is_absolute() and native.is_file():
        return str(native.resolve())
    return ""


def store_product_image(source_path):
    """Copia la imagen con UUID y devuelve únicamente la referencia relativa."""
    selected = Path(_clean_path(source_path))
    # Una selección explícita importa ese archivo, aunque haya una copia homónima.
    source_path = str(selected.resolve()) if selected.is_file() else resolve_image_path(source_path)
    if not source_path:
        raise ValueError("No se encontro la imagen seleccionada.")
    source_file = Path(source_path)
    ext = source_file.suffix.lower()
    if ext not in _FORMATS:
        ext = ".jpg"
    safe_name = "".join(ch for ch in source_file.stem if ch.isalnum() or ch in "_-")
    filename = f"{safe_name[:80] or 'producto'}_{uuid4().hex}{ext}"
    target = image_directory() / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source_file) as source:
        img = ImageOps.exif_transpose(source)
        if _FORMATS[ext] == "JPEG":
            img = img.convert("RGB")
        # La creación exclusiva también impide sobrescribir si un nombre se repite.
        with target.open("xb") as output:
            try:
                img.save(output, _FORMATS[ext], **({"quality": 92} if ext in (".jpg", ".jpeg") else {}))
            except Exception:
                output.close()
                target.unlink()
                raise
    return filename


def normalize_image_path(path):
    """Reutiliza copias administradas e importa fotos externas que aún existen.

    Las referencias no recuperables se conservan para no perder su ubicación
    original ni impedir la edición de los demás datos del producto.
    """
    path = _clean_path(path)
    resolved = resolve_image_path(path)
    if not resolved:
        return path
    try:
        return Path(resolved).relative_to(image_directory().resolve()).as_posix()
    except ValueError:
        return store_product_image(resolved)


def migrate_product_image_paths(db):
    """Convierte las referencias existentes al abrir la base; es idempotente."""
    converted = {}
    with db.transaction():
        for row in db.query("SELECT id, image_path FROM products WHERE image_path IS NOT NULL AND image_path != ''"):
            original = row["image_path"]
            if original not in converted:
                try:
                    converted[original] = normalize_image_path(original)
                except (OSError, ValueError):
                    logging.getLogger(__name__).warning(
                        "No se pudo migrar la foto del producto %s; se conserva su referencia.", row["id"]
                    )
                    converted[original] = original
            if converted[original] != original:
                db.execute("UPDATE products SET image_path=? WHERE id=?", (converted[original], row["id"]))
