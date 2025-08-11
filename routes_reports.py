from flask import Blueprint, render_template, request, abort
from flask_login import login_required, current_user
from models import db, Product, Location, ProductAnalysis, LocationAnalysis

reports_bp = Blueprint('reports_bp', __name__)

@reports_bp.route('/reports/strategic-analysis')
@login_required
def strategic_analysis_panel():
    if not current_user.can('view_stock'):
        abort(403)
    
    products_to_reorder = ProductAnalysis.query.filter_by(status='REORDER_NOW').join(Product).order_by(ProductAnalysis.days_of_supply).all()
    slow_moving_products = ProductAnalysis.query.filter_by(status='SLOW_MOVING').join(Product).order_by(ProductAnalysis.last_movement_date).all()
    
    location_activity = LocationAnalysis.query.join(Location).order_by(LocationAnalysis.total_movements.desc()).all()

    return render_template(
        "strategic_analysis_panel.html",
        products_to_reorder=products_to_reorder,
        slow_moving_products=slow_moving_products,
        location_activity=location_activity,
        title="Stratejik Analiz Paneli"
    )