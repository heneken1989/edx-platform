import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from ..models import QuizResult

logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["POST"])
def save_quiz_results(request):
    """
    Save quiz results to database
    """
    try:
        data = json.loads(request.body)
        logger.info(f"Received quiz results data: {data}")
        
        # Extract data
        section_id = data.get('section_id')
        unit_id = data.get('unit_id')
        course_id = data.get('course_id')
        user_id = data.get('user_id')
        template_id = data.get('template_id', 67)
        test_session_id = data.get('test_session_id')
        quiz_data = data.get('quiz_data', {})
        status = data.get('status', 'processing')  # Default to processing
        
        # Validate required fields
        if not all([section_id, unit_id, course_id, user_id, test_session_id]):
            return JsonResponse({
                'success': False,
                'error': 'Missing required fields'
            }, status=400)
        
        # Save to database
        try:
            # Create or update QuizResult
            quiz_result, created = QuizResult.objects.update_or_create(
                user_id=user_id,
                section_id=section_id,
                unit_id=unit_id,
                template_id=template_id,
                test_session_id=test_session_id,
                defaults={
                    'course_id': course_id,
                    'quiz_data': quiz_data,
                    'score': quiz_data.get('score', 0),
                    'is_correct': quiz_data.get('correctCount', 0) > 0,
                    'status': status
                }
            )
            
            # If status is 'completed', update all records with same test_session_id to completed
            if status == 'completed':
                updated_count = QuizResult.objects.filter(
                    user_id=user_id,
                    test_session_id=test_session_id
                ).update(status='completed')
                logger.info(f"Updated {updated_count} records to completed status for session {test_session_id}")
            
            logger.info(f"Quiz results {'created' if created else 'updated'} for user {user_id}, session {test_session_id}")
            logger.info(f"Quiz data: {quiz_data}")
            
            return JsonResponse({
                'success': True,
                'quiz_result_id': f"quiz_{test_session_id}",
                'message': 'Quiz results saved successfully'
            })
            
        except Exception as e:
            logger.error(f"Error saving quiz results to database: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'Database error: {str(e)}'
            }, status=500)
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Error saving quiz results: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@csrf_exempt
@require_http_methods(["GET"])
def get_test_summary(request):
    """
    Get test summary for a user and test session
    """
    try:
        user_id = request.GET.get('user_id')
        test_session_id = request.GET.get('test_session_id')
        section_id = request.GET.get('section_id')
        limit = int(request.GET.get('limit', 3))
        
        if not user_id:
            return JsonResponse({
                'success': False,
                'error': 'user_id is required'
            }, status=400)
        
        # For now, return mock data
        # In a real implementation, you would query the database here
        if test_session_id:
            # Return specific test session summary
            summary = {
                'test_session_id': test_session_id,
                'user_id': user_id,
                'section_id': section_id or 'mock_section',
                'total_questions': 34,
                'answered_questions': 1,
                'correct_answers': 1,
                'incorrect_answers': 0,
                'percentage': 100,
                'total_score': 1,
                'average_score': 1,
                'started_at': '2025-01-18T10:00:00Z',
                'completed_at': '2025-01-18T10:05:00Z',
                'questions': [
                    {
                        'unit_id': 'mock_unit_1',
                        'status': 'answered',
                        'is_correct': True,
                        'score': 1,
                        'quiz_data': {
                            'answers': ['71'],
                            'correctCount': 1,
                            'answeredCount': 1,
                            'totalQuestions': 34,
                            'score': 0.029
                        }
                    }
                ]
            }
            
            return JsonResponse({
                'success': True,
                'summary': summary
            })
        else:
            # Return all test results for user (when no specific test_session_id)
            logger.info(f"Fetching all test results for user {user_id}, section_id: {section_id}")
            
            try:
                # Query QuizResult model - only get completed results
                results = QuizResult.objects.filter(user_id=user_id, status='completed')
                if section_id:
                    results = results.filter(section_id=section_id)
                results = results.order_by('-created_at')[:limit]
                
                # Convert to summary format
                summaries = []
                for result in results:
                    quiz_data = result.quiz_data or {}
                    summaries.append({
                        'test_session_id': result.test_session_id,
                        'user_id': result.user_id,
                        'section_id': result.section_id,
                        'total_questions': quiz_data.get('totalQuestions', 0),
                        'answered_questions': quiz_data.get('answeredCount', 0),
                        'correct_answers': quiz_data.get('correctCount', 0),
                        'incorrect_answers': quiz_data.get('answeredCount', 0) - quiz_data.get('correctCount', 0),
                        'percentage': round(quiz_data.get('score', 0) * 100) if quiz_data.get('score') else 0,
                        'completed_at': result.created_at.isoformat(),
                        'questions': []  # TODO: Add detailed question data if needed
                    })
                
                logger.info(f"Found {len(summaries)} test results for user {user_id}")
                
                return JsonResponse({
                    'success': True,
                    'summaries': summaries
                })
                
            except Exception as e:
                logger.error(f"Error querying test results: {str(e)}")
                return JsonResponse({
                    'success': True,
                    'summaries': []
                })
        
    except Exception as e:
        logger.error(f"Error getting test summary: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)