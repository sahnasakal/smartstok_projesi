from celery_app import celery
from models import db, Product, StockItem, StockMovement, ProductAnalysis, LocationAnalysis, Location
from sqlalchemy import func
from datetime import datetime, timedelta

@celery.task
def run_daily_strategic_analysis():
    print("Günlük stratejik analiz görevi başlatılıyor...")
    
    # --- ÜRÜN ANALİZİ ---
    products = Product.query.all()
    analysis_period_days = 30  # Analiz için son 30 günü baz alıyoruz
    start_date = datetime.utcnow() - timedelta(days=analysis_period_days)

    for product in products:
        # Mevcut stoğu hesapla
        current_stock = db.session.query(func.sum(StockItem.quantity)).filter(StockItem.product_id == product.id).scalar() or 0
        
        # Son 30 gündeki satış hızını (stok çıkışlarını) hesapla
        total_moved_out = db.session.query(func.sum(StockMovement.quantity)).filter(
            StockMovement.product_id == product.id,
            StockMovement.quantity < 0,
            StockMovement.timestamp >= start_date
        ).scalar() or 0
        
        # Gunicorn'un eksi(-) değerleri pozitif yaptığı için mutlak değer alıyoruz
        total_moved_out = abs(total_moved_out)
        
        daily_velocity = total_moved_out / analysis_period_days if total_moved_out > 0 else 0.0
        
        # Kalan stok gününü hesapla
        days_of_supply = int(current_stock / daily_velocity) if daily_velocity > 0 else 9999
        
        # Son hareket tarihini bul
        last_movement = StockMovement.query.filter_by(product_id=product.id).order_by(StockMovement.timestamp.desc()).first()
        last_movement_date = last_movement.timestamp if last_movement else None
        
        # Durumu belirle (basit kurallar)
        status = 'HEALTHY' # Varsayılan
        if daily_velocity > 0 and days_of_supply < 15: # 15 günden az stoğu kalmışsa
            status = 'REORDER_NOW'
        elif last_movement_date and last_movement_date < datetime.utcnow() - timedelta(days=90): # 90 gündür hareket görmemişse
            status = 'SLOW_MOVING'
            
        # Analiz kaydını bul veya oluştur ve güncelle
        analysis = ProductAnalysis.query.filter_by(product_id=product.id).first()
        if not analysis:
            analysis = ProductAnalysis(product_id=product.id)
            db.session.add(analysis)
            
        analysis.analysis_date = datetime.utcnow()
        analysis.daily_velocity = daily_velocity
        analysis.days_of_supply = days_of_supply
        analysis.last_movement_date = last_movement_date
        analysis.status = status

    # --- LOKASYON ANALİZİ ---
    locations = Location.query.all()
    for loc in locations:
        pick_count = db.session.query(func.count(StockMovement.id)).filter(
            StockMovement.location_id == loc.id,
            StockMovement.quantity < 0,
            StockMovement.timestamp >= start_date
        ).scalar() or 0
        
        place_count = db.session.query(func.count(StockMovement.id)).filter(
            StockMovement.location_id == loc.id,
            StockMovement.quantity > 0,
            StockMovement.timestamp >= start_date
        ).scalar() or 0
        
        total_movements = pick_count + place_count
        
        status = 'NORMAL'
        if total_movements > 50: # Son 30 günde 50'den fazla hareket gördüyse (bu değer ayarlanabilir)
            status = 'HOT_ZONE'
        elif total_movements < 5: # 5'ten az hareket gördüyse
            status = 'COLD_ZONE'
            
        loc_analysis = LocationAnalysis.query.filter_by(location_id=loc.id).first()
        if not loc_analysis:
            loc_analysis = LocationAnalysis(location_id=loc.id)
            db.session.add(loc_analysis)
            
        loc_analysis.analysis_date = datetime.utcnow()
        loc_analysis.total_movements = total_movements
        loc_analysis.pick_count = pick_count
        loc_analysis.place_count = place_count
        loc_analysis.status = status
        
    db.session.commit()
    print("Günlük stratejik analiz görevi tamamlandı.")
    return "Analysis complete."