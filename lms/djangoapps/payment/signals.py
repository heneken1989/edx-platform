"""
Signal handlers for payment app
"""
import logging
from django.dispatch import receiver
from django.contrib.auth.models import User
from common.djangoapps.student.models import CourseEnrollment
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.djangoapps.user_authn.views.register import REGISTER_USER
from openedx_events.learning.signals import STUDENT_REGISTRATION_COMPLETED
from django.utils import timezone

log = logging.getLogger(__name__)

# Debug: Log when signals module is imported
log.info("Payment signals module imported successfully")


def auto_enroll_user_in_all_courses(user):
    """
    Auto enroll a user in all available courses
    """
    try:
        # Get all available courses
        # Get all available courses (remove time restrictions for auto enrollment)
        all_courses = CourseOverview.objects.all()
        
        enrolled_count = 0
        already_enrolled_count = 0
        error_count = 0
        
        log.info(f'Starting auto enrollment for user {user.username} in {all_courses.count()} courses')
        
        for course_overview in all_courses:
            try:
                # Check if user is already enrolled
                existing_enrollment = CourseEnrollment.get_enrollment(
                    user, 
                    course_overview.id
                )
                
                if existing_enrollment and existing_enrollment.is_active:
                    already_enrolled_count += 1
                    log.debug(f'User {user.username} already enrolled in {course_overview.display_name}')
                else:
                    # Enroll user in the course
                    enrollment, created = CourseEnrollment.enroll(
                        user=user,
                        course_key=course_overview.id,
                        mode='verified'  # Default to verified mode
                    )
                    
                    if created:
                        enrolled_count += 1
                        log.info(f'Auto enrolled user {user.username} in {course_overview.display_name}')
                    else:
                        already_enrolled_count += 1
                        log.debug(f'User {user.username} already enrolled in {course_overview.display_name}')
                        
            except Exception as e:
                error_count += 1
                log.error(f'Error auto enrolling user {user.username} in {course_overview.display_name}: {str(e)}')
        
        log.info(f'Auto enrollment completed for user {user.username}: '
                f'{enrolled_count} new enrollments, {already_enrolled_count} already enrolled, {error_count} errors')
        
        return {
            'enrolled_count': enrolled_count,
            'already_enrolled_count': already_enrolled_count,
            'error_count': error_count,
            'total_courses': all_courses.count()
        }
        
    except Exception as e:
        log.error(f'Error in auto_enroll_user_in_all_courses for user {user.username}: {str(e)}')
        return None


@receiver(REGISTER_USER)
def auto_enroll_on_registration(sender, user, registration, **kwargs):
    """
    Auto enroll user in all courses when they register
    """
    try:
        log.info(f'=== REGISTER_USER SIGNAL RECEIVED ===')
        log.info(f'User {user.username} registered, starting auto enrollment')
        result = auto_enroll_user_in_all_courses(user)
        
        if result:
            log.info(f'Auto enrollment result for {user.username}: {result}')
        else:
            log.error(f'Auto enrollment failed for {user.username}')
            
    except Exception as e:
        log.error(f'Error in auto_enroll_on_registration for user {user.username}: {str(e)}')


@receiver(STUDENT_REGISTRATION_COMPLETED)
def auto_enroll_on_registration_completed(sender, user, **kwargs):
    """
    Auto enroll user in all courses when registration is completed
    This is a backup signal in case REGISTER_USER doesn't work
    """
    try:
        log.info(f'=== STUDENT_REGISTRATION_COMPLETED SIGNAL RECEIVED ===')
        log.info(f'Student registration completed for {user.username}, starting auto enrollment')
        
        # Get the actual User object from UserData
        from django.contrib.auth.models import User
        try:
            actual_user = User.objects.get(username=user.username)
            result = auto_enroll_user_in_all_courses(actual_user)
            
            if result:
                log.info(f'Auto enrollment result for {user.username}: {result}')
            else:
                log.error(f'Auto enrollment failed for {user.username}')
        except User.DoesNotExist:
            log.error(f'User {user.username} not found in database')
            
    except Exception as e:
        # Use getattr to safely access username attribute
        username = getattr(user, 'username', 'unknown')
        log.error(f'Error in auto_enroll_on_registration_completed for user {username}: {str(e)}')
