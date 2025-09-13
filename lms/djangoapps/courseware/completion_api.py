"""
Simple API for marking problem completion without triggering EdX grading system.
This is for statistics only - not official grading.
"""

import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.shortcuts import render
from openedx.core.djangoapps.user_api.models import UserPreference


@csrf_exempt
@require_POST
@login_required
def mark_problem_completed(request):
    """
    Mark a problem as completed for statistics tracking.
    Does NOT trigger EdX grading - just sets completion flag.
    """
    try:
        data = json.loads(request.body.decode('utf-8'))
        problem_id = data.get('problem_id', '')
        unit_id = data.get('unit_id', '')
        score = data.get('score', 0)
        
        if not problem_id:
            return JsonResponse({'error': 'problem_id required'}, status=400)
        
        # Create unique key for this problem completion
        completion_key = f"problem_completed_{problem_id}"
        
        # Store completion in UserPreference for statistics
        UserPreference.objects.update_or_create(
            user=request.user,
            key=completion_key,
            defaults={
                'value': json.dumps({
                    'completed': True,
                    'score': score,
                    'unit_id': unit_id,
                    'timestamp': timezone.now().isoformat()
                })
            }
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Problem marked as completed',
            'problem_id': problem_id
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def get_user_completion_stats(request):
    """
    Get completion statistics for current user.
    """
    try:
        # Get all completed problems for this user
        completed_problems = UserPreference.objects.filter(
            user=request.user,
            key__startswith='problem_completed_'
        )
        
        stats = {
            'total_completed': completed_problems.count(),
            'problems': []
        }
        
        for pref in completed_problems:
            try:
                problem_data = json.loads(pref.value)
                problem_id = pref.key.replace('problem_completed_', '')
                stats['problems'].append({
                    'problem_id': problem_id,
                    'completed': problem_data.get('completed', True),
                    'score': problem_data.get('score', 0),
                    'timestamp': problem_data.get('timestamp', ''),
                    'unit_id': problem_data.get('unit_id', '')
                })
            except:
                continue
        
        return JsonResponse(stats)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def completion_stats_page(request):
    """
    Display completion statistics page.
    """
    return render(request, 'completion_stats.html')
