from django.test import TestCase
from django.test import Client
from django.urls import reverse
from aliss.tests.fixtures import Fixtures
from aliss.models import *

class v3SearchViewTestCase(TestCase):

    def setUp(self):
      self.service = Fixtures.create()
      self.client = Client()

    def test_get(self):
        response = self.client.get("/api/v3/search/", { 'postcode': 'G2 4AA' }, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertTrue('count' in response.data)
        self.assertTrue('results' in response.data)
        service_result = response.data['results'][0]
        self.assertTrue('url' in service_result)

    def tearDown(self):
        for organisation in Organisation.objects.filter(name="TestOrg"):
            organisation.delete()