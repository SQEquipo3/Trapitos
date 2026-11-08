"""Clientes, proveedores y empleados (RF-11, RF-12, RF-13, RF-14)."""
import sqlite3

import pytest

from mis_trapitos.data.repositories import clientes, empleados, proveedores
from utils import today_text
from mis_trapitos.services import ventas as ventas_srv
from tests.tc import tc


def cliente(nombre="Ana"):
    return (nombre, "555-1", "a@x.com", "Calle 1", "Guadalajara", "Vestidos")


@tc("ITS_CON_01", nivel="ITS", modulo="contactos", reqs=["RF-11", "RF-12"],
    nombre="Alta/edición de clientes, historial y producto favorito")
def test_alta_y_edicion_de_cliente(db):
    """Verificar el módulo de clientes (RF-11, RF-12) en mis_trapitos/data/repositories/clientes.py: alta y
    edición con guardar(), existencia con existe(), y la consulta del historial de compras con
    historial(), resumen_compras() y producto_favorito(). El historial une sales, sale_items y products
    y muestra el estado (ACTIVA o CANCELADA) de cada venta.

    Precondiciones: Fixtures db, empleado y make_product. Cliente 'Ana' de Guadalajara (helper cliente()
      del archivo).
    Pasos:
    - Crear el cliente con clientes.guardar(db, None, cliente()) y editarlo con clientes.guardar(db,
      cid, cliente('Ana Lopez')).
    - Leer con clientes.obtener_por_id(db, cid) y llamar clientes.existe(db, cid) y existe(db, 999).
    - En test_historial_resumen_y_producto_favorito: vender al cliente 3 blusas y 1 falda en dos ventas;
      llamar historial(), resumen_compras() y producto_favorito().
    - En test_historial_de_cliente_incluye_estado_de_cada_venta (tests/test_reportes.py): con el
      conjunto de datos 'mundo', llamar clientes_repo.historial(db, cli).
    Esperado:
    - El nombre editado 'Ana Lopez' persiste; existe() es True para el cliente y False para 999.
    - historial tiene 2 filas, resumen_compras()['compras'] = 2 y producto_favorito()['producto'] =
      'Blusa'.
    - El historial del cliente con una venta cancelada contiene los estados ACTIVA y CANCELADA.
    """
    cid = clientes.guardar(db, None, cliente())
    clientes.guardar(db, cid, cliente("Ana Lopez"))
    assert clientes.obtener_por_id(db, cid)["name"] == "Ana Lopez"
    assert clientes.existe(db, cid) and not clientes.existe(db, 999)


@tc("ITS_CON_02", nivel="ITS", modulo="contactos", reqs=["RF-13", "RF-14"],
    nombre="Integridad referencial de clientes y proveedores")
def test_cliente_con_ventas_no_se_puede_eliminar(db, empleado, make_product):
    """Verificar la integridad referencial de clientes y proveedores (RF-13, RF-14): no se puede eliminar
    un cliente que tiene ventas ni un proveedor que tiene productos (llaves foráneas), y no se pueden
    registrar dos proveedores con el mismo nombre (UNIQUE). Funciones: clientes.eliminar(),
    proveedores.guardar(), proveedores.eliminar(), proveedores.listar().

    Precondiciones: Fixtures db, empleado y make_product.
    Pasos:
    - Crear un cliente, venderle 1 producto con ventas_srv.registrar() y llamar clientes.eliminar(db,
      cid).
    - En test_alta_de_proveedor_y_lista: crear 'Textiles SA' con proveedores.guardar() y llamar
      proveedores.existe() y proveedores.listar().
    - En test_proveedor_duplicado_o_con_productos_no_se_elimina: intentar guardar otro proveedor
      'Textiles SA'.
    - Ligar un producto al proveedor con make_product(supplier_id=sid) y llamar proveedores.eliminar(db,
      sid).
    Esperado:
    - Eliminar el cliente con ventas levanta sqlite3.IntegrityError.
    - El proveedor válido existe y aparece primero en listar() con nombre 'Textiles SA'.
    - El proveedor duplicado y la eliminación del proveedor con productos levantan IntegrityError.
    """
    cid = clientes.guardar(db, None, cliente())
    pid = make_product()
    ventas_srv.registrar(db, cid, empleado, "Efectivo", 0, [{"product_id": pid, "quantity": 1}])
    with pytest.raises(sqlite3.IntegrityError):
        clientes.eliminar(db, cid)


@tc("ITS_CON_01")
def test_historial_resumen_y_producto_favorito(db, empleado, make_product):
    cid = clientes.guardar(db, None, cliente())
    a, b = make_product(name="Blusa"), make_product(name="Falda")
    ventas_srv.registrar(db, cid, empleado, "Efectivo", 0, [{"product_id": a, "quantity": 3}])
    ventas_srv.registrar(db, cid, empleado, "Efectivo", 0, [{"product_id": b, "quantity": 1}])
    assert len(clientes.historial(db, cid)) == 2
    assert clientes.resumen_compras(db, cid)["compras"] == 2
    assert clientes.producto_favorito(db, cid)["producto"] == "Blusa"


@tc("ITS_CON_02")
def test_alta_de_proveedor_y_lista(db):
    pid = proveedores.guardar(db, None, ("Textiles SA", "555", "Av 1", "Blusas", today_text()))
    assert proveedores.existe(db, pid) and proveedores.listar(db)[0]["nombre"] == "Textiles SA"


@tc("ITS_CON_02")
def test_proveedor_duplicado_o_con_productos_no_se_elimina(db, make_product):
    sid = proveedores.guardar(db, None, ("Textiles SA", "555", "Av 1", "x", today_text()))
    with pytest.raises(sqlite3.IntegrityError):
        proveedores.guardar(db, None, ("Textiles SA", "1", "x", "x", today_text()))
    make_product(supplier_id=sid)
    with pytest.raises(sqlite3.IntegrityError):
        proveedores.eliminar(db, sid)


@tc("UTS_CON_01")
def test_empleado_no_cambia_password_si_viene_vacio(db):
    eid = empleados.guardar(db, None, "Luis", "luis", "secreto", "Vendedor")
    empleados.guardar(db, eid, "Luis R", "luis", "", "Vendedor")
    assert empleados.autenticar(db, "luis", "secreto") is not None


@tc("UTS_CON_01", nivel="UTS", modulo="contactos", reqs=["SEG-01"],
    nombre="Unicidad de usuario de empleado y conservación de contraseña")
def test_usuario_de_empleado_es_unico(db):
    """Verificar dos reglas de empleados.guardar() (mis_trapitos/data/repositories/empleados.py): el nombre
    de usuario es único (UNIQUE en employees.username) y, al editar un empleado con la contraseña vacía,
    se conserva la contraseña anterior en lugar de borrarla (SEG-01).

    Precondiciones: Fixture db (base temporal vacía).
    Pasos:
    - Llamar empleados.guardar(db, None, 'A', 'igual', '1', 'Vendedor').
    - Llamar empleados.guardar(db, None, 'B', 'igual', '2', 'Vendedor') con el mismo usuario.
    - En test_empleado_no_cambia_password_si_viene_vacio: crear 'luis' con contraseña 'secreto' y
      editarlo con empleados.guardar(db, eid, 'Luis R', 'luis', '', 'Vendedor').
    - Llamar empleados.autenticar(db, 'luis', 'secreto').
    Esperado:
    - El segundo alta con usuario 'igual' levanta sqlite3.IntegrityError.
    - autenticar con la contraseña original 'secreto' regresa el empleado.
    """
    empleados.guardar(db, None, "A", "igual", "1", "Vendedor")
    with pytest.raises(sqlite3.IntegrityError):
        empleados.guardar(db, None, "B", "igual", "2", "Vendedor")
