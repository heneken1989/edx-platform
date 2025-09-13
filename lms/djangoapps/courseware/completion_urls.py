"""
URL patterns for completion API
"""
from django.urls import path
from . import completion_api, quiz_completion_api

urlpatterns = [
    # Official EdX BlockCompletion API
    path('mark_block_completion/', quiz_completion_api.mark_block_completion, name='mark_block_completion'),
    path('view_completions/', quiz_completion_api.view_completions, name='view_completions'),
    
    # Original completion APIs
    path('mark_completed/', completion_api.mark_problem_completed, name='mark_problem_completed'),
    path('completion_stats/', completion_api.get_user_completion_stats, name='get_completion_stats'),
    path('stats_page/', completion_api.completion_stats_page, name='completion_stats_page'),
    
    # Quiz completion API
    path('mark_quiz_finished/', quiz_completion_api.mark_quiz_finished, name='mark_quiz_finished'),
    path('quiz_summary/', quiz_completion_api.get_quiz_summary, name='get_quiz_summary'),
    path('quiz_summary_page/', quiz_completion_api.quiz_summary_page, name='quiz_summary_page'),
    
    # Check completion status API
    path('check_block_completion/', quiz_completion_api.check_block_completion, name='check_block_completion'),
    
    # 🧪 Test API endpoints
    path('test_completion_api/', quiz_completion_api.test_completion_api, name='test_completion_api'),
]
