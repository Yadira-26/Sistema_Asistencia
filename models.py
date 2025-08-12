
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash

# Modelo para usuarios administrativos
class AdminUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<AdminUser {self.username}>'

class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(50), nullable=False)
    position = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    # Todos los campos ya están como nullable=False excepto email y phone, que ya se cambiaron.
    qr_code = db.Column(db.String(255), nullable=True)  # Ruta del archivo QR
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Reconocimiento facial
    # ...eliminado reconocimiento facial...
    
    # Relación con asistencias
    attendances = db.relationship('Attendance', backref='employee', lazy=True)
    
    def __repr__(self):
        return f'<Employee {self.employee_id}: {self.name} {self.last_name}>'
    
    @property
    def full_name(self):
        return f"{self.name} {self.last_name}"

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.String(20), db.ForeignKey('employee.employee_id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    attendance_type = db.Column(db.String(10), nullable=False)  # 'entrada' o 'salida'
    date = db.Column(db.Date, default=datetime.utcnow().date())
    notes = db.Column(db.Text, nullable=True)
    is_late = db.Column(db.Boolean, default=False)  # True si la entrada fue tarde
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    address = db.Column(db.String(255), nullable=True)  # Dirección legible
    
    def __repr__(self):
        return f'<Attendance {self.employee_id}: {self.attendance_type} at {self.timestamp}>'

class WorkSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.String(20), db.ForeignKey('employee.employee_id'), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0=Lunes, 6=Domingo
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    
    def __repr__(self):
        return f'<WorkSchedule {self.employee_id}: Day {self.day_of_week}>'

