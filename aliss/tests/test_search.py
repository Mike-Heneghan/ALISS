from django.test import TestCase
from django.test import Client
from django.urls import reverse
from aliss.tests.fixtures import Fixtures
from aliss.models import *
from aliss.search import *


class SearchTestCase(TestCase):
    fixtures = ['service_areas.json', 'g2_postcodes.json']

    def setUp(self):
        t, u, c, _ = Fixtures.create_users()
        self.org = Fixtures.create_organisation(t, u, c)
        self.org2 = Organisation.objects.create(name="Test0rg", description="A test description",
            created_by=self.org.created_by, updated_by=self.org.updated_by)
        close = Fixtures.create_location(self.org)
        far = Fixtures.create_another_location(self.org)

        self.s1 = Service.objects.create(name="Food For All", description="A handy food activity", organisation=self.org, created_by=t, updated_by=u)
        self.s2 = Service.objects.create(name="Physical Fun", description="Physical activity classes", organisation=self.org, created_by=t, updated_by=u)
        self.s3 = Service.objects.create(name="Step Fit 1", description="Physical activity classes", organisation=self.org, created_by=t, updated_by=u)
        self.s4 = Service.objects.create(name="Step Fit 2", description="Phyzical activiti classes", organisation=self.org, created_by=t, updated_by=u)

        self.s1.locations.add(close); self.s1.save()
        self.s2.locations.add(close); self.s2.save()
        self.s3.locations.add(close); self.s3.save()
        self.s4.locations.add(far); self.s4.save()

        pks = [self.s1.pk, self.s2.pk, self.s3.pk, self.s4.pk]
        self.queryset = get_services(Fixtures.es_connection(), pks)

    def test_filter_by_postcode(self):
        p = Postcode.objects.get(pk="G2 4AA")
        result = filter_by_postcode(self.queryset, p, 100)
        self.assertNotEqual(result.count(), self.queryset.count())

    def test_postcode_order(self):
        p = Postcode.objects.get(pk="G2 4AA")
        result = filter_by_postcode(self.queryset, p, 100000)
        order  = postcode_order(result, p)
        services = Service.objects.filter(id__in=order["ids"]).order_by(order["order"])
        self.assertTrue(services[0] in [self.s1, self.s2, self.s3])
        self.assertEqual(services[3], self.s4)
        self.assertEqual(result.count(), self.queryset.count())

    def test_combined_order(self):
        p = Postcode.objects.get(pk="G2 9ZZ")
        result = filter_by_postcode(self.queryset, p, 100000)
        result = filter_by_query(result, "Physical Activity")
        order  = combined_order(result, p)
        services = Service.objects.filter(id__in=order["ids"]).order_by(order["order"])
        self.assertNotEqual(services[2], self.s4)
        self.assertEqual(result.count(), 3)

    def test_organisation_query(self):
        org_queryset = get_organisations(Fixtures.es_organisation_connection(), [self.org.pk, self.org2.pk])
        result = filter_organisations_by_query_all(org_queryset, "TestOrg").execute()
        self.assertEqual(str(self.org.pk), result[0].id)
        self.assertEqual(str(self.org2.pk), result[1].id)

    def tearDown(self):
        Fixtures.organisation_teardown()


'''
HIDDEN AS INCONSISTENCIES ON TRAVIS
TODO: try repeating and count success testing method
def test_keyword_order(self):
    result = filter_by_query(self.queryset, "Physical Activity")
    order  = keyword_order(result)
    services = Service.objects.filter(id__in=order["ids"]).order_by(order["order"])
    print("\n")
    for hit in result:
        print(hit.name)
        print(hit.meta.to_dict())
    self.assertEqual(result.count(), 3)
    self.assertEqual(services[0], self.s2)
    self.assertEqual(services[2], self.s4)
'''
