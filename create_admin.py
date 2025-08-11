import os
from app import create_app, db
from models import User, Role

app = create_app()

with app.app_context():
    print("Admin kullanıcısı ve rolleri kontrol ediliyor...")
    
    # Her ihtimale karşı varsayılan rollerin var olduğundan emin ol
    Role.insert_roles()

    # 'Admin' rolünü veritabanından bul
    admin_role = Role.query.filter_by(name='Admin').first()

    if not admin_role:
        print("HATA: 'Admin' rolü veritabanında bulunamadı!")
    
    # Admin kullanıcısının var olup olmadığını kontrol et
    elif User.query.filter_by(username='admin').first() is None:
        print("Admin kullanıcısı bulunamadı, yeni bir tane oluşturuluyor...")
        admin_user = User(
            username='admin',
            role=admin_role  # YENİ: Kullanıcıya Admin rolünü ata
        )
        admin_password = os.environ.get('ADMIN_PASSWORD', 'default_password')
        admin_user.set_password(admin_password)
        db.session.add(admin_user)
        db.session.commit()
        print(f"Admin kullanıcısı '{admin_user.username}' başarıyla oluşturuldu ve 'Admin' rolü atandı.")
    else:
        # Mevcut admin kullanıcısının rolü yoksa ata
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user.role:
            admin_user.role = admin_role
            db.session.commit()
            print("Mevcut Admin kullanıcısına 'Admin' rolü atandı.")
        else:
            print("Admin kullanıcısı zaten mevcut ve bir role sahip.")