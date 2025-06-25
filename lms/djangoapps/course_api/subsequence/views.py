"""
Subsequence Progress API Views
"""

from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework import status
from opaque_keys.edx.keys import CourseKey, UsageKey
from opaque_keys import InvalidKeyError
from xmodule.modulestore.exceptions import ItemNotFoundError
from xmodule.modulestore.django import modulestore
from lms.djangoapps.courseware.courses import get_course_with_access
from completion.models import BlockCompletion
from openedx.core.lib.api.view_utils import DeveloperErrorViewMixin, view_auth_classes
from lms.djangoapps.course_blocks.api import get_course_blocks


@view_auth_classes()
class SubsequenceProgressView(DeveloperErrorViewMixin, APIView):
    """
    **Use Case**
        * Get the completion status of a subsequence for a user.

    **Example Request**
        GET /api/courseware/v1/subsequence/{course_key}/{subsequence_id}/progress

    **Response Values**
        * completion_status: The completion status of the subsequence
        * title: The title of the subsequence
    """

    def get(self, request, course_key, subsequence_id):
        """
        Handle GET requests to get the completion status of a subsequence.
        """
        if not request.user or not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        try:
            # Convert course_key from string to CourseKey object
            course_key = CourseKey.from_string(course_key)
            usage_key = UsageKey.from_string(subsequence_id)
            store = modulestore()
            course_usage_key = store.make_course_usage_key(course_key)          
            block_data = get_course_blocks(request.user, course_usage_key, allow_start_dates_in_future=True, include_completion=True)
            subsequence = modulestore().get_item(usage_key)           
            children = subsequence.children
            complete_count, incomplete_count, locked_count = 0, 0, 0
            total_units = 0
            for unit_key in children:
                total_units += 1
                complete = block_data.get_xblock_field(unit_key, 'complete', False)
                contains_gated_content = block_data.get_xblock_field(unit_key, 'contains_gated_content', False)
                if contains_gated_content:
                    locked_count += 1
                elif complete:
                    complete_count += 1
                else:
                    incomplete_count += 1
            return JsonResponse({
                'title': subsequence.display_name,
                'complete_count': complete_count,
                'incomplete_count': incomplete_count,
                'locked_count': locked_count,
                'total_units': total_units,
            })

        except (InvalidKeyError, ItemNotFoundError) as error:
            return JsonResponse({
                'error': str(error)
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as error:
            return JsonResponse({
                'error': str(error)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR) 
        





