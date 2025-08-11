from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')

    db.init_app(app)
    login_manager.init_app(app)

    # Register blueprints
    from .routes.reports import reports_bp
    app.register_blueprint(reports_bp)

    # Add more blueprints as needed
    return app