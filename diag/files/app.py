import os
import traceback
import pandas as pd
from flask import Flask, jsonify, render_template, request, redirect, url_for, abort, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from sqlalchemy import func, not_
from werkzeug.utils import secure_filename
from jinja2 import TemplateNotFound

# --- EXTENSIONS ---
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message = "Bu sayfayı görüntülemek için lütfen giriş yapın."
login_manager.login_message_category = "info"

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    from models import (
        User, Product, Location, StockItem, StockMovement,
        LocationCategory, Role, Permission
    )

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # -------------------------------
    # GENEL
    # -------------------------------
    @app.route('/')
    @login_required
    def index():
        return redirect(url_for('dashboard'))

    @app.route('/dashboard')
    @login_required
    def dashboard():
        return render_template('dashboard.html', title="Ana Panel")

    # -------------------------------
    # GİRİŞ / ÇIKIŞ
    # -------------------------------
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            user = User.query.filter_by(username=username).first()
            if user is None or not user.check_password(password):
                flash('Geçersiz kullanıcı adı veya şifre', 'danger')
                return redirect(url_for('login'))
            login_user(user, remember=True)
            return redirect(url_for('dashboard'))
        return render_template('login.html')

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        return redirect(url_for('login'))

    # -------------------------------
    # API
    # -------------------------------
    @app.route('/api/search_barcode')
    @login_required
    def search_barcode():
        barcode = request.args.get('barcode', '')
        if not barcode:
            return jsonify({'error': 'Barkod parametresi eksik'}), 400
        product = Product.query.filter_by(barcode=barcode).first()
        if product:
            return jsonify({'type': 'product', 'id': product.id, 'name': product.name, 'barcode': product.barcode})
        location = Location.query.filter_by(barcode=barcode).first()
        if location:
            return jsonify({'type': 'location', 'id': location.id, 'description': location.description, 'barcode': location.barcode})
        return jsonify({'error': 'Barkod bulunamadı'}), 404

    # -------------------------------
    # LOKASYON KATEGORİLERİ
    # -------------------------------
    @app.route('/location_categories')
    @login_required
    def location_categories():
        if not current_user.can('edit_catalog'): abort(403)
        categories = LocationCategory.query.order_by(LocationCategory.name).all()
        return render_template('location_categories.html', categories=categories, title="Lokasyon Kategorileri")

    @app.route('/location_categories/add', methods=['GET', 'POST'])
    @login_required
    def add_location_category():
        if not current_user.can('edit_catalog'): abort(403)
        if request.method == 'POST':
            name = (request.form.get('name') or '').strip()
            if name and not LocationCategory.query.filter_by(name=name).first():
                db.session.add(LocationCategory(name=name))
                db.session.commit()
                flash('Kategori başarıyla eklendi.', 'success')
            else:
                flash('Bu kategori zaten mevcut veya geçersiz isim.', 'danger')
            return redirect(url_for('location_categories'))
        return render_template('add_edit_location_category.html', title="Yeni Kategori Ekle")

    @app.route('/location_categories/edit/<int:id>', methods=['GET', 'POST'])
    @login_required
    def edit_location_category(id):
        if not current_user.can('edit_catalog'): abort(403)
        category = LocationCategory.query.get_or_404(id)
        if request.method == 'POST':
            name = (request.form.get('name') or '').strip()
            if name:
                category.name = name
                db.session.commit()
                flash('Kategori güncellendi.', 'success')
            else:
                flash('Geçersiz isim.', 'danger')
            return redirect(url_for('location_categories'))
        return render_template('add_edit_location_category.html', category=category, title="Kategoriyi Düzenle")

    @app.route('/location_categories/delete/<int:id>', methods=['POST'])
    @login_required
    def delete_location_category(id):
        if not current_user.can('delete_catalog'): abort(403)
        category = LocationCategory.query.get_or_404(id)
        if category.locations.first():
            flash('Bu kategoriye atanmış lokasyonlar var. Önce lokasyonları silin veya başka bir kategoriye atayın.', 'danger')
        else:
            db.session.delete(category)
            db.session.commit()
            flash('Kategori silindi.', 'success')
        return redirect(url_for('location_categories'))

    # -------------------------------
    # LOKASYONLAR
    # -------------------------------
    @app.route('/locations')
    @login_required
    def locations():
        page = request.args.get('page', 1, type=int)
        query = request.args.get('query', '')
        base_query = Location.query.join(LocationCategory)
        if query:
            search = f"%{query}%"
            base_query = base_query.filter(db.or_(
                Location.barcode.ilike(search),
                Location.description.ilike(search),
                LocationCategory.name.ilike(search)
            ))
        pagination = base_query.order_by(Location.barcode).paginate(
            page=page, per_page=app.config['POSTS_PER_PAGE'], error_out=False)
        return render_template('locations.html', pagination=pagination, query=query, title="Lokasyonlar")

    @app.route('/locations/add', methods=['GET', 'POST'])
    @login_required
    def add_location():
        if not current_user.can('edit_catalog'):
            flash('Yeni lokasyon ekleme yetkiniz yok.', 'info')
            return redirect(url_for('locations'))
        categories = LocationCategory.query.order_by(LocationCategory.name).all()
        if not categories:
            flash('Önce bir Lokasyon Kategorisi eklemelisiniz!', 'danger')
            return redirect(url_for('add_location_category'))
        if request.method == 'POST':
            barcode = (request.form.get('barcode') or '').strip()
            description = (request.form.get('description') or '').strip()
            category_id = request.form.get('category_id')
            if barcode and not Location.query.filter_by(barcode=barcode).first():
                db.session.add(Location(barcode=barcode, description=description, category_id=category_id))
                db.session.commit()
                flash('Lokasyon başarıyla eklendi.', 'success')
                return redirect(url_for('locations'))
            else:
                flash('Bu barkod zaten mevcut veya geçersiz.', 'danger')
        return render_template('add_edit_location.html', categories=categories, title="Yeni Lokasyon Ekle",
                               location=None, view_only=False)

    @app.route('/locations/edit/<int:id>', methods=['GET', 'POST'])
    @login_required
    def edit_location(id):
        location = Location.query.get_or_404(id)
        view_only = not current_user.can('edit_catalog')
        if request.method == 'POST':
            if view_only: abort(403)
            location.description = request.form.get('description')
            location.category_id = request.form.get('category_id')
            db.session.commit()
            flash('Lokasyon güncellendi.', 'success')
            return redirect(url_for('locations'))
        categories = LocationCategory.query.order_by(LocationCategory.name).all() if not view_only else None
        title = "Lokasyon Görüntüle" if view_only else "Lokasyonu Düzenle"
        return render_template('add_edit_location.html', location=location, categories=categories,
                               title=title, view_only=view_only)

    @app.route('/locations/bulk_delete', methods=['POST'])
    @login_required
    def bulk_delete_locations():
        if not current_user.can('delete_catalog'): abort(403)
        location_ids = request.form.getlist('location_ids')
        if not location_ids:
            flash('Silmek için en az bir lokasyon seçmelisiniz.', 'info')
            return redirect(url_for('locations'))
        try:
            StockMovement.query.filter(StockMovement.location_id.in_(location_ids)).delete(synchronize_session=False)
            StockItem.query.filter(StockItem.location_id.in_(location_ids)).delete(synchronize_session=False)
            Location.query.filter(Location.id.in_(location_ids)).delete(synchronize_session=False)
            db.session.commit()
            flash(f'{len(location_ids)} adet lokasyon ve ilgili stokları başarıyla silindi.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Lokasyonlar silinirken bir hata oluştu: {e}', 'danger')
        return redirect(url_for('locations'))

    @app.route('/locations/empty')
    @login_required
    def empty_locations():
        locations_with_stock = db.session.query(StockItem.location_id).filter(StockItem.quantity > 0).distinct()
        empty_locs = Location.query.filter(not_(Location.id.in_(locations_with_stock))).order_by(Location.barcode).all()
        return render_template('empty_locations.html', locations=empty_locs, title="Boş Lokasyonlar")

    # -------------------------------
    # ÜRÜNLER
    # -------------------------------
    @app.route('/products')
    @login_required
    def products():
        page = request.args.get('page', 1, type=int)
        query = request.args.get('query', '')
        base_query = Product.query
        if query:
            search = f"%{query}%"
            base_query = base_query.filter(db.or_(Product.barcode.ilike(search), Product.name.ilike(search)))
        pagination = base_query.order_by(Product.name).paginate(
            page=page, per_page=app.config['POSTS_PER_PAGE'], error_out=False)
        return render_template('products.html', pagination=pagination, query=query, title="Ürünler")

    @app.route('/products/add', methods=['GET', 'POST'])
    @login_required
    def add_product():
        if not current_user.can('edit_catalog'):
            flash('Yeni ürün ekleme yetkiniz yok.', 'info')
            return redirect(url_for('products'))
        if request.method == 'POST':
            barcode = (request.form.get('barcode') or '').strip()
            name = (request.form.get('name') or '').strip()
            description = request.form.get('description') or ''
            if not barcode or not name:
                flash('Barkod ve İsim zorunlu.', 'danger')
            elif Product.query.filter_by(barcode=barcode).first():
                flash('Bu barkod zaten kayıtlı!', 'danger')
            else:
                db.session.add(Product(barcode=barcode, name=name, description=description))
                db.session.commit()
                flash('Ürün başarıyla eklendi!', 'success')
                return redirect(url_for('products'))
        return render_template('add_edit_product.html', title="Yeni Ürün Ekle", product=None, view_only=False)

    @app.route('/products/edit/<int:id>', methods=['GET', 'POST'])
    @login_required
    def edit_product(id):
        product = Product.query.get_or_404(id)
        view_only = not current_user.can('edit_catalog')
        if request.method == 'POST':
            if view_only: abort(403)
            product.name = request.form.get('name')
            product.description = request.form.get('description')
            db.session.commit()
            flash('Ürün güncellendi.', 'success')
            return redirect(url_for('products'))
        title = "Ürün Görüntüle" if view_only else "Ürünü Düzenle"
        return render_template('add_edit_product.html', product=product, title=title, view_only=view_only)

    @app.route('/products/bulk_delete', methods=['POST'])
    @login_required
    def bulk_delete_products():
        if not current_user.can('delete_catalog'): abort(403)
        product_ids = request.form.getlist('product_ids')
        if not product_ids:
            flash('Silmek için en az bir ürün seçmelisiniz.', 'info')
            return redirect(url_for('products'))
        try:
            StockMovement.query.filter(StockMovement.product_id.in_(product_ids)).delete(synchronize_session=False)
            StockItem.query.filter(StockItem.product_id.in_(product_ids)).delete(synchronize_session=False)
            Product.query.filter(Product.id.in_(product_ids)).delete(synchronize_session=False)
            db.session.commit()
            flash(f'{len(product_ids)} adet ürün ve ilgili stokları başarıyla silindi.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Ürünler silinirken bir hata oluştu: {e}', 'danger')
        return redirect(url_for('products'))

    # -------------------------------
    # STOK
    # -------------------------------
    @app.route('/stock')
    @login_required
    def stock():
        page = request.args.get('page', 1, type=int)
        query = request.args.get('query', '')
        base_query = db.session.query(StockItem, Product, Location).join(Product).join(Location).filter(StockItem.quantity > 0)
        if query:
            search = f"%{query}%"
            base_query = base_query.filter(db.or_(Product.name.ilike(search),
                                                  Product.barcode.ilike(search),
                                                  Location.barcode.ilike(search),
                                                  Location.description.ilike(search)))
        pagination = base_query.order_by(Product.name, Location.barcode).paginate(
            page=page, per_page=app.config['POSTS_PER_PAGE'], error_out=False)
        return render_template('stock.html', pagination=pagination, query=query, title="Stok Durumu")

    @app.route('/scan')
    @login_required
    def scan():
        return render_template('scan.html', title="Barkod Okut")

    @app.route('/stock/add', methods=['GET', 'POST'])
    @login_required
    def add_stock():
        if not current_user.can('add_stock'):
            flash('Stoğa ürün ekleme yetkiniz yok.', 'info')
            return redirect(url_for('stock'))
        if request.method == 'POST':
            flash('Stok ekleme işlemi (demo).', 'info')
            return redirect(url_for('stock'))
        return render_template('add_remove_stock.html', action='add', title="Stoğa Ekle")

    @app.route('/stock/remove', methods=['GET', 'POST'])
    @login_required
    def remove_stock():
        if not current_user.can('remove_stock'):
            flash('Stoktan ürün düşme yetkiniz yok.', 'info')
            return redirect(url_for('stock'))
        if request.method == 'POST':
            flash('Stok düşme işlemi (demo).', 'info')
            return redirect(url_for('stock'))
        return render_template('add_remove_stock.html', action='remove', title="Stoktan Düş")

    @app.route('/stock/transfer', methods=['GET', 'POST'])
    @login_required
    def stock_transfer():
        if not current_user.can('transfer_stock'):
            flash('Stok transferi yapma yetkiniz yok.', 'info')
            return redirect(url_for('stock'))
        if request.method == 'POST':
            flash('Stok transfer işlemi (demo).', 'info')
            return redirect(url_for('stock'))
        return render_template('stock_transfer.html', title="Stok Transferi")

    @app.route('/stock/history')
    @login_required
    def stock_history():
        page = request.args.get('page', 1, type=int)
        query = request.args.get('query', '')
        base_query = StockMovement.query.join(Product).join(Location).join(User)
        if query:
            search = f"%{query}%"
            base_query = base_query.filter(db.or_(Product.name.ilike(search),
                                                  Product.barcode.ilike(search),
                                                  Location.barcode.ilike(search),
                                                  User.username.ilike(search)))
        pagination = base_query.order_by(StockMovement.timestamp.desc()).paginate(
            page=page, per_page=app.config['POSTS_PER_PAGE'], error_out=False)
        return render_template('stock_history.html', pagination=pagination, query=query, title="Stok Geçmişi")

    # -------------------------------
    # YÖNETİCİ – Roller
    # -------------------------------
    @app.route('/admin/roles')
    @login_required
    def roles():
        if not current_user.is_admin: abort(403)
        all_roles = Role.query.order_by(Role.id).all()
        return render_template('roles.html', roles=all_roles, title="Rol Yönetimi")

    @app.route('/admin/roles/add', methods=['GET', 'POST'])
    @login_required
    def add_role():
        if not current_user.is_admin: abort(403)
        if request.method == 'POST':
            name = (request.form.get('name') or '').strip()
            if not name:
                flash('Rol adı zorunlu.', 'danger')
                return redirect(request.url)
            if Role.query.filter_by(name=name).first():
                flash('Bu rol zaten mevcut.', 'warning')
                return redirect(request.url)
            role = Role(name=name)
            db.session.add(role)
            db.session.commit()
            flash('Rol eklendi.', 'success')
            return redirect(url_for('roles'))
        return render_template('add_edit_role.html', title="Rol Ekle")

    @app.route('/admin/roles/edit/<int:id>', methods=['GET', 'POST'])
    @login_required
    def edit_role(id):
        if not current_user.is_admin: abort(403)
        role = Role.query.get_or_404(id)
        if request.method == 'POST':
            name = (request.form.get('name') or '').strip()
            if not name:
                flash('Rol adı zorunlu.', 'danger')
                return redirect(request.url)
            if Role.query.filter(Role.id != id, Role.name == name).first():
                flash('Bu isimde başka bir rol var.', 'warning')
                return redirect(request.url)
            role.name = name
            db.session.commit()
            flash('Rol güncellendi.', 'success')
            return redirect(url_for('roles'))
        return render_template('add_edit_role.html', role=role, title="Rolü Düzenle")

    @app.route('/admin/roles/delete/<int:id>', methods=['POST'])
    @login_required
    def delete_role(id):
        if not current_user.is_admin: abort(403)
        role = Role.query.get_or_404(id)
        if role.users.count() > 0:
            flash('Bu role atanmış kullanıcılar var. Önce kullanıcıların rolünü değiştirin.', 'danger')
        else:
            db.session.delete(role)
            db.session.commit()
            flash('Rol silindi.', 'success')
        return redirect(url_for('roles'))

    # -------------------------------
    # VERİ İÇE AKTARMA
    # -------------------------------
    @app.route('/import/<string:data_type>', methods=['GET', 'POST'])
    @login_required
    def import_data(data_type):
        if data_type not in ('products', 'locations'):
            abort(404)
        if request.method == 'POST':
            file = request.files.get('file')
            if not file or file.filename == '':
                flash('Lütfen bir dosya seçin.', 'danger')
                return redirect(request.url)

            os.makedirs('/app/uploads', exist_ok=True)
            fname = secure_filename(file.filename)
            fpath = os.path.join('/app/uploads', fname)
            file.save(fpath)

            try:
                if fname.lower().endswith('.xlsx'):
                    df = pd.read_excel(fpath)
                else:
                    df = pd.read_csv(fpath)

                if data_type == 'products':
                    for _, r in df.iterrows():
                        name = (str(r.get('name') or '').strip())
                        barcode = (str(r.get('barcode') or '').strip())
                        if not name or not barcode:
                            continue
                        if not Product.query.filter_by(barcode=barcode).first():
                            p = Product(name=name, barcode=barcode, description=(r.get('description') or ''))
                            db.session.add(p)

                elif data_type == 'locations':
                    for _, r in df.iterrows():
                        barcode = (str(r.get('barcode') or '').strip())
                        description = (str(r.get('description') or '').strip())
                        if not barcode:
                            continue
                        if not Location.query.filter_by(barcode=barcode).first():
                            cat_name = (str(r.get('category_name') or '').strip())
                            cat = None
                            if cat_name:
                                cat = LocationCategory.query.filter_by(name=cat_name).first()
                                if not cat:
                                    cat = LocationCategory(name=cat_name)
                                    db.session.add(cat); db.session.flush()
                            loc = Location(barcode=barcode, description=description,
                                           category_id=(cat.id if cat else None))
                            db.session.add(loc)

                db.session.commit()
                flash(f'{data_type} içe aktarma tamamlandı.', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'İçe aktarma hatası: {e}', 'danger')
            finally:
                try: os.remove(fpath)
                except Exception: pass

            return redirect(url_for('products' if data_type == 'products' else 'locations'))
        return render_template('import_data.html', data_type=data_type, title="Veri İçe Aktarma")

    # -------------------------------
    # HATA SAYFASI
    # -------------------------------
    @app.errorhandler(404)
    def not_found(e):
        # 404.html yoksa düz metne düş
        try:
            return render_template("404.html"), 404
        except TemplateNotFound:
            return "404 Not Found", 404

    return app

app = create_app()

if __name__ == '__main__':
    app.run()
