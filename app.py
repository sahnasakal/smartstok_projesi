import os
from flask import Flask, jsonify, render_template, request, redirect, url_for, abort, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from sqlalchemy import func, not_
from werkzeug.utils import secure_filename
import pandas as pd
import traceback

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

    from routes_dashboard import dashboard_bp
    app.register_blueprint(dashboard_bp)
    from routes_reports import reports_bp
    app.register_blueprint(reports_bp)

    from models import User, Product, Location, StockItem, StockMovement, LocationCategory, Role, Permission

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.route('/')
    @login_required
    def index():
        return redirect(url_for('dashboard_bp.dashboard'))

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard_bp.dashboard'))
        if request.method == 'POST':
            user = User.query.filter_by(username=request.form['username']).first()
            if user is None or not user.check_password(request.form['password']):
                flash('Geçersiz kullanıcı adı veya şifre', 'danger')
                return redirect(url_for('login'))
            login_user(user, remember=True)
            return redirect(url_for('dashboard_bp.dashboard'))
        return render_template('login.html', title="Giriş Yap")

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        return redirect(url_for('login'))

    @app.route('/api/search_barcode')
    @login_required
    def search_barcode():
        barcode = request.args.get('barcode', '')
        if not barcode: return jsonify({'error': 'Barkod parametresi eksik'}), 400
        product = Product.query.filter_by(barcode=barcode).first()
        if product: return jsonify({'type': 'product', 'id': product.id, 'name': product.name, 'barcode': product.barcode})
        location = Location.query.filter_by(barcode=barcode).first()
        if location: return jsonify({'type': 'location', 'id': location.id, 'description': location.description, 'barcode': location.barcode})
        return jsonify({'error': 'Barkod bulunamadı'}), 404

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
            name = request.form.get('name')
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
            name = request.form.get('name')
            if name:
                category.name = name
                db.session.commit()
                flash('Kategori güncellendi.', 'success')
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

    @app.route('/locations')
    @login_required
    def locations():
        if not current_user.can('view_stock'): abort(403)
        page = request.args.get('page', 1, type=int)
        query = request.args.get('query', '')
        base_query = Location.query.join(LocationCategory)
        if query:
            search = f"%{query}%"
            base_query = base_query.filter(db.or_(Location.barcode.ilike(search), Location.description.ilike(search), LocationCategory.name.ilike(search)))
        pagination = base_query.order_by(Location.barcode).paginate(page=page, per_page=app.config['POSTS_PER_PAGE'], error_out=False)
        return render_template('locations.html', pagination=pagination, query=query, title="Lokasyonlar")

    @app.route('/locations/add', methods=['GET', 'POST'])
    @login_required
    def add_location():
        if not current_user.can('edit_catalog'): abort(403)
        categories = LocationCategory.query.order_by(LocationCategory.name).all()
        if not categories:
            flash('Önce bir Lokasyon Kategorisi eklemelisiniz!', 'danger')
            return redirect(url_for('add_location_category'))
        if request.method == 'POST':
            barcode = request.form.get('barcode')
            if barcode and not Location.query.filter_by(barcode=barcode).first():
                db.session.add(Location(barcode=barcode, description=request.form.get('description'), category_id=request.form.get('category_id')))
                db.session.commit()
                flash('Lokasyon başarıyla eklendi.', 'success')
                return redirect(url_for('locations'))
            else:
                flash('Bu barkod zaten mevcut veya geçersiz.', 'danger')
        return render_template('add_edit_location.html', categories=categories, title="Yeni Lokasyon Ekle")

    @app.route('/locations/edit/<int:id>', methods=['GET', 'POST'])
    @login_required
    def edit_location(id):
        if not current_user.can('edit_catalog'): abort(403)
        location = Location.query.get_or_404(id)
        categories = LocationCategory.query.order_by(LocationCategory.name).all()
        if request.method == 'POST':
            location.description = request.form.get('description')
            location.category_id = request.form.get('category_id')
            db.session.commit()
            flash('Lokasyon güncellendi.', 'success')
            return redirect(url_for('locations'))
        return render_template('add_edit_location.html', location=location, categories=categories, title="Lokasyonu Düzenle")

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
        if not current_user.can('view_stock'): abort(403)
        locations_with_stock = db.session.query(StockItem.location_id).filter(StockItem.quantity > 0).distinct()
        empty_locs = Location.query.filter(not_(Location.id.in_(locations_with_stock))).order_by(Location.barcode).all()
        return render_template('empty_locations.html', locations=empty_locs, title="Boş Lokasyonlar")

    @app.route('/products')
    @login_required
    def products():
        if not current_user.can('view_stock'): abort(403)
        page = request.args.get('page', 1, type=int)
        query = request.args.get('query', '')
        base_query = Product.query
        if query:
            search = f"%{query}%"
            base_query = base_query.filter(db.or_(Product.barcode.ilike(search), Product.name.ilike(search)))
        pagination = base_query.order_by(Product.name).paginate(page=page, per_page=app.config['POSTS_PER_PAGE'], error_out=False)
        return render_template('products.html', pagination=pagination, query=query, title="Ürünler")

    @app.route('/products/add', methods=['GET', 'POST'])
    @login_required
    def add_product():
        if not current_user.can('edit_catalog'): abort(403)
        if request.method == 'POST':
            barcode = request.form['barcode']
            if Product.query.filter_by(barcode=barcode).first():
                flash('Bu barkod zaten kayıtlı!', 'danger')
            else:
                db.session.add(Product(
                    barcode=barcode, 
                    name=request.form['name'], 
                    description=request.form['description'],
                    minimum_stock_level=request.form.get('minimum_stock_level', 0, type=int)
                ))
                db.session.commit()
                flash('Ürün başarıyla eklendi!', 'success')
                return redirect(url_for('products'))
        return render_template('add_edit_product.html', title="Yeni Ürün Ekle")

    @app.route('/products/edit/<int:id>', methods=['GET', 'POST'])
    @login_required
    def edit_product(id):
        if not current_user.can('edit_catalog'): abort(403)
        product = Product.query.get_or_404(id)
        if request.method == 'POST':
            product.name = request.form['name']
            product.description = request.form['description']
            product.minimum_stock_level = request.form.get('minimum_stock_level', 0, type=int)
            db.session.commit()
            flash('Ürün güncellendi.', 'success')
            return redirect(url_for('products'))
        return render_template('add_edit_product.html', product=product, title="Ürünü Düzenle")

    @app.route('/products/delete/<int:id>', methods=['POST'])
    @login_required
    def delete_product(id):
        if not current_user.can('delete_catalog'): abort(403)
        product = Product.query.get_or_404(id)
        StockMovement.query.filter_by(product_id=id).delete()
        StockItem.query.filter_by(product_id=id).delete()
        db.session.delete(product)
        db.session.commit()
        flash('Ürün ve ilgili tüm stok kayıtları silindi.', 'success')
        return redirect(url_for('products'))

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

    @app.route('/stock')
    @login_required
    def stock():
        page = request.args.get('page', 1, type=int)
        query = request.args.get('query', '')
        base_query = db.session.query(StockItem, Product, Location).join(Product).join(Location).filter(StockItem.quantity > 0)
        if query:
            search = f"%{query}%"
            base_query = base_query.filter(db.or_(Product.name.ilike(search), Product.barcode.ilike(search), Location.barcode.ilike(search), Location.description.ilike(search)))
        pagination = base_query.order_by(Product.name, Location.barcode).paginate(page=page, per_page=app.config['POSTS_PER_PAGE'], error_out=False)
        return render_template('stock.html', pagination=pagination, query=query, title="Stok Durumu")

    @app.route('/scan')
    @login_required
    def scan():
        return render_template('scan.html', title="Barkod Okut")

    @app.route('/stock/add', methods=['GET', 'POST'])
    @login_required
    def add_stock():
        if not current_user.can('add_stock'): abort(403)
        if request.method == 'POST':
            product_barcode = request.form['product_barcode']
            location_barcode = request.form['location_barcode']
            quantity = int(request.form['quantity'])
            product = Product.query.filter_by(barcode=product_barcode).first()
            location = Location.query.filter_by(barcode=location_barcode).first()
            if not product: flash('Ürün barkodu bulunamadı.', 'danger')
            elif not location: flash('Lokasyon barkodu bulunamadı.', 'danger')
            else:
                stock_item = StockItem.query.filter_by(product_id=product.id, location_id=location.id).first()
                if stock_item: stock_item.quantity += quantity
                else:
                    stock_item = StockItem(product_id=product.id, location_id=location.id, quantity=quantity)
                    db.session.add(stock_item)
                db.session.add(StockMovement(quantity=quantity, product_id=product.id, location_id=location.id, user_id=current_user.id))
                db.session.commit()
                flash(f'{quantity} adet {product.name} ürünü {location.barcode} lokasyonuna eklendi.', 'success')
                return redirect(url_for('stock'))
        return render_template('add_remove_stock.html', action='add', title="Stoğa Ekle")

    @app.route('/stock/remove', methods=['GET', 'POST'])
    @login_required
    def remove_stock():
        if not current_user.can('remove_stock'): abort(403)
        if request.method == 'POST':
            product_barcode = request.form['product_barcode']
            location_barcode = request.form['location_barcode']
            quantity = int(request.form['quantity'])
            product = Product.query.filter_by(barcode=product_barcode).first()
            location = Location.query.filter_by(barcode=location_barcode).first()
            if not product: flash('Ürün barkodu bulunamadı.', 'danger')
            elif not location: flash('Lokasyon barkodu bulunamadı.', 'danger')
            else:
                stock_item = StockItem.query.filter_by(product_id=product.id, location_id=location.id).first()
                if not stock_item or stock_item.quantity < quantity:
                    flash('Yetersiz stok veya ürün bu lokasyonda mevcut değil.', 'danger')
                else:
                    stock_item.quantity -= quantity
                    db.session.add(StockMovement(quantity=-quantity, product_id=product.id, location_id=location.id, user_id=current_user.id))
                    db.session.commit()
                    flash(f'{quantity} adet {product.name} ürünü {location.barcode} lokasyonundan düşüldü.', 'success')
                    return redirect(url_for('stock'))
        return render_template('add_remove_stock.html', action='remove', title="Stoktan Düş")

    @app.route('/stock/transfer', methods=['GET', 'POST'])
    @login_required
    def stock_transfer():
        if not current_user.can('transfer_stock'): abort(403)
        if request.method == 'POST':
            product_barcode = request.form['product_barcode']
            from_location_barcode = request.form['from_location_barcode']
            to_location_barcode = request.form['to_location_barcode']
            quantity = int(request.form['quantity'])
            product = Product.query.filter_by(barcode=product_barcode).first()
            from_location = Location.query.filter_by(barcode=from_location_barcode).first()
            to_location = Location.query.filter_by(barcode=to_location_barcode).first()
            if from_location_barcode == to_location_barcode: flash('Kaynak ve hedef lokasyon aynı olamaz.', 'danger')
            elif not product: flash('Ürün barkodu bulunamadı.', 'danger')
            elif not from_location: flash('Kaynak lokasyon barkodu bulunamadı.', 'danger')
            elif not to_location: flash('Hedef lokasyon barkodu bulunamadı.', 'danger')
            else:
                from_stock = StockItem.query.filter_by(product_id=product.id, location_id=from_location.id).first()
                if not from_stock or from_stock.quantity < quantity:
                    flash('Kaynak lokasyonda yetersiz stok.', 'danger')
                else:
                    from_stock.quantity -= quantity
                    db.session.add(StockMovement(quantity=-quantity, product_id=product.id, location_id=from_location.id, user_id=current_user.id))
                    to_stock = StockItem.query.filter_by(product_id=product.id, location_id=to_location.id).first()
                    if to_stock: to_stock.quantity += quantity
                    else:
                        db.session.add(StockItem(product_id=product.id, location_id=to_location.id, quantity=quantity))
                    db.session.add(StockMovement(quantity=quantity, product_id=product.id, location_id=to_location.id, user_id=current_user.id))
                    db.session.commit()
                    flash('Stok transferi başarıyla tamamlandı.', 'success')
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
            base_query = base_query.filter(db.or_(Product.name.ilike(search), Product.barcode.ilike(search), Location.barcode.ilike(search), User.username.ilike(search)))
        pagination = base_query.order_by(StockMovement.timestamp.desc()).paginate(page=page, per_page=app.config['POSTS_PER_PAGE'], error_out=False)
        return render_template('stock_history.html', pagination=pagination, query=query, title="Stok Geçmişi")

    @app.route('/import/<string:data_type>', methods=['GET', 'POST'])
    @login_required
    def import_data(data_type):
        if not current_user.can('edit_catalog'): abort(403)
        if request.method == 'POST':
            if 'file' not in request.files:
                flash('Dosya seçilmedi.', 'danger')
                return redirect(request.url)
            file = request.files['file']
            if file.filename == '':
                flash('Dosya seçilmedi.', 'danger')
                return redirect(request.url)
            if file:
                try:
                    df = pd.read_excel(file)
                    if data_type == 'products':
                        for _, row in df.iterrows():
                            if not Product.query.filter_by(barcode=str(row['barcode'])).first():
                                db.session.add(Product(barcode=str(row['barcode']), name=row['name'], description=str(row.get('description', ''))))
                        db.session.commit()
                        flash('Ürünler başarıyla içe aktarıldı.', 'success')
                    elif data_type == 'locations':
                         for _, row in df.iterrows():
                            barcode = str(row['barcode'])
                            category_name = str(row['category_name'])
                            category = LocationCategory.query.filter_by(name=category_name).first()
                            if not category:
                                flash(f"'{category_name}' adında bir kategori bulunamadı. Lütfen önce kategoriyi oluşturun.", "danger")
                                db.session.rollback()
                                return redirect(url_for('import_data', data_type='locations'))
                            if not Location.query.filter_by(barcode=barcode).first():
                                db.session.add(Location(barcode=barcode, description=str(row.get('description', '')), category_id=category.id))
                         db.session.commit()
                         flash('Lokasyonlar başarıyla içe aktarıldı.', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Dosya işlenirken bir hata oluştu: {e}', 'danger')
                return redirect(url_for(f'{data_type}'))
        return render_template('import_data.html', data_type=data_type, title="Toplu Veri Aktarımı")

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
            role_name = request.form.get('name')
            if role_name and not Role.query.filter_by(name=role_name).first():
                new_role = Role(name=role_name)
                selected_permissions = request.form.getlist('permissions')
                for p_name in selected_permissions:
                    perm = Permission.query.filter_by(name=p_name).first()
                    if perm: new_role.permissions.append(perm)
                db.session.add(new_role)
                db.session.commit()
                flash('Yeni rol başarıyla eklendi.', 'success')
                return redirect(url_for('roles'))
            else:
                flash('Bu rol adı zaten mevcut veya geçersiz.', 'danger')
        all_permissions = Permission.query.order_by('name').all()
        return render_template('add_edit_role.html', all_permissions=all_permissions, title="Yeni Rol Ekle", role=None)

    @app.route('/admin/roles/edit/<int:id>', methods=['GET', 'POST'])
    @login_required
    def edit_role(id):
        if not current_user.is_admin: abort(403)
        role = Role.query.get_or_404(id)
        if request.method == 'POST':
            role.name = request.form.get('name')
            role.permissions = []
            selected_permissions = request.form.getlist('permissions')
            for p_name in selected_permissions:
                perm = Permission.query.filter_by(name=p_name).first()
                if perm: role.permissions.append(perm)
            db.session.commit()
            flash('Rol güncellendi.', 'success')
            return redirect(url_for('roles'))
        all_permissions = Permission.query.order_by('name').all()
        return render_template('add_edit_role.html', role=role, all_permissions=all_permissions, title="Rolü Düzenle")

    @app.route('/admin/roles/delete/<int:id>', methods=['POST'])
    @login_required
    def delete_role(id):
        if not current_user.is_admin: abort(403)
        role = Role.query.get_or_404(id)
        if role.name in ['Admin', 'Depo Sorumlusu', 'Personel']:
            flash('Varsayılan roller silinemez.', 'danger')
            return redirect(url_for('roles'))
        if role.users.first():
            flash('Bu role atanmış kullanıcılar var. Rolü silemezsiniz.', 'danger')
            return redirect(url_for('roles'))
        db.session.delete(role)
        db.session.commit()
        flash('Rol silindi.', 'success')
        return redirect(url_for('roles'))

    @app.route('/users')
    @login_required
    def users():
        if not current_user.can('manage_users'): abort(403)
        user_list = User.query.order_by(User.username).all()
        return render_template('users.html', users=user_list, title="Kullanıcılar")

    @app.route('/users/add', methods=['GET', 'POST'])
    @login_required
    def add_user():
        if not current_user.can('manage_users'): abort(403)
        roles = Role.query.order_by(Role.name).all()
        if request.method == 'POST':
            username = request.form['username']
            if User.query.filter_by(username=username).first():
                flash('Bu kullanıcı adı zaten mevcut.', 'danger')
            else:
                new_user = User(username=username, role_id=request.form.get('role_id'))
                new_user.set_password(request.form['password'])
                db.session.add(new_user)
                db.session.commit()
                flash('Yeni kullanıcı başarıyla eklendi.', 'success')
                return redirect(url_for('users'))
        return render_template('add_user.html', roles=roles, title="Yeni Kullanıcı Ekle")

    @app.route('/users/delete/<int:id>', methods=['POST'])
    @login_required
    def delete_user(id):
        if not current_user.can('manage_users'): abort(403)
        if id == current_user.id:
            flash('Kendinizi silemezsiniz.', 'danger')
            return redirect(url_for('users'))
        user_to_delete = User.query.get_or_404(id)
        db.session.delete(user_to_delete)
        db.session.commit()
        flash('Kullanıcı silindi.', 'success')
        return redirect(url_for('users'))
    
    return app

app = create_app()

if __name__ == '__main__':
    app.run()