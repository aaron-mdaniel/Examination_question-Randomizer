import os
from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "info"


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)

    app.config["SECRET_KEY"] = os.getenv(
        "SECRET_KEY", "dev-only-change-this-secret-before-deployment"
    )
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL", "sqlite:///" + os.path.join(app.instance_path, "exam_randomizer.db")
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    login_manager.init_app(app)

    from app.models import User, Question, Exam, GeneratedPaper, GeneratedPaperQuestion
    from app.auth import auth_bp
    from app.main import main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    with app.app_context():
        db.create_all()
        # Create a development teacher account only when no users exist.
        # Change this password immediately and remove this helper for deployment.
        if User.query.count() == 0:
            teacher = User(
                username="teacher",
                email="teacher@example.com",
                role="teacher",
            )
            teacher.set_password("ChangeMe123!")
            db.session.add(teacher)
            db.session.commit()

    return app
