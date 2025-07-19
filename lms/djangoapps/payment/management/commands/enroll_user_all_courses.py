"""
Management command to enroll a user in all available courses
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from common.djangoapps.student.models import CourseEnrollment
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from django.utils import timezone


class Command(BaseCommand):
    help = 'Enroll a user in all available courses'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Username of the user to enroll')
        parser.add_argument(
            '--mode',
            type=str,
            default='verified',
            help='Enrollment mode (default: verified)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-enrollment even if already enrolled'
        )

    def handle(self, *args, **options):
        username = options['username']
        mode = options['mode']
        force = options['force']

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f'User "{username}" does not exist')

        # Get all available courses
        all_courses = CourseOverview.objects.filter(
            start__lte=timezone.now(),
            end__gte=timezone.now(),
        )

        self.stdout.write(f'Found {all_courses.count()} available courses')
        
        enrolled_count = 0
        already_enrolled_count = 0
        error_count = 0

        for course_overview in all_courses:
            try:
                # Check if user is already enrolled
                existing_enrollment = CourseEnrollment.get_enrollment(
                    user, 
                    course_overview.id
                )
                
                if existing_enrollment and existing_enrollment.is_active:
                    if force:
                        # Update existing enrollment mode
                        existing_enrollment.update_enrollment(mode=mode)
                        enrolled_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'Updated enrollment for {course_overview.display_name}'
                            )
                        )
                    else:
                        already_enrolled_count += 1
                        self.stdout.write(
                            f'Already enrolled in {course_overview.display_name}'
                        )
                else:
                    # Enroll user in the course
                    enrollment, created = CourseEnrollment.enroll(
                        user=user,
                        course_key=course_overview.id,
                        mode=mode
                    )
                    
                    if created:
                        enrolled_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'Enrolled in {course_overview.display_name}'
                            )
                        )
                    else:
                        already_enrolled_count += 1
                        self.stdout.write(
                            f'Already enrolled in {course_overview.display_name}'
                        )
                        
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'Error enrolling in {course_overview.display_name}: {str(e)}'
                    )
                )

        self.stdout.write('\n' + '='*50)
        self.stdout.write(f'Enrollment Summary for user "{username}":')
        self.stdout.write(f'  - New enrollments: {enrolled_count}')
        self.stdout.write(f'  - Already enrolled: {already_enrolled_count}')
        self.stdout.write(f'  - Errors: {error_count}')
        self.stdout.write(f'  - Total courses processed: {all_courses.count()}')
        self.stdout.write('='*50) 