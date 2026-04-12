# Importacion de librerias necesarias
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session, Response
import csv
import io
import re
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__, template_folder=".", static_folder=".", static_url_path="")
app.secret_key = "1fedfsfs@@./addfs12456d"
DB_PATH = "app.db"
ADMIN_EMAIL = "admin@managelist.com"
ADMIN_NAME = "Administrator"
ADMIN_PASSWORD = "Admin12345!"

datos = [10, 20, 30]


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def is_admin_session():
    return bool(session.get("is_admin", False))


def is_authenticated():
    return bool(session.get("display_name"))


def validate_device_payload(device_name, mac_address, location, assigned_user, ip_address, status):
    if not device_name or len(device_name) > 80:
        return "Device invalido"

    if not re.fullmatch(r"[A-F0-9]{12}", mac_address):
        return "MAC invalida. Usa 12 caracteres hexadecimales sin separadores"

    if not location or len(location) > 80:
        return "Ubicacion invalida"

    if not assigned_user or len(assigned_user) > 80:
        return "Usuario asignado invalido"

    if not re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", ip_address):
        return "IP invalida"

    octets = [int(part) for part in ip_address.split(".")]
    if any(part > 255 for part in octets):
        return "IP invalida"

    if status not in {"Online", "Offline"}:
        return "Status invalido"

    return None


def validate_server_payload(server_name, hostname, operating_system, environment, role_name, status):
    if not server_name or len(server_name) > 80:
        return "Server invalido"
    if not hostname or len(hostname) > 80:
        return "Hostname invalido"
    if not operating_system or len(operating_system) > 80:
        return "Sistema operativo invalido"
    if environment not in {"Production", "Testing"}:
        return "Ambiente invalido"
    if not role_name or len(role_name) > 80:
        return "Rol invalido"
    if status not in {"Online", "Offline"}:
        return "Status invalido"
    return None


def validate_nfv_payload(asset_name, asset_type, vendor, model, management_ip, status):
    if not asset_name or len(asset_name) > 80:
        return "Activo NFV invalido"
    if asset_type not in {"Router", "Switch"}:
        return "Tipo de activo invalido"
    if not vendor or len(vendor) > 80:
        return "Vendor invalido"
    if not model or len(model) > 80:
        return "Modelo invalido"
    if not re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", management_ip):
        return "IP de gestion invalida"

    octets = [int(part) for part in management_ip.split(".")]
    if any(part > 255 for part in octets):
        return "IP de gestion invalida"

    if status not in {"Online", "Offline"}:
        return "Status invalido"
    return None


def validate_user_payload(nombre, email, password, password_required=False):
    if not nombre or len(nombre) > 80:
        return "Nombre invalido"
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return "Email invalido"
    if email == ADMIN_EMAIL:
        return "Ese correo es reservado para el administrador"
    if password_required and len(password) < 8:
        return "La contrasena debe tener al menos 8 caracteres"
    if password and len(password) < 8:
        return "La contrasena debe tener al menos 8 caracteres"
    return None


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_name TEXT NOT NULL,
                mac_address TEXT NOT NULL UNIQUE,
                location TEXT NOT NULL,
                assigned_user TEXT NOT NULL,
                ip_address TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('Online', 'Offline'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS servers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_name TEXT NOT NULL,
                hostname TEXT NOT NULL,
                operating_system TEXT NOT NULL,
                environment TEXT NOT NULL CHECK(environment IN ('Production', 'Testing')),
                role_name TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('Online', 'Offline'))
            )
        """)
        server_columns = [row[1] for row in conn.execute("PRAGMA table_info(servers)").fetchall()]
        if "endpoint_name" in server_columns and "hostname" not in server_columns:
            conn.execute("ALTER TABLE servers RENAME COLUMN endpoint_name TO hostname")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS nfv_assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_name TEXT NOT NULL,
                asset_type TEXT NOT NULL CHECK(asset_type IN ('Router', 'Switch')),
                vendor TEXT NOT NULL,
                model TEXT NOT NULL,
                management_ip TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('Online', 'Offline'))
            )
        """)
        conn.execute(
            "INSERT OR IGNORE INTO users (nombre, email, password_hash) VALUES (?, ?, ?)",
            (ADMIN_NAME, ADMIN_EMAIL, generate_password_hash(ADMIN_PASSWORD)),
        )
        conn.execute(
            "UPDATE users SET nombre = ?, password_hash = ? WHERE email = ?",
            (ADMIN_NAME, generate_password_hash(ADMIN_PASSWORD), ADMIN_EMAIL),
        )


@app.route("/")
def index():
    if not is_authenticated():
        flash("Debes iniciar sesion para ver el dashboard")
        return redirect(url_for("logging_page"))

    display_name = session.get("display_name", "Invitado")
    edit_device_id = request.args.get("edit_device", type=int)
    edit_server_id = request.args.get("edit_server", type=int)
    edit_nfv_id = request.args.get("edit_nfv", type=int)
    edit_user_id = request.args.get("edit_user", type=int)
    search_query = request.args.get("device_q", "").strip()
    status_filter = request.args.get("device_status", "").strip()
    server_query = request.args.get("server_q", "").strip()
    server_status = request.args.get("server_status", "").strip()
    nfv_query = request.args.get("nfv_q", "").strip()
    nfv_status = request.args.get("nfv_status", "").strip()
    nfv_type = request.args.get("nfv_type", "").strip()

    where_clauses = []
    params = []

    if search_query:
        like_query = f"%{search_query}%"
        where_clauses.append(
            """
            (
                device_name LIKE ?
                OR mac_address LIKE ?
                OR assigned_user LIKE ?
                OR ip_address LIKE ?
            )
            """
        )
        params.extend([like_query, like_query, like_query, like_query])

    if status_filter in {"Online", "Offline"}:
        where_clauses.append("status = ?")
        params.append(status_filter)

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    server_where = []
    server_params = []
    if server_query:
        like_query = f"%{server_query}%"
        server_where.append(
            """
            (
                server_name LIKE ?
                OR hostname LIKE ?
                OR operating_system LIKE ?
                OR role_name LIKE ?
            )
            """
        )
        server_params.extend([like_query, like_query, like_query, like_query])
    if server_status in {"Online", "Offline"}:
        server_where.append("status = ?")
        server_params.append(server_status)
    server_where_sql = ""
    if server_where:
        server_where_sql = "WHERE " + " AND ".join(server_where)

    nfv_where = []
    nfv_params = []
    if nfv_query:
        like_query = f"%{nfv_query}%"
        nfv_where.append(
            """
            (
                asset_name LIKE ?
                OR vendor LIKE ?
                OR model LIKE ?
                OR management_ip LIKE ?
            )
            """
        )
        nfv_params.extend([like_query, like_query, like_query, like_query])
    if nfv_type in {"Router", "Switch"}:
        nfv_where.append("asset_type = ?")
        nfv_params.append(nfv_type)
    if nfv_status in {"Online", "Offline"}:
        nfv_where.append("status = ?")
        nfv_params.append(nfv_status)
    nfv_where_sql = ""
    if nfv_where:
        nfv_where_sql = "WHERE " + " AND ".join(nfv_where)

    with get_db_connection() as conn:
        devices = conn.execute(
            f"""
            SELECT id, device_name, mac_address, location, assigned_user, ip_address, status
            FROM devices
            {where_sql}
            ORDER BY id DESC
            """,
            params,
        ).fetchall()
        edit_device = None
        if edit_device_id:
            edit_device = conn.execute(
                """
                SELECT id, device_name, mac_address, location, assigned_user, ip_address, status
                FROM devices
                WHERE id = ?
                """,
                (edit_device_id,),
            ).fetchone()
        servers = conn.execute(
            f"""
            SELECT id, server_name, hostname, operating_system, environment, role_name, status
            FROM servers
            {server_where_sql}
            ORDER BY id DESC
            """,
            server_params,
        ).fetchall()
        edit_server = None
        if edit_server_id:
            edit_server = conn.execute(
                """
                SELECT id, server_name, hostname, operating_system, environment, role_name, status
                FROM servers
                WHERE id = ?
                """,
                (edit_server_id,),
            ).fetchone()
        nfv_items = conn.execute(
            f"""
            SELECT id, asset_name, asset_type, vendor, model, management_ip, status
            FROM nfv_assets
            {nfv_where_sql}
            ORDER BY id DESC
            """,
            nfv_params,
        ).fetchall()
        edit_nfv = None
        if edit_nfv_id:
            edit_nfv = conn.execute(
                """
                SELECT id, asset_name, asset_type, vendor, model, management_ip, status
                FROM nfv_assets
                WHERE id = ?
                """,
                (edit_nfv_id,),
            ).fetchone()
        users = conn.execute(
            """
            SELECT id, nombre, email
            FROM users
            ORDER BY CASE WHEN email = ? THEN 0 ELSE 1 END, id ASC
            """,
            (ADMIN_EMAIL,),
        ).fetchall()
        edit_user = None
        if edit_user_id:
            edit_user = conn.execute(
                """
                SELECT id, nombre, email
                FROM users
                WHERE id = ?
                """,
                (edit_user_id,),
            ).fetchone()

    online_count = sum(1 for device in devices if device["status"] == "Online")
    offline_count = sum(1 for device in devices if device["status"] == "Offline")
    server_online_count = sum(1 for server in servers if server["status"] == "Online")
    server_offline_count = sum(1 for server in servers if server["status"] == "Offline")
    nfv_router_count = sum(1 for item in nfv_items if item["asset_type"] == "Router")
    nfv_switch_count = sum(1 for item in nfv_items if item["asset_type"] == "Switch")

    return render_template(
        "main.html",
        display_name=display_name,
        devices=devices,
        online_count=online_count,
        offline_count=offline_count,
        server_online_count=server_online_count,
        server_offline_count=server_offline_count,
        nfv_router_count=nfv_router_count,
        nfv_switch_count=nfv_switch_count,
        is_admin=is_admin_session(),
        edit_device=edit_device,
        device_q=search_query,
        device_status=status_filter,
        servers=servers,
        edit_server=edit_server,
        server_q=server_query,
        server_status=server_status,
        nfv_items=nfv_items,
        edit_nfv=edit_nfv,
        nfv_q=nfv_query,
        nfv_status=nfv_status,
        nfv_type=nfv_type,
        users=users,
        edit_user=edit_user,
    )


@app.route("/datos")
def obtener_datos():
    return jsonify(datos)


@app.route("/cambiar")
def cambiar():
    global datos
    datos = [5, 50, 15]
    return jsonify(datos)


@app.route("/download/inventory")
def download_inventory():
    if not is_authenticated():
        flash("Debes iniciar sesion para descargar el inventario")
        return redirect(url_for("logging_page"))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["section", "name", "type_or_role", "owner_or_vendor", "ip_or_hostname", "status"])

    with get_db_connection() as conn:
        devices = conn.execute(
            """
            SELECT device_name, assigned_user, ip_address, status
            FROM devices
            ORDER BY id ASC
            """
        ).fetchall()
        for device in devices:
            writer.writerow([
                "device",
                device["device_name"],
                "endpoint",
                device["assigned_user"],
                device["ip_address"],
                device["status"],
            ])

        servers = conn.execute(
            """
            SELECT server_name, role_name, hostname, status
            FROM servers
            ORDER BY id ASC
            """
        ).fetchall()
        for server in servers:
            writer.writerow([
                "server",
                server["server_name"],
                server["role_name"],
                "infrastructure",
                server["hostname"],
                server["status"],
            ])

        nfv_items = conn.execute(
            """
            SELECT asset_name, asset_type, vendor, management_ip, status
            FROM nfv_assets
            ORDER BY id ASC
            """
        ).fetchall()
        for item in nfv_items:
            writer.writerow([
                "nfv",
                item["asset_name"],
                item["asset_type"],
                item["vendor"],
                item["management_ip"],
                item["status"],
            ])

        if is_admin_session():
            users = conn.execute(
                """
                SELECT nombre, email
                FROM users
                ORDER BY id ASC
                """
            ).fetchall()
            for user in users:
                writer.writerow([
                    "user",
                    user["nombre"],
                    "account",
                    user["email"],
                    "",
                    "active",
                ])

    csv_data = output.getvalue()
    output.close()

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=managelist_inventory.csv"},
    )


def build_csv_response(filename, header, rows):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(header)
    writer.writerows(rows)
    csv_data = output.getvalue()
    output.close()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.route("/download/devices")
def download_devices():
    if not is_authenticated():
        flash("Debes iniciar sesion para descargar dispositivos")
        return redirect(url_for("logging_page"))

    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT device_name, mac_address, location, assigned_user, ip_address, status
            FROM devices
            ORDER BY id ASC
            """
        ).fetchall()

    return build_csv_response(
        "devices.csv",
        ["device_name", "mac_address", "location", "assigned_user", "ip_address", "status"],
        rows,
    )


@app.route("/download/servers")
def download_servers():
    if not is_authenticated():
        flash("Debes iniciar sesion para descargar servidores")
        return redirect(url_for("logging_page"))

    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT server_name, hostname, operating_system, environment, role_name, status
            FROM servers
            ORDER BY id ASC
            """
        ).fetchall()

    return build_csv_response(
        "servers.csv",
        ["server_name", "hostname", "operating_system", "environment", "role_name", "status"],
        rows,
    )


@app.route("/download/nfv")
def download_nfv():
    if not is_authenticated():
        flash("Debes iniciar sesion para descargar activos NFV")
        return redirect(url_for("logging_page"))

    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT asset_name, asset_type, vendor, model, management_ip, status
            FROM nfv_assets
            ORDER BY id ASC
            """
        ).fetchall()

    return build_csv_response(
        "nfv_assets.csv",
        ["asset_name", "asset_type", "vendor", "model", "management_ip", "status"],
        rows,
    )


@app.route("/download/users")
def download_users():
    if not is_authenticated():
        flash("Debes iniciar sesion para descargar usuarios")
        return redirect(url_for("logging_page"))

    if not is_admin_session():
        flash("Solo el administrador puede descargar usuarios")
        return redirect(url_for("index", _anchor="dashboard"))

    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT nombre, email
            FROM users
            ORDER BY id ASC
            """
        ).fetchall()

    return build_csv_response(
        "users.csv",
        ["nombre", "email"],
        rows,
    )


@app.route("/logging")
def logging_page():
    if is_authenticated():
        return redirect(url_for("index"))
    return render_template("log.html")


@app.route("/crear_cuenta")
def crear_page():
    flash("La creacion de cuentas solo la puede hacer el administrador desde el dashboard")
    if is_authenticated():
        return redirect(url_for("index", _anchor="dashboard"))
    return redirect(url_for("logging_page"))


@app.route("/submit", methods=["POST"])
def submit():
    flash("La creacion de cuentas solo la puede hacer el administrador desde el dashboard")
    if is_authenticated():
        return redirect(url_for("index", _anchor="dashboard"))
    return redirect(url_for("logging_page"))


@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        flash("Email invalido")
        return redirect(url_for("logging_page"))

    if not password:
        flash("Contrasena requerida")
        return redirect(url_for("logging_page"))

    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT nombre, email, password_hash FROM users WHERE email = ?",
            (email,),
        ).fetchone()

    if row is None or not check_password_hash(row[2], password):
        flash("Credenciales invalidas")
        return redirect(url_for("logging_page"))

    session["display_name"] = ADMIN_NAME if row[1] == ADMIN_EMAIL else row[0]
    session["is_admin"] = row[1] == ADMIN_EMAIL
    flash("Login exitoso")
    return redirect(url_for("index"))


@app.route("/users/create", methods=["POST"])
def create_user():
    if not is_admin_session():
        flash("Solo el administrador puede registrar usuarios")
        return redirect(url_for("index", _anchor="dashboard"))

    nombre = request.form.get("nombre", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    validation_error = validate_user_payload(nombre, email, password, password_required=True)
    if validation_error:
        flash(validation_error)
        return redirect(url_for("index", _anchor="dashboard"))

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO users (nombre, email, password_hash) VALUES (?, ?, ?)",
                (nombre, email, generate_password_hash(password)),
            )
    except sqlite3.IntegrityError:
        flash("Ese correo ya esta registrado")
        return redirect(url_for("index", _anchor="dashboard"))

    flash("Usuario creado correctamente")
    return redirect(url_for("index", _anchor="dashboard"))


@app.route("/users/update/<int:user_id>", methods=["POST"])
def update_user(user_id):
    if not is_admin_session():
        flash("Solo el administrador puede modificar usuarios")
        return redirect(url_for("index", _anchor="dashboard"))

    nombre = request.form.get("nombre", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    with sqlite3.connect(DB_PATH) as conn:
        current_user = conn.execute(
            "SELECT email FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

        if current_user is None:
            flash("Usuario no encontrado")
            return redirect(url_for("index", _anchor="dashboard"))

        if current_user[0] == ADMIN_EMAIL:
            flash("La cuenta del administrador no se puede editar desde aqui")
            return redirect(url_for("index", _anchor="dashboard"))

    validation_error = validate_user_payload(nombre, email, password, password_required=False)
    if validation_error:
        flash(validation_error)
        return redirect(url_for("index", _anchor="dashboard", edit_user=user_id))

    try:
        with sqlite3.connect(DB_PATH) as conn:
            if password:
                conn.execute(
                    """
                    UPDATE users
                    SET nombre = ?, email = ?, password_hash = ?
                    WHERE id = ?
                    """,
                    (nombre, email, generate_password_hash(password), user_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE users
                    SET nombre = ?, email = ?
                    WHERE id = ?
                    """,
                    (nombre, email, user_id),
                )
    except sqlite3.IntegrityError:
        flash("Ese correo ya esta registrado")
        return redirect(url_for("index", _anchor="dashboard", edit_user=user_id))

    flash("Usuario actualizado correctamente")
    return redirect(url_for("index", _anchor="dashboard"))


@app.route("/users/delete/<int:user_id>", methods=["POST"])
def delete_user(user_id):
    if not is_admin_session():
        flash("Solo el administrador puede eliminar usuarios")
        return redirect(url_for("index", _anchor="dashboard"))

    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT email FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

        if row is None:
            flash("Usuario no encontrado")
            return redirect(url_for("index", _anchor="dashboard"))

        if row[0] == ADMIN_EMAIL:
            flash("La cuenta del administrador no se puede eliminar")
            return redirect(url_for("index", _anchor="dashboard"))

        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))

    flash("Usuario eliminado")
    return redirect(url_for("index", _anchor="dashboard"))

@app.route("/devices/create", methods=["POST"])
def create_device():
    if not is_admin_session():
        flash("Solo el administrador puede registrar dispositivos")
        return redirect(url_for("index", _anchor="devices"))

    device_name = request.form.get("device_name", "").strip()
    mac_address = request.form.get("mac_address", "").strip().upper()
    location = request.form.get("location", "").strip()
    assigned_user = request.form.get("assigned_user", "").strip()
    ip_address = request.form.get("ip_address", "").strip()
    status = request.form.get("status", "").strip()

    validation_error = validate_device_payload(
        device_name, mac_address, location, assigned_user, ip_address, status
    )
    if validation_error:
        flash(validation_error)
        return redirect(url_for("index", _anchor="devices"))

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO devices (device_name, mac_address, location, assigned_user, ip_address, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (device_name, mac_address, location, assigned_user, ip_address, status),
            )
    except sqlite3.IntegrityError:
        flash("La MAC ya existe en la tabla")
        return redirect(url_for("index", _anchor="devices"))

    flash("Dispositivo agregado correctamente")
    return redirect(url_for("index", _anchor="devices"))


@app.route("/devices/update/<int:device_id>", methods=["POST"])
def update_device(device_id):
    if not is_admin_session():
        flash("Solo el administrador puede modificar dispositivos")
        return redirect(url_for("index", _anchor="devices"))

    device_name = request.form.get("device_name", "").strip()
    mac_address = request.form.get("mac_address", "").strip().upper()
    location = request.form.get("location", "").strip()
    assigned_user = request.form.get("assigned_user", "").strip()
    ip_address = request.form.get("ip_address", "").strip()
    status = request.form.get("status", "").strip()

    validation_error = validate_device_payload(
        device_name, mac_address, location, assigned_user, ip_address, status
    )
    if validation_error:
        flash(validation_error)
        return redirect(url_for("index", _anchor="devices", edit_device=device_id))

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                UPDATE devices
                SET device_name = ?, mac_address = ?, location = ?, assigned_user = ?, ip_address = ?, status = ?
                WHERE id = ?
                """,
                (device_name, mac_address, location, assigned_user, ip_address, status, device_id),
            )
    except sqlite3.IntegrityError:
        flash("La MAC ya existe en la tabla")
        return redirect(url_for("index", _anchor="devices", edit_device=device_id))

    flash("Dispositivo actualizado correctamente")
    return redirect(url_for("index", _anchor="devices"))


@app.route("/devices/delete/<int:device_id>", methods=["POST"])
def delete_device(device_id):
    if not is_admin_session():
        flash("Solo el administrador puede eliminar dispositivos")
        return redirect(url_for("index", _anchor="devices"))

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM devices WHERE id = ?", (device_id,))

    flash("Dispositivo eliminado")
    return redirect(url_for("index", _anchor="devices"))


@app.route("/servers/create", methods=["POST"])
def create_server():
    if not is_admin_session():
        flash("Solo el administrador puede registrar servidores")
        return redirect(url_for("index", _anchor="server"))

    server_name = request.form.get("server_name", "").strip()
    hostname = request.form.get("hostname", "").strip()
    operating_system = request.form.get("operating_system", "").strip()
    environment = request.form.get("environment", "").strip()
    role_name = request.form.get("role_name", "").strip()
    status = request.form.get("status", "").strip()

    validation_error = validate_server_payload(
        server_name, hostname, operating_system, environment, role_name, status
    )
    if validation_error:
        flash(validation_error)
        return redirect(url_for("index", _anchor="server"))

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO servers (server_name, hostname, operating_system, environment, role_name, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (server_name, hostname, operating_system, environment, role_name, status),
        )

    flash("Servidor agregado correctamente")
    return redirect(url_for("index", _anchor="server"))


@app.route("/servers/update/<int:server_id>", methods=["POST"])
def update_server(server_id):
    if not is_admin_session():
        flash("Solo el administrador puede modificar servidores")
        return redirect(url_for("index", _anchor="server"))

    server_name = request.form.get("server_name", "").strip()
    hostname = request.form.get("hostname", "").strip()
    operating_system = request.form.get("operating_system", "").strip()
    environment = request.form.get("environment", "").strip()
    role_name = request.form.get("role_name", "").strip()
    status = request.form.get("status", "").strip()

    validation_error = validate_server_payload(
        server_name, hostname, operating_system, environment, role_name, status
    )
    if validation_error:
        flash(validation_error)
        return redirect(url_for("index", _anchor="server", edit_server=server_id))

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            UPDATE servers
            SET server_name = ?, hostname = ?, operating_system = ?, environment = ?, role_name = ?, status = ?
            WHERE id = ?
            """,
            (server_name, hostname, operating_system, environment, role_name, status, server_id),
        )

    flash("Servidor actualizado correctamente")
    return redirect(url_for("index", _anchor="server"))


@app.route("/servers/delete/<int:server_id>", methods=["POST"])
def delete_server(server_id):
    if not is_admin_session():
        flash("Solo el administrador puede eliminar servidores")
        return redirect(url_for("index", _anchor="server"))

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM servers WHERE id = ?", (server_id,))

    flash("Servidor eliminado")
    return redirect(url_for("index", _anchor="server"))


@app.route("/nfv/create", methods=["POST"])
def create_nfv():
    if not is_admin_session():
        flash("Solo el administrador puede registrar activos NFV")
        return redirect(url_for("index", _anchor="devices-software"))

    asset_name = request.form.get("asset_name", "").strip()
    asset_type = request.form.get("asset_type", "").strip()
    vendor = request.form.get("vendor", "").strip()
    model = request.form.get("model", "").strip()
    management_ip = request.form.get("management_ip", "").strip()
    status = request.form.get("status", "").strip()

    validation_error = validate_nfv_payload(
        asset_name, asset_type, vendor, model, management_ip, status
    )
    if validation_error:
        flash(validation_error)
        return redirect(url_for("index", _anchor="devices-software"))

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO nfv_assets (asset_name, asset_type, vendor, model, management_ip, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (asset_name, asset_type, vendor, model, management_ip, status),
        )

    flash("Activo NFV agregado correctamente")
    return redirect(url_for("index", _anchor="devices-software"))


@app.route("/nfv/update/<int:nfv_id>", methods=["POST"])
def update_nfv(nfv_id):
    if not is_admin_session():
        flash("Solo el administrador puede modificar activos NFV")
        return redirect(url_for("index", _anchor="devices-software"))

    asset_name = request.form.get("asset_name", "").strip()
    asset_type = request.form.get("asset_type", "").strip()
    vendor = request.form.get("vendor", "").strip()
    model = request.form.get("model", "").strip()
    management_ip = request.form.get("management_ip", "").strip()
    status = request.form.get("status", "").strip()

    validation_error = validate_nfv_payload(
        asset_name, asset_type, vendor, model, management_ip, status
    )
    if validation_error:
        flash(validation_error)
        return redirect(url_for("index", _anchor="devices-software", edit_nfv=nfv_id))

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            UPDATE nfv_assets
            SET asset_name = ?, asset_type = ?, vendor = ?, model = ?, management_ip = ?, status = ?
            WHERE id = ?
            """,
            (asset_name, asset_type, vendor, model, management_ip, status, nfv_id),
        )

    flash("Activo NFV actualizado correctamente")
    return redirect(url_for("index", _anchor="devices-software"))


@app.route("/nfv/delete/<int:nfv_id>", methods=["POST"])
def delete_nfv(nfv_id):
    if not is_admin_session():
        flash("Solo el administrador puede eliminar activos NFV")
        return redirect(url_for("index", _anchor="devices-software"))

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM nfv_assets WHERE id = ?", (nfv_id,))

    flash("Activo NFV eliminado")
    return redirect(url_for("index", _anchor="devices-software"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("logging_page"))


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0" , port=5000, debug=True)

