from celery import shared_task
from services.emails import EmailService

@shared_task(bind=True, autoretry_for=(Exception,), max_retries=3, countdown=60, ignore_result=True)
def send_email_task(self, to_email: str, subject: str, body: str):
    EmailService.send_email(to_email, subject, body)