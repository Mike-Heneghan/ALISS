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
        location1 = Fixtures.create_location(self.org)
        location2 = Fixtures.create_another_location(self.org)

        self.s1 = Service.objects.create(name="Food For All", description="A handy food activity", organisation=self.org, created_by=t, updated_by=u)
        self.s2 = Service.objects.create(name="Physical Fun", description="Physical activity classes", organisation=self.org, created_by=t, updated_by=u)
        self.s3 = Service.objects.create(name="Step Fit 1", description="Physical activity classes", organisation=self.org, created_by=t, updated_by=u)
        self.s4 = Service.objects.create(name="Step Fit 2", description="Phyzical activiti classes", organisation=self.org, created_by=t, updated_by=u)

        self.s1.locations.add(location1); self.s1.save()
        self.s2.locations.add(location1); self.s2.save()
        self.s3.locations.add(location1); self.s3.save()
        self.s4.locations.add(location2); self.s4.save()

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
        result = filter_organisations_by_query_all(org_queryset, "TestOrg")
        order = keyword_order(result)
        orgs = Organisation.objects.filter(id__in=order["ids"]).order_by(order["order"])
        self.assertEqual(self.org.id, orgs[0].id)
        self.assertEqual(self.org2.id, orgs[1].id)

    # def test_keyword_order(self):
    #     success_counter = 0
    #     failure_counter = 0
    #     loop_counter = 0
    #     while loop_counter < 10:
    #         result = filter_by_query(self.queryset, "Physical Activity")
    #         order  = keyword_order(result)
    #         services = Service.objects.filter(id__in=order["ids"]).order_by(order["order"])
    #         if ((services[0] == self.s2) and (services[2] == self.s4)):
    #             success_counter += 1
    #         else:
    #             failure_counter += 1
    #         loop_counter += 1
    #     print ("\n")
    #     print ("The success count is: " + str(success_counter))
    #     print ("\n")
    #     print ("The failure count is: " + str(failure_counter))
    #     self.assertEqual(result.count(), 3)
    #     self.assertTrue(success_counter > 8)

    def tearDown(self):
        Fixtures.organisation_teardown()
