"""Repositorio de reportes.

Aquí viven las consultas que antes estaban en Database.report().
El SQL y los nombres de los reportes se movieron sin modificarse.
Recibe el objeto Database (data/database.py).
"""


def ejecutar(db, name, param=""):
    param = (param or "").strip()
    if name == "Inventario general actualizado":
        return db.query(
            """SELECT p.id, p.code AS codigo, p.name AS producto, p.category AS categoria,
                      p.size AS talla, p.color, p.stock, p.sale_price AS precio,
                      COALESCE(s.name,'') AS proveedor
               FROM products p LEFT JOIN suppliers s ON s.id=p.supplier_id
               ORDER BY p.category, p.name"""
        )
    if name == "Productos con stock bajo":
        limit = int(param or 5)
        return db.query(
            "SELECT code AS codigo, name AS producto, category AS categoria, size AS talla, color, stock "
            "FROM products WHERE stock <= ? ORDER BY stock ASC",
            (limit,),
        )
    if name == "Ventas diarias, semanales y mensuales":
        return db.query(
            """SELECT 'Dia actual' AS periodo, COALESCE(SUM(total),0) AS total
               FROM sales WHERE status='ACTIVA' AND date(sale_datetime)=date('now')
               UNION ALL
               SELECT 'Ultimos 7 dias', COALESCE(SUM(total),0)
               FROM sales WHERE status='ACTIVA' AND date(sale_datetime)>=date('now','-6 day')
               UNION ALL
               SELECT 'Mes actual', COALESCE(SUM(total),0)
               FROM sales WHERE status='ACTIVA'
               AND strftime('%Y-%m',sale_datetime)=strftime('%Y-%m','now')"""
        )
    if name == "Ventas por producto":
        return db.query(
            """SELECT p.code AS codigo, p.name AS producto, SUM(si.quantity) AS piezas,
                      SUM(si.line_total) AS ventas
               FROM sale_items si JOIN products p ON p.id=si.product_id
               JOIN sales s ON s.id=si.sale_id
               WHERE s.status='ACTIVA' GROUP BY p.id ORDER BY piezas DESC"""
        )
    if name == "Ventas por metodo de pago":
        return db.query(
            "SELECT payment_method AS metodo, COUNT(*) AS ventas, SUM(total) AS total "
            "FROM sales WHERE status='ACTIVA' GROUP BY payment_method ORDER BY ventas DESC"
        )
    if name == "Ventas por empleado":
        return db.query(
            """SELECT e.name AS empleado, COUNT(s.id) AS ventas, COALESCE(SUM(s.total),0) AS total
               FROM employees e LEFT JOIN sales s ON s.employee_id=e.id AND s.status='ACTIVA'
               GROUP BY e.id ORDER BY total DESC"""
        )
    if name == "Productos mas vendidos":
        return db.query(
            """SELECT p.code AS codigo, p.name AS producto, SUM(si.quantity) AS piezas
               FROM sale_items si JOIN products p ON p.id=si.product_id
               JOIN sales s ON s.id=si.sale_id
               WHERE s.status='ACTIVA' GROUP BY p.id ORDER BY piezas DESC LIMIT 20"""
        )
    if name == "Productos menos vendidos":
        return db.query(
            """SELECT p.code AS codigo, p.name AS producto,
                      COALESCE(SUM(CASE WHEN s.status='ACTIVA' THEN si.quantity ELSE 0 END),0) AS piezas
               FROM products p LEFT JOIN sale_items si ON si.product_id=p.id
               LEFT JOIN sales s ON s.id=si.sale_id
               GROUP BY p.id ORDER BY piezas ASC LIMIT 20"""
        )
    if name == "Entradas de mercancia":
        return db.query(
            """SELECT im.movement_datetime AS fecha, p.code AS codigo, p.name AS producto,
                      im.quantity AS cantidad, im.reason AS motivo
               FROM inventory_movements im JOIN products p ON p.id=im.product_id
               WHERE im.movement_type IN ('ENTRADA','AJUSTE') AND im.quantity > 0
               ORDER BY im.movement_datetime DESC"""
        )
    if name == "Clientes frecuentes":
        return db.query(
            """SELECT c.name AS cliente, c.phone AS telefono, COUNT(s.id) AS compras,
                      COALESCE(SUM(s.total),0) AS total
               FROM customers c LEFT JOIN sales s ON s.customer_id=c.id AND s.status='ACTIVA'
               GROUP BY c.id ORDER BY compras DESC, total DESC"""
        )
    if name == "Resumen de utilidades":
        return db.query(
            """SELECT p.code AS codigo, p.name AS producto, SUM(si.quantity) AS piezas,
                      SUM(si.line_total) AS ventas, SUM(si.quantity * p.purchase_price) AS costo,
                      SUM(si.line_total - si.quantity * p.purchase_price) AS utilidad
               FROM sale_items si JOIN products p ON p.id=si.product_id
               JOIN sales s ON s.id=si.sale_id
               WHERE s.status='ACTIVA' GROUP BY p.id ORDER BY utilidad DESC"""
        )
    if name == "Productos devueltos o cancelados":
        return db.query(
            """SELECT im.movement_datetime AS fecha, im.movement_type AS tipo, p.code AS codigo,
                      p.name AS producto, im.quantity AS cantidad, im.reason AS motivo,
                      im.related_sale_id AS venta
               FROM inventory_movements im JOIN products p ON p.id=im.product_id
               WHERE im.movement_type IN ('DEVOLUCION','CANCELACION')
               ORDER BY im.movement_datetime DESC"""
        )
    if name == "Productos disponibles por categoria":
        if not param:
            raise ValueError("Escribe una categoria.")
        return db.query(
            "SELECT code AS codigo, name AS producto, category AS categoria, size AS talla, color, "
            "stock, sale_price AS precio FROM products "
            "WHERE category LIKE ? AND stock > 0 ORDER BY name",
            (f"%{param}%",),
        )
    if name == "Productos en oferta":
        return db.query(
            """SELECT p.code AS codigo, p.name AS producto, pr.discount_percent AS descuento,
                      pr.start_date AS inicio, pr.end_date AS fin
               FROM promotions pr JOIN products p ON p.id=pr.product_id
               WHERE date('now') BETWEEN date(pr.start_date) AND date(pr.end_date)
               ORDER BY pr.discount_percent DESC"""
        )
    if name == "Metodos de pago mas utilizados":
        return ejecutar(db, "Ventas por metodo de pago", param)
    if name == "Productos mas vendidos ultimo mes":
        return db.query(
            """SELECT p.code AS codigo, p.name AS producto, SUM(si.quantity) AS piezas
               FROM sale_items si JOIN products p ON p.id=si.product_id
               JOIN sales s ON s.id=si.sale_id
               WHERE s.status='ACTIVA' AND date(s.sale_datetime)>=date('now','-1 month')
               GROUP BY p.id ORDER BY piezas DESC"""
        )
    if name == "Ventas ultimos tres dias":
        return db.query(
            """SELECT s.id AS venta, s.sale_datetime AS fecha, COALESCE(c.name,'') AS cliente,
                      e.name AS empleado, s.payment_method AS metodo, s.total, s.status AS estado
               FROM sales s LEFT JOIN customers c ON c.id=s.customer_id
               JOIN employees e ON e.id=s.employee_id
               WHERE date(s.sale_datetime)>=date('now','-3 day')
               ORDER BY s.sale_datetime DESC"""
        )
    if name == "Productos de proveedor especifico":
        if not param:
            raise ValueError("Escribe ID o nombre del proveedor.")
        if param.isdigit():
            return db.query(
                """SELECT p.code AS codigo, p.name AS producto, p.category AS categoria,
                          p.size AS talla, p.color, p.stock, s.name AS proveedor
                   FROM products p JOIN suppliers s ON s.id=p.supplier_id WHERE s.id=?""",
                (int(param),),
            )
        return db.query(
            """SELECT p.code AS codigo, p.name AS producto, p.category AS categoria,
                      p.size AS talla, p.color, p.stock, s.name AS proveedor
               FROM products p JOIN suppliers s ON s.id=p.supplier_id WHERE s.name LIKE ?""",
            (f"%{param}%",),
        )
    if name == "Productos comprados mas de una vez por cliente":
        if not param or not param.isdigit():
            raise ValueError("Escribe el ID del cliente.")
        return db.query(
            """SELECT p.code AS codigo, p.name AS producto, SUM(si.quantity) AS piezas,
                      COUNT(DISTINCT s.id) AS compras
               FROM sales s JOIN sale_items si ON si.sale_id=s.id
               JOIN products p ON p.id=si.product_id
               WHERE s.status='ACTIVA' AND s.customer_id=?
               GROUP BY p.id HAVING COUNT(DISTINCT s.id)>1 OR SUM(si.quantity)>1
               ORDER BY piezas DESC""",
            (int(param),),
        )
    if name == "Productos vendidos por categoria ultimo mes":
        if not param:
            raise ValueError("Escribe una categoria.")
        return db.query(
            """SELECT p.category AS categoria, p.code AS codigo, p.name AS producto,
                      SUM(si.quantity) AS piezas, SUM(si.line_total) AS total
               FROM sale_items si JOIN products p ON p.id=si.product_id
               JOIN sales s ON s.id=si.sale_id
               WHERE s.status='ACTIVA' AND date(s.sale_datetime)>=date('now','-1 month')
               AND p.category LIKE ?
               GROUP BY p.id ORDER BY piezas DESC""",
            (f"%{param}%",),
        )
    if name == "Productos con precio superior y existencias":
        value = float(param or 0)
        return db.query(
            "SELECT code AS codigo, name AS producto, category AS categoria, sale_price AS precio, stock "
            "FROM products WHERE sale_price > ? AND stock > 0 ORDER BY sale_price DESC",
            (value,),
        )
    if name == "Producto con mayor descuento vigente":
        return db.query(
            """SELECT p.code AS codigo, p.name AS producto, pr.discount_percent AS descuento,
                      pr.start_date AS inicio, pr.end_date AS fin
               FROM promotions pr JOIN products p ON p.id=pr.product_id
               WHERE date('now') BETWEEN date(pr.start_date) AND date(pr.end_date)
               ORDER BY pr.discount_percent DESC LIMIT 1"""
        )
    if name == "Compras por ciudad o region":
        return db.query(
            """SELECT COALESCE(c.city_region,'Sin region') AS region, COUNT(s.id) AS compras,
                      SUM(s.total) AS total
               FROM sales s LEFT JOIN customers c ON c.id=s.customer_id
               WHERE s.status='ACTIVA' GROUP BY c.city_region ORDER BY compras DESC"""
        )
    if name == "Productos no vendidos ultimos tres meses":
        return db.query(
            """SELECT p.code AS codigo, p.name AS producto, p.category AS categoria, p.stock
               FROM products p
               WHERE p.id NOT IN (
                   SELECT DISTINCT si.product_id FROM sale_items si
                   JOIN sales s ON s.id=si.sale_id
                   WHERE s.status='ACTIVA' AND date(s.sale_datetime)>=date('now','-3 month')
               )
               ORDER BY p.name"""
        )
    raise ValueError("Reporte no reconocido.")
