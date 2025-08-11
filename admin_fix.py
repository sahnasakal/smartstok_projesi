from sqlalchemy import inspect
from werkzeug.security import generate_password_hash

# Modelleri esnek import
try:
    from app import app, db
except Exception as e:
    raise SystemExit(f"[ERR] app import edilemedi: {e}")

try:
    from models import User, Role
except Exception:
    try:
        from app import User, Role
    except Exception:
        from models import User
        Role = None  # Role modeli yoksa rol adımlarını atlayacağız

ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = '4471Aras.'
ROLE_NAME      = 'admin'   # bir çok projede küçük harf beklenir

with app.app_context():
    # 1) Tüm kullanıcıları sil
    deleted_users = User.query.delete()
    db.session.commit()
    print(f"[INFO] {deleted_users} kullanıcı silindi.")

    # 2) Rol tablosu varsa sıfırla ve 'admin' rolünü oluştur
    admin_role = None
    if Role is not None:
        try:
            Role.query.delete()
            db.session.commit()
            print("[INFO] Roller silindi.")
        except Exception as e:
            print("[WARN] Rol silme atlandı:", e)

        admin_role = Role.query.filter_by(name=ROLE_NAME).first()
        if not admin_role:
            admin_role = Role(name=ROLE_NAME)
            db.session.add(admin_role)
            db.session.commit()
            print(f"[FIX] Rol oluşturuldu: {ROLE_NAME}")

    # 3) Admin oluştur (mümkün olan tüm alanları set et)
    cols = {c.key for c in inspect(User).mapper.columns}
    kwargs = dict(
        username=ADMIN_USERNAME,
        password_hash=generate_password_hash(ADMIN_PASSWORD)
    )
    if 'is_admin' in cols:
        kwargs['is_admin'] = True
    if 'role_name' in cols:
        kwargs['role_name'] = ROLE_NAME
    if hasattr(User, 'role_id') and admin_role is not None:
        kwargs['role_id'] = admin_role.id

    u = User(**kwargs)
    db.session.add(u)
    db.session.commit()

    if hasattr(User, 'role') and admin_role is not None:
        try:
            u.role = admin_role
            db.session.commit()
        except Exception as e:
            print("[WARN] role ilişkilendirme atlandı:", e)

    print("[OK] Admin oluşturuldu | username=", ADMIN_USERNAME, "| password=", ADMIN_PASSWORD)
    print('[USER AFTER]', {
        'username': u.username,
        'is_admin': getattr(u, 'is_admin', None),
        'role_id': getattr(u, 'role_id', None),
        'role_name': getattr(u, 'role_name', None),
        'bound_role': getattr(getattr(u, 'role', None), 'name', None) if hasattr(u, 'role') else None,
    })
