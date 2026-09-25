from unittest.mock import patch
from django.test import TestCase
from rest_framework.test import APIClient

class SceneApiTests(TestCase):
    def setUp(self): self.client = APIClient()
    def test_health(self):
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['celery'])
    def test_rejects_invalid_wkt(self):
        response = self.client.post('/api/search/', {'wkt': 'not-wkt'}, format='json')
        self.assertEqual(response.status_code, 400)
    @patch('scenes.views.search_asf', return_value=[])
    def test_search_polygon(self, mocked):
        response = self.client.post('/api/search/', {'wkt': 'POLYGON ((30 31, 30.1 31, 30.1 31.1, 30 31.1, 30 31))'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 0)
        mocked.assert_called_once()
