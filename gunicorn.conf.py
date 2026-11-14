import os
from app import validate_configuration
validate_configuration()
bind = '0.0.0.0:' + os.getenv('PORT', '8080')
workers = 1
threads = 8
timeout = 180
accesslog = '-'
errorlog = '-'
