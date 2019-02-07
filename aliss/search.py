from django.conf import settings
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from elasticsearch_dsl import Q
from aliss.models import ServiceArea
from django.db.models import Case, When

def _get_connection():
    import certifi
    return Elasticsearch([settings.ELASTICSEARCH_URL], http_auth=(settings.ELASTICSEARCH_USERNAME, settings.ELASTICSEARCH_PASSWORD))


def get_connection():
    return _get_connection()


service_mapping = {
    'id': {'type': 'keyword'},
    'organisation': {
        'properties': {
            'id': {'type': 'keyword'},
            'name': {'type': 'text'},
            'slug': {'type': 'keyword'}
        }
    },
    'created_on': {'type': 'date'},
    'updated_on': {'type': 'date'},
    'last_edited': {'type': 'date'},
    'slug': {'type': 'keyword'},
    'name': {
        'type': 'text',
        'analyzer': 'bigram_combiner'
    },
    'description': {
        'type': 'text',
        'analyzer': 'description_analyzer',
    },
    'url': {'type': 'keyword'},
    'phone': {'type': 'keyword'},
    'email': {'type': 'keyword'},
    'categories': {
        'properties': {
            'id': {'type': 'integer'},
            'name': {'type': 'keyword'},
            'slug': {'type': 'keyword'}
        }
    },
    'parent_categories': {
        'properties': {
            'id': {'type': 'integer'},
            'name': {'type': 'keyword'},
            'slug': {'type': 'keyword'}
        }
    },
    'locations': {
        'properties': {
            'id': {'type': 'keyword'},
            'formatted_address': {'type': 'keyword'},
            'name': {'type': 'text'},
            'description': {
                'type': 'text',
                'analyzer': 'description_analyzer',
            },
            'street_address': {'type': 'keyword'},
            'locality': {'type': 'keyword'},
            'region': {'type': 'keyword'},
            'state': {'type': 'keyword'},
            'postal_code': {'type': 'keyword'},
            'country': {'type': 'keyword'},
            'point': {'type': 'geo_point'},
        }
    },
    'service_areas': {
        'properties': {
            'id': {'type': 'integer'},
            'code': {'type': 'keyword'},
            'type': {'type': 'keyword'},
            'name': {'type': 'keyword'}
        }
    }
}

organisation_mapping = {
    'id': {'type': 'keyword'},
    'name': {
        'type': 'text',
        'analyzer': 'bigram_combiner'},
    'description': {
        'type': 'text',
        'analyzer': 'description_analyzer',
    },
    'published':{'type':'boolean'},
    'created_on':{'type':'date'},
    'is_claimed':{'type':'boolean'}
}


def service_to_body(service):
    parent_categories =[]
    for category in service.categories.all():
        while category.parent:
            parent_categories.append(category.parent)
            category = category.parent

    return {
        'id': str(service.id),
        'organisation': {
            'id': service.organisation.pk,
            'name': service.organisation.name,
            'is_claimed': service.organisation.is_claimed,
            'slug': service.organisation.slug
        },
        'created_on': service.created_on,
        'updated_on': service.updated_on,
        'last_edited': service.last_edited,
        'name': service.name,
        'description': service.description,
        'slug': service.slug,
        'url': service.url,
        'email': service.email,
        'phone': service.phone,
        'categories': [{
            'id': category.pk,
            'name': category.name,
            'slug': category.slug
        } for category in service.categories.all()],
        'parent_categories': [{
            'id': category.pk,
            'name': category.name,
            'slug': category.slug
        } for category in parent_categories],
        'locations': [{
            'id': location.id,
            'name': location.name,
            'formatted_address': location.formatted_address,
            'description': location.description,
            'street_address': location.street_address,
            'locality': location.locality,
            'region': location.region,
            'state': location.state,
            'postal_code': location.postal_code,
            'country': location.country,
            'point': {
                'lat': location.latitude,
                'lon': location.longitude
            }
        } for location in service.locations.all()],
        'service_areas': [{
            'id': service_area.pk,
            'code': service_area.code,
            'type': service_area.get_type_display(),
            'type_code': service_area.type,
            'name': service_area.name,
        } for service_area in service.service_areas.all()]
    }

def organisation_to_body(organisation):
    return {
        'id': str(organisation.id),
        'name': organisation.name,
        'description': organisation.description,
        'published': organisation.published,
        'created_on': organisation.created_on,
        'is_claimed': organisation.is_claimed
    }


def filter_by_query(queryset, q):
    queryset = queryset.query({
        "bool": {
            "must": [{
                "multi_match": {
                    "query": q, "operator": "and", "type": "most_fields",
                    "fields": ["name^2", "description^1.5", "categories.name"],
                    "fuzziness": "AUTO:4,7"
                }
            }],
            "should": [{
                "multi_match": {
                    "query": q, "operator": "or", "type": "most_fields",
                    "fields": ["name^2", "description^1.5", "categories.name"]
                }
            }]
        }        
    })
    return queryset


def filter_organisations_by_query_all(queryset, q):
    queryset = queryset.query({
        "bool": {
            "should":[
                {
                    "multi_match": {
                        "query": q,
                        "type": "most_fields",
                        "operator": "and",
                        "fields":["name^2", "description"],
                        "fuzziness": "AUTO:4,7"
                    }
                }, {
                    "multi_match": {
                        "query": q,
                        "type": "most_fields",
                        "operator": "and",
                        "fields": ["name^2", "description^1.5"],
                    }
                }
            ]
        }
    })
    return queryset


def filter_organisations_by_query_published(queryset, q):
    queryset = filter_organisations_by_query_all(queryset, q)
    queryset = queryset.query({
        "bool":{
            "must":{ "term":{ "published":"true" } }
        }
    })
    return queryset


def filter_by_postcode(queryset, postcode, radius=5000):
    # Give us everything that:
    # A) has a service area that is connected to our postcode
    # B) is within radius distance AND has either no service_areas or a
    #    service area in our postcode
    # This ensures that all returned results serve the postcode in some way
    # Results that are within radius but have a service area that is not
    # connected to the postcode, such as a close by service that serves a
    # different council area will not be shown.

    queryset = queryset.filter(
        Q('terms', service_areas__code=postcode.codes) |
        (
            (~Q('exists', field='service_areas') | Q('terms', service_areas__code=postcode.codes)) &
             Q('geo_distance', distance="{0}m".format(radius), locations__point={
                "lat": postcode.latitude,
                "lon": postcode.longitude
            })
        )
    )

    queryset = queryset.query(
        Q(
            {'function_score': {
                "functions": [{
                    "gauss": {
                        "locations.point": {
                            "origin": {
                                "lat" : postcode.latitude,
                                "lon" : postcode.longitude
                            },
                        "scale": "{0}m".format(radius/3),
                        "decay": 0.3
                        }
                    },
            }]}}
        )
    )
    return queryset


def sort_by_postcode(queryset, postcode):
    queryset = queryset.sort({
        '_geo_distance': {
            "locations.point": {"lat": postcode.latitude, "lon": postcode.longitude },
            "order":"asc", "unit":"m"
        },
        '_score': { 'order': 'desc' }
    })
    return queryset


def sort_by_score(queryset):
    queryset = queryset.sort({
        "_score": { "order": "desc" }
    })
    return queryset


def filter_by_category(queryset, category):
    return queryset.query('function_score',
        query=Q('term', categories__id=category.pk) | Q('term', parent_categories__id=category.pk),
        functions=[
            {
                'weight': 2,
                'filter': Q('term', categories__id=category.pk)
            }
        ],
        score_mode="sum",
    )


def filter_by_location_type(queryset, type):
    if type == 'local':
        return queryset.exclude('terms', service_areas__type_code=[
            ServiceArea.COUNTRY,
            ServiceArea.REGION
        ])
    elif type == 'national':
        return queryset.filter('terms', service_areas__type_code=[
            ServiceArea.COUNTRY,
            ServiceArea.REGION
        ])
    else:
        return queryset


def get_service(queryset, service_id):
    return queryset.query(Q({
        "term" : { "id" : service_id }
    })).execute()


def get_services(queryset, service_ids):
    return queryset.query({
        "terms" : { "id" : service_ids}
    })


def get_organisations(queryset, org_ids):
    return queryset.query({
        "terms" : { "id" : org_ids}
    })


def get_organisation_by_id(queryset, organisation_id):
    return queryset.query(Q({
        "term": {"id": organisation_id }
    })).execute()


def filter_by_last_edited(queryset, comparison_date):
    queryset = queryset.query({
        "bool": {
            "filter": {"range":{"last_edited":{"gte":comparison_date}}}
    }})
    return queryset


def order_organistations_by_created_on(queryset):
    queryset = queryset.sort({
        "created_on":"desc"
    })
    return queryset


def filter_by_created_on(queryset, comparison_date):
    queryset = queryset.query({
        "bool": {
            "filter": {"range":{"created_on":{"gte":comparison_date}}}
    }})
    return queryset


def positions_dict(queryset):
    results = queryset.count()
    sorted_hits = queryset[0:results].execute()
    positions = {}
    i = 0
    while i < results:
        positions[sorted_hits[i].id] = None
        if "sort" not in sorted_hits[i].meta:
            positions[sorted_hits[i].id] = i
        elif type(sorted_hits[i].meta.sort[0]) == float:
            positions[sorted_hits[i].id] = i
        i=i+1
    return positions


def postcode_order(queryset, postcode):
    postcode_sqs = sort_by_postcode(queryset, postcode)
    positions = positions_dict(postcode_sqs)
    return {
        "ids": list(positions.keys()),
        "order": Case(*[When(id=key, then=positions[key]) for key in positions])
    }


def keyword_order(queryset):
    #keyword_queryset = filter_by_query(queryset, query)
    positions = positions_dict(queryset)
    return {
        "ids": list(positions.keys()),
        "order": Case(*[When(id=key, then=positions[key]) for key in positions])
    }


def combined_order(filtered_queryset, postcode):
    postcode_sqs = sort_by_postcode(filtered_queryset, postcode)

    distance_sorted = positions_dict(postcode_sqs)
    keyword_sorted  = positions_dict(filtered_queryset)

    positions = { "distance": distance_sorted, "keyword": keyword_sorted }
    combined = {}

    for key in positions["distance"]:
      if positions["distance"][key] == None:
        combined[key] = float(positions["keyword"][key])
      else:
        total = positions["distance"][key] + positions["keyword"][key]
        combined[key] = (total / 2.0)

    return {
        "ids": list(combined.keys()),
        "order": Case(*[When(id=key, then=combined[key]) for key in combined])
    }