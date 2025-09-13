"""
Simple API to mark quiz completion status for summary statistics.
"""

import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.shortcuts import render
from openedx.core.djangoapps.user_api.models import UserPreference
from completion.models import BlockCompletion
from opaque_keys.edx.keys import UsageKey
from opaque_keys import InvalidKeyError
import logging

log = logging.getLogger(__name__)

def add_cors_headers(response):
    """Add CORS headers to response"""
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Content-Type, X-CSRFToken'
    return response


@csrf_exempt
def mark_block_completion(request):
    """
    API endpoint to mark a block as completed. 
    Simple version that stores in UserPreference for basic tracking.
    """
    # Handle OPTIONS request for CORS
    if request.method == 'OPTIONS':
        response = JsonResponse({'status': 'options_ok'})
        return add_cors_headers(response)
    
    # Only allow POST
    if request.method != 'POST':
        response = JsonResponse({'error': 'Method not allowed'}, status=405)
        return add_cors_headers(response)
    
    try:
        # Parse request data
        data = json.loads(request.body.decode('utf-8'))
        block_key_str = data.get('block_key', '')
        completion = data.get('completion', 1.0)
        
        log.info(f"Received completion request: block_key={block_key_str}, completion={completion}")
        
        if not block_key_str:
            response = JsonResponse({'error': 'block_key is required'}, status=400)
            return add_cors_headers(response)
        
        # Store in UserPreference for persistent tracking
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            # For testing, create a default user or use anonymous tracking
            user_id = 'anonymous'
            log.info("Using anonymous user for completion tracking")
        else:
            user_id = user.username
        
        # Store completion data in UserPreference
        completion_data = {
            'block_key': block_key_str,
            'completion': completion,
            'timestamp': timezone.now().isoformat(),
            'user': user_id,
            'score_percentage': completion * 100
        }
        
        # Save to BOTH UserPreference AND BlockCompletion (the one that Progress page reads)
        saved_to_db = False
        
        if user and user.is_authenticated:
            # Save to UserPreference for our custom tracking
            try:
                preference_key = f"quiz_completion_{block_key_str}"
                UserPreference.objects.update_or_create(
                    user=user,
                    key=preference_key,
                    defaults={'value': json.dumps(completion_data)}
                )
                log.info(f"Saved to UserPreference: {preference_key}")
            except Exception as e:
                log.error(f"Failed to save UserPreference: {str(e)}")
            
            # ✅ SAVE TO BlockCompletion TABLE (what Progress page reads!)
            try:
                from opaque_keys.edx.keys import UsageKey, CourseKey
                from opaque_keys import InvalidKeyError
                from completion.models import BlockCompletion
                
                # Parse or create proper course_key and block_key
                course_key = None
                block_usage_key = None
                
                # Try to parse existing UsageKey
                try:
                    block_usage_key = UsageKey.from_string(block_key_str)
                    course_key = block_usage_key.course_key
                    log.info(f"Parsed existing UsageKey: {block_usage_key}")
                except InvalidKeyError:
                    # Create new JSInput problem key
                    import re
                    
                    # Extract course info from block_key_str
                    course_match = re.search(r'course-v1:([^\/\+]+\+[^\/\+]+\+[^\/\+]+)', block_key_str)
                    if course_match:
                        course_key = CourseKey.from_string(f"course-v1:{course_match.group(1)}")
                    else:
                        # Extract from block-v1 format
                        block_match = re.search(r'block-v1:([^\/\+]+\+[^\/\+]+\+[^\/\+]+)', block_key_str)
                        if block_match:
                            course_key = CourseKey.from_string(f"course-v1:{block_match.group(1)}")
                        else:
                            # Fallback course
                            course_key = CourseKey.from_string("course-v1:Manabi+N51+2026")
                    
                    # Create JSInput problem UsageKey
                    from opaque_keys.edx.locator import BlockUsageLocator
                    problem_id = f"jsinput_template18_{int(timezone.now().timestamp())}"
                    block_usage_key = BlockUsageLocator(
                        course_key=course_key,
                        block_type='problem',
                        block_id=problem_id
                    )
                    log.info(f"Created JSInput UsageKey: {block_usage_key}")
                
                # Save to BlockCompletion with correct structure
                completion_obj, created = BlockCompletion.objects.update_or_create(
                    user=user,
                    context_key=course_key,
                    block_key=block_usage_key,
                    defaults={
                        'block_type': 'problem',
                        'completion': completion
                    }
                )
                
                log.info(f"✅ BlockCompletion saved: user={user.username}, course={course_key}, block={block_usage_key}, completion={completion}, created={created}")
                saved_to_db = True
                
            except Exception as e:
                log.error(f"BlockCompletion failed: {str(e)}")
                saved_to_db = False
        
        log.info(f"Completion recorded: {completion_data} - BlockCompletion saved: {saved_to_db}")
        
        response = JsonResponse({
            'status': 'success',
            'block_key': block_key_str,
            'completion': completion,
            'user': user_id,
            'saved_to_userpreference': user and user.is_authenticated,
            'saved_to_blockcompletion': saved_to_db,
            'message': 'Completion recorded successfully - affects Progress page!' if saved_to_db else 'Completion recorded (UserPreference only)'
        })
        return add_cors_headers(response)
        
    except json.JSONDecodeError as e:
        log.error(f"JSON decode error: {str(e)}")
        response = JsonResponse({'error': 'Invalid JSON: ' + str(e)}, status=400)
        return add_cors_headers(response)
    except Exception as e:
        log.error(f"Unexpected error: {str(e)}")
        response = JsonResponse({'error': 'Server error: ' + str(e)}, status=500)
        return add_cors_headers(response)


@csrf_exempt
def view_completions(request):
    """
    API endpoint to view all completion data for debugging
    """
    if request.method == 'OPTIONS':
        response = JsonResponse({'status': 'options_ok'})
        return add_cors_headers(response)
    
    try:
        # Get all quiz completion preferences
        completions = []
        all_prefs = UserPreference.objects.filter(key__startswith='quiz_completion_')
        
        for pref in all_prefs:
            try:
                completion_data = json.loads(pref.value)
                completions.append({
                    'user': pref.user.username if pref.user else 'unknown',
                    'preference_key': pref.key,
                    'data': completion_data
                })
            except:
                continue
        
        response = JsonResponse({
            'status': 'success',
            'total_completions': len(completions),
            'completions': completions[:20]  # Limit to 20 for display
        })
        return add_cors_headers(response)
        
    except Exception as e:
        log.error(f"Error viewing completions: {str(e)}")
        response = JsonResponse({'error': str(e)}, status=500)
        return add_cors_headers(response)


@csrf_exempt
@require_POST
@login_required
def mark_quiz_finished(request):
    """
    Mark a quiz as finished for summary statistics.
    Simple boolean flag: finished = true/false
    """
    try:
        data = json.loads(request.body.decode('utf-8'))
        quiz_id = data.get('quiz_id', '')
        unit_id = data.get('unit_id', '')
        finished = data.get('finished', True)
        score = data.get('score', 0)
        
        if not quiz_id:
            return JsonResponse({'error': 'quiz_id required'}, status=400)
        
        # Create unique key for this quiz completion
        completion_key = f"quiz_finished_{quiz_id}"
        
        # Store simple finished status
        UserPreference.objects.update_or_create(
            user=request.user,
            key=completion_key,
            defaults={
                'value': json.dumps({
                    'finished': finished,
                    'score': score,
                    'unit_id': unit_id,
                    'last_updated': timezone.now().isoformat()
                })
            }
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Quiz marked as {"finished" if finished else "not finished"}',
            'quiz_id': quiz_id,
            'finished': finished
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def get_quiz_summary(request):
    """
    Get summary of finished/unfinished quizzes for current user.
    """
    try:
        # Get all quiz completion status for this user
        quiz_completions = UserPreference.objects.filter(
            user=request.user,
            key__startswith='quiz_finished_'
        )
        
        finished_count = 0
        total_count = quiz_completions.count()
        quiz_list = []
        
        for pref in quiz_completions:
            try:
                quiz_data = json.loads(pref.value)
                quiz_id = pref.key.replace('quiz_finished_', '')
                
                is_finished = quiz_data.get('finished', False)
                if is_finished:
                    finished_count += 1
                
                quiz_list.append({
                    'quiz_id': quiz_id,
                    'finished': is_finished,
                    'score': quiz_data.get('score', 0),
                    'unit_id': quiz_data.get('unit_id', ''),
                    'last_updated': quiz_data.get('last_updated', '')
                })
            except:
                continue
        
        summary = {
            'total_quizzes': total_count,
            'finished_quizzes': finished_count,
            'unfinished_quizzes': total_count - finished_count,
            'completion_rate': round((finished_count / total_count * 100) if total_count > 0 else 0, 1),
            'quiz_list': quiz_list
        }
        
        return JsonResponse(summary)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def quiz_summary_page(request):
    """
    Display quiz summary page.
    """
    return render(request, 'quiz_summary.html')


@csrf_exempt  
def test_completion_api(request):
    """
    🧪 TEST API to manually test BlockCompletion creation and retrieval
    
    Usage:
    POST /courseware/test_completion_api/
    {
        "test_type": "create_completion" | "list_completions" | "view_all"
    }
    """
    # Handle OPTIONS request for CORS
    if request.method == 'OPTIONS':
        response = JsonResponse({'status': 'options_ok'})
        return add_cors_headers(response)
    
    if request.method == 'GET':
        # Simple test page
        return JsonResponse({
            'message': '🧪 Completion Test API',
            'endpoints': {
                'create_test': 'POST with {"test_type": "create_completion"}',
                'list_user': 'POST with {"test_type": "list_completions"}', 
                'view_all': 'POST with {"test_type": "view_all"}'
            },
            'note': 'This API tests BlockCompletion table operations'
        })
    
    # Only allow POST for actual tests
    if request.method != 'POST':
        response = JsonResponse({'error': 'Method not allowed'}, status=405)
        return add_cors_headers(response)
        
    try:
        # Parse request data
        data = json.loads(request.body.decode('utf-8'))
        test_type = data.get('test_type', 'create_completion')
        
        user = getattr(request, 'user', None)
        results = []
        
        if test_type == 'create_completion':
            # 🧪 Test creating BlockCompletion record
            try:
                from opaque_keys.edx.keys import CourseKey
                from opaque_keys.edx.locator import BlockUsageLocator
                from completion.models import BlockCompletion
                
                if not user or not user.is_authenticated:
                    # Create for anonymous testing
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    user, _ = User.objects.get_or_create(username='test_user')
                
                # Create test completion record
                course_key = CourseKey.from_string("course-v1:Manabi+N51+2026")
                test_block_id = f"test_jsinput_{int(timezone.now().timestamp())}"
                block_usage_key = BlockUsageLocator(
                    course_key=course_key,
                    block_type='problem',
                    block_id=test_block_id
                )
                
                completion_obj, created = BlockCompletion.objects.update_or_create(
                    user=user,
                    context_key=course_key,
                    block_key=block_usage_key,
                    defaults={
                        'block_type': 'problem',
                        'completion': 1.0
                    }
                )
                
                results.append({
                    'action': '✅ create_blockcompletion',
                    'success': True,
                    'created': created,
                    'course': str(course_key),
                    'block': str(block_usage_key),
                    'completion': 1.0,
                    'user': user.username,
                    'note': 'This will appear in Progress page!'
                })
                
            except Exception as e:
                results.append({
                    'action': '❌ create_blockcompletion',
                    'success': False,
                    'error': str(e)
                })
        
        elif test_type == 'list_completions':
            # 🧪 Test listing user's completions
            try:
                from completion.models import BlockCompletion
                
                if not user or not user.is_authenticated:
                    results.append({
                        'action': 'list_completions',
                        'success': False,
                        'error': 'Login required'
                    })
                else:
                    completions = BlockCompletion.objects.filter(user=user)
                    completion_list = []
                    
                    for comp in completions:
                        completion_list.append({
                            'course': str(comp.context_key),
                            'block': str(comp.block_key),
                            'type': comp.block_type,
                            'completion': comp.completion,
                            'created': comp.created.isoformat() if comp.created else None
                        })
                    
                    results.append({
                        'action': '📋 list_completions',
                        'success': True,
                        'user': user.username,
                        'count': len(completion_list),
                        'completions': completion_list
                    })
                
            except Exception as e:
                results.append({
                    'action': '❌ list_completions',
                    'success': False,
                    'error': str(e)
                })
                
        elif test_type == 'view_all':
            # 🧪 Test viewing all completion data
            try:
                from completion.models import BlockCompletion
                
                # Get recent BlockCompletion records
                recent_completions = BlockCompletion.objects.all().order_by('-modified')[:10]
                completion_list = []
                
                for comp in recent_completions:
                    completion_list.append({
                        'user': comp.user.username,
                        'course': str(comp.context_key),
                        'block': str(comp.block_key),
                        'type': comp.block_type,
                        'completion': comp.completion,
                        'created': comp.created.isoformat() if comp.created else None
                    })
                
                results.append({
                    'action': '👁️ view_all_completions',
                    'success': True,
                    'total_records': BlockCompletion.objects.count(),
                    'recent_10': completion_list,
                    'note': 'These are the records Progress page reads from'
                })
                
            except Exception as e:
                results.append({
                    'action': '❌ view_all',
                    'success': False,
                    'error': str(e)
                })
        
        response = JsonResponse({
            'status': 'success',
            'test_type': test_type,
            'user': user.username if user and user.is_authenticated else 'anonymous',
            'timestamp': timezone.now().isoformat(),
            'results': results,
            'next_steps': 'Check Progress page to see if completion count increased!'
        })
        return add_cors_headers(response)
        
    except json.JSONDecodeError as e:
        response = JsonResponse({'error': 'Invalid JSON: ' + str(e)}, status=400)
        return add_cors_headers(response)
    except Exception as e:
        log.error(f"Test API error: {str(e)}")
        response = JsonResponse({'error': 'Server error: ' + str(e)}, status=500)
        return add_cors_headers(response)


@csrf_exempt
def check_block_completion(request):
    """
    API endpoint to check completion status of a block
    """
    # Handle OPTIONS request for CORS
    if request.method == 'OPTIONS':
        response = JsonResponse({'status': 'options_ok'})
        return add_cors_headers(response)
    
    if request.method != 'POST':
        response = JsonResponse({'error': 'Method not allowed'}, status=405)
        return add_cors_headers(response)
    
    try:
        # Parse request data
        data = json.loads(request.body.decode('utf-8'))
        block_key_str = data.get('block_key', '')
        
        if not block_key_str:
            response = JsonResponse({'error': 'block_key is required'}, status=400)
            return add_cors_headers(response)
        
        log.info(f"Checking completion for block: {block_key_str}")
        
        # Parse block key
        try:
            block_key = UsageKey.from_string(block_key_str)
        except InvalidKeyError:
            response = JsonResponse({'error': 'Invalid block_key format'}, status=400)
            return add_cors_headers(response)
        
        # Check BlockCompletion table - find by block_key (UsageKey)
        is_completed = False
        completion_value = 0
        
        if request.user and request.user.is_authenticated:
            try:
                completion_obj = BlockCompletion.objects.get(
                    user=request.user,
                    block_key=block_key
                )
                is_completed = completion_obj.completion > 0
                completion_value = completion_obj.completion
                log.info(f"Found completion in BlockCompletion: {completion_value}")
            except BlockCompletion.DoesNotExist:
                log.info("No completion found in BlockCompletion table")
        else:
            log.info("User not authenticated, skipping BlockCompletion check")
        
        # Also check UserPreference as fallback
        if request.user and request.user.is_authenticated:
            try:
                pref_key = f"quiz_completion_{block_key_str}"
                user_pref = UserPreference.objects.get(
                    user=request.user,
                    key=pref_key
                )
                pref_data = json.loads(user_pref.value)
                pref_completion = pref_data.get('completion', 0)
                if pref_completion > 0:
                    is_completed = True
                    completion_value = max(completion_value, pref_completion)
                    log.info(f"Found completion in UserPreference: {pref_completion}")
            except UserPreference.DoesNotExist:
                log.info("No completion found in UserPreference")
        else:
            log.info("User not authenticated, skipping UserPreference check")
        
        # Get user info for response
        user_info = 'anonymous'
        if request.user and request.user.is_authenticated:
            user_info = request.user.username
        elif hasattr(request, 'user') and request.user:
            user_info = f'user_{request.user.id}' if hasattr(request.user, 'id') else 'unknown'
        
        response = JsonResponse({
            'status': 'success',
            'block_key': block_key_str,
            'is_completed': is_completed,
            'completion': completion_value,
            'user': user_info,
            'authenticated': request.user.is_authenticated if request.user else False
        })
        return add_cors_headers(response)
        
    except Exception as e:
        log.error(f"Error checking completion: {str(e)}")
        response = JsonResponse({'error': str(e)}, status=500)
        return add_cors_headers(response)
