from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, session
import os
import secrets
from werkzeug.utils import secure_filename
from flask_migrate import Migrate
from datetime import datetime, date, timedelta
import base64
import re
import time
from collections import defaultdict

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Generar SECRET_KEY segura
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or secrets.token_hex(32)

# Configuraciones de seguridad
app.config['SESSION_COOKIE_SECURE'] = False  # Cambiar a True en producción con HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)  # Sesión expira en 2 horas

# Rate limiting simple
login_attempts = defaultdict(list)
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_TIME = 300  # 5 minutos

from models import db, Employee, Attendance, WorkSchedule, AdminUser

import pandas as pd

# Funciones de validación de seguridad
def validate_employee_id(employee_id):
    """Validar formato de ID de empleado"""
    if not employee_id or len(employee_id) > 20:
        return False
    return re.match(r'^[A-Za-z0-9_-]+$', employee_id) is not None

def validate_email(email):
    """Validar formato de email"""
    if not email or len(email) > 120:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_name(name):
    """Validar nombres (solo letras, espacios y acentos)"""
    if not name or len(name) > 100:
        return False
    pattern = r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$'
    return re.match(pattern, name) is not None

def is_rate_limited(ip_address):
    """Verificar si una IP está limitada por intentos de login"""
    now = time.time()
    attempts = login_attempts[ip_address]
    
    # Limpiar intentos antiguos
    attempts[:] = [attempt for attempt in attempts if now - attempt < LOCKOUT_TIME]
    
    return len(attempts) >= MAX_LOGIN_ATTEMPTS

def add_login_attempt(ip_address):
    """Registrar un intento de login fallido"""
    login_attempts[ip_address].append(time.time())

def generate_csrf_token():
    """Generar token CSRF"""
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(16)
    return session['csrf_token']

def validate_csrf_token(token):
    """Validar token CSRF"""
    return token and session.get('csrf_token') == token

# Agregar función al contexto de templates
@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf_token())

# Agregar encabezados de seguridad
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    # CSP deshabilitada temporalmente para verificar estilos
    # Una vez que confirmes que los estilos funcionan, puedes descomentar esto:
    """
    if app.debug:
        # Modo desarrollo - CSP muy permisiva
        response.headers['Content-Security-Policy'] = (
            "default-src 'self' 'unsafe-inline' 'unsafe-eval' *; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' *; "
            "style-src 'self' 'unsafe-inline' *; "
            "font-src 'self' *; "
            "img-src 'self' data: blob: *; "
            "connect-src 'self' *;"
        )
    """
    
    return response

# Decorador para requerir login admin
def admin_login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_user_id'):
            flash('Debes iniciar sesión como administrador.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Verificar rate limiting
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        if is_rate_limited(client_ip):
            flash('Demasiados intentos de login. Intenta de nuevo en 5 minutos.', 'danger')
            return render_template('login.html')
        
        # Validar CSRF token
        csrf_token = request.form.get('csrf_token')
        if not validate_csrf_token(csrf_token):
            flash('Token de seguridad inválido. Intenta de nuevo.', 'danger')
            return render_template('login.html')
        
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        # Validación básica
        if not username or not password:
            flash('Usuario y contraseña son obligatorios.', 'danger')
            return render_template('login.html')
        
        if len(username) > 50 or len(password) > 128:
            flash('Usuario o contraseña demasiado largos.', 'danger')
            return render_template('login.html')
        
        # Verificar credenciales
        user = AdminUser.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['admin_user_id'] = user.id
            session['admin_username'] = user.username
            session.permanent = True
            
            # Limpiar intentos fallidos
            if client_ip in login_attempts:
                del login_attempts[client_ip]
            
            flash('Bienvenido, administrador.', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            # Registrar intento fallido
            add_login_attempt(client_ip)
            flash('Usuario o contraseña incorrectos.', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('admin_user_id', None)
    session.pop('admin_username', None)
    flash('Sesión cerrada.', 'info')
    return redirect(url_for('scanner'))


@app.route('/admin')
@admin_login_required
def admin_dashboard():
    today = date.today()
    total_empleados = Employee.query.filter_by(is_active=True).count()
    total_asistencias = Attendance.query.filter_by(date=today, attendance_type='entrada').count()
    llegadas_tarde = Attendance.query.filter_by(date=today, attendance_type='entrada', is_late=True).count()
    porcentaje_asistencia = 0
    if total_empleados > 0:
        porcentaje_asistencia = round((total_asistencias / total_empleados) * 100, 2)
    return render_template('admin_dashboard.html',
        total_empleados=total_empleados,
        total_asistencias=total_asistencias,
        llegadas_tarde=llegadas_tarde,
        porcentaje_asistencia=porcentaje_asistencia)


@app.route("/export_excel", methods=["POST"])
def export_excel():
    start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
    end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()
    employee_id = request.form.get('employee_id')
    
    if employee_id:
        # Para reporte individual, usar listado completo
        from reports import generate_individual_report
        summary, error = generate_individual_report(start_date, end_date, employee_id)
    else:
        # Para reporte general, usar listado detallado de todos los empleados
        from reports import generate_general_detailed_report
        summary, error = generate_general_detailed_report(start_date, end_date)
    
    # Filtrar la columna attendance_id para el Excel
    if summary is not None and 'attendance_id' in summary.columns:
        summary = summary.drop(['attendance_id'], axis=1)
    
    filename = "reporte_asistencia.xlsx"
    filepath = f"static/{filename}"
    summary.to_excel(filepath, index=False)
    return send_file(filepath, as_attachment=True, download_name=filename)
db.init_app(app)
migrate = Migrate(app, db)

from qr_generator import generate_qr_code
from reports import generate_daily_report, generate_attendance_chart, generate_department_chart, generate_pdf_report, get_attendance_data

@app.route('/')
def index():
    if session.get('admin_user_id'):
        today = date.today()
        total_empleados = Employee.query.filter_by(is_active=True).count()
        total_asistencias = Attendance.query.filter_by(date=today, attendance_type='entrada').count()
        llegadas_tarde = Attendance.query.filter_by(date=today, attendance_type='entrada', is_late=True).count()
        porcentaje_asistencia = 0
        if total_empleados > 0:
            porcentaje_asistencia = round((total_asistencias / total_empleados) * 100, 2)
        return render_template('admin_dashboard.html',
            total_empleados=total_empleados,
            total_asistencias=total_asistencias,
            llegadas_tarde=llegadas_tarde,
            porcentaje_asistencia=porcentaje_asistencia)
    else:
        return redirect(url_for('scanner'))
    if session.get('admin_user_id'):
        today = date.today()
        total_empleados = Employee.query.filter_by(is_active=True).count()
        total_asistencias = Attendance.query.filter_by(date=today, attendance_type='entrada').count()
        llegadas_tarde = Attendance.query.filter_by(date=today, attendance_type='entrada', is_late=True).count()
        porcentaje_asistencia = 0
        if total_empleados > 0:
            porcentaje_asistencia = round((total_asistencias / total_empleados) * 100, 2)
        return render_template('admin_dashboard.html',
            total_empleados=total_empleados,
            total_asistencias=total_asistencias,
            llegadas_tarde=llegadas_tarde,
            porcentaje_asistencia=porcentaje_asistencia)
    else:
        return redirect(url_for('scanner'))
@app.route("/register_attendance", methods=["POST"])
def register_attendance():
    try:
        data = request.get_json()
        employee_id = data.get('employee_id')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        address = data.get('address')
        if not employee_id:
            return jsonify({'success': False, 'message': 'ID de empleado requerido'})
        employee = Employee.query.filter_by(employee_id=employee_id, is_active=True).first()
        if not employee:
            return jsonify({'success': False, 'message': f'Empleado {employee_id} no encontrado o inactivo'})
        today = date.today()
        entradas_hoy = Attendance.query.filter_by(employee_id=employee_id, date=today, attendance_type='entrada').count()
        salidas_hoy = Attendance.query.filter_by(employee_id=employee_id, date=today, attendance_type='salida').count()
        ahora = datetime.now()
        from models import WorkSchedule
        dia_semana = ahora.weekday()
        ws = WorkSchedule.query.filter_by(employee_id=employee_id, day_of_week=dia_semana, is_active=True).first()
        if ws:
            hora_entrada_permitida = ahora.replace(hour=ws.start_time.hour, minute=ws.start_time.minute, second=0, microsecond=0)
        else:
            hora_entrada_permitida = ahora.replace(hour=8, minute=0, second=0, microsecond=0)
        if entradas_hoy == 0:
            if ahora < hora_entrada_permitida:
                return jsonify({'success': False, 'message': f'No se puede marcar asistencia antes de la hora permitida ({hora_entrada_permitida.strftime("%H:%M")}).'})
            attendance_type = 'entrada'
            is_late = ahora > hora_entrada_permitida
            new_attendance = Attendance(
                employee_id=employee_id,
                attendance_type=attendance_type,
                timestamp=ahora,
                date=today,
                is_late=is_late,
                latitude=latitude,
                longitude=longitude,
                address=address
            )
            db.session.add(new_attendance)
            db.session.commit()
            return jsonify({
                'success': True,
                'message': '¡Se registró tu asistencia correctamente!',
                'is_late': is_late,
                'attendance_type': attendance_type
            })
        elif entradas_hoy == 1 and salidas_hoy == 0:
            attendance_type = 'salida'
            is_late = False
            new_attendance = Attendance(
                employee_id=employee_id,
                attendance_type=attendance_type,
                timestamp=ahora,
                date=today,
                is_late=is_late,
                latitude=latitude,
                longitude=longitude,
                address=address
            )
            db.session.add(new_attendance)
            db.session.commit()
            return jsonify({
                'success': True,
                'message': '¡Se registró tu salida correctamente!',
                'is_late': is_late,
                'attendance_type': attendance_type
            })
        else:
            return jsonify({'success': False, 'message': 'No puedes volver a marcar otra vez asistencia porque ya se marcó para hoy.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error interno: {str(e)}'})
    
    if error:
        flash(error, 'error')
        return render_template("reports.html", 
                             today=today.strftime('%Y-%m-%d'),
                             week_ago=week_ago.strftime('%Y-%m-%d'),
                             employees=employees)
    
    return render_template("reports.html",
                         today=today.strftime('%Y-%m-%d'),
                         week_ago=week_ago.strftime('%Y-%m-%d'),
                         employees=employees,
                         report_data=report_data,
                         report_title=f"Reporte Diario - {report_date.strftime('%d/%m/%Y')}",
                         start_date=report_date.strftime('%Y-%m-%d'),
                         end_date=report_date.strftime('%Y-%m-%d'))

@app.route("/daily_report", methods=["POST"])
def daily_report():
    report_date = datetime.strptime(request.form['report_date'], '%Y-%m-%d').date()
    from reports import get_attendance_data, summarize_hours_worked
    df = get_attendance_data(start_date=report_date, end_date=report_date)
    summary = summarize_hours_worked(df)
    today = date.today()
    week_ago = today - timedelta(days=7)
    employees = Employee.query.filter_by(is_active=True).all()
    return render_template("reports.html",
        today=today.strftime('%Y-%m-%d'),
        week_ago=week_ago.strftime('%Y-%m-%d'),
        employees=employees,
        report_data=summary,
        report_title=f"Reporte Diario - {report_date.strftime('%d/%m/%Y')}",
        start_date=report_date.strftime('%Y-%m-%d'),
        end_date=report_date.strftime('%Y-%m-%d'),
        show_charts=False,
        csrf_token=generate_csrf_token())

@app.route("/period_report", methods=["POST"])
def period_report():
    start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
    end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()
    charts = []
    attendance_chart = generate_attendance_chart(start_date, end_date)
    if attendance_chart:
        chart_data = base64.b64encode(attendance_chart.getvalue()).decode()
        charts.append({
            'title': 'Asistencia por Día',
            'data': chart_data
        })
    dept_chart = generate_department_chart(start_date, end_date)
    if dept_chart:
        chart_data = base64.b64encode(dept_chart.getvalue()).decode()
        charts.append({
            'title': 'Empleados por Departamento',
            'data': chart_data
        })
    from reports import get_attendance_data, summarize_hours_worked
    df = get_attendance_data(start_date=start_date, end_date=end_date)
    summary = summarize_hours_worked(df)
    today = date.today()
    week_ago = today - timedelta(days=7)
    employees = Employee.query.filter_by(is_active=True).all()
    return render_template("reports.html",
        today=today.strftime('%Y-%m-%d'),
        week_ago=week_ago.strftime('%Y-%m-%d'),
        employees=employees,
        charts=charts,
        report_data=summary,
        report_title=f"Reporte de Período - {start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}",
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        show_charts=True)

@app.route("/employee_report", methods=["POST"])
def employee_report():
    employee_id = request.form['employee_id']
    start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
    end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()
    
    from reports import generate_individual_report
    summary, error = generate_individual_report(start_date, end_date, employee_id)
    
    today = date.today()
    week_ago = today - timedelta(days=7)
    employees = Employee.query.filter_by(is_active=True).all()
    
    if error:
        flash(error, 'error')
        return render_template("reports.html", 
                             today=today.strftime('%Y-%m-%d'),
                             week_ago=week_ago.strftime('%Y-%m-%d'),
                             employees=employees,
                             csrf_token=generate_csrf_token())
    
    employee = Employee.query.filter_by(employee_id=employee_id).first()
    employee_name = employee.full_name if employee else employee_id
    start_date_formatted = start_date.strftime('%d/%m/%Y')
    end_date_formatted = end_date.strftime('%d/%m/%Y')
    
    return render_template("reports.html",
                         today=today.strftime('%Y-%m-%d'),
                         week_ago=week_ago.strftime('%Y-%m-%d'),
                         employees=employees,
                         report_data=summary,
                         report_title=f"Reporte Individual - {employee_name} - {start_date_formatted} - {end_date_formatted}",
                         start_date=start_date.strftime('%Y-%m-%d'),
                         end_date=end_date.strftime('%Y-%m-%d'),
                         employee_id=employee_id,
                         employee_name=employee_name,
                         csrf_token=generate_csrf_token())

@app.route("/general_report", methods=["POST"])
def general_report():
    start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
    end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()
    
    from reports import generate_general_detailed_report
    summary, error = generate_general_detailed_report(start_date, end_date)
    
    today = date.today()
    week_ago = today - timedelta(days=7)
    employees = Employee.query.filter_by(is_active=True).all()
    
    if error:
        flash(error, 'error')
        return render_template("reports.html", 
                             today=today.strftime('%Y-%m-%d'),
                             week_ago=week_ago.strftime('%Y-%m-%d'),
                             employees=employees,
                             csrf_token=generate_csrf_token())
    
    start_date_formatted = start_date.strftime('%d/%m/%Y')
    end_date_formatted = end_date.strftime('%d/%m/%Y')
    
    return render_template("reports.html",
                         today=today.strftime('%Y-%m-%d'),
                         week_ago=week_ago.strftime('%Y-%m-%d'),
                         employees=employees,
                         report_data=summary,
                         report_title=f"Reporte General - {start_date_formatted} - {end_date_formatted}",
                         start_date=start_date.strftime('%Y-%m-%d'),
                         end_date=end_date.strftime('%Y-%m-%d'),
                         csrf_token=generate_csrf_token())

@app.route("/employees")
def employees():
    employees = Employee.query.filter_by(is_active=True).all()
    return render_template("employees.html", employees=employees)

# Editar empleado
@app.route("/employees/edit/<employee_id>", methods=["GET", "POST"])
def edit_employee(employee_id):
    employee = Employee.query.filter_by(employee_id=employee_id).first_or_404()
    from models import WorkSchedule
    import datetime
    if request.method == "POST":
        employee.name = request.form["name"]
        employee.last_name = request.form["last_name"]
        employee.department = request.form["department"]
        employee.position = request.form["position"]
        email = request.form.get("email")
        # Validar email único (excepto el propio)
        if Employee.query.filter(Employee.email == email, Employee.employee_id != employee_id).first():
            flash("El correo electrónico ya está siendo usado por otro empleado.", "error")
            return render_template("edit_employee.html", employee=employee)
        employee.email = email
        employee.phone = request.form.get("phone")

        # Eliminado procesamiento de imagen de rostro

        # Actualizar horario fijo si se proporcionan nuevos valores
        start_time = request.form.get("start_time")
        end_time = request.form.get("end_time")
        if start_time and end_time:
            # Actualizar todos los registros de horario activo de este empleado
            ws_list = WorkSchedule.query.filter_by(employee_id=employee_id, is_active=True).all()
            for ws in ws_list:
                ws.start_time = datetime.datetime.strptime(start_time, "%H:%M").time()
                ws.end_time = datetime.datetime.strptime(end_time, "%H:%M").time()
            db.session.commit()

        db.session.commit()
        flash("Empleado actualizado correctamente.")
        return redirect(url_for("employees"))

    # Obtener horario actual para mostrar en el formulario
    ws = WorkSchedule.query.filter_by(employee_id=employee_id, is_active=True).first()
    start_time = ws.start_time.strftime("%H:%M") if ws else ""
    end_time = ws.end_time.strftime("%H:%M") if ws else ""
    return render_template("edit_employee.html", employee=employee, start_time=start_time, end_time=end_time)

# Eliminar empleado
def delete_employee(employee_id):
    employee = Employee.query.filter_by(employee_id=employee_id).first_or_404()
    db.session.delete(employee)
    db.session.commit()
    flash("Empleado eliminado correctamente.")
    return redirect(url_for("employees"))

# Registrar las rutas después de definir las funciones
app.add_url_rule("/employees/edit/<employee_id>", view_func=edit_employee, methods=["GET", "POST"])
app.add_url_rule("/employees/delete/<employee_id>", view_func=delete_employee, methods=["POST"])

@app.route('/scanner')
def scanner():
    today = date.today()
    today_attendances = Attendance.query.filter_by(date=today).order_by(Attendance.timestamp.desc()).all()
    return render_template('scanner.html', today_attendances=today_attendances)

@app.route('/reports', methods=['GET'])
def reports():
    today = date.today()
    week_ago = today - timedelta(days=7)
    employees = Employee.query.filter_by(is_active=True).all()
    return render_template("reports.html",
        today=today.strftime('%Y-%m-%d'),
        week_ago=week_ago.strftime('%Y-%m-%d'),
        employees=employees,
        report_data=None,
        csrf_token=generate_csrf_token())

@app.route('/employees/add', methods=['GET', 'POST'])
@admin_login_required
def add_employee():
    if request.method == 'POST':
        # Validar CSRF token
        csrf_token = request.form.get('csrf_token')
        if not validate_csrf_token(csrf_token):
            flash('Token de seguridad inválido.', 'danger')
            return render_template('add_employees.html')
        
        # Obtener y limpiar datos
        name = request.form.get('name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        department = request.form.get('department', '').strip()
        position = request.form.get('position', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        employee_id = request.form.get('employee_id', '').strip()
        
        # Validaciones de seguridad
        if not all([name, last_name, department, position, email, phone, employee_id]):
            flash('Todos los campos son obligatorios.', 'danger')
            return render_template('add_employees.html')
        
        if not validate_name(name):
            flash('Nombre inválido. Solo se permiten letras y espacios.', 'danger')
            return render_template('add_employees.html')
        
        if not validate_name(last_name):
            flash('Apellido inválido. Solo se permiten letras y espacios.', 'danger')
            return render_template('add_employees.html')
        
        if not validate_employee_id(employee_id):
            flash('ID de empleado inválido. Solo letras, números, guiones y guiones bajos.', 'danger')
            return render_template('add_employees.html')
        
        if not validate_email(email):
            flash('Formato de email inválido.', 'danger')
            return render_template('add_employees.html')
        
        if len(department) > 50 or len(position) > 50:
            flash('Departamento y posición no pueden exceder 50 caracteres.', 'danger')
            return render_template('add_employees.html')
        
        if len(phone) > 20:
            flash('Teléfono no puede exceder 20 caracteres.', 'danger')
            return render_template('add_employees.html')
        
        # Validar unicidad
        if Employee.query.filter_by(email=email).first():
            flash('El correo electrónico ya está registrado.', 'danger')
            return render_template('add_employees.html')
        
        if Employee.query.filter_by(employee_id=employee_id).first():
            flash('El ID de empleado ya está registrado.', 'danger')
            return render_template('add_employees.html')
        
        try:
            # Generar QR automáticamente
            from qr_generator import generate_qr_code
            qr_path = generate_qr_code(employee_id, employee_id)

            new_employee = Employee(
                employee_id=employee_id,
                name=name,
                last_name=last_name,
                department=department,
                position=position,
                email=email,
                phone=phone,
                is_active=True,
                qr_code=qr_path
            )
            db.session.add(new_employee)
            db.session.commit()
            flash('Empleado agregado correctamente y QR generado.', 'success')
            return redirect(url_for('employees'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al agregar empleado: {str(e)}', 'danger')
            return render_template('add_employees.html')
    
    return render_template('add_employees.html')

@app.route("/export_pdf", methods=["POST"])
def export_pdf():
    start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
    end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()
    employee_id = request.form.get('employee_id')
    
    if employee_id:
        # Para reporte individual, usar listado completo
        from reports import generate_individual_report
        summary, error = generate_individual_report(start_date, end_date, employee_id)
    else:
        # Para reporte general, usar listado detallado de todos los empleados
        from reports import generate_general_detailed_report
        summary, error = generate_general_detailed_report(start_date, end_date)
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import inch, cm
    import io
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    elements = []
    styles = getSampleStyleSheet()
    small_style = ParagraphStyle('small', parent=styles['Normal'], fontSize=6, leading=7)
    dir_style = ParagraphStyle('dir', parent=small_style, wordWrap='CJK', leading=7, fontSize=6, alignment=0, leftIndent=2, rightIndent=2, spaceBefore=2, spaceAfter=2)
    elements.append(Paragraph("Reporte de Asistencia", styles['Title']))
    
    # Agregar subtítulo con empleado y fechas si es reporte individual
    if employee_id:
        employee = Employee.query.filter_by(employee_id=employee_id).first()
        if employee:
            start_date_formatted = start_date.strftime('%d/%m/%Y')
            end_date_formatted = end_date.strftime('%d/%m/%Y')
            subtitle = f"{employee.full_name} - {start_date_formatted} - {end_date_formatted}"
            elements.append(Paragraph(subtitle, styles['Heading2']))
    else:
        # Para reportes generales, solo mostrar el rango de fechas
        start_date_formatted = start_date.strftime('%d/%m/%Y')
        end_date_formatted = end_date.strftime('%d/%m/%Y')
        subtitle = f"Período: {start_date_formatted} - {end_date_formatted}"
        elements.append(Paragraph(subtitle, styles['Heading3']))
    
    elements.append(Spacer(1, 12))
    if summary is not None and not summary.empty:
        # Filtrar la columna attendance_id para el PDF
        summary_pdf = summary.copy()
        if 'attendance_id' in summary_pdf.columns:
            summary_pdf = summary_pdf.drop(['attendance_id'], axis=1)
        
        data = [summary_pdf.columns.tolist()] + summary_pdf.values.tolist()
        # Cambiar cabecera 'Horas Trabajadas' por dos líneas
        if 'Horas Trabajadas' in data[0]:
            idx = data[0].index('Horas Trabajadas')
            data[0][idx] = 'Horas\nTrabajadas'
        # Detectar columna dirección y horas
        direccion_idx = None
        for i, col in enumerate(data[0]):
            if 'direc' in col.lower():
                direccion_idx = i
        col_count = len(data[0])
        table_width = 7.2 * inch
        min_col_width = 1.2 * cm
        # Asignar ancho fijo grande a dirección
        if direccion_idx is not None:
            dir_col_width = 5.0 * cm
            other_col_width = (table_width - dir_col_width) / (col_count - 1)
            col_widths = [dir_col_width if i == direccion_idx else other_col_width for i in range(col_count)]
        else:
            col_width = max(table_width / col_count, min_col_width)
            col_widths = [col_width] * col_count
        max_chars = [int(w // 4) for w in col_widths]
        def format_cell(val, i):
            s = str(val)
            if direccion_idx is not None and i == direccion_idx:
                max_len = 120
                s = s[:max_len] + ('...' if len(s) > max_len else '')
                return Paragraph(s.replace('\n', '<br/>'), dir_style)
            return s if len(s) <= max_chars[i] else s[:max_chars[i]-3] + '...'
        data_out = [data[0]]
        for row in data[1:]:
            data_out.append([format_cell(cell, i) for i, cell in enumerate(row)])
        table = Table(data_out, colWidths=col_widths, hAlign='CENTER')
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph("No hay datos para el período seleccionado.", styles['Normal']))
    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="reporte_asistencia.pdf", mimetype='application/pdf')

@app.route('/add_admin', methods=['POST'])
@admin_login_required
def add_admin():
    username = request.form.get('username')
    password = request.form.get('password')
    if not username or not password:
        flash('Todos los campos son obligatorios.', 'danger')
        return redirect(url_for('admin_dashboard'))
    if AdminUser.query.filter_by(username=username).first():
        flash('El nombre de usuario ya existe.', 'danger')
        return redirect(url_for('admin_dashboard'))
    new_admin = AdminUser(username=username)
    new_admin.set_password(password)
    db.session.add(new_admin)
    db.session.commit()
    flash(f'Administrador "{username}" creado correctamente.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin_management')
@admin_login_required
def admin_management():
    admins = AdminUser.query.all()
    return render_template('admin_management.html', admins=admins)

@app.route('/update_attendance_time', methods=['POST'])
@admin_login_required
def update_attendance_time():
    try:
        data = request.get_json()
        attendance_id = data.get('attendance_id')
        new_time = data.get('new_time')
        csrf_token = data.get('csrf_token')
        
        # Validar CSRF token
        if not validate_csrf_token(csrf_token):
            return jsonify({'success': False, 'message': 'Token de seguridad inválido'})
        
        if not attendance_id or not new_time:
            return jsonify({'success': False, 'message': 'Datos incompletos'})
        
        # Validar que attendance_id sea numérico
        try:
            attendance_id = int(attendance_id)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'ID de asistencia inválido'})
        
        # Validar formato de hora (HH:MM:SS)
        try:
            from datetime import datetime
            datetime.strptime(new_time, '%H:%M:%S')
        except ValueError:
            return jsonify({'success': False, 'message': 'Formato de hora inválido. Use HH:MM:SS'})
        
        attendance = Attendance.query.get(attendance_id)
        if not attendance:
            return jsonify({'success': False, 'message': 'Registro de asistencia no encontrado'})
        
        # Actualizar la hora manteniendo la fecha
        from datetime import datetime, time
        new_time_obj = datetime.strptime(new_time, '%H:%M:%S').time()
        updated_timestamp = datetime.combine(attendance.timestamp.date(), new_time_obj)
        
        attendance.timestamp = updated_timestamp
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Hora actualizada correctamente',
            'new_timestamp': updated_timestamp.strftime('%H:%M:%S')
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
