# app.py
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
import os
from tienda_db import BaseDatosTienda

app = Flask(__name__)
app.secret_key = "cambia-esto-por-algo-seguro"

app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

db = BaseDatosTienda(ruta="./", bd="tienda.sqlite3")
db.semilla_productos()

def carrito_session():
    # carrito: { "producto_id": cantidad }
    if "carrito" not in session:
        session["carrito"] = {}
    return session["carrito"]

@app.context_processor
def inject_user():
    user = None
    is_admin = False
    username = session.get("username")
    if username:
        user = username
        is_admin = session.get("role") == "admin"
    return dict(current_user=user, is_admin=is_admin, db=db)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "username" not in session:
            flash("Debes iniciar sesión para acceder a esta página.")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Acceso denegado. Solo admin puede entrar.")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated

@app.route("/")
def index():
    productos = db.listar_productos()
    return render_template("index.html", productos=productos, carrito=carrito_session())

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        if not username or not password:
            flash("Usuario y contraseña son obligatorios.")
            return redirect(url_for("register"))

        if db.obtener_usuario_por_username(username):
            flash("El usuario ya existe. Inicia sesión o usa otro.")
            return redirect(url_for("register"))

        password_hash = generate_password_hash(password)
        db.crear_usuario(username, password_hash, "user")
        flash("Registro exitoso. Inicia sesión.")
        return redirect(url_for("login"))

    return render_template("auth_form.html", action="register")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        user = db.obtener_usuario_por_username(username)

        if not user or not check_password_hash(user["password_hash"], password):
            flash("Credenciales inválidas.")
            return redirect(url_for("login"))

        session["username"] = user["username"]
        session["role"] = user["role"]
        flash(f"Bienvenido {user['username']}!")
        return redirect(url_for("index"))

    return render_template("auth_form.html", action="login")

@app.route("/logout")
def logout():
    session.pop("username", None)
    session.pop("role", None)
    flash("Sesión cerrada.")
    return redirect(url_for("index"))

@app.route("/producto/<int:producto_id>")
def producto(producto_id):
    p = db.obtener_producto(producto_id)
    if not p:
        return "Producto no encontrado", 404
    return render_template("producto.html", p=p, carrito=carrito_session())

@app.route("/admin/productos")
@admin_required
def admin_productos():
    productos = db.listar_productos()
    return render_template("admin_productos.html", productos=productos)

@app.route("/admin/producto/nuevo", methods=["GET", "POST"])
@admin_required
def admin_producto_nuevo():
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        descripcion = request.form.get("descripcion", "").strip()
        precio = request.form.get("precio", type=float)
        stock = request.form.get("stock", type=int)
        imagen_path = None

        # Manejar subida de imagen
        imagen_file = request.files.get('imagen')
        if imagen_file and allowed_file(imagen_file.filename):
            filename = secure_filename(imagen_file.filename)
            imagen_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            imagen_path = 'uploads/' + filename

        if not nombre or precio is None or stock is None:
            flash("Todos los campos son obligatorios.")
            return redirect(url_for("admin_producto_nuevo"))

        db.crear_producto(nombre, descripcion, precio, stock, imagen_path)
        flash("Producto creado con éxito.")
        return redirect(url_for("admin_productos"))

    return render_template("producto_form.html", action="nuevo", producto=None)

@app.route("/admin/producto/<int:producto_id>/editar", methods=["GET", "POST"])
@admin_required
def admin_producto_editar(producto_id):
    producto = db.obtener_producto(producto_id)
    if not producto:
        flash("Producto no encontrado.")
        return redirect(url_for("admin_productos"))

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        descripcion = request.form.get("descripcion", "").strip()
        precio = request.form.get("precio", type=float)
        stock = request.form.get("stock", type=int)
        imagen_path = producto['imagen']  # Mantener imagen existente por defecto

        # Manejar subida de nueva imagen
        imagen_file = request.files.get('imagen')
        if imagen_file and allowed_file(imagen_file.filename):
            filename = secure_filename(imagen_file.filename)
            imagen_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            imagen_path = 'uploads/' + filename

        if not nombre or precio is None or stock is None:
            flash("Todos los campos son obligatorios.")
            return redirect(url_for("admin_producto_editar", producto_id=producto_id))

        db.cursor.execute("""
            UPDATE productos
            SET nombre=?, descripcion=?, precio=?, stock=?, imagen=?
            WHERE id=?;
        """, (nombre, descripcion, precio, stock, imagen_path, producto_id))
        db.con.commit()

        flash("Producto actualizado.")
        return redirect(url_for("admin_productos"))

    return render_template("producto_form.html", action="editar", producto=producto)

@app.route("/admin/producto/<int:producto_id>/eliminar", methods=["POST"])
@admin_required
def admin_producto_eliminar(producto_id):
    eliminado = db.eliminar_producto(producto_id)
    if not eliminado:
        flash("No se pudo eliminar el producto. Puede que tenga pedidos asociados.")
    else:
        flash("Producto eliminado.")
    return redirect(url_for("admin_productos"))

@app.route("/admin/contenido")
@admin_required
def admin_contenido():
    contenido = db.listar_contenido()
    return render_template("admin_contenido.html", contenido=contenido)

@app.route("/admin/contenido/editar", methods=["GET", "POST"])
@admin_required
def admin_contenido_editar():
    if request.method == "POST":
        updates = {}
        for key in request.form:
            if key.startswith("contenido_"):
                clave = key[10:]  # Remove "contenido_" prefix
                texto = request.form[key].strip()
                updates[clave] = texto
        
        for clave, texto in updates.items():
            db.guardar_contenido(clave, texto)
        
        flash("Contenido actualizado.")
        return redirect(url_for("admin_contenido"))
    
    contenido = db.listar_contenido()
    return render_template("admin_contenido_editar.html", contenido=contenido)

@app.route("/carrito/agregar", methods=["POST"])
@login_required
def carrito_agregar():
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
@login_required
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
@login_required
def carrito_quitar():
    pid = request.form.get("producto_id", type=int)
    cart = carrito_session()
    cart.pop(str(pid), None)
    session["carrito"] = cart
    return redirect(url_for("carrito"))

@app.route("/checkout", methods=["POST"])
@login_required
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


    '''
    Instrucciones de ejecucion 
    
    ejecutar en terminal: pip install flask
    ejecutar en terminal: py app.py
    abrir en la web: http://127.0.0.1:5000/
    '''