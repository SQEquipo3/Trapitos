"""Clientes, proveedores y empleados (RF-11, RF-12, RF-13, RF-14)."""
import sqlite3

import pytest

from mis_trapitos.data.repositories import clientes, empleados, proveedores
from utils import today_text
from mis_trapitos.services import ventas as ventas_srv


def cliente(nombre="Ana"):
    return (nombre, "555-1", "a@x.com", "Calle 1", "Guadalajara", "Vestidos")


def test_alta_y_edicion_de_cliente(db):
    cid = clientes.guardar(db, None, cliente())
    clientes.guardar(db, cid, cliente("Ana Lopez"))
    assert clientes.obtener_por_id(db, cid)["name"] == "Ana Lopez"
    assert clientes.existe(db, cid) and not clientes.existe(db, 999)


def test_cliente_con_ventas_no_se_puede_eliminar(db, empleado, make_product):
    cid = clientes.guardar(db, None, cliente())
    pid = make_product()
    ventas_srv.registrar(db, cid, empleado, "Efectivo", 0, [{"product_id": pid, "quantity": 1}])
    with pytest.raises(sqlite3.IntegrityError):
        clientes.eliminar(db, cid)


def test_historial_resumen_y_producto_favorito(db, empleado, make_product):
    cid = clientes.guardar(db, None, cliente())
    a, b = make_product(name="Blusa"), make_product(name="Falda")
    ventas_srv.registrar(db, cid, empleado, "Efectivo", 0, [{"product_id": a, "quantity": 3}])
    ventas_srv.registrar(db, cid, empleado, "Efectivo", 0, [{"product_id": b, "quantity": 1}])
    assert len(clientes.historial(db, cid)) == 2
    assert clientes.resumen_compras(db, cid)["compras"] == 2
    assert clientes.producto_favorito(db, cid)["producto"] == "Blusa"


def test_alta_de_proveedor_y_lista(db):
    pid = proveedores.guardar(db, None, ("Textiles SA", "555", "Av 1", "Blusas", today_text()))
    assert proveedores.existe(db, pid) and proveedores.listar(db)[0]["nombre"] == "Textiles SA"


def test_proveedor_duplicado_o_con_productos_no_se_elimina(db, make_product):
    sid = proveedores.guardar(db, None, ("Textiles SA", "555", "Av 1", "x", today_text()))
    with pytest.raises(sqlite3.IntegrityError):
        proveedores.guardar(db, None, ("Textiles SA", "1", "x", "x", today_text()))
    make_product(supplier_id=sid)
    with pytest.raises(sqlite3.IntegrityError):
        proveedores.eliminar(db, sid)


def test_empleado_no_cambia_password_si_viene_vacio(db):
    eid = empleados.guardar(db, None, "Luis", "luis", "secreto", "Vendedor")
    empleados.guardar(db, eid, "Luis R", "luis", "", "Vendedor")
    assert empleados.autenticar(db, "luis", "secreto") is not None


def test_usuario_de_empleado_es_unico(db):
    empleados.guardar(db, None, "A", "igual", "1", "Vendedor")
    with pytest.raises(sqlite3.IntegrityError):
        empleados.guardar(db, None, "B", "igual", "2", "Vendedor")
