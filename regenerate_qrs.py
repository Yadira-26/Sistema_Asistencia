from app import app
from models import db, Employee
from qr_generator import generate_qr_code

# Script para regenerar los QR de todos los empleados

def regenerate_all_qrs():
    with app.app_context():
        employees = Employee.query.all()
        for emp in employees:
            # Generar y guardar el QR
            qr_path = generate_qr_code(emp.employee_id, emp.employee_id)
            emp.qr_code = qr_path
        db.session.commit()
        print("Todos los QR han sido regenerados y actualizados en la base de datos.")

if __name__ == "__main__":
    regenerate_all_qrs()
