from sphinx import addnodes
from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.domains.python import PyXRefRole, PyMethod
from sphinx.util import logging
from sphinx.ext import autodoc
logger = logging.getLogger(__name__)


ANNO_CLS = nodes.emphasis

def build_xref(title, target, innernode=ANNO_CLS, contnode=None, env=None):
    refnode = addnodes.pending_xref('', refdomain='py', refexplicit=False, reftype='class', reftarget=target)

    refnode += contnode or innernode(title, title)
    if env:
        env.get_domain('py').process_field_xref(refnode)
    return refnode

class BuiltinPropertyDocumenter(autodoc.PropertyDocumenter):
    """An autodoc Documenter for built-in :func:`property` objects (descriptors
    defined with the `@property` decorator)

    This overrides the existing :class:`autodoc.PropertyDocumenter` and uses a
    `.. builtinproperty::` directive to provide type information and `readonly`
    status (see :class:`BuiltinPropertyDirective`).

    :pep:`484` annotations on the `getter` method will be passed to the
    :attr:`~BuiltinPropertyDirective.proptype` option of the directive.

    If no `setter` method is present, the property is assumed to be read-only
    and will be passed to :attr:`BuiltinPropertyDirective.readonly`

    """
    priority = autodoc.PropertyDocumenter.priority + 1
    directivetype = 'builtinproperty'

    def add_directive_header(self, sig: str) -> None:
        sourcename = self.get_sourcename()
        anno = self.object.fget.__annotations__.get('return')
        readonly = self.object.fset is None
        autodoc.Documenter.add_directive_header(self, sig)
        self.add_line('   :property:', sourcename)
        if readonly:
            self.add_line(f'   :readonly:', sourcename)
        if anno is not None:
            anno_type = getattr(anno, '__qualname__', None)
            if anno_type is None:
                anno_type = str(anno)
            self.add_line(f'   :proptype: {anno_type}', sourcename)

class BuiltinPropertyDirective(PyMethod):
    """A directive for more informative :func:`property` documentation

    Options
    -------

    :param str proptype: The property type
    :param bool readonly: Indicates if the property is read-only (no `setter`)
    """
    option_spec = PyMethod.option_spec.copy()
    option_spec.update({
        'proptype':directives.unchanged,
        'readonly':directives.flag,
    })

    def handle_signature(self, sig, signode):
        rtype = self.retann = self.options.get('proptype')
        r = super().handle_signature(sig, signode)
        if rtype is not None:
            anno = addnodes.desc_returns('', '')
            anno += build_xref(rtype, rtype)
            signode += anno
        if 'readonly' in self.options:
            # signode['classes'].append('readonly')
            # t = ' [{}]'.format(l_('READ ONLY'))
            t = '   [read-only]'
            signode += nodes.emphasis(t, t)#, classes=['readonly-label'])#, 'align-center'])
        return r

def setup(app):
    app.setup_extension('sphinx.ext.autodoc')

    app.add_directive_to_domain('py', 'builtinproperty', BuiltinPropertyDirective)
    builtinproperty_role = PyXRefRole()
    app.add_role_to_domain('py', 'builtinproperty', builtinproperty_role)

    app.add_autodocumenter(BuiltinPropertyDocumenter, override=True)
    return {
        'version': '0.1',
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
