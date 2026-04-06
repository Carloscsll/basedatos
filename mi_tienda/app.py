from flask import Flask, render_template, request, redirect, url_for, session, flash
from functools import wraps
from tienda_db import BaseDatosTienda
import hashlib

app = Flask(__name__)
app.secret_key = "cambia-esto-por-algo-seguro"

db = BaseDatosTienda(ruta="./", bd="tienda.sqlite3")
db.semilla_productos()

# Credenciales del admin (cambiar por valores seguros)
ADMIN_USER = "admin"
ADMIN_PASSWORD = "admin123"

# Diccionario temporal para usuarios registrados (en producción usar base de datos)
usuarios_registrados = {}

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def login_requerido(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "admin" not in session or not session["admin"]:
            flash("Debes iniciar sesión como administrador.")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def carrito_session():
    if "carrito" not in session:
        session["carrito"] = {}
    return session["carrito"]

@app.route("/")
def index():
    # Si es admin, redirige a panel admin
    if session.get("admin"):
        return redirect(url_for("admin_productos"))
    
    # Si no está logueado, redirige a login
    if "usuario" not in session:
        return redirect(url_for("login"))
    
    productos = db.listar_productos()
    return render_template("index.html", productos=productos, carrito=carrito_session(), usuario=session.get("usuario"))

@app.route("/admin/productos")
@login_requerido
def admin_productos():
    """Vista solo para admin de los productos sin carrito"""
    productos = db.listar_productos()
    return render_template("admin_productos.html", productos=productos, admin=True)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        contraseña = request.form.get("contraseña", "").strip()
        
        if usuario == ADMIN_USER and contraseña == ADMIN_PASSWORD:
            session["admin"] = True
            session["usuario"] = "Administrador"
            flash("¡Bienvenido administrador!")
            return redirect(url_for("index"))
        elif usuario in usuarios_registrados and usuarios_registrados[usuario] == hash_password(contraseña):
            session["usuario"] = usuario
            session["admin"] = False
            flash(f"¡Bienvenido {usuario}!")
            return redirect(url_for("index"))
        else:
            flash("Usuario o contraseña incorrectos.")
    
    return render_template("login.html")

@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        contraseña = request.form.get("contraseña", "").strip()
        confirmar = request.form.get("confirmar", "").strip()
        
        if not usuario or not contraseña:
            flash("Usuario y contraseña son obligatorios.")
            return redirect(url_for("registro"))
        
        if contraseña != confirmar:
            flash("Las contraseñas no coinciden.")
            return redirect(url_for("registro"))
        
        if usuario in usuarios_registrados or usuario == ADMIN_USER:
            flash("El usuario ya existe.")
            return redirect(url_for("registro"))
        
        usuarios_registrados[usuario] = hash_password(contraseña)
        flash("¡Registro exitoso! Ahora inicia sesión.")
        return redirect(url_for("login"))
    
    return render_template("registro.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Has cerrado sesión.")
    return redirect(url_for("login"))

@app.route("/producto/<int:producto_id>")
def producto(producto_id):
    if "usuario" not in session and "admin" not in session:
        return redirect(url_for("login"))
    
    p = db.obtener_producto(producto_id)
    if not p:
        return "Producto no encontrado", 404
    return render_template("producto.html", p=p, carrito=carrito_session(), admin=session.get("admin", False), usuario=session.get("usuario"))

@app.route("/producto/agregar", methods=["POST"])
@login_requerido
def producto_agregar():
    nombre = request.form.get("nombre", "").strip()
    descripcion = request.form.get("descripcion", "").strip()
    precio = request.form.get("precio", type=float)
    stock = request.form.get("stock", type=int)

    if not nombre or precio is None or stock is None:
        flash("Todos los campos son obligatorios.")
        return redirect(url_for("admin_productos"))

    db.crear_producto(nombre, descripcion, precio, stock)
    flash("Producto agregado.")
    return redirect(url_for("admin_productos"))

@app.route("/carrito/agregar", methods=["POST"])
def carrito_agregar():
    # Los admin no pueden agregar al carrito
    if session.get("admin"):
        flash("Los administradores no pueden usar el carrito.")
        return redirect(url_for("admin_productos"))
    
    # Si no está logueado como usuario, redirige a login
    if "usuario" not in session:
        return redirect(url_for("login"))
    
    pid = request.form.get("producto_id", type=int)
    qty = request.form.get("cantidad", type=int, default=1)

    p = db.obtener_producto(pid)
    if not p:
        flash("Producto no existe.")
        return redirect(url_for("index"))

    cart = carrito_session()
    cart[str(pid)] = int(cart.get(str(pid), 0)) + max(qty, 1)
    session["carrito"] = cart
    flash("Agregado al carrito.")
    return redirect(request.referrer or url_for("index"))

@app.route("/carrito")
def carrito():
    if "usuario" not in session and "admin" not in session:
        return redirect(url_for("login"))
    
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

@app.route("/producto/eliminar/<int:producto_id>", methods=["POST"])
@login_requerido
def producto_eliminar(producto_id):
    p = db.obtener_producto(producto_id)
    if not p:
        flash("Producto no encontrado.")
        return redirect(url_for("index"))
    
    db.eliminar_producto(producto_id)
    flash(f"Producto '{p['nombre']}' eliminado.")
    return redirect(url_for("index"))

@app.route("/producto/actualizar-stock/<int:producto_id>", methods=["POST"])
@login_requerido
def producto_actualizar_stock(producto_id):
    nuevo_stock = request.form.get("stock", type=int)
    
    if nuevo_stock is None or nuevo_stock < 0:
        flash("Stock inválido.")
        return redirect(url_for("index"))
    
    p = db.obtener_producto(producto_id)
    if not p:
        flash("Producto no encontrado.")
        return redirect(url_for("index"))
    
    db.actualizar_stock(producto_id, nuevo_stock)
    flash(f"Stock de '{p['nombre']}' actualizado a {nuevo_stock}.")
    return redirect(url_for("index"))

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
        return redirect(url_for("index"))

    items = [{"producto_id": int(pid), "cantidad": int(qty)} for pid, qty in cart.items()]

    pedido_id = db.crear_pedido(nombre, email, items)
    if not pedido_id:
        flash("No se pudo procesar el pedido (¿stock insuficiente?).")
        return redirect(url_for("carrito"))

    session["carrito"] = {}
    return render_template("checkout_ok.html", pedido_id=pedido_id)

if __name__ == "__main__":
    app.run(debug=True)