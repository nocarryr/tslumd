from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.domains.python import PyFunction, PyXRefRole

class EventDirective(PyFunction):
    pass

def setup(app):
    app.add_directive_to_domain('py', 'event', EventDirective)
    event_role = PyXRefRole()
    app.add_role_to_domain('py', 'event', event_role)
    return {
        'version': '0.1',
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
