import matplotlib
matplotlib.use('Agg')
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
from datetime import datetime, date, timedelta
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import io
import base64
from models import Employee, Attendance, db

def summarize_hours_worked(df):
    if df.empty:
        return pd.DataFrame()
    employee_summary = []
    for employee_id in df['employee_id'].unique():
        emp_data = df[df['employee_id'] == employee_id].sort_values('timestamp')
        entradas = emp_data[emp_data['attendance_type'] == 'entrada']['timestamp'].tolist()
        salidas = emp_data[emp_data['attendance_type'] == 'salida']['timestamp'].tolist()
        total_seconds = 0
        used_salidas = set()
        for entrada_time in entradas:
            salida_time = None
            for idx, s in enumerate(salidas):
                if s > entrada_time and idx not in used_salidas:
                    salida_time = s
                    used_salidas.add(idx)
                    break
            if entrada_time and salida_time:
                total_seconds += int((salida_time - entrada_time).total_seconds())
        # Solo mostrar horas si hay al menos una salida válida
        if total_seconds > 0:
            horas = total_seconds // 3600
            minutos = (total_seconds % 3600) // 60
            segundos = total_seconds % 60
            horas_str = []
            if horas > 0:
                horas_str.append(f"{horas} hora{'s' if horas != 1 else ''}")
            if minutos > 0:
                horas_str.append(f"{minutos} minuto{'s' if minutos != 1 else ''}")
            if segundos > 0:
                horas_str.append(f"{segundos} segundo{'s' if segundos != 1 else ''}")
            horas_legible = ', '.join(horas_str)
        else:
            horas_legible = 'N/A'
        entrada_time = entradas[0] if entradas else None
        # Salida solo si hay alguna salida válida
        salida_time = None
        for s in reversed(salidas):
            if entradas and s > entradas[0]:
                salida_time = s
                break
        address = emp_data[emp_data['attendance_type'] == 'entrada']['address'].iloc[0] if not emp_data[emp_data['attendance_type'] == 'entrada'].empty and 'address' in emp_data else ''
        # Obtener el ID de la primera entrada para referencia
        attendance_id = emp_data[emp_data['attendance_type'] == 'entrada']['attendance_id'].iloc[0] if not emp_data[emp_data['attendance_type'] == 'entrada'].empty and 'attendance_id' in emp_data else None
        employee_summary.append({
            'ID': employee_id,
            'Nombre': emp_data['employee_name'].iloc[0],
            'Departamento': emp_data['department'].iloc[0],
            'Entrada': entrada_time.strftime('%H:%M:%S') if entrada_time else 'No registrada',
            'Salida': salida_time.strftime('%H:%M:%S') if salida_time else 'No registrada',
            'Horas Trabajadas': horas_legible,
            'Dirección': address,
            'attendance_id': attendance_id  # ID para edición
        })
    return pd.DataFrame(employee_summary)

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
            'attendance_id': attendance.id,  # Incluir ID de asistencia
            'employee_id': attendance.employee_id,
            'employee_name': attendance.employee.full_name,
            'department': attendance.employee.department,
            'date': attendance.date,
            'timestamp': attendance.timestamp,
            'attendance_type': attendance.attendance_type,
            'address': getattr(attendance, 'address', '')
        })
    
    return pd.DataFrame(data)

def generate_individual_report(start_date, end_date, employee_id):
    """
    Genera un reporte individual mostrando cada día por separado.
    """
    df = get_attendance_data(start_date=start_date, end_date=end_date, employee_id=employee_id)
    
    if df.empty:
        return None, f"No hay datos de asistencia para el empleado {employee_id} en el período seleccionado."
    
    # Agrupar por fecha para mostrar cada día
    employee_summary = []
    
    # Obtener todas las fechas únicas en el período
    for target_date in df['date'].unique():
        day_data = df[df['date'] == target_date]
        
        entrada = day_data[day_data['attendance_type'] == 'entrada']
        salida = day_data[day_data['attendance_type'] == 'salida']
        
        fecha_str = target_date.strftime('%d/%m/%Y')
        entrada_time = entrada['timestamp'].iloc[0] if not entrada.empty else None
        salida_time = salida['timestamp'].iloc[-1] if not salida.empty else None
        
        # Calcular horas trabajadas
        hours_worked = 0
        if entrada_time and salida_time:
            hours_worked = (salida_time - entrada_time).total_seconds()
            horas = int(hours_worked // 3600)
            minutos = int((hours_worked % 3600) // 60)
            segundos = int(hours_worked % 60)
            
            horas_str = []
            if horas > 0:
                horas_str.append(f"{horas} hora{'s' if horas != 1 else ''}")
            if minutos > 0:
                horas_str.append(f"{minutos} minuto{'s' if minutos != 1 else ''}")
            if segundos > 0:
                horas_str.append(f"{segundos} segundo{'s' if segundos != 1 else ''}")
            horas_legible = ', '.join(horas_str) if horas_str else '0 segundos'
        else:
            horas_legible = 'N/A'
        
        # Obtener información adicional
        address = entrada['address'].iloc[0] if not entrada.empty and 'address' in entrada else ''
        attendance_id = entrada['attendance_id'].iloc[0] if not entrada.empty and 'attendance_id' in entrada else None
        
        employee_summary.append({
            'attendance_id': attendance_id,
            'Fecha': fecha_str,
            'ID': employee_id,
            'Nombre': day_data['employee_name'].iloc[0],
            'Departamento': day_data['department'].iloc[0],
            'Entrada': entrada_time.strftime('%H:%M:%S') if entrada_time else 'No registrada',
            'Salida': salida_time.strftime('%H:%M:%S') if salida_time else 'No registrada',
            'Horas Trabajadas': horas_legible,
            'Dirección': address
        })
    
    # Ordenar por fecha
    employee_summary = sorted(employee_summary, key=lambda x: x['Fecha'])
    
    return pd.DataFrame(employee_summary), None

def generate_general_detailed_report(start_date, end_date):
    """
    Genera un reporte general detallado mostrando todas las asistencias día por día de todos los empleados.
    """
    df = get_attendance_data(start_date=start_date, end_date=end_date)
    
    if df.empty:
        return None, f"No hay datos de asistencia en el período seleccionado."
    
    # Agrupar por empleado y fecha para mostrar cada día
    all_attendances = []
    
    # Obtener todas las combinaciones únicas de empleado y fecha
    for (employee_id, target_date), group in df.groupby(['employee_id', 'date']):
        entrada = group[group['attendance_type'] == 'entrada']
        salida = group[group['attendance_type'] == 'salida']
        
        fecha_str = target_date.strftime('%d/%m/%Y')
        entrada_time = entrada['timestamp'].iloc[0] if not entrada.empty else None
        salida_time = salida['timestamp'].iloc[-1] if not salida.empty else None
        
        # Calcular horas trabajadas
        if entrada_time and salida_time:
            hours_worked = (salida_time - entrada_time).total_seconds()
            horas = int(hours_worked // 3600)
            minutos = int((hours_worked % 3600) // 60)
            segundos = int(hours_worked % 60)
            
            horas_str = []
            if horas > 0:
                horas_str.append(f"{horas} hora{'s' if horas != 1 else ''}")
            if minutos > 0:
                horas_str.append(f"{minutos} minuto{'s' if minutos != 1 else ''}")
            if segundos > 0:
                horas_str.append(f"{segundos} segundo{'s' if segundos != 1 else ''}")
            horas_legible = ', '.join(horas_str) if horas_str else '0 segundos'
        else:
            horas_legible = 'N/A'
        
        # Obtener información adicional
        address = entrada['address'].iloc[0] if not entrada.empty and 'address' in entrada else ''
        attendance_id = entrada['attendance_id'].iloc[0] if not entrada.empty and 'attendance_id' in entrada else None
        
        all_attendances.append({
            'attendance_id': attendance_id,
            'Fecha': fecha_str,
            'ID': employee_id,
            'Nombre': group['employee_name'].iloc[0],
            'Departamento': group['department'].iloc[0],
            'Entrada': entrada_time.strftime('%H:%M:%S') if entrada_time else 'No registrada',
            'Salida': salida_time.strftime('%H:%M:%S') if salida_time else 'No registrada',
            'Horas Trabajadas': horas_legible,
            'Dirección': address
        })
    
    # Ordenar por fecha y luego por empleado
    all_attendances = sorted(all_attendances, key=lambda x: (x['Fecha'], x['ID']))
    
    return pd.DataFrame(all_attendances), None

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
        
        # Obtener latitud, longitud y dirección de la primera entrada (si existe)
        lat = entrada['latitude'].iloc[0] if not entrada.empty and 'latitude' in entrada else None
        lon = entrada['longitude'].iloc[0] if not entrada.empty and 'longitude' in entrada else None
        address = entrada['address'].iloc[0] if not entrada.empty and 'address' in entrada else ''
        # Obtener el ID de la primera entrada para referencia
        attendance_id = entrada['attendance_id'].iloc[0] if not entrada.empty and 'attendance_id' in entrada else None
        lat_str = f"{lat:.6f}" if lat is not None else "-"
        lon_str = f"{lon:.6f}" if lon is not None else "-"
        employee_summary.append({
            'attendance_id': attendance_id,  # ID para edición
            'ID': employee_id,
            'Nombre': emp_data['employee_name'].iloc[0],
            'Departamento': emp_data['department'].iloc[0],
            'Entrada': entrada_time.strftime('%H:%M:%S') if entrada_time else 'No registrada',
            'Salida': salida_time.strftime('%H:%M:%S') if salida_time else 'No registrada',
            'Horas Trabajadas': f"{hours_worked:.2f}" if hours_worked > 0 else 'N/A',
            'Latitud': lat_str,
            'Longitud': lon_str,
            'Dirección': address
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
    plt.gca().xaxis.set_major_locator(mticker.MaxNLocator(nbins=15))

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
    
    summary = summarize_hours_worked(df)
    return summary, None