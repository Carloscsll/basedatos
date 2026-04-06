# app.py
from functools import wraps
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from werkzeug.security import check_password_hash, generate_password_hash
from tienda_db import BaseDatosTienda

app = Flask(__name__)
app.secret_key = "TiEnda_SecRET_Clav_ña_1234567890"  # Cambia esto por una clave segura en producción

# Servir archivos desde la carpeta imagenes
@app.route("/imagenes/<path:filename>")
def descargar_imagen(filename):
    return send_from_directory(os.path.join(os.path.dirname(__file__), "imagenes"), filename)

db = BaseDatosTienda(ruta="./", bd="tienda.sqlite3")
db.semilla_productos()
db.reemplazar_imagenes_externas_por_local("foto portada.jpg")
db.limpiar_usuarios_no_admin()  # Limpia usuarios registrados, mantiene solo admin


def normalizar_nombre_imagen(valor):
    valor = (valor or "").strip()
    if not valor:
        return ""

    lower = valor.lower()
    if lower.startswith("http://") or lower.startswith("https://"):
        return None

    if lower.startswith("/imagenes/"):
        valor = valor[len("/imagenes/"):]

    return os.path.basename(valor).strip()


def semilla_usuarios_demo():
    # Credenciales demo iniciales:
    # EmilianoAdmin / Holakhace
    # cliente / cliente123
    admin_username = "EmilianoAdmin"
    admin_password_hash = generate_password_hash("Holakhace")

    admin = db.obtener_usuario_por_username(admin_username)
    admin_legacy = db.obtener_usuario_por_username("admin")

    if admin:
        # Mantiene el username pedido y actualiza la contraseña en cada arranque.
        db.cursor.execute(
            """
            UPDATE usuarios
            SET password_hash=?, rol='admin', nombre='Administrador'
            WHERE id=?;
            """,
            (admin_password_hash, int(admin["id"])),
        )
        db.con.commit()
    elif admin_legacy:
        # Migra el usuario admin antiguo al nuevo username.
        db.cursor.execute(
            """
            UPDATE usuarios
            SET username=?, password_hash=?, rol='admin', nombre='Administrador'
            WHERE id=?;
            """,
            (admin_username, admin_password_hash, int(admin_legacy["id"])),
        )
        db.con.commit()
    else:
        db.crear_usuario(
            username=admin_username,
            password_hash=admin_password_hash,
            rol="admin",
            nombre="Administrador",
        )


semilla_usuarios_demo()

def carrito_session():
    # carrito: { "producto_id": cantidad }
    if "carrito" not in session:
        session["carrito"] = {}
    return session["carrito"]


def usuario_actual():
    return session.get("usuario")


def usuario_autenticado():
    return usuario_actual() is not None


def es_admin():
    u = usuario_actual() or {}
    return u.get("rol") == "admin"


def login_requerido(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not usuario_autenticado():
            flash("Inicia sesión para continuar.")
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)

    return wrapper


@app.context_processor
def inyectar_usuario_template():
    return {
        "usuario": usuario_actual(),
        "es_admin": es_admin(),
    }


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        u = db.obtener_usuario_por_username(username)
        if not u or not check_password_hash(u["password_hash"], password):
            flash("Usuario o contraseña incorrectos.")
            return redirect(url_for("login"))

        session["usuario"] = {
            "id": int(u["id"]),
            "username": u["username"],
            "nombre": u["nombre"],
            "rol": u["rol"],
        }
        flash(f"Bienvenido, {u['nombre']}.")

        destino = request.form.get("next") or request.args.get("next") or url_for("index")
        return redirect(destino)

    return render_template("login.html")


@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")
        
        # Validaciones
        if not username:
            flash("El nombre de usuario es obligatorio.")
            return redirect(url_for("registro"))
        
        if len(username) < 3:
            flash("El nombre de usuario debe tener al menos 3 caracteres.")
            return redirect(url_for("registro"))
        
        if not password or len(password) < 6:
            flash("La contraseña debe tener al menos 6 caracteres.")
            return redirect(url_for("registro"))
        
        if password != password_confirm:
            flash("Las contraseñas no coinciden.")
            return redirect(url_for("registro"))
        
        # Validar que el username no exista
        if db.obtener_usuario_por_username(username):
            flash("Este nombre de usuario ya está registrado.")
            return redirect(url_for("registro"))
        
        # Crear usuario
        user_id = db.crear_usuario(
            username=username,
            password_hash=generate_password_hash(password),
            rol="usuario",
            nombre=username,
        )
        
        if not user_id:
            flash("No se pudo registrar el usuario.")
            return redirect(url_for("registro"))
        
        # Iniciar sesión automáticamente después del registro
        session["usuario"] = {
            "id": int(user_id),
            "username": username,
            "nombre": username,
            "rol": "usuario",
        }
        flash("Perfil creado exitosamente. ¡Bienvenido!")
        return redirect(url_for("index"))
    
    return render_template("registro.html")


@app.route("/logout")
def logout():
    session.pop("usuario", None)
    session.pop("carrito", None)
    flash("Sesión cerrada.")
    return redirect(url_for("index"))

@app.route("/")
def index():
    destacados = db.listar_productos()[:3]
    return render_template("inicio.html", destacados=destacados)


@app.route("/tienda")
def tienda():
    productos = db.listar_productos()[:3]
    return render_template("index.html", productos=productos)

@app.route("/producto/<int:producto_id>")
def producto(producto_id):
    p = db.obtener_producto(producto_id)
    if not p:
        return "Producto no encontrado", 404
    return render_template("producto.html", p=p)

@app.route("/productos/nuevo", methods=["GET", "POST"])
@login_requerido
def producto_nuevo():
    if not es_admin():
        flash("Solo el administrador puede crear productos.")
        return redirect(url_for("index"))

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        descripcion = request.form.get("descripcion", "").strip()
        imagen_valor = request.form.get("imagen_url", "")
        imagen_url = normalizar_nombre_imagen(imagen_valor)
        precio = request.form.get("precio", type=float)
        stock = request.form.get("stock", type=int)

        if imagen_url is None:
            flash("La imagen debe ser un archivo local de la carpeta imagenes, no una URL externa.")
            return redirect(url_for("producto_nuevo"))

        if not nombre:
            flash("El nombre del producto es obligatorio.")
            return redirect(url_for("producto_nuevo"))

        if precio is None or precio < 0:
            flash("El precio debe ser un número mayor o igual a 0.")
            return redirect(url_for("producto_nuevo"))

        if stock is None or stock < 0:
            flash("El stock debe ser un entero mayor o igual a 0.")
            return redirect(url_for("producto_nuevo"))

        producto_id = db.crear_producto(nombre, descripcion, precio, stock, imagen_url=imagen_url)
        if not producto_id:
            flash("No se pudo guardar el producto.")
            return redirect(url_for("producto_nuevo"))

        flash("Producto creado correctamente.")
        return redirect(url_for("producto", producto_id=producto_id))

    return render_template("nuevo_producto.html")


@app.route("/producto/<int:producto_id>/imagen", methods=["POST"])
@login_requerido
def producto_actualizar_imagen(producto_id):
    if not es_admin():
        flash("Solo el administrador puede cambiar imágenes de productos.")
        return redirect(url_for("tienda"))

    p = db.obtener_producto(producto_id)
    if not p:
        flash("Producto no encontrado.")
        return redirect(url_for("tienda"))

    imagen_url = normalizar_nombre_imagen(request.form.get("imagen_url", ""))
    if imagen_url is None:
        flash("La imagen debe ser un archivo local de la carpeta imagenes, no una URL externa.")
        return redirect(request.referrer or url_for("tienda"))

    if db.actualizar_imagen_producto(producto_id, imagen_url):
        flash("Imagen del producto actualizada.")
    else:
        flash("No se pudo actualizar la imagen del producto.")

    return redirect(request.referrer or url_for("tienda"))

@app.route("/admin/productos")
@login_requerido
def admin_productos():
    if not es_admin():
        flash("Solo el administrador puede acceder a esta sección.")
        return redirect(url_for("index"))
    
    productos = db.listar_productos()
    return render_template("admin_productos.html", productos=productos)

@app.route("/producto/<int:producto_id>/editar", methods=["GET", "POST"])
@login_requerido
def producto_editar(producto_id):
    if not es_admin():
        flash("Solo el administrador puede editar productos.")
        return redirect(url_for("tienda"))

    p = db.obtener_producto(producto_id)
    if not p:
        flash("Producto no encontrado.")
        return redirect(url_for("admin_productos"))

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        descripcion = request.form.get("descripcion", "").strip()
        imagen_url = normalizar_nombre_imagen(request.form.get("imagen_url", ""))
        precio = request.form.get("precio", type=float)
        stock = request.form.get("stock", type=int)

        if not nombre:
            flash("El nombre del producto es obligatorio.")
            return redirect(url_for("producto_editar", producto_id=producto_id))

        if imagen_url is None:
            flash("La imagen debe ser un archivo local de la carpeta imagenes, no una URL externa.")
            return redirect(url_for("producto_editar", producto_id=producto_id))

        if precio is None or precio < 0:
            flash("El precio debe ser un número mayor o igual a 0.")
            return redirect(url_for("producto_editar", producto_id=producto_id))

        if stock is None or stock < 0:
            flash("El stock debe ser un entero mayor o igual a 0.")
            return redirect(url_for("producto_editar", producto_id=producto_id))

        if db.actualizar_producto(producto_id, nombre, descripcion, precio, stock, imagen_url):
            flash("Producto actualizado correctamente.")
            return redirect(url_for("admin_productos"))
        else:
            flash("No se pudo actualizar el producto.")
            return redirect(url_for("producto_editar", producto_id=producto_id))

    return render_template("editar_producto.html", p=p)

@app.route("/producto/<int:producto_id>/eliminar", methods=["POST"])
@login_requerido
def producto_eliminar(producto_id):
    if not es_admin():
        flash("Solo el administrador puede eliminar productos.")
        return redirect(url_for("tienda"))

    p = db.obtener_producto(producto_id)
    if not p:
        flash("Producto no encontrado.")
        return redirect(url_for("admin_productos"))

    if db.eliminar_producto(producto_id):
        flash(f"Producto '{p['nombre']}' eliminado correctamente.")
    else:
        flash("No se pudo eliminar el producto.")

    return redirect(url_for("admin_productos"))

@app.route("/carrito/agregar", methods=["POST"])
def carrito_agregar():
    pid = request.form.get("producto_id", type=int)
    qty = request.form.get("cantidad", type=int, default=1)

    p = db.obtener_producto(pid)
    if not p:
        flash("Producto no existe.")
        return redirect(url_for("tienda"))

    cart = carrito_session()
    cart[str(pid)] = int(cart.get(str(pid), 0)) + max(qty, 1)
    session["carrito"] = cart
    flash("Agregado al carrito.")
    return redirect(request.referrer or url_for("tienda"))

@app.route("/carrito")
def carrito():
    cart = carrito_session()
    items = []
    total = 0.0

    for pid_str, qty in cart.items():
        p = db.obtener_producto(int(pid_str))
        if not p:
            continue
        subtotal = float(p["precio"]) * int(qty)
        total += subtotal
        items.append({"p": p, "qty": int(qty), "subtotal": subtotal})

    return render_template("carrito.html", items=items, total=total)

@app.route("/carrito/quitar", methods=["POST"])
def carrito_quitar():
    pid = request.form.get("producto_id", type=int)
    cart = carrito_session()
    cart.pop(str(pid), None)
    session["carrito"] = cart
    return redirect(url_for("carrito"))

@app.route("/checkout", methods=["POST"])
def checkout():
    nombre = request.form.get("nombre", "").strip()
    email = request.form.get("email", "").strip() or None

    if not nombre:
        flash("Escribe tu nombre para continuar.")
        return redirect(url_for("carrito"))

    cart = carrito_session()
    if not cart:
        flash("Tu carrito está vacío.")
        return redirect(url_for("tienda"))

    items = [{"producto_id": int(pid), "cantidad": int(qty)} for pid, qty in cart.items()]

    pedido_id = db.crear_pedido(nombre, email, items)
    if not pedido_id:
        flash("No se pudo procesar el pedido (¿stock insuficiente?).")
        return redirect(url_for("carrito"))

    session["carrito"] = {}
    return render_template("checkout_ok.html", pedido_id=pedido_id)

if __name__ == "__main__":
    app.run(debug=True)