from .base import *

DEBUG = False

# Elasticsearch
ELASTICSEARCH_URL = os.environ.get('BONSAI_URL')
ELASTICSEARCH_USERNAME = os.environ.get('ELASTICSEARCH_USERNAME', '')
ELASTICSEARCH_PASSWORD = os.environ.get('ELASTICSEARCH_PASSWORD', '')
