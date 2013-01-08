from flask import url_for, jsonify

from moxie.core.representations import Representation, HALRepresentation


class CourseRepresentation(Representation):

    def __init__(self, course):
        self.course = course
        self.presentations = [PresentationRepresentation(p) for p in course.presentations]

    def as_dict(self):
        return {
            'id': self.course.id,
            'title': self.course.title,
            'description': self.course.description,
            'provider': self.course.provider,
            'subjects': self.course.subjects,
            'presentations': [p.as_dict() for p in self.presentations]
        }

    def as_json(self):
        return jsonify(self.as_dict())


class PresentationRepresentation(Representation):

    def __init__(self, presentation):
        self.presentation = presentation

    def as_dict(self):
        response = {
            'id': self.presentation.id,
            'location': self.presentation.location,
            'apply_link': self.presentation.apply_link,
            }
        if self.presentation.start:
            response['start'] = self.presentation.start.isoformat()
        if self.presentation.end:
            response['end'] = self.presentation.end.isoformat()
        if self.presentation.apply_from:
            response['apply_from'] = self.presentation.apply_from.isoformat()
        if self.presentation.apply_until:
            response['apply_until'] = self.presentation.apply_until.isoformat()
        if self.presentation.attendance_mode:
            response['attendance_mode'] = self.presentation.attendance_mode
        if self.presentation.attendance_pattern:
            response['attendance_pattern'] = self.presentation.attendance_pattern
        if self.presentation.study_mode:
            response['study_mode'] = self.presentation.study_mode
        return response


class HALCourseRepresentation(CourseRepresentation):

    def __init__(self, course, endpoint):
        super(HALCourseRepresentation, self).__init__(course)
        self.endpoint = endpoint

    def as_dict(self):
        base = super(HALCourseRepresentation, self).as_dict()
        links = {'self': {
                    'href': url_for(self.endpoint, id=self.course.id)
                }
        }
        return HALRepresentation(base, links).as_dict()

    def as_json(self):
        return jsonify(self.as_dict())


class CoursesRepresentation(object):

    def __init__(self, query, results):
        self.query = query
        self.results = results

    def as_dict(self, representation=CourseRepresentation):
        return {
            'query': self.query,
            'results': [representation(r).as_dict() for r in self.results]
        }

    def as_json(self):
        return jsonify(self.as_dict())


class HALCoursesRepresentation(CoursesRepresentation):

    def __init__(self, query, results, endpoint):
        super(HALCoursesRepresentation, self).__init__(query, results)
        self.endpoint = endpoint

    def as_dict(self):
        response = {
            'query': self.query,
        }
        # Need to have the '.' before 'course' to correctly pick the URL
        courses = [HALCourseRepresentation(r, '.course').as_dict() for r in self.results]
        links = {'self': {
            'href': url_for(self.endpoint, q=self.query)
            }
        }
        return HALRepresentation(response, links, {'courses': courses}).as_dict()

    def as_json(self):
        return jsonify(self.as_dict())


class SubjectRepresentation(object):
    def __init__(self, subject):
        self.subject = subject

    def as_dict(self):
        return {self.subject.title: self.subject.count}


class SubjectsRepresentation(object):
    def __init__(self, subjects):
        self.subjects = subjects

    def as_dict(self, representation=SubjectRepresentation):
        subjects = dict()
        for subject in self.subjects:
            subjects.update(representation(subject).as_dict())
        return subjects

    def as_json(self):
        return jsonify(self.as_dict())


class HALSubjectsRepresentation(object):
    def __init__(self, subjects, endpoint):
        self.subjects = subjects
        self.endpoint = endpoint

    def as_dict(self):
        subjects = []
        for subject in self.subjects:
            subjects.append({
                'title': subject.title,
                'href': url_for('.search', q='course_subject:"%s"' % subject.title)
                })
        links = {'self': {'href': url_for(self.endpoint)},
                'courses:subject': subjects,
                }
        return HALRepresentation({}, links).as_dict()

    def as_json(self):
        return jsonify(self.as_dict())
