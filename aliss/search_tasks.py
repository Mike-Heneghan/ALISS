from django.conf import settings

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from elasticsearch_dsl import Q

from aliss.models import Organisation, Service, Postcode
from aliss.search import _get_connection, service_to_body, organisation_to_body, service_mapping, organisation_mapping


index_settings = {
    'analysis': {
        "filter": {
            "my_stop": {
                "type": "stop",
                "stopwords": "_english_"
            },
            "custom_shingle": {
                "type": "shingle",
                "min_shingle_size": 2,
                "max_shingle_size": 3,
                "output_unigrams": True
            },
            "my_char_filter": {
                "type": "pattern_replace",
                "pattern": " ",
                "replacement": ""
            }
        },
        'analyzer': {
            'description_analyzer': {
                'type': 'custom',
                'tokenizer': 'standard',
                'char_filter': ['html_strip'],
                'filter': ['standard', 'lowercase', 'my_stop']
            },
            "bigram_combiner": {
                "tokenizer": "standard",
                "filter": ["lowercase", "custom_shingle", "my_char_filter", "my_stop"]
            }
        }
    }
}


def create_service_index(connection=None):
    if connection==None:
        connection = _get_connection()
    body = {
        'mappings': {
            'service': { 'properties': service_mapping }
        },
        'settings': index_settings
    }
    connection.indices.create(index='search', body=body)


def create_org_index(connection=None):
    if connection==None:
        connection = _get_connection()
    body = {
        'mappings': {
            'organisation':{ 'properties': organisation_mapping }
        },
        'settings': index_settings
    }
    connection.indices.create(index='organisation_search', body=body)


def create_index():
    connection = _get_connection()
    create_service_index(connection)
    create_org_index(connection)


def create_slugs(force=False):
    connection = _get_connection()
    services = Service.objects
    organisations = Organisation.objects

    if force:
        services = services.all()
        organisations = organisations.all()
    else:
        services = services.filter(slug=None).all()
        organisations = organisations.filter(slug=None).all()

    print("No. of service slugs to update: ", services.count())
    for s in services:
        s.generate_slug(force)
        s.save()

    print("No. of org slugs to update: ", organisations.count())
    for o in organisations:
        o.generate_slug(force)
        o.save()


def create_last_edited(force=False):
    connection = _get_connection()
    services = Service.objects
    organisations = Organisation.objects

    if force:
        services = services.all()
        organisations = organisations.all()
    else:
        services = services.filter(last_edited=None).all()
        organisations = organisations.filter(last_edited=None).all()

    print("No.of services with last_edited to update: ", organisations.count())
    for s in services:
        s.generate_last_edited(force)
        s.save()

    print("No. of org with last_edited updated: ", organisations.count())
    for o in organisations:
        o.generate_last_edited(force)
        o.save()


def index_services(connection=None):
    if connection == None:
        connection = _get_connection()
    services = Service.objects.filter(organisation__published=True).all().iterator()
    for ok in bulk(connection, ({
        '_index': 'search',
        '_type': 'service',
        '_id': service.pk,
        '_source': service_to_body(service)
    } for service in services)):
        print("%s Services indexed" % ok)


def index_organisations(organisations=Organisation.objects.all(), connection=None):
    if connection == None:
        connection = _get_connection()
    organisations = organisations.iterator()
    for ok in bulk(connection, ({
        '_index':'organisation_search',
        '_type':'organisation',
        '_id':organisation.pk,
        '_source': organisation_to_body(organisation)
    } for organisation in organisations)):
        print("%s Organisations indexed" % ok)


def index_all():
    connection = _get_connection()
    index_services()
    index_organisations()


def delete_index():
    connection = _get_connection()
    connection.indices.delete('search', ignore=404)
    connection.indices.delete('organisation_search', ignore=404)