from flask import Blueprint

payment = Blueprint('payment', __name__)

from app.payment import views