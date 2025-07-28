from flask import send_file

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_migrate import Migrate
from datetime import datetime, date, timedelta
import base64

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'tu_clave_secreta_aqui'

from models import db, Employee, Attendance, WorkSchedule

import pandas as pd

@app.route("/export_excel", methods=["POST"])
def export_excel():
    start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
    end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()
    employee_id = request.form.get('employee_id')
    from reports import get_attendance_data
    df = get_attendance_data(start_date=start_date, end_date=end_date, employee_id=employee_id)
    # Formatear columnas como en la vista web
    df['date'] = pd.to_datetime(df['date'], errors='coerce').dt.strftime('%d/%m/%Y')
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce').dt.strftime('%H:%M:%S')
    df['attendance_type'] = df['attendance_type'].str.title()
    df['latitude'] = df['latitude'].apply(lambda x: f"{x:.6f}" if pd.notnull(x) else "-")
    df['longitude'] = df['longitude'].apply(lambda x: f"{x:.6f}" if pd.notnull(x) else "-")
    columns = ['employee_id', 'employee_name', 'department', 'date', 'timestamp', 'attendance_type', 'latitude', 'longitude']
    df = df[columns]
    df.columns = ['ID Empleado', 'Nombre', 'Departamento', 'Fecha', 'Hora', 'Tipo', 'Latitud', 'Longitud']
    filename = "reporte_asistencia.xlsx"
    filepath = f"static/{filename}"
    df.to_excel(filepath, index=False)
    return send_file(filepath, as_attachment=True, download_name=filename)
db.init_app(app)
migrate = Migrate(app, db)

from qr_generator import generate_qr_code
from reports import generate_daily_report, generate_attendance_chart, generate_department_chart, generate_pdf_report, get_attendance_data

@app.route('/')
def index():
    # Estadísticas para el dashboard
    total_employees = Employee.query.filter_by(is_active=True).count()
    today = date.today()
    today_attendance = Attendance.query.filter_by(date=today).count()
    
    # Últimas 5 asistencias
    recent_attendances = Attendance.query.order_by(Attendance.timestamp.desc()).limit(5).all()
    
    # Calcular estadísticas adicionales
    # Contar llegadas tardías de hoy (solo entradas)
    late_arrivals = Attendance.query.filter_by(date=today, attendance_type='entrada', is_late=True).count()
    # Puedes mejorar el cálculo de attendance_rate si lo deseas
    attendance_rate = 85  # Implementar cálculo real

    return render_template('index.html', 
                         total_employees=total_employees,
                         today_attendance=today_attendance,
                         recent_attendances=recent_attendances,
                         late_arrivals=late_arrivals,
                         attendance_rate=attendance_rate)

@app.route("/employees")
def employees():
    employees = Employee.query.all()
    return render_template("employees.html", employees=employees)

@app.route("/employees/add", methods=["GET", "POST"])
def add_employee():
    if request.method == "POST":
        employee_id = request.form["employee_id"]
        name = request.form["name"]
        last_name = request.form["last_name"]
        department = request.form["department"]
        position = request.form["position"]
        email = request.form.get("email")
        phone = request.form.get("phone")

        # Generar QR y guardar la ruta
        qr_code_path = generate_qr_code(employee_id, employee_id)

        new_employee = Employee(
            employee_id=employee_id,
            name=name,
            last_name=last_name,
            department=department,
            position=position,
            email=email,
            phone=phone,
            qr_code=qr_code_path
        )
        db.session.add(new_employee)
        db.session.commit()
        flash("Empleado añadido exitosamente y QR generado.")
        return redirect(url_for("employees"))
    return render_template("add_employees.html")

@app.route("/qr_test/<employee_id>")
def qr_test(employee_id):
    # Esta ruta es solo para pruebas, en un entorno real se generaría al añadir el empleado
    qr_path = generate_qr_code(employee_id, employee_id)
    return f"QR para {employee_id} generado en: {qr_path}<br><img src=\"{url_for('static', filename=qr_path)}\">"

@app.route("/scanner")
def scanner():
    today = date.today()
    today_attendances = Attendance.query.filter_by(date=today).order_by(Attendance.timestamp.desc()).all()
    return render_template("scanner.html", today_attendances=today_attendances)

@app.route("/register_attendance", methods=["POST"])
def register_attendance():
    try:
        data = request.get_json()
        employee_id = data.get('employee_id')
        
        if not employee_id:
            return jsonify({'success': False, 'message': 'ID de empleado requerido'})
        
        # Buscar el empleado
        employee = Employee.query.filter_by(employee_id=employee_id, is_active=True).first()
        if not employee:
            return jsonify({'success': False, 'message': f'Empleado {employee_id} no encontrado o inactivo'})
        
        # Verificar el último registro del día
        today = date.today()
        last_attendance = Attendance.query.filter_by(
            employee_id=employee_id, 
            date=today
        ).order_by(Attendance.timestamp.desc()).first()
        
        # Determinar el tipo de asistencia
        if not last_attendance:
            attendance_type = 'entrada'
        elif last_attendance.attendance_type == 'entrada':
            attendance_type = 'salida'
        else:
            attendance_type = 'entrada'
        
        # Eliminada la restricción de tiempo mínimo entre registros
        
        # Definir hora de entrada permitida (8:00 AM)
        hora_entrada_permitida = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
        ahora = datetime.now()
        is_late = False
        if attendance_type == 'entrada' and ahora > hora_entrada_permitida:
            is_late = True
        # Obtener latitud y longitud del request
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        # Crear nuevo registro de asistencia
        new_attendance = Attendance(
            employee_id=employee_id,
            attendance_type=attendance_type,
            timestamp=ahora,
            date=today,
            is_late=is_late,
            latitude=latitude,
            longitude=longitude
        )
        
        db.session.add(new_attendance)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{attendance_type.title()} registrada para {employee.full_name} a las {new_attendance.timestamp.strftime("%H:%M:%S")}',
            'is_late': is_late,
            'attendance_type': attendance_type
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error interno: {str(e)}'})

@app.route("/reports")
def reports():
    today = date.today()
    week_ago = today - timedelta(days=7)
    employees = Employee.query.filter_by(is_active=True).all()
    
    return render_template("reports.html", 
                         today=today.strftime('%Y-%m-%d'),
                         week_ago=week_ago.strftime('%Y-%m-%d'),
                         employees=employees)

@app.route("/daily_report", methods=["POST"])
def daily_report():
    report_date = datetime.strptime(request.form['report_date'], '%Y-%m-%d').date()
    
    report_data, error = generate_daily_report(report_date)
    
    today = date.today()
    week_ago = today - timedelta(days=7)
    employees = Employee.query.filter_by(is_active=True).all()
    
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

@app.route("/period_report", methods=["POST"])
def period_report():
    start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
    end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()
    
    # Generar gráficos
    charts = []
    
    # Gráfico de asistencia por día
    attendance_chart = generate_attendance_chart(start_date, end_date)
    if attendance_chart:
        chart_data = base64.b64encode(attendance_chart.getvalue()).decode()
        charts.append({
            'title': 'Asistencia por Día',
            'data': chart_data
        })
    
    # Gráfico por departamento
    dept_chart = generate_department_chart(start_date, end_date)
    if dept_chart:
        chart_data = base64.b64encode(dept_chart.getvalue()).decode()
        charts.append({
            'title': 'Empleados por Departamento',
            'data': chart_data
        })
    
    today = date.today()
    week_ago = today - timedelta(days=7)
    employees = Employee.query.filter_by(is_active=True).all()
    
    return render_template("reports.html",
                         today=today.strftime('%Y-%m-%d'),
                         week_ago=week_ago.strftime('%Y-%m-%d'),
                         employees=employees,
                         charts=charts,
                         report_title=f"Reporte de Período - {start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}",
                         start_date=start_date.strftime('%Y-%m-%d'),
                         end_date=end_date.strftime('%Y-%m-%d'))

@app.route("/employee_report", methods=["POST"])
def employee_report():
    employee_id = request.form['employee_id']
    start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
    end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()
    
    df = get_attendance_data(start_date=start_date, end_date=end_date, employee_id=employee_id)
    
    today = date.today()
    week_ago = today - timedelta(days=7)
    employees = Employee.query.filter_by(is_active=True).all()
    
    if df.empty:
        flash(f'No hay datos de asistencia para el empleado {employee_id} en el período seleccionado.', 'error')
        return render_template("reports.html", 
                             today=today.strftime('%Y-%m-%d'),
                             week_ago=week_ago.strftime('%Y-%m-%d'),
                             employees=employees)
    
    # Formatear datos para mostrar
    display_data = df[['date', 'timestamp', 'attendance_type', 'latitude', 'longitude']].copy()
    import pandas as pd
    display_data['date'] = pd.to_datetime(display_data['date'], errors='coerce').dt.strftime('%d/%m/%Y')
    display_data['timestamp'] = pd.to_datetime(display_data['timestamp'], errors='coerce').dt.strftime('%H:%M:%S')
    display_data['attendance_type'] = display_data['attendance_type'].str.title()
    display_data['latitude'] = display_data['latitude'].apply(lambda x: f"{x:.6f}" if pd.notnull(x) else "-")
    display_data['longitude'] = display_data['longitude'].apply(lambda x: f"{x:.6f}" if pd.notnull(x) else "-")
    display_data.columns = ['Fecha', 'Hora', 'Tipo', 'Latitud', 'Longitud']
    
    employee_name = df['employee_name'].iloc[0]
    
    return render_template("reports.html",
                         today=today.strftime('%Y-%m-%d'),
                         week_ago=week_ago.strftime('%Y-%m-%d'),
                         employees=employees,
                         report_data=display_data,
                         report_title=f"Reporte Individual - {employee_name}",
                         start_date=start_date.strftime('%Y-%m-%d'),
                         end_date=end_date.strftime('%Y-%m-%d'),
                         employee_id=employee_id)

@app.route("/export_pdf", methods=["POST"])
def export_pdf():
    start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
    end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()
    employee_id = request.form.get('employee_id')

    if employee_id:
        filename = f"reporte_asistencia_{employee_id}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"
    else:
        filename = f"reporte_asistencia_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"
    filepath = f"static/{filename}"

    try:
        if employee_id:
            # Generar PDF solo para el empleado seleccionado
            from reports import get_attendance_data
            df = get_attendance_data(start_date=start_date, end_date=end_date, employee_id=employee_id)
            # Puedes adaptar generate_pdf_report para aceptar un DataFrame, o crear una función similar
            # Aquí reutilizamos generate_pdf_report pero solo con los datos filtrados
            # Para simplicidad, generamos un PDF básico
            import pandas as pd
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet
            doc = SimpleDocTemplate(filepath, pagesize=A4)
            styles = getSampleStyleSheet()
            story = []
            title = Paragraph(f"Reporte de Asistencia Individual<br/>{employee_id}<br/>{start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}", styles['Heading1'])
            story.append(title)
            story.append(Spacer(1, 20))
            if not df.empty:
                table_data = [['Fecha', 'Hora', 'Tipo']]
                df['date'] = pd.to_datetime(df['date'], errors='coerce').dt.strftime('%d/%m/%Y')
                df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce').dt.strftime('%H:%M:%S')
                df['attendance_type'] = df['attendance_type'].str.title()
                for _, row in df.iterrows():
                    table_data.append([row['date'], row['timestamp'], row['attendance_type']])
                detail_table = Table(table_data)
                detail_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                ]))
                story.append(detail_table)
            else:
                story.append(Paragraph("No hay datos de asistencia para el período seleccionado.", styles['Normal']))
            doc.build(story)
        else:
            generate_pdf_report(start_date, end_date, filepath)
        return send_file(filepath, as_attachment=True, download_name=filename)
    except Exception as e:
        flash(f'Error al generar el PDF: {str(e)}', 'error')
        return redirect(url_for('reports'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
