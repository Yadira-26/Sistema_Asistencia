from app import app
from models import db, Employee, Attendance
from qr_generator import generate_qr_code
from datetime import datetime, date, timedelta
import random

def create_test_data():
    """
    Crea datos de prueba para el sistema.
    """
    with app.app_context():
        # Crear empleados de prueba
        employees_data = [
            {
                'employee_id': 'EMP001',
                'name': 'Juan',
                'last_name': 'Pérez',
                'department': 'Desarrollo',
                'position': 'Desarrollador Senior',
                'email': 'juan.perez@empresa.com',
                'phone': '555-0001'
            },
            {
                'employee_id': 'EMP002',
                'name': 'María',
                'last_name': 'González',
                'department': 'Recursos Humanos',
                'position': 'Gerente de RRHH',
                'email': 'maria.gonzalez@empresa.com',
                'phone': '555-0002'
            },
            {
                'employee_id': 'EMP003',
                'name': 'Carlos',
                'last_name': 'Rodríguez',
                'department': 'Desarrollo',
                'position': 'Desarrollador Junior',
                'email': 'carlos.rodriguez@empresa.com',
                'phone': '555-0003'
            },
            {
                'employee_id': 'EMP004',
                'name': 'Ana',
                'last_name': 'Martínez',
                'department': 'Marketing',
                'position': 'Especialista en Marketing',
                'email': 'ana.martinez@empresa.com',
                'phone': '555-0004'
            },
            {
                'employee_id': 'EMP005',
                'name': 'Luis',
                'last_name': 'López',
                'department': 'Ventas',
                'position': 'Ejecutivo de Ventas',
                'email': 'luis.lopez@empresa.com',
                'phone': '555-0005'
            }
        ]
        
        # Crear empleados
        for emp_data in employees_data:
            existing = Employee.query.filter_by(employee_id=emp_data['employee_id']).first()
            if not existing:
                # Generar QR
                qr_path = generate_qr_code(emp_data['employee_id'], emp_data['employee_id'])
                
                employee = Employee(
                    employee_id=emp_data['employee_id'],
                    name=emp_data['name'],
                    last_name=emp_data['last_name'],
                    department=emp_data['department'],
                    position=emp_data['position'],
                    email=emp_data['email'],
                    phone=emp_data['phone'],
                    qr_code=qr_path
                )
                db.session.add(employee)
        
        db.session.commit()
        print("Empleados de prueba creados exitosamente.")
        
        # Crear registros de asistencia de prueba para los últimos 7 días
        today = date.today()
        
        for i in range(7):
            current_date = today - timedelta(days=i)
            
            for emp_data in employees_data:
                employee_id = emp_data['employee_id']
                
                # Simular entrada (80% de probabilidad)
                if random.random() < 0.8:
                    entrada_hour = random.randint(7, 9)
                    entrada_minute = random.randint(0, 59)
                    entrada_time = datetime.combine(current_date, datetime.min.time().replace(
                        hour=entrada_hour, minute=entrada_minute
                    ))
                    
                    entrada = Attendance(
                        employee_id=employee_id,
                        attendance_type='entrada',
                        timestamp=entrada_time,
                        date=current_date
                    )
                    db.session.add(entrada)
                    
                    # Simular salida (90% de probabilidad si hay entrada)
                    if random.random() < 0.9:
                        salida_hour = random.randint(17, 19)
                        salida_minute = random.randint(0, 59)
                        salida_time = datetime.combine(current_date, datetime.min.time().replace(
                            hour=salida_hour, minute=salida_minute
                        ))
                        
                        salida = Attendance(
                            employee_id=employee_id,
                            attendance_type='salida',
                            timestamp=salida_time,
                            date=current_date
                        )
                        db.session.add(salida)
        
        db.session.commit()
        print("Registros de asistencia de prueba creados exitosamente.")

if __name__ == '__main__':
    create_test_data()
