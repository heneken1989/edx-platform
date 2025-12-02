"""
Configuration for selective course enrollment after payment

This module allows configuring which parts of courses should be enrolled
when a user purchases the All Access subscription.
"""

# Example configuration for selective enrollment
ENROLLMENT_CONFIG = {
    # Option 1: Enroll only in specific courses
    'enroll_specific_courses': [
        # 'course-v1:Manabi+N51+2026',
        # 'course-v1:Manabi+N41+2026',
    ],
    
    # Option 2: Enroll only in courses matching patterns
    'course_id_patterns': [
        # 'course-v1:Manabi+N5*',  # All N5 courses
        # 'course-v1:Manabi+N4*',  # All N4 courses
    ],
    
    # Option 3: Enroll only in courses with specific sections/sequences
    # This requires checking course structure
    'enroll_courses_with_sections': [
        # {
        #     'course_id_pattern': 'course-v1:Manabi+N5*',
        #     'section_display_names': ['Module 1: Grammar', 'Module 2: Vocabulary'],
        #     'exclude_sections': ['Module 3: Test'],  # Optional: exclude specific sections
        # },
    ],
    
    # Option 4: Enroll only in courses with specific tags/metadata
    'enroll_courses_with_tags': [
        # 'n5-level',
        # 'beginner',
    ],
    
    # Option 5: Exclude specific courses
    'exclude_courses': [
        # 'course-v1:Manabi+Advanced+2026',
    ],
    
    # Option 6: Enroll all courses (default behavior)
    'enroll_all': True,  # Set to False to enable selective enrollment
}

def should_enroll_course(course_id, course_overview=None):
    """
    Determine if a course should be enrolled based on configuration
    
    Args:
        course_id: Course key string
        course_overview: CourseOverview object (optional, for advanced filtering)
    
    Returns:
        bool: True if course should be enrolled
    """
    config = ENROLLMENT_CONFIG
    
    # If enroll_all is True, enroll all courses (default behavior)
    if config.get('enroll_all', True):
        # Check exclude list
        if course_id in config.get('exclude_courses', []):
            return False
        return True
    
    # Selective enrollment logic
    course_id_str = str(course_id)
    
    # Check specific courses list
    if course_id_str in config.get('enroll_specific_courses', []):
        return True
    
    # Check course ID patterns
    import fnmatch
    for pattern in config.get('course_id_patterns', []):
        if fnmatch.fnmatch(course_id_str, pattern):
            return True
    
    # Check tags/metadata (requires course_overview)
    if course_overview:
        # This would require custom metadata field or tags
        # For now, this is a placeholder
        pass
    
    # Check section-based enrollment (requires course_overview and course structure)
    if course_overview:
        for section_config in config.get('enroll_courses_with_sections', []):
            pattern = section_config.get('course_id_pattern', '')
            if fnmatch.fnmatch(course_id_str, pattern):
                # Would need to check course structure here
                # This requires fetching course outline
                return True
    
    return False

