# 📋 Sistema de Asistencia QR

Sistema web de control de asistencia empresarial mediante códigos QR desarrollado en Flask.

## 🌟 Características

- ✅ Registro de asistencia mediante códigos QR únicos
- ✅ Dashboard administrativo con estadísticas en tiempo real
- ✅ Gestión completa de empleados (CRUD)
- ✅ 4 tipos de reportes (Diario, Período, Individual, General)
- ✅ Exportación a PDF y Excel
- ✅ Edición de horarios por administradores
- ✅ Geolocalización automática
- ✅ Sistema de seguridad robusto (CSRF, Rate Limiting)
- ✅ Interfaz responsive para móviles

## 🛠️ Tecnologías Utilizadas

- **Backend:** Python Flask
- **Base de Datos:** SQLite (desarrollo) / PostgreSQL (producción)
- **Frontend:** HTML5, CSS3, Bootstrap 4, JavaScript
- **Reportes:** Pandas, Matplotlib, ReportLab
- **QR:** qrcode library
- **Seguridad:** Flask-Limiter, CSRF Protection

## ⚙️ Requisitos del Sistema

- Python 3.8+
- Git
- Navegador web moderno
- Cámara (para escaneo QR)

## 🚀 Instalación

### 1. Clonar el repositorio
```bash
git clone https://github.com/Yadira-26/Sistema_Asistencia.git
cd Sistema_Asistencia
```

### 2. Crear entorno virtual
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar base de datos
```bash
# Aplicar migraciones
flask db upgrade
```

### 5. Crear usuario administrador
```bash
python create_admin.py
```
Sigue las instrucciones para crear tu usuario y contraseña de administrador.

### 6. Ejecutar la aplicación
```bash
python app.py
```

### 7. Acceder al sistema
- **Aplicación principal:** http://localhost:5000
- **Panel administrativo:** http://localhost:5000/admin_login

## 👥 Uso del Sistema

### Para Empleados:
1. Escanear el código QR personal con la cámara del móvil
2. Permitir acceso a geolocalización
3. Confirmar registro de entrada/salida

### Para Administradores:
1. Acceder al panel admin: `/admin_login`
2. Gestionar empleados en la sección "Empleados"
3. Generar reportes en la sección "Reportes"
4. Editar horarios directamente en los reportes

## 📊 Tipos de Reportes

1. **Reporte Diario:** Asistencias de un día específico
2. **Reporte por Período:** Gráficos estadísticos de un rango de fechas
3. **Reporte Individual:** Historial detallado por empleado
4. **Reporte General:** Todas las asistencias de un período

## 🔒 Características de Seguridad

- Contraseñas hasheadas con Werkzeug
- Protección CSRF en todos los formularios
- Rate limiting para prevenir ataques de fuerza bruta
- Validación y sanitización de datos de entrada
- Gestión segura de sesiones
- Encabezados de seguridad HTTP

## 📁 Estructura del Proyecto

```
Sistema_Asistencia/
│
├── app.py                 # Aplicación principal Flask
├── models.py              # Modelos de base de datos
├── reports.py             # Generación de reportes
├── qr_generator.py        # Generación de códigos QR
├── requirements.txt       # Dependencias Python
├── create_admin.py        # Script para crear admin
│
├── templates/             # Plantillas HTML
│   ├── base.html
│   ├── index.html
│   ├── admin_dashboard.html
│   ├── employees.html
│   ├── reports.html
│   └── ...
│
├── static/               # Archivos estáticos
│   ├── qr_codes/        # Códigos QR generados
│   └── ...
│
├── migrations/           # Migraciones de base de datos
└── instance/            # Base de datos (no incluida en repo)
```

## 🐛 Troubleshooting

### Error: "Module not found"
```bash
pip install -r requirements.txt
```

### Error de base de datos
```bash
flask db upgrade
```

### Puerto en uso
Cambiar el puerto en `app.py`:
```python
app.run(debug=True, port=5001)
```

## 🔧 Configuración para Producción

### Variables de entorno recomendadas:
```bash
FLASK_ENV=production
SECRET_KEY=tu_clave_super_secreta
DATABASE_URL=postgresql://usuario:contraseña@localhost/bd_asistencia
```

### Usar servidor WSGI:
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## 📈 Características Avanzadas

- **Edición de Horarios:** Los administradores pueden modificar horas de entrada y salida directamente en los reportes
- **Exportación Múltiple:** PDF y Excel para todos los tipos de reportes
- **Geolocalización:** Registro automático de ubicación GPS
- **Responsive Design:** Optimizado para dispositivos móviles
- **Estadísticas en Tiempo Real:** Dashboard con métricas actualizadas

## 🤝 Contribuciones

Este es un proyecto privado. Para sugerencias o reportes de bugs, contactar al desarrollador.

## 📄 Licencia

Proyecto propietario - Todos los derechos reservados.

## 👨‍💻 Desarrollado por

**Yadira-26** - Sistema de Asistencia QR v1.0

---

## 📁 Mejoras a futuro 

Implementar reconocimineto facial 

⭐ Si este proyecto te resulta útil, ¡dale una estrella en GitHub!
