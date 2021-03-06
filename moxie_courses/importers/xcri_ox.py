import logging
from collections import defaultdict
from dateutil import parser
from xml import sax

from moxie.core.search import SearchServerException
from moxie.core.search.solr import SolrSearch


logger = logging.getLogger(__name__)

XCRI_NS = "http://xcri.org/profiles/1.2/catalog"
OXCAP_NS = "http://purl.ox.ac.uk/oxcap/ns/"
MLO_NS = "http://purl.org/net/mlo"
DC_NS = "http://purl.org/dc/elements/1.1/"

# Elements to keep in, represents a document
# If the value is not None, this is the attribute that will be used
PARSE_STRUCTURE = {
    (XCRI_NS, "provider"): {
            (DC_NS, "title"): None,
        },
    (XCRI_NS, "course"): {
            (DC_NS, "description"): None,
            (DC_NS, "subject"): None,
            (DC_NS, "identifier"): None,
            (DC_NS, "title"): None,
        },
    (XCRI_NS, "presentation"): {
            (DC_NS, "identifier"): None,
            (OXCAP_NS, "bookingEndpoint"): None,
            (MLO_NS, "start"): "dtf",
            (XCRI_NS, "end"): "dtf",
            (XCRI_NS, "applyFrom"): "dtf",
            (XCRI_NS, "applyUntil"): "dtf",
            (OXCAP_NS, "memberApplyTo"): None,
            (XCRI_NS, "attendanceMode"): None,
            (XCRI_NS, "attendancePattern"): None,
            (XCRI_NS, "studyMode"): None,
            },
}

# Elements to keep in
VENUE_STRUCTURE = {
    (XCRI_NS, "provider"): {
        (DC_NS, "identifier"): None
    }
}

class XcriOxHandler(sax.ContentHandler):

    def __init__(self):
        self.presentations = []
        self.element_data = defaultdict(list)
        self.parse = None   # structure that is currently parsed
        self.tag = None     # current name of the key
        self.capture_data = False
        self.in_venue = False

    def startElementNS(self, (uri, localname), qname, attributes):
        self.capture_data = False
        self.data = ''
        # dealing with the xcri:provider being in two different structures
        # that we need to parse...
        if (uri, localname) in PARSE_STRUCTURE and not self.in_venue:
            self.parse = (uri, localname)
            return
        elif (uri, localname) in VENUE_STRUCTURE and self.in_venue:
            self.parse = (uri, localname)
            return

        if self.parse is not None:
            if not self.in_venue:
                element = PARSE_STRUCTURE[self.parse]
            else:
                element = VENUE_STRUCTURE[self.parse]

            if localname == 'venue':
                self.in_venue = True
                self.capture_data = False

            if (uri, localname) in element and not self.in_venue:
                # Capture data with given key except if we need the attribute
                attr = element[(uri, localname)]
                self.capture_data = True
                self.tag = "{element}_{key}".format(
                    element=self.parse[1],
                    key=localname)
                if attr:
                    self.capture_data = False
                for name, value in attributes.items():
                    qname = attributes.getQNameByName(name)
                    prefix, property = self._split_qname(qname)
                    if property == attr:
                        # Use the value of the attribute instead of the element
                        self.element_data[self.tag] = [value]
            elif (uri, localname) in element and self.in_venue:
                self.capture_data = True
                self.tag = "{element}_venue_{key}".format(
                    element='presentation',
                    key=localname)

    def endElementNS(self, (uri, localname), qname):
        if self.capture_data:
            self.element_data[self.tag].append(self.data)
        self.data = ''

        if localname == 'venue':
            self.in_venue = False
            # Structure to continue to parse is a presentation
            self.parse = (XCRI_NS, "presentation")
        elif localname == 'presentation':
            self.presentations.append(self.element_data.copy())

        if (uri, localname) in PARSE_STRUCTURE and not self.in_venue:
            for key in PARSE_STRUCTURE[(uri, localname)].keys():
                # Removes all keys corresponding to the element
                k = "{element}_{key}".format(element=localname, key=key[1])
                if k in self.element_data:
                    del self.element_data[k]

            if localname == 'presentation':
                # structure is provider although we're parsing a presentation...
                for key in VENUE_STRUCTURE[(uri, 'provider')].keys():
                    k = "{element}_venue_{key}".format(element='presentation', key=key[1])
                    if k in self.element_data:
                        del self.element_data[k]

            self.parse = None

    def characters(self, data):
        self.data += data

    def endDocument(self):
        logger.debug("Parsed {0} presentations.".format(len(self.presentations)))

    @classmethod
    def _split_qname(self, qname):
        """Split a QName in an attempt to find the prefix
        :param qname: QName
        :return tuple with prefix and localname; prefix None if no NS
        """
        qname_split = qname.split(':')
        if len(qname_split) == 2:
            prefix, local = qname_split
        else:
            prefix = None
            local = qname
        return prefix, local


class XcriOxImporter(object):
    """Import a feed from an XCRI XML document
    WARNING: as we do need to have ONE unique identifier, preferably not a URI as it needs to be exposed (e.g. GET parameter),
    we took the decision to split the URI from data.ox (in the form of course.data.ox.ac.uk) and replace '/' by '-'.
    This is done by the method _get_identifier of this class. This might cause some problems in the future as we have no
    guarantee that this URI scheme will still work. Alternative solutions could be:
    * to keep the URI and urlencode it when it is exposed
    * to do a hash of the URI and work with this hash
    Unfortunately both solutions are not very readable.
    """

    def __init__(self, indexer, xcri_file, buffer_size=8192,
                 handler=XcriOxHandler):
        self.indexer = indexer
        self.xcri_file = xcri_file
        self.buffer_size = buffer_size
        self.handler = handler()
        self.presentations = []
        self.ignore_subjects = ['Graduate Training', 'Qualitative', 'Quantitative']

    def run(self):
        self.parse()
        try:
            self.indexer.index(self.presentations)
        except SearchServerException as sse:
            logger.error("Error when indexing courses", exc_info=True)
        finally:
            self.indexer.commit()

    def parse(self):
        parser = sax.make_parser()
        parser.setContentHandler(self.handler)
        parser.setFeature(sax.handler.feature_namespaces, 1)
        parser.parse(self.xcri_file)
        #buffered_data = self.xcri_file.read(self.buffer_size)
        #while buffered_data:
        #    parser.feed(buffered_data)
        #    buffered_data = self.xcri_file.read(self.buffer_size)
        #parser.close()

        # transformations
        for p in self.handler.presentations:
            try:
                p['provider_title'] = p['provider_title'][0]
                p['course_title'] = p['course_title'][0]
                p['course_identifier'] = self._get_identifier(p['course_identifier'])
                p['course_description'] = ''.join(p['course_description'])
                presentation_id = self._get_identifier(p['presentation_identifier'])
                if not presentation_id:
                    # Presentation identifier is the main ID for a document
                    # if there is no ID, we do not want to import it
                    raise Exception("Presentation with no ID")
                p['presentation_identifier'] = presentation_id
                if 'presentation_start' in p:
                    p['presentation_start'] = self._date_to_solr_format(p['presentation_start'][0])
                if 'presentation_end' in p:
                    p['presentation_end'] = self._date_to_solr_format(p['presentation_end'][0])
                if 'presentation_applyFrom' in p:
                    p['presentation_applyFrom'] = self._date_to_solr_format(p['presentation_applyFrom'][0])
                if 'presentation_applyUntil' in p:
                    p['presentation_applyUntil'] = self._date_to_solr_format(p['presentation_applyUntil'][0])
                if 'presentation_bookingEndpoint' in p:
                    p['presentation_bookingEndpoint'] = p['presentation_bookingEndpoint'][0]
                if 'presentation_memberApplyTo' in p:
                    p['presentation_memberApplyTo'] = p['presentation_memberApplyTo'][0]
                if 'presentation_attendanceMode' in p:
                    p['presentation_attendanceMode'] = p['presentation_attendanceMode'][0]
                if 'presentation_attendancePattern' in p:
                    p['presentation_attendancePattern'] = p['presentation_attendancePattern'][0]
                if 'presentation_venue_identifier' in p:
                    # we're only interested by OxPoints ID atm
                    oxpoints = self._get_identifier(p['presentation_venue_identifier'],
                        uri_base="http://oxpoints.oucs.ox.ac.uk/id/")
                    if oxpoints:
                        p['presentation_venue_identifier'] = 'oxpoints:{id}'.format(id=oxpoints)
                    else:
                        del p['presentation_venue_identifier']

                p['course_subject'] = [subject for subject in p['course_subject'] if subject not in self.ignore_subjects]

                self.presentations.append(p)
            except Exception as e:
                logger.warning("Couldn't transform presentation", exc_info=True,
                    extra={'presentation': p})

    @classmethod
    def _date_to_solr_format(cls, date):
        """Transforms date from '2008-01-01' to '2008-01-01T00:00:00Z'
        :param date: date to format
        :return date formatted as 2008-01-01T00:00:00Z
        """
        return parser.parse(date).strftime("%Y-%m-%dT%H:%M:%SZ")

    @classmethod
    def _get_identifier(cls, identifiers, uri_base="https://course.data.ox.ac.uk/id/"):
        """Get an ID from a list of strings.
        NOTE: it is expected to have one identifier as an URI
        We keep the last part of this URI
        :param identifiers: list of identifier
        :return ID as a string
        """
        for identifier in identifiers:
            if identifier.startswith('http'):
                return identifier[len(uri_base):].replace('/', '-')
        return None

def main():
    logging.basicConfig(level=logging.DEBUG)
    import argparse
    args = argparse.ArgumentParser()
    args.add_argument('xcri_file', type=argparse.FileType('r'))
    ns = args.parse_args()
    solr = SolrSearch('courses', 'http://33.33.33.10:8080/solr/')
    xcri_importer = XcriOxImporter(solr, ns.xcri_file)
    xcri_importer.run()


if __name__ == '__main__':
    main()