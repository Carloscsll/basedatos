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
        self.semilla_usuarios()
        self.semilla_contenido()

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
                    precio REAL NOT NULL CHECK(precio >= 0),
                    stock INTEGER NOT NULL DEFAULT 0 CHECK(stock >= 0),
                    imagen TEXT
                );
            """)

            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS pedidos(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cliente_nombre TEXT NOT NULL,
                    cliente_email TEXT,
                    total REAL NOT NULL CHECK(total >= 0),
                    creado_en TEXT NOT NULL DEFAULT (datetime('now'))
                );
            """)

            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS pedido_items(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pedido_id INTEGER NOT NULL,
                    producto_id INTEGER NOT NULL,
                    cantidad INTEGER NOT NULL CHECK(cantidad > 0),
                    precio_unit REAL NOT NULL CHECK(precio_unit >= 0),
                    FOREIGN KEY(pedido_id) REFERENCES pedidos(id)
                        ON DELETE CASCADE ON UPDATE CASCADE,
                    FOREIGN KEY(producto_id) REFERENCES productos(id)
                        ON DELETE RESTRICT ON UPDATE CASCADE
                );
            """)

            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS usuarios(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('user','admin'))
                );
            """)

            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS contenido(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    clave TEXT NOT NULL UNIQUE,
                    texto TEXT NOT NULL
                );
            """)

            self.con.commit()
        except Error as e:
            print(f"[DB] Error creando tablas: {e}")

        # Migración: Agregar columna imagen si no existe
        try:
            self.cursor.execute("PRAGMA table_info(productos);")
            columns = [row[1] for row in self.cursor.fetchall()]
            if 'imagen' not in columns:
                self.cursor.execute("ALTER TABLE productos ADD COLUMN imagen TEXT;")
                self.con.commit()
                print("[DB] Columna 'imagen' agregada a productos.")
        except Error as e:
            print(f"[DB] Error en migración: {e}")

    # --------- Productos (CRUD) ----------
    def crear_producto(self, nombre, descripcion, precio, stock, imagen=None):
        try:
            self.cursor.execute("""
                INSERT INTO productos(nombre, descripcion, precio, stock, imagen)
                VALUES(?,?,?,?,?);
            """, (nombre.strip(), descripcion, float(precio), int(stock), imagen))
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

    # --------- Pedidos ----------
    def crear_pedido(self, cliente_nombre, cliente_email, items):
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

                self.cursor.execute("SELECT id, precio, stock FROM productos WHERE id=?;", (pid,))
                p = self.cursor.fetchone()
                if not p:
                    raise ValueError(f"Producto {pid} no existe")
                if p["stock"] < qty:
                    raise ValueError(f"Stock insuficiente para producto {pid}")

                precio_unit = float(p["precio"])
                total += precio_unit * qty
                lineas.append((pid, qty, precio_unit))

            self.cursor.execute("""
                INSERT INTO pedidos(cliente_nombre, cliente_email, total)
                VALUES(?,?,?);
            """, (cliente_nombre.strip(), cliente_email, total))
            pedido_id = self.cursor.lastrowid

            for (pid, qty, precio_unit) in lineas:
                self.cursor.execute("""
                    INSERT INTO pedido_items(pedido_id, producto_id, cantidad, precio_unit)
                    VALUES(?,?,?,?);
                """, (pedido_id, pid, qty, precio_unit))

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

    def semilla_productos(self, reset=False, productos=None):
        """Crea o restablece productos de ejemplo.

        reset: si es True borra todos los productos antes de sembrar.
        productos: lista opcional de tuplas (nombre, descripcion, precio, stock).
        """
        if productos is None:
            productos = [
                ("Playera", "Playera 100% algodón", 199.0, 20),
                ("Taza", "Taza cerámica 350ml", 129.0, 15),
                ("Sticker Pack", "Paquete de 10 stickers", 59.0, 50),
            ]

        try:
            if reset:
                self.cursor.execute("DELETE FROM productos;")
                self.con.commit()

            self.cursor.execute("SELECT COUNT(*) as c FROM productos;")
            c = self.cursor.fetchone()["c"]

            if c == 0:
                for nombre, descripcion, precio, stock in productos:
                    self.crear_producto(nombre, descripcion, precio, stock)
        except Error as e:
            print(f"[DB] Error semilla: {e}")

    # --------- Usuarios ----------
    def crear_usuario(self, username, password_hash, role='user'):
        try:
            u = username.strip().lower()
            self.cursor.execute("""
                INSERT INTO usuarios(username, password_hash, role)
                VALUES(?,?,?);
            """, (u, password_hash, role))
            self.con.commit()
            return self.cursor.lastrowid
        except Error as e:
            print(f"[DB] No se pudo crear usuario: {e}")
            return None

    def obtener_usuario_por_username(self, username):
        try:
            self.cursor.execute("SELECT * FROM usuarios WHERE username=?;", (username.strip().lower(),))
            return self.cursor.fetchone()
        except Error as e:
            print(f"[DB] Error obteniendo usuario: {e}")
            return None

    def semilla_usuarios(self):
        try:
            self.cursor.execute("SELECT COUNT(*) as c FROM usuarios;")
            c = self.cursor.fetchone()["c"]
            if c == 0:
                # Usuario admin para pruebas
                from werkzeug.security import generate_password_hash
                self.crear_usuario("admin", generate_password_hash("admin123"), "admin")
                self.crear_usuario("cliente", generate_password_hash("cliente123"), "user")
        except Error as e:
            print(f"[DB] Error semilla usuarios: {e}")

    def semilla_contenido(self):
        try:
            self.cursor.execute("SELECT COUNT(*) as c FROM contenido;")
            c = self.cursor.fetchone()["c"]
            if c == 0:
                contenido_inicial = [
                    ("titulo_principal", "Bienvenido a Mi Tienda"),
                    ("descripcion_principal", "Encuentra productos seleccionados, precios competitivos y una experiencia de compra clara."),
                    ("titulo_nosotros", "Sobre Nosotros"),
                    ("descripcion_nosotros", "Somos una tienda pequeña comprometida con la calidad, el servicio y la satisfacción de nuestros clientes."),
                    ("titulo_catalogo", "Catálogo"),
                    ("footer", "Hecho con Flask + SQLite")
                ]
                for clave, texto in contenido_inicial:
                    self.guardar_contenido(clave, texto)
        except Error as e:
            print(f"[DB] Error semilla contenido: {e}")

    def eliminar_producto(self, producto_id):
        try:
            self.cursor.execute("DELETE FROM productos WHERE id=?;", (producto_id,))
            self.con.commit()
            return self.cursor.rowcount > 0
        except Error as e:
            print(f"[DB] Error eliminando producto: {e}")
            return False

    # --------- Contenido ----------
    def obtener_contenido(self, clave):
        try:
            self.cursor.execute("SELECT texto FROM contenido WHERE clave=?;", (clave,))
            row = self.cursor.fetchone()
            return row["texto"] if row else None
        except Error as e:
            print(f"[DB] Error obteniendo contenido: {e}")
            return None

    def guardar_contenido(self, clave, texto):
        try:
            self.cursor.execute("""
                INSERT OR REPLACE INTO contenido(clave, texto)
                VALUES(?,?);
            """, (clave, texto))
            self.con.commit()
            return True
        except Error as e:
            print(f"[DB] Error guardando contenido: {e}")
            return False

    def listar_contenido(self):
        try:
            self.cursor.execute("SELECT clave, texto FROM contenido ORDER BY clave;")
            return self.cursor.fetchall()
        except Error as e:
            print(f"[DB] Error listando contenido: {e}")
            return []
