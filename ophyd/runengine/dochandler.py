from __future__ import print_function

import logging


logging.basicConfig(level=logging.DEBUG)


def is_event(doc):
    return set(('descriptor', 'data')).issubset(doc)

def is_descriptor(doc):
    return set(('begin_run_event', 'keys')).issubset(doc)


class DocHandler(object):
    '''DocHandlers are used to subscribe for reception of Run documents.

    Parameters:
    -------------
    run : Run instance
    subs : list
           A list of valid Run event-types to subscribe to.

           Eg: ['begin_run', 'end_run', '*'] would subscribe
           to begin_run and end_run events, as well as all events 
           which produce event_descriptors.
    '''
    def __init__(self, run, subs):
        
        if 'begin_run' in subs:
            run.subscribe(self.on_begin_run, event_type='begin_run')
        
        if 'end_run' in subs:
            run.subscribe(self.on_end_run, event_type='end_run')

        if '*' in subs:
            run.subscribe(self.on_event, event_type='*')

    def on_begin_run(self, doc, **kwargs):
        logging.debug('\n\nbegin_run = %s\n', doc)

    def on_end_run(self, doc, **kwargs):
        logging.debug('\n\nend_run = %s\n', doc)

    def on_event(self, doc, **kwargs):
        if is_descriptor(doc):
            logging.debug('\n\nevent descriptor = %s\n', doc)
        elif is_event(doc):
            logging.debug('\n\nevent = %s\n', doc)
        else:
            raise ValueError('Malformed document - %s' % doc)


class ActiveDocHandler(DocHandler):
    pass
