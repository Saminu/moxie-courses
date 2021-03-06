from datetime import datetime


class Course(object):
    def __init__(self, id, title="", description="", provider="",
            subjects=None, presentations=None):
        self.id = id
        self.title = title
        self.description = description
        self.provider = provider
        self.subjects = subjects or []
        self.presentations = presentations or []


class Presentation(object):
    def __init__(self, id, course, start=None, end=None, location="",
            apply_link="", booking_endpoint="",
            apply_from=None, apply_until=None, date_apply=None,
            attendance_mode=None, attendance_pattern=None, study_mode=None,
            booking_status=None, booking_id=None):
        self.id = id
        self.course = course
        self.start = start
        self.end = end
        self.location = location
        self.apply_link = apply_link
        self.booking_endpoint = booking_endpoint
        self.apply_from = apply_from
        self.apply_until = apply_until
        self.date_apply = date_apply or datetime.now()
        self.attendance_mode = attendance_mode
        self.attendance_pattern = attendance_pattern
        self.study_mode = study_mode
        self.booking_status = booking_status
        self.booking_id = booking_id

    @property
    def bookable(self):
        if self.apply_from and self.apply_until and self.booking_endpoint:
            return self.apply_from < self.date_apply < self.apply_until
        return False


class Subject(object):
    def __init__(self, title, count=None):
        self.title = title
        self.count = count
