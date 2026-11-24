"""Regresiones del issue #89 con imágenes y bases de datos desechables."""

from pathlib import Path
import shutil

from PIL import Image
import pytest

from mis_trapitos.data import product_images
from mis_trapitos.data.database import Database
from mis_trapitos.data.repositories import productos
from tests.tc import tc


@pytest.fixture
def image_dir(tmp_path, monkeypatch):
    directory = tmp_path / "app" / product_images.IMAGE_DIR
    directory.mkdir(parents=True)
    monkeypatch.setattr(product_images, "image_directory", lambda: directory)
    return directory


def make_image(path, color="blue", mode="RGB", exif=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new(mode, (32, 48), color).save(path, **({"exif": exif} if exif else {}))
    return path


def product_data(path="", code="FOTO-1"):
    return (code, "Blusa", "Ropa", "M", "Azul", 10, 20, 5, None,
            "2026-11-11", "Marca", "Todo", path)


@tc("ITS_PRO_IMG_01", nivel="ITS", modulo="productos", reqs=["RF-01"],
    nombre="Fotos portables y migración de referencias anteriores")
def test_copias_inmediatas_con_mismo_nombre_no_sobrescriben(image_dir, tmp_path):
    """Guardar fotos homónimas conserva ambas imágenes y genera rutas relativas.

    Precondiciones: Dos PNG del mismo nombre en carpetas temporales distintas.
    Pasos:
    - Importar la foto azul dos veces y la roja una vez, sin esperas.
    - Leer las tres referencias devueltas y sus archivos.
    Esperado:
    - Tres nombres diferentes, relativos a la carpeta de imágenes.
    - Las copias conservan tamaño y color; los originales siguen disponibles.
    """
    blue = make_image(tmp_path / "azul" / "blusa.png")
    red = make_image(tmp_path / "roja" / "blusa.png", "red")
    references = [product_images.store_product_image(path) for path in (blue, blue, red)]
    assert len(set(references)) == 3
    for reference, color in zip(references, ((0, 0, 255), (0, 0, 255), (255, 0, 0))):
        assert not Path(reference).is_absolute()
        assert Path(reference).parent == Path(".")
        with Image.open(image_dir / reference) as saved:
            assert saved.size == (32, 48)
            assert saved.getpixel((0, 0)) == color
    assert blue.is_file() and red.is_file()


@tc("ITS_PRO_IMG_01")
def test_no_sobrescribe_archivo_aun_si_uuid_colisiona(image_dir, tmp_path, monkeypatch):
    from uuid import UUID

    monkeypatch.setattr(product_images, "uuid4", lambda: UUID(int=1))
    source = make_image(tmp_path / "blusa.png")
    reference = product_images.store_product_image(source)
    make_image(source, "red")
    with pytest.raises(FileExistsError):
        product_images.store_product_image(source)
    with Image.open(image_dir / reference) as saved:
        assert saved.getpixel((0, 0)) == (0, 0, 255)


@tc("ITS_PRO_IMG_01")
def test_conserva_orientacion_exif_y_conversion_jpeg(image_dir, tmp_path):
    exif = Image.Exif()
    exif[274] = 6  # Rotación de 90 grados.
    source = make_image(tmp_path / "camara.jpg", exif=exif)
    reference = product_images.store_product_image(source)
    with Image.open(image_dir / reference) as saved:
        assert saved.size == (48, 32)
        assert saved.getexif().get(274, 1) == 1
    rgba = make_image(tmp_path / "transparente.tiff", mode="RGBA")
    reference = product_images.store_product_image(rgba)
    with Image.open(image_dir / reference) as saved:
        assert saved.format == "JPEG"
        assert saved.mode == "RGB"


@tc("ITS_PRO_IMG_01")
@pytest.mark.parametrize("legacy", [
    "blusa.png",
    "mis_trapitos_imagenes/blusa.png",
    r"mis_trapitos_imagenes\blusa.png",
    r"C:\equipo-anterior\Trapitos\mis_trapitos_imagenes\blusa.png",
    "/equipo-anterior/Trapitos/mis_trapitos_imagenes/blusa.png",
])
def test_resuelve_referencias_sin_depender_del_directorio_actual(image_dir, tmp_path, monkeypatch, legacy):
    current = make_image(image_dir / "blusa.png")
    other = tmp_path / "otro_directorio"
    other.mkdir()
    make_image(other / "blusa.png", "red")
    monkeypatch.chdir(other)
    assert product_images.resolve_image_path(legacy) == str(current.resolve())
    assert product_images.normalize_image_path(legacy) == "blusa.png"


@tc("ITS_PRO_IMG_01")
def test_restaurar_base_y_fotos_en_otra_carpeta(image_dir, tmp_path, monkeypatch):
    source = make_image(tmp_path / "foto.png")
    database_path = image_dir.parent / "inventario.db"
    db = Database(database_path, load_examples=False)
    try:
        product_id = productos.guardar(db, None, product_data(str(source)))
        reference = db.scalar("SELECT image_path FROM products WHERE id=?", (product_id,))
        assert Path(reference).name == reference
    finally:
        db.close()
    restored = tmp_path / "restaurada"
    shutil.copytree(image_dir.parent, restored)
    source.unlink()
    (image_dir / reference).unlink()
    restored_images = restored / product_images.IMAGE_DIR
    monkeypatch.setattr(product_images, "image_directory", lambda: restored_images)
    monkeypatch.chdir(tmp_path)
    db = Database(restored / "inventario.db", load_examples=False)
    try:
        saved_reference = db.scalar("SELECT image_path FROM products WHERE id=?", (product_id,))
        assert saved_reference == reference
        with Image.open(product_images.resolve_image_path(saved_reference)) as photo:
            assert photo.getpixel((0, 0)) == (0, 0, 255)
    finally:
        db.close()


@tc("ITS_PRO_IMG_01")
def test_migra_al_abrir_sin_duplicar_copias_y_conserva_faltantes(image_dir, tmp_path):
    managed = make_image(image_dir / "existente.png")
    external = make_image(tmp_path / "externa.png")
    missing = str(tmp_path / "ausente.png")
    broken = tmp_path / "corrupta.png"
    broken.write_text("no es una imagen", encoding="utf-8")
    originals = [str(managed), str(external), str(external), missing, str(broken), "", None,
                 r"C:\antigua\mis_trapitos_imagenes\existente.png"]
    database_path = tmp_path / "inventario.db"
    db = Database(database_path, load_examples=False)
    try:
        for index, original in enumerate(originals):
            product_id = productos.guardar(db, None, product_data(code=f"FOTO-{index}"))
            db.execute("UPDATE products SET image_path=? WHERE id=?", (original, product_id))
    finally:
        db.close()
    for _ in range(2):
        db = Database(database_path, load_examples=False)
        try:
            references = [row[0] for row in db.query("SELECT image_path FROM products ORDER BY id")]
            assert references[0] == references[7] == "existente.png"
            assert references[1] == references[2]
            assert Path(references[1]).name == references[1]
            assert (image_dir / references[1]).is_file()
            assert references[3:7] == [missing, str(broken), "", None]
            assert db.scalar("SELECT COUNT(*) FROM inventory_movements") == len(originals)
        finally:
            db.close()
        assert len(list(image_dir.iterdir())) == 2
    assert external.is_file() and managed.is_file()


@tc("ITS_PRO_IMG_01")
def test_editar_producto_importa_foto_y_reutiliza_la_copia(image_dir, tmp_path, db):
    product_id = productos.guardar(db, None, product_data())
    source = make_image(tmp_path / "nueva.png")
    productos.guardar(db, product_id, product_data(str(source)))
    reference = db.scalar("SELECT image_path FROM products WHERE id=?", (product_id,))
    productos.guardar(db, product_id, product_data(reference))
    assert db.scalar("SELECT image_path FROM products WHERE id=?", (product_id,)) == reference
    assert list(image_dir.iterdir()) == [image_dir / reference]


@tc("ITS_PRO_IMG_01")
def test_migracion_prefiere_fotos_restauradas_a_la_instalacion_anterior(image_dir, tmp_path):
    old = make_image(tmp_path / "anterior" / product_images.IMAGE_DIR / "blusa.png", "red")
    restored = make_image(image_dir / "blusa.png", "blue")
    assert product_images.resolve_image_path(str(old)) == str(restored.resolve())
    assert product_images.normalize_image_path(str(old)) == "blusa.png"


@tc("ITS_PRO_IMG_01")
def test_seleccion_explicita_importa_original_aunque_exista_foto_homonima(image_dir, tmp_path):
    selected = make_image(tmp_path / "otra_app" / product_images.IMAGE_DIR / "blusa.png", "red")
    make_image(image_dir / "blusa.png", "blue")
    reference = product_images.store_product_image(selected)
    with Image.open(image_dir / reference) as saved:
        assert saved.getpixel((0, 0)) == (255, 0, 0)


@tc("ITS_PRO_IMG_01")
def test_no_resuelve_referencia_relativa_fuera_de_imagenes(image_dir):
    make_image(image_dir.parent / "privada.png")
    assert product_images.resolve_image_path("../privada.png") == ""
    assert product_images.resolve_image_path("mis_trapitos_imagenes/../privada.png") == ""


@tc("ITS_PRO_IMG_01")
def test_archivo_corrupto_no_crea_copia(image_dir, tmp_path):
    source = tmp_path / "falsa.png"
    source.write_text("no es una imagen", encoding="utf-8")
    with pytest.raises(OSError):
        product_images.store_product_image(source)
    assert list(image_dir.iterdir()) == []
