from app import create_app
from models import Role

# Bu betik, veritabanına varsayılan rolleri ve izinleri ekler.
# Sadece bir kez çalıştırmanız yeterlidir.

app = create_app()
with app.app_context():
    print("Varsayılan roller ve izinler veritabanına ekleniyor...")
    Role.insert_roles()
    print("İşlem tamamlandı.")