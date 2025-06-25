"""
Tests for CMS API connectivity
"""
import json
from django.urls import reverse
from xmodule.modulestore.tests.factories import CourseFactory, ItemFactory
from cms.djangoapps.contentstore.tests.utils import ContentStoreTestCase

class TestCMSAPIConnectivity(ContentStoreTestCase):
    """
    Test suite for checking CMS API connectivity
    """
    def setUp(self):
        """
        Set up test data
        """
        super().setUp()
        # Create a test course
        self.course = CourseFactory.create(
            org='test_org',
            course='test_course',
            run='test_run',
            display_name='Test Course'
        )
        
        # Create a test problem
        self.problem = ItemFactory.create(
            parent=self.course,
            category='problem',
            display_name='Test Problem'
        )

    def test_xblock_api_connectivity(self):
        """
        Test GET request to XBlock API endpoint
        """
        url = reverse('xblock_handler', kwargs={
            'usage_key_string': str(self.problem.location)
        })
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['display_name'], 'Test Problem')
        self.assertEqual(data['category'], 'problem')

    def test_container_api_connectivity(self):
        """
        Test GET request to Container API endpoint
        """
        url = reverse('container_handler', kwargs={
            'usage_key_string': str(self.course.location)
        })
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['display_name'], 'Test Course')
        self.assertEqual(data['category'], 'course')

    def test_xblock_metadata_update(self):
        """
        Test PUT request to update XBlock metadata
        """
        url = reverse('xblock_handler', kwargs={
            'usage_key_string': str(self.problem.location)
        })
        new_display_name = 'Updated Problem'
        data = {
            'metadata': {
                'display_name': new_display_name,
                'max_attempts': 3,
                'weight': 1.0,
                'showanswer': 'finished',
                'rerandomize': 'always',
                'graded': True
            }
        }
        response = self.client.put(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        # Verify the update
        response = self.client.get(url)
        data = json.loads(response.content)
        self.assertEqual(data['display_name'], new_display_name)
        self.assertEqual(data['metadata']['max_attempts'], 3)
        self.assertEqual(data['metadata']['weight'], 1.0)
        self.assertEqual(data['metadata']['showanswer'], 'finished')
        self.assertEqual(data['metadata']['rerandomize'], 'always')
        self.assertEqual(data['metadata']['graded'], True) 