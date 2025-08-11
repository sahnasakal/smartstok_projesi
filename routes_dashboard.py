from flask import Blueprint, render_template
from flask_login import login_required
from sqlalchemy import func
from models import db, Product, Location, StockItem

dashboard_bp = Blueprint('dashboard_bp', __name__)

@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    total_products = Product.query.count()
    total_locations = Location.query.count()
    
    occupied_locations_query = db.session.query(StockItem.location_id).filter(StockItem.quantity > 0).distinct()
    occupied_locations = occupied_locations_query.count()
    
    empty_locations = total_locations - occupied_locations
    location_fill_rate = round((occupied_locations / total_locations) * 100, 2) if total_locations > 0 else 0

    return render_template("dashboard.html",
                           title="Ana Panel",
                           total_products=total_products,
                           total_locations=total_locations,
                           location_fill_rate=location_fill_rate,
                           empty_locations=empty_locations)