"""
URLs for subsequence progress API
"""

from django.urls import path, re_path
from .views import SubsequenceProgressView

urlpatterns = [
    re_path(
        r'^v1/subsequence/(?P<course_key>[^/]+)/(?P<subsequence_id>[^/]+)/progress$',
        SubsequenceProgressView.as_view(),
        name='subsequence-progress'
    ),
] 