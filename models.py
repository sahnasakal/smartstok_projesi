from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import datetime

# Roller ve İzinler arasındaki çoktan-çoğa ilişki için yardımcı tablo
roles_permissions = db.Table('roles_permissions',
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permissions.id'), primary_key=True)
)

class Permission(db.Model):
    __tablename__ = 'permissions'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False) # Örn: 'edit_catalog'
    description = db.Column(db.String(128)) # Örn: 'Katalog Düzenleme'

class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    users = db.relationship('User', backref='role', lazy='dynamic')
    permissions = db.relationship('Permission', secondary=roles_permissions, backref=db.backref('roles', lazy='dynamic'), lazy='dynamic')

    def has_permission(self, perm_name):
        return self.permissions.filter_by(name=perm_name).first() is not None

    @staticmethod
    def insert_roles():
        all_permissions = {
            'view_stock': 'Stok Görüntüleme',
            'add_stock': 'Stok Ekleme',
            'remove_stock': 'Stok Düşme',
            'transfer_stock': 'Stok Transferi',
            'edit_catalog': 'Katalog Düzenleme',
            'delete_catalog': 'Katalog Silme',
            'manage_users': 'Kullanıcı Yönetimi',
            'admin': 'Tam Yetki (Admin)'
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
            'Depo Sorumlusu': [
                'view_stock', 'add_stock', 'remove_stock', 'transfer_stock',
                'edit_catalog', 'delete_catalog'
            ],
            'Admin': [p for p in all_permissions.keys()]
        }
        
        for r_name, r_perms in roles_with_permissions.items():
            role = Role.query.filter_by(name=r_name).first()
            if role is None:
                role = Role(name=r_name)
                db.session.add(role)
            
            role.permissions = [] # Önceki izinleri temizle
            
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

    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

    def can(self, perm_name):
        return self.role is not None and self.role.has_permission(perm_name)

    @property
    def is_admin(self):
        return self.can('admin')

# --- Diğer Modeller (DEĞİŞİKLİK YOK) ---
class LocationCategory(db.Model):
    __tablename__ = 'location_categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    locations = db.relationship('Location', backref='category', lazy='dynamic')

class Location(db.Model):
    __tablename__ = 'locations'
    id = db.Column(db.Integer, primary_key=True)
    barcode = db.Column(db.String(128), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('location_categories.id'), nullable=False)
    stock_items = db.relationship('StockItem', backref='location', lazy='dynamic', cascade="all, delete-orphan")
    analysis = db.relationship('LocationAnalysis', back_populates='location', uselist=False, cascade="all, delete-orphan")

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    barcode = db.Column(db.String(128), unique=True, nullable=False, index=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    # YENİ EKLENEN ALAN
    minimum_stock_level = db.Column(db.Integer, nullable=False, default=0, server_default='0')

    stock_items = db.relationship('StockItem', backref='product', lazy='dynamic', cascade="all, delete-orphan")
    analysis = db.relationship('ProductAnalysis', back_populates='product', uselist=False, cascade="all, delete-orphan")

    # MEVCUT STOK MİKTARINI HESAPLAYAN YARDIMCI ÖZELLİK (PROPERTY)
    @property
    def total_quantity(self):
        """Bu ürünün tüm lokasyonlardaki toplam stok miktarını döndürür."""
        # self.stock_items, veritabanı sorgusu olduğu için verimli değildir.
        # Bunun yerine doğrudan bir toplama sorgusu daha performanslıdır.
        total = db.session.query(db.func.sum(StockItem.quantity)).filter(StockItem.product_id == self.id).scalar()
        return total or 0

class StockItem(db.Model):
    __tablename__ = 'stock_items'
    id = db.Column(db.Integer, primary_key=True)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('product_id', 'location_id', name='_product_location_uc'),)

class StockMovement(db.Model):
    __tablename__ = 'stock_movements'
    id = db.Column(db.Integer, primary_key=True)
    quantity = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.datetime.utcnow)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_ref = db.relationship('Product')
    location_ref = db.relationship('Location')
    user_ref = db.relationship('User')
    
class ProductAnalysis(db.Model):
    __tablename__ = 'product_analysis'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), unique=True, nullable=False, index=True)
    analysis_date = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    
    daily_velocity = db.Column(db.Float, default=0.0)
    days_of_supply = db.Column(db.Integer, default=9999)
    last_movement_date = db.Column(db.DateTime)
    status = db.Column(db.String(64), index=True) # Örn: 'REORDER_NOW', 'SLOW_MOVING', 'HEALTHY'

    product = db.relationship('Product', back_populates='analysis')

class LocationAnalysis(db.Model):
    __tablename__ = 'location_analysis'
    id = db.Column(db.Integer, primary_key=True)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), unique=True, nullable=False, index=True)
    analysis_date = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    
    total_movements = db.Column(db.Integer, default=0)
    pick_count = db.Column(db.Integer, default=0)
    place_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(64), index=True) # Örn: 'HOT_ZONE', 'COLD_ZONE', 'NORMAL'

    location = db.relationship('Location', back_populates='analysis')