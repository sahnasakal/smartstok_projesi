from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# ---- Rol & İzin ----
roles_permissions = db.Table(
    'roles_permissions',
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permissions.id'), primary_key=True)
)

class Permission(db.Model):
    __tablename__ = 'permissions'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    description = db.Column(db.String(128))

class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    users = db.relationship('User', backref='role', lazy='dynamic')
    permissions = db.relationship(
        'Permission',
        secondary=roles_permissions,
        backref=db.backref('roles', lazy='dynamic'),
        lazy='dynamic'
    )

    def has_permission(self, perm_name):
        return self.permissions.filter_by(name=perm_name).first() is not None

    @staticmethod
    def insert_roles():
        all_permissions = {
            'view_stock': 'Stok Görüntüleme', 'add_stock': 'Stok Ekleme',
            'remove_stock': 'Stok Düşme', 'transfer_stock': 'Stok Transferi',
            'edit_catalog': 'Katalog Düzenleme', 'delete_catalog': 'Katalog Silme',
            'manage_users': 'Kullanıcı Yönetimi', 'admin': 'Tam Yetki (Admin)'
        }
        for p_name, p_desc in all_permissions.items():
            perm = Permission.query.filter_by(name=p_name).first()
            if perm is None:
                perm = Permission(name=p_name)
            perm.description = p_desc
            db.session.add(perm)
        db.session.commit()

        roles_with_permissions = {
            'Personel': ['view_stock', 'add_stock', 'remove_stock', 'transfer_stock'],
            'Depo Sorumlusu': ['view_stock', 'add_stock', 'remove_stock', 'transfer_stock', 'edit_catalog', 'delete_catalog'],
            'Admin': list(all_permissions.keys())
        }
        for r_name, r_perms in roles_with_permissions.items():
            role = Role.query.filter_by(name=r_name).first()
            if role is None:
                role = Role(name=r_name)
                db.session.add(role)
            role.permissions = []
            for p_name in r_perms:
                perm = Permission.query.filter_by(name=p_name).first()
                if perm:
                    role.permissions.append(perm)
        db.session.commit()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True, nullable=False)
    password_hash = db.Column(db.String(256))
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def can(self, perm_name):
        if self.role is None:
            return False
        return self.role.has_permission(perm_name)

    @property
    def is_admin(self):
        return self.can('admin')

# ---- Katalog & Stok ----
class LocationCategory(db.Model):
    __tablename__ = 'location_categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)

    # categories -> locations
    locations = db.relationship('Location', backref='category', lazy='dynamic')

    def __repr__(self):
        return f"<LocationCategory {self.name}>"

class Location(db.Model):
    __tablename__ = 'locations'
    id = db.Column(db.Integer, primary_key=True)
    barcode = db.Column(db.String(64), unique=True, nullable=False, index=True)
    description = db.Column(db.String(255))
    category_id = db.Column(db.Integer, db.ForeignKey('location_categories.id'), nullable=False)

    stock_items = db.relationship('StockItem', backref='location', lazy='dynamic')

    def __repr__(self):
        return f"<Location {self.barcode}>"

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    barcode = db.Column(db.String(64), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)

    stock_items = db.relationship('StockItem', backref='product', lazy='dynamic')

    def __repr__(self):
        return f"<Product {self.barcode} - {self.name}>"

class StockItem(db.Model):
    __tablename__ = 'stock_items'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False, default=0)

    def __repr__(self):
        return f"<StockItem P:{self.product_id} L:{self.location_id} Q:{self.quantity}>"

class StockMovement(db.Model):
    __tablename__ = 'stock_movements'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    quantity = db.Column(db.Integer, nullable=False)
    action = db.Column(db.String(16), nullable=False)  # 'add', 'remove', 'transfer'
    timestamp = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    product = db.relationship('Product')
    location = db.relationship('Location')
    user = db.relationship('User')

    def __repr__(self):
        return f"<StockMovement {self.action} q={self.quantity}>"
