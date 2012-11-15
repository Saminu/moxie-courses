import logging
from collections import defaultdict

from xml import sax

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
            },
}


class XcriOxHandler(sax.ContentHandler):

    def __init__(self):
        self.presentations = []
        self.element_data = defaultdict(list)
        self.parse = None   # structure that is currently parsed
        self.tag = None     # current name of the key
        self.capture_data = False

    def startElementNS(self, (uri, localname), qname, attributes):
        self.capture_data = False
        if (uri, localname) in PARSE_STRUCTURE:
            self.parse = (uri, localname)
        elif self.parse is not None:
            element = PARSE_STRUCTURE[self.parse]
            if (uri, localname) in element:
                attr = element[(uri, localname)]
                self.capture_data = attributes.getLength() == 0
                self.tag = "{element}_{key}".format(
                    element=self.parse[1],
                    key=localname)
                for name, value in attributes.items():
                    qname = attributes.getQNameByName(name)
                    prefix, property = self._split_qname(qname)
                    if property == attr:
                        # Use the value of the attribute instead of the element
                        self.element_data[self.tag] = value
                        self.capture_data = False

    def endElementNS(self, (uri, localname), qname):
        if (uri, localname) == (XCRI_NS, "presentation"):
            #logger.debug(self.element_data)
            self.presentations.append(self.element_data)
            self.parse = None
            self.element_data = defaultdict(list)

    def endDocument(self):
        logger.debug("Parsed {0} presentations.".format(len(self.presentations)))

    def characters(self, data):
        if self.capture_data:
            if data.strip():
                self.element_data[self.tag].append(data.strip())

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

    def __init__(self, indexer, xcri_file, buffer_size=8192,
                 handler=XcriOxHandler):
        self.indexer = indexer
        self.xcri_file = xcri_file
        self.buffer_size = buffer_size
        self.handler = handler()
        self.presentations = []

    def run(self):
        self.parse()
        self.indexer.index(self.presentations)
        self.indexer.commit()

    def parse(self):
        parser = sax.make_parser()
        parser.setContentHandler(self.handler)
        parser.setFeature(sax.handler.feature_namespaces, 1)
        buffered_data = self.xcri_file.read(self.buffer_size)
        while buffered_data:
            parser.feed(buffered_data)
            buffered_data = self.xcri_file.read(self.buffer_size)
        parser.close()

        # transformations
        for p in self.handler.presentations:
            try:
                p['provider_title'] = p['provider_title'][0]
                p['course_title'] = p['course_title'][0]
                p['course_identifier'] = self._get_identifier(p['course_identifier'])
                if type(p['course_description']) == list:
                    p['course_description'] = p['course_description'][0]
                p['presentation_identifier'] = self._get_identifier(p['presentation_identifier'])
                if 'presentation_start' in p:
                    p['presentation_start'] = self._date_to_solr_format(p['presentation_start'])
                if 'presentation_end' in p:
                    p['presentation_end'] = self._date_to_solr_format(p['presentation_end'])
                if 'presentation_applyFrom' in p:
                    p['presentation_applyFrom'] = self._date_to_solr_format(p['presentation_applyFrom'])
                if 'presentation_applyUntil' in p:
                    p['presentation_applyUntil'] = self._date_to_solr_format(p['presentation_applyUntil'])
                if 'presentation_bookingEndpoint' in p:
                    p['presentation_bookingEndpoint'] = p['presentation_bookingEndpoint'][0]

                self.presentations.append(p)
            except Exception as e:
                logger.debug(e)

    @classmethod
    def _date_to_solr_format(cls, date):
        """Transforms date from '2008-01-01' to '2008-01-01T00:00:00Z'
        :param date: date to format
        :return date formatted as 2008-01-01T00:00:00Z
        """
        elements = date.split('-')
        return "{year}-{month}-{day}T00:00:00Z".format(
            year=elements[0],
            month=elements[1],
            day=elements[2]
        )

    @classmethod
    def _get_identifier(cls, identifiers):
        """Get an ID from a list of strings.
        NOTE: it is expected to have one identifier as an URI
        :param identifiers: list of identifier
        :return ID as a string or None
        """
        for identifier in identifiers:
            if identifier.startswith('http'):
                return identifier.split('/')[-1]
        return None

def main():
    logging.basicConfig(level=logging.DEBUG)
    import argparse
    args = argparse.ArgumentParser()
    args.add_argument('xcri_file', type=argparse.FileType('r'))
    ns = args.parse_args()
    solr = SolrSearch('collection1', 'http://localhost:8983/solr/')
    xcri_importer = XcriOxImporter(solr, ns.xcri_file)
    xcri_importer.run()


if __name__ == '__main__':
    main()