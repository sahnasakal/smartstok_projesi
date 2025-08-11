from app import create_app
from celery import Celery
from celery.schedules import crontab

flask_app = create_app()

def make_celery(app):
    celery = Celery(app.import_name)
    celery.config_from_object(app.config, namespace='CELERY')
    celery.conf.update(app.config)
    celery.autodiscover_tasks()

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery

celery = make_celery(flask_app)

celery.conf.beat_schedule = {
    'run-daily-analysis-every-night': {
        'task': 'tasks.run_daily_strategic_analysis',
        'schedule': crontab(hour=3, minute=5),
    },
}