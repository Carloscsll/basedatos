# tienda_db.py
import os
import sqlite3
from sqlite3 import Error


class BaseDatosTienda:
    def __init__(self, ruta="./", bd="tienda.sqlite3"):
        self.bd_path = os.path.join(ruta, bd)
        self.con = None
        self.cursor = None
        self.conectar()
        self.crear_tablas()

    def conectar(self):
        try:
            self.con = sqlite3.connect(self.bd_path, check_same_thread=False)
            self.con.row_factory = sqlite3.Row
            self.cursor = self.con.cursor()
            self.cursor.execute("PRAGMA foreign_keys = ON;")
            self.con.commit()
        except Error as e:
            print(f"[DB] Error al conectar: {e}")

    def cerrar(self):
        try:
            if self.con:
                self.con.close()
        except Error as e:
            print(f"[DB] Error al cerrar: {e}")

    def crear_tablas(self):
        try:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS productos(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT NOT NULL,
                    descripcion TEXT,
                    imagen_url TEXT,
                    precio REAL NOT NULL CHECK(precio >= 0),
                    costo REAL NOT NULL DEFAULT 0 CHECK(costo >= 0),
                    stock INTEGER NOT NULL DEFAULT 0 CHECK(stock >= 0)
                );
            """)

            # Migracion simple para bases ya creadas sin columna imagen_url.
            self.cursor.execute("PRAGMA table_info(productos);")
            cols = [row["name"] for row in self.cursor.fetchall()]
            if "imagen_url" not in cols:
                self.cursor.execute("ALTER TABLE productos ADD COLUMN imagen_url TEXT;")
            if "costo" not in cols:
                self.cursor.execute("ALTER TABLE productos ADD COLUMN costo REAL NOT NULL DEFAULT 0;")

            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS pedidos(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cliente_nombre TEXT NOT NULL,
                    cliente_email TEXT,
                    cliente_direccion TEXT NOT NULL DEFAULT '',
                    estado TEXT NOT NULL DEFAULT 'realizado' CHECK(estado IN ('realizado', 'enviado', 'entregado')),
                    total REAL NOT NULL CHECK(total >= 0),
                    creado_en TEXT NOT NULL DEFAULT (datetime('now'))
                );
            """)

            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS usuarios(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    rol TEXT NOT NULL CHECK(rol IN ('admin', 'usuario')),
                    nombre TEXT NOT NULL
                );
            """)

            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS pedido_items(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pedido_id INTEGER NOT NULL,
                    producto_id INTEGER NOT NULL,
                    cantidad INTEGER NOT NULL CHECK(cantidad > 0),
                    precio_unit REAL NOT NULL CHECK(precio_unit >= 0),
                    costo_unit REAL NOT NULL DEFAULT 0 CHECK(costo_unit >= 0),
                    FOREIGN KEY(pedido_id) REFERENCES pedidos(id)
                        ON DELETE CASCADE ON UPDATE CASCADE,
                    FOREIGN KEY(producto_id) REFERENCES productos(id)
                        ON DELETE RESTRICT ON UPDATE CASCADE
                );
            """)

            self.cursor.execute("PRAGMA table_info(pedidos);")
            cols_pedidos = [row["name"] for row in self.cursor.fetchall()]
            if "cliente_direccion" not in cols_pedidos:
                self.cursor.execute("ALTER TABLE pedidos ADD COLUMN cliente_direccion TEXT NOT NULL DEFAULT '';")
            if "estado" not in cols_pedidos:
                self.cursor.execute("ALTER TABLE pedidos ADD COLUMN estado TEXT NOT NULL DEFAULT 'realizado';")

            self.cursor.execute("PRAGMA table_info(pedido_items);")
            cols_items = [row["name"] for row in self.cursor.fetchall()]
            if "costo_unit" not in cols_items:
                self.cursor.execute("ALTER TABLE pedido_items ADD COLUMN costo_unit REAL NOT NULL DEFAULT 0;")

            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS avisos(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    titulo TEXT NOT NULL,
                    mensaje TEXT NOT NULL,
                    creado_en TEXT NOT NULL DEFAULT (datetime('now'))
                );
            """)

            self.con.commit()
        except Error as e:
            print(f"[DB] Error creando tablas: {e}")

    # --------- Productos (CRUD) ----------
    def crear_producto(self, nombre, descripcion, precio, stock, costo=0, imagen_url=None):
        try:
            self.cursor.execute("""
                INSERT INTO productos(nombre, descripcion, imagen_url, precio, costo, stock)
                VALUES(?,?,?,?,?,?);
            """, (nombre.strip(), descripcion, (imagen_url or "").strip() or None, float(precio), float(costo), int(stock)))
            self.con.commit()
            return self.cursor.lastrowid
        except Error as e:
            print(f"[DB] No se pudo crear producto: {e}")
            return None

    def listar_productos(self):
        try:
            self.cursor.execute("SELECT * FROM productos ORDER BY id DESC;")
            return self.cursor.fetchall()
        except Error as e:
            print(f"[DB] Error listando productos: {e}")
            return []

    def obtener_producto(self, producto_id):
        try:
            self.cursor.execute("SELECT * FROM productos WHERE id=?;", (producto_id,))
            return self.cursor.fetchone()
        except Error as e:
            print(f"[DB] Error obteniendo producto: {e}")
            return None

    def actualizar_imagen_producto(self, producto_id, imagen_url):
        try:
            self.cursor.execute(
                "UPDATE productos SET imagen_url=? WHERE id=?;",
                ((imagen_url or "").strip() or None, int(producto_id)),
            )
            self.con.commit()
            return self.cursor.rowcount > 0
        except Error as e:
            print(f"[DB] Error actualizando imagen de producto: {e}")
            return False

    def actualizar_stock(self, producto_id, nuevo_stock):
        try:
            self.cursor.execute(
                "UPDATE productos SET stock=? WHERE id=?;",
                (int(nuevo_stock), producto_id)
            )
            self.con.commit()
            return self.cursor.rowcount > 0
        except Error as e:
            print(f"[DB] Error actualizando stock: {e}")
            return False

    def actualizar_producto(self, producto_id, nombre, descripcion, precio, stock, costo, imagen_url=None):
        try:
            self.cursor.execute("""
                UPDATE productos
                SET nombre=?, descripcion=?, precio=?, costo=?, stock=?, imagen_url=?
                WHERE id=?;
            """, (
                nombre.strip(),
                descripcion.strip() if descripcion else None,
                float(precio),
                float(costo),
                int(stock),
                (imagen_url or "").strip() or None,
                int(producto_id)
            ))
            self.con.commit()
            return self.cursor.rowcount > 0
        except Error as e:
            print(f"[DB] Error actualizando producto: {e}")
            return False

    def eliminar_producto(self, producto_id):
        try:
            self.cursor.execute("DELETE FROM productos WHERE id=?;", (int(producto_id),))
            self.con.commit()
            return self.cursor.rowcount > 0
        except Error as e:
            print(f"[DB] Error eliminando producto: {e}")
            return False

    # --------- Usuarios ----------
    def crear_usuario(self, username, password_hash, rol, nombre):
        try:
            self.cursor.execute("""
                INSERT INTO usuarios(username, password_hash, rol, nombre)
                VALUES(?,?,?,?);
            """, (username.strip(), password_hash, rol, nombre.strip()))
            self.con.commit()
            return self.cursor.lastrowid
        except Error as e:
            print(f"[DB] No se pudo crear usuario: {e}")
            return None

    def obtener_usuario_por_username(self, username):
        try:
            self.cursor.execute("SELECT * FROM usuarios WHERE username=?;", (username.strip(),))
            return self.cursor.fetchone()
        except Error as e:
            print(f"[DB] Error obteniendo usuario: {e}")
            return None

    # --------- Pedidos ----------
    def crear_pedido(self, cliente_nombre, cliente_email, cliente_direccion, items):
        """
        items: lista de dicts: [{"producto_id":1, "cantidad":2}, ...]
        - Calcula total
        - Valida stock
        - Descuenta stock
        - Inserta pedido + items en transacción
        """
        try:
            self.cursor.execute("BEGIN;")

            total = 0.0
            lineas = []

            for it in items:
                pid = int(it["producto_id"])
                qty = int(it["cantidad"])

                self.cursor.execute("SELECT id, precio, costo, stock FROM productos WHERE id=?;", (pid,))
                p = self.cursor.fetchone()
                if not p:
                    raise ValueError(f"Producto {pid} no existe")
                if p["stock"] < qty:
                    raise ValueError(f"Stock insuficiente para producto {pid}")

                precio_unit = float(p["precio"])
                costo_unit = float(p["costo"] or 0)
                total += precio_unit * qty
                lineas.append((pid, qty, precio_unit, costo_unit))

            self.cursor.execute("""
                INSERT INTO pedidos(cliente_nombre, cliente_email, cliente_direccion, estado, total)
                VALUES(?,?,?,?,?);
            """, (cliente_nombre.strip(), cliente_email, cliente_direccion.strip(), "realizado", total))
            pedido_id = self.cursor.lastrowid

            for (pid, qty, precio_unit, costo_unit) in lineas:
                self.cursor.execute("""
                    INSERT INTO pedido_items(pedido_id, producto_id, cantidad, precio_unit, costo_unit)
                    VALUES(?,?,?,?,?);
                """, (pedido_id, pid, qty, precio_unit, costo_unit))

                # descontar stock
                self.cursor.execute("""
                    UPDATE productos SET stock = stock - ?
                    WHERE id=?;
                """, (qty, pid))

            self.con.commit()
            return pedido_id

        except Exception as e:
            self.con.rollback()
            print(f"[DB] Error creando pedido: {e}")
            return None

    def semilla_productos(self):
        """Crea 3 productos de ejemplo base."""
        try:
            self.cursor.execute("SELECT COUNT(*) AS total FROM productos;")
            total_productos = int(self.cursor.fetchone()["total"] or 0)
            if total_productos > 0:
                return

            base = [
                ("Playera", "Playera 100% algodón", 199.0, 120.0, 20, "foto portada.jpg"),
                ("Taza", "Taza cerámica 350ml", 129.0, 70.0, 15, "foto portada.jpg"),
                ("Sticker Pack", "Paquete de 10 stickers", 59.0, 20.0, 50, "foto portada.jpg"),
            ]

            for nombre, descripcion, precio, costo, stock, imagen_local in base:
                self.cursor.execute("SELECT 1 FROM productos WHERE nombre=? LIMIT 1;", (nombre,))
                existe = self.cursor.fetchone()
                if not existe:
                    self.crear_producto(
                        nombre,
                        descripcion,
                        precio,
                        stock,
                        costo=costo,
                        imagen_url=imagen_local,
                    )
        except Error as e:
            print(f"[DB] Error semilla: {e}")

    def reemplazar_imagenes_externas_por_local(self, imagen_local="foto portada.jpg"):
        """Convierte imagenes externas (http/https) a un archivo local en /imagenes."""
        try:
            self.cursor.execute(
                """
                UPDATE productos
                SET imagen_url=?
                WHERE imagen_url LIKE 'http://%'
                   OR imagen_url LIKE 'https://%';
                """,
                ((imagen_local or "").strip() or None,),
            )
            self.con.commit()
            return self.cursor.rowcount
        except Error as e:
            print(f"[DB] Error reemplazando imagenes externas: {e}")
            return 0

    def semilla_usuarios(self):
        """Compatibilidad: la semilla de usuarios se maneja desde app.py."""
        return None

    def limpiar_usuarios_no_admin(self):
        """Elimina todos los usuarios excepto los admins."""
        try:
            self.cursor.execute("DELETE FROM usuarios WHERE rol != 'admin';")
            self.con.commit()
            return self.cursor.rowcount
        except Error as e:
            print(f"[DB] Error limpiando usuarios: {e}")
            return 0

    # --------- Avisos ----------
    def crear_aviso(self, titulo, mensaje):
        try:
            self.cursor.execute(
                """
                INSERT INTO avisos(titulo, mensaje)
                VALUES(?, ?);
                """,
                (titulo.strip(), mensaje.strip()),
            )
            self.con.commit()
            return self.cursor.lastrowid
        except Error as e:
            print(f"[DB] Error creando aviso: {e}")
            return None

    def listar_avisos(self, limit=50):
        try:
            self.cursor.execute(
                """
                SELECT *
                FROM avisos
                ORDER BY id DESC
                LIMIT ?;
                """,
                (int(limit),),
            )
            return self.cursor.fetchall()
        except Error as e:
            print(f"[DB] Error listando avisos: {e}")
            return []

    def eliminar_aviso(self, aviso_id):
        try:
            self.cursor.execute("DELETE FROM avisos WHERE id=?;", (int(aviso_id),))
            self.con.commit()
            return self.cursor.rowcount > 0
        except Error as e:
            print(f"[DB] Error eliminando aviso: {e}")
            return False

    # --------- Reportes ----------
    def obtener_pedido(self, pedido_id):
        try:
            self.cursor.execute("SELECT * FROM pedidos WHERE id=?;", (int(pedido_id),))
            return self.cursor.fetchone()
        except Error as e:
            print(f"[DB] Error obteniendo pedido: {e}")
            return None

    def listar_items_pedido(self, pedido_id):
        try:
            self.cursor.execute(
                """
                SELECT pi.*, p.nombre AS producto_nombre
                FROM pedido_items pi
                JOIN productos p ON p.id = pi.producto_id
                WHERE pi.pedido_id=?
                ORDER BY pi.id ASC;
                """,
                (int(pedido_id),),
            )
            return self.cursor.fetchall()
        except Error as e:
            print(f"[DB] Error listando items del pedido: {e}")
            return []

    def actualizar_estado_pedido(self, pedido_id, estado):
        try:
            self.cursor.execute("UPDATE pedidos SET estado=? WHERE id=?;", (estado, int(pedido_id)))
            self.con.commit()
            return self.cursor.rowcount > 0
        except Error as e:
            print(f"[DB] Error actualizando estado de pedido: {e}")
            return False

    def reporte_finanzas_hoy(self):
        """Devuelve resumen de ingresos, costos, ganancias y pedidos de hoy (hora local)."""
        try:
            self.cursor.execute(
                """
                SELECT
                    COUNT(*) AS total_pedidos,
                    COALESCE(SUM(total), 0) AS total_ingresos
                FROM pedidos
                WHERE date(creado_en, 'localtime') = date('now', 'localtime');
                """
            )
            resumen = self.cursor.fetchone()

            self.cursor.execute(
                """
                SELECT
                    p.id,
                    p.cliente_nombre,
                    p.cliente_email,
                    p.cliente_direccion,
                    p.estado,
                    p.total,
                    p.creado_en,
                    COALESCE(SUM(pi.cantidad * pi.costo_unit), 0) AS costo_total
                FROM pedidos p
                LEFT JOIN pedido_items pi ON pi.pedido_id = p.id
                WHERE date(p.creado_en, 'localtime') = date('now', 'localtime')
                GROUP BY p.id
                ORDER BY p.id DESC;
                """
            )
            pedidos = self.cursor.fetchall()

            total_ingresos = float(resumen["total_ingresos"] or 0)
            total_costos = float(sum(float(pedido["costo_total"] or 0) for pedido in pedidos))

            return {
                "total_pedidos": int(resumen["total_pedidos"] or 0),
                "total_ingresos": total_ingresos,
                "total_costos": total_costos,
                "total_ganancias": total_ingresos - total_costos,
                "pedidos": pedidos,
            }
        except Error as e:
            print(f"[DB] Error generando reporte de ventas: {e}")
            return {"total_pedidos": 0, "total_ingresos": 0.0, "total_costos": 0.0, "total_ganancias": 0.0, "pedidos": []}