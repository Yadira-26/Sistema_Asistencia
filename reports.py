import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, date, timedelta
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import io
import base64
from models import Employee, Attendance, db

def get_attendance_data(start_date=None, end_date=None, employee_id=None):
    """
    Obtiene datos de asistencia filtrados por fecha y empleado.
    """
    query = Attendance.query
    
    if start_date:
        query = query.filter(Attendance.date >= start_date)
    if end_date:
        query = query.filter(Attendance.date <= end_date)
    if employee_id:
        query = query.filter(Attendance.employee_id == employee_id)
    
    attendances = query.all()
    
    data = []
    for attendance in attendances:
        data.append({
            'employee_id': attendance.employee_id,
            'employee_name': attendance.employee.full_name,
            'department': attendance.employee.department,
            'date': attendance.date,
            'timestamp': attendance.timestamp,
            'attendance_type': attendance.attendance_type,
            'latitude': getattr(attendance, 'latitude', None),
            'longitude': getattr(attendance, 'longitude', None)
        })
    
    return pd.DataFrame(data)

def generate_daily_report(target_date=None):
    """
    Genera un reporte diario de asistencia.
    """
    if not target_date:
        target_date = date.today()
    
    df = get_attendance_data(start_date=target_date, end_date=target_date)
    print(f"[DEBUG] Asistencias encontradas para {target_date}: {len(df)} registros")
    print(df)
    
    if df.empty:
        return None, "No hay datos de asistencia para la fecha seleccionada."
    
    # Agrupar por empleado
    employee_summary = []
    for employee_id in df['employee_id'].unique():
        emp_data = df[df['employee_id'] == employee_id]
        
        entrada = emp_data[emp_data['attendance_type'] == 'entrada']
        salida = emp_data[emp_data['attendance_type'] == 'salida']
        
        entrada_time = entrada['timestamp'].iloc[0] if not entrada.empty else None
        salida_time = salida['timestamp'].iloc[-1] if not salida.empty else None
        
        # Calcular horas trabajadas
        hours_worked = 0
        if entrada_time and salida_time:
            hours_worked = (salida_time - entrada_time).total_seconds() / 3600
        
        # Obtener latitud y longitud de la primera entrada (si existe)
        lat = entrada['latitude'].iloc[0] if not entrada.empty and 'latitude' in entrada else None
        lon = entrada['longitude'].iloc[0] if not entrada.empty and 'longitude' in entrada else None
        lat_str = f"{lat:.6f}" if lat is not None else "-"
        lon_str = f"{lon:.6f}" if lon is not None else "-"
        employee_summary.append({
            'ID': employee_id,
            'Nombre': emp_data['employee_name'].iloc[0],
            'Departamento': emp_data['department'].iloc[0],
            'Entrada': entrada_time.strftime('%H:%M:%S') if entrada_time else 'No registrada',
            'Salida': salida_time.strftime('%H:%M:%S') if salida_time else 'No registrada',
            'Horas Trabajadas': f"{hours_worked:.2f}" if hours_worked > 0 else 'N/A',
            'Latitud': lat_str,
            'Longitud': lon_str
        })
    
    return pd.DataFrame(employee_summary), None

def generate_attendance_chart(start_date, end_date):
    """
    Genera un gráfico de asistencia por día.
    """
    df = get_attendance_data(start_date=start_date, end_date=end_date)
    
    if df.empty:
        return None
    
    # Contar asistencias por día
    daily_counts = df.groupby('date').size().reset_index(name='count')
    
    plt.figure(figsize=(12, 6))
    plt.plot(daily_counts['date'], daily_counts['count'], marker='o', linewidth=2, markersize=8)
    plt.title('Registros de Asistencia por Día', fontsize=16, fontweight='bold')
    plt.xlabel('Fecha', fontsize=12)
    plt.ylabel('Número de Registros', fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    
    # Formatear fechas en el eje X
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d/%m/%Y'))
    plt.gca().xaxis.set_major_locator(mdates.DayLocator(interval=1))
    
    plt.tight_layout()
    
    # Guardar en memoria
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', dpi=300, bbox_inches='tight')
    img_buffer.seek(0)
    plt.close()
    
    return img_buffer

def generate_department_chart(start_date, end_date):
    """
    Genera un gráfico de asistencia por departamento.
    """
    df = get_attendance_data(start_date=start_date, end_date=end_date)
    
    if df.empty:
        return None
    
    # Contar empleados únicos por departamento
    dept_counts = df.groupby('department')['employee_id'].nunique().reset_index()
    dept_counts.columns = ['Departamento', 'Empleados']
    
    plt.figure(figsize=(10, 6))
    bars = plt.bar(dept_counts['Departamento'], dept_counts['Empleados'], 
                   color=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7'])
    
    plt.title('Empleados Activos por Departamento', fontsize=16, fontweight='bold')
    plt.xlabel('Departamento', fontsize=12)
    plt.ylabel('Número de Empleados', fontsize=12)
    plt.xticks(rotation=45)
    
    # Añadir valores en las barras
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}', ha='center', va='bottom', fontweight='bold')
    
    plt.tight_layout()
    
    # Guardar en memoria
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', dpi=300, bbox_inches='tight')
    img_buffer.seek(0)
    plt.close()
    
    return img_buffer

def generate_pdf_report(start_date, end_date, filename):
    """
    Genera un reporte PDF completo.
    """
    doc = SimpleDocTemplate(filename, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    # Título
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=1  # Centrado
    )
    
    title = Paragraph(f"Reporte de Asistencia<br/>{start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}", title_style)
    story.append(title)
    story.append(Spacer(1, 20))
    
    # Resumen estadístico
    df = get_attendance_data(start_date=start_date, end_date=end_date)
    
    if not df.empty:
        total_records = len(df)
        unique_employees = df['employee_id'].nunique()
        departments = df['department'].nunique()
        
        summary_data = [
            ['Métrica', 'Valor'],
            ['Total de Registros', str(total_records)],
            ['Empleados Únicos', str(unique_employees)],
            ['Departamentos', str(departments)],
            ['Período', f"{start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}"]
        ]
        
        summary_table = Table(summary_data)
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(Paragraph("Resumen Estadístico", styles['Heading2']))
        story.append(summary_table)
        story.append(Spacer(1, 20))
        
        # Tabla de asistencia detallada
        story.append(Paragraph("Detalle de Asistencias", styles['Heading2']))
        
        # Preparar datos para la tabla
        table_data = [['ID Empleado', 'Nombre', 'Departamento', 'Fecha', 'Hora', 'Tipo', 'Latitud', 'Longitud']]

        for _, row in df.iterrows():
            # Manejar posibles valores nulos
            lat = getattr(row, 'latitude', None)
            lon = getattr(row, 'longitude', None)
            lat_str = f"{lat:.6f}" if lat is not None else "-"
            lon_str = f"{lon:.6f}" if lon is not None else "-"
            table_data.append([
                row['employee_id'],
                row['employee_name'],
                row['department'],
                row['date'].strftime('%d/%m/%Y'),
                row['timestamp'].strftime('%H:%M:%S'),
                row['attendance_type'].title(),
                lat_str,
                lon_str
            ])

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
    return filename