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

    def _to_json(self):
        return {
                'id': self.id,
                'title': self.title,
                'description': self.description,
                'provider': self.provider,
                'subjects': self.subjects,
                'presentations': [p._to_json() for p in self.presentations]
                }


class Presentation(object):
    def __init__(self, id, course, start=None, end=None, location="",
            apply_link="", booking_endpoint="",
            apply_from=None, apply_until=None, date_apply=None):
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

    @property
    def bookable(self):
        if self.apply_from and self.apply_until:
            return self.apply_from < self.date_apply < self.apply_until
        return False

    def _to_json(self):
        response = {
                'id': self.id,
                'location': self.location,
                'apply_link': self.apply_link,
                }
        if self.start:
            response['start'] = self.start.isoformat()
        if self.end:
            response['end'] = self.end.isoformat()
        if self.apply_from:
            response['apply_from'] = self.apply_from.isoformat()
        if self.apply_until:
            response['apply_until'] = self.apply_until.isoformat()
        return response
