from models import db, AdminUser
from app import app

with app.app_context():
    username = 'admin'
    password = 'admin123'
    if not AdminUser.query.filter_by(username=username).first():
        user = AdminUser(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        print(f'Usuario admin creado: {username} / {password}')
    else:
        print('El usuario admin ya existe.')
