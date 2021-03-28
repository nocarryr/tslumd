from sphinx import addnodes
from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.domains.python import PyXRefRole, PyAttribute

def _parse_propertyobj_section(self, section):
    """Injected into :class:`sphinx.ext.napoleon.docstring.GoogleDocstring`
    to transform a `Properties` section and add `.. propertyobj` directives

    (monkeypatching is done in conf.py)
    """
    lines = []
    field_type = ':Properties:'
    padding = ' ' * len(field_type)
    fields = self._consume_fields()
    multi = len(fields) > 1
    lines.append(field_type)
    for _name, _type, _desc in fields:
        field_block = []
        field_block.append(f'.. propertyobj:: {_name}')
        if _type:
            field_block.extend(self._indent([f':type: {_type}'], 3))
        prop_cls = 'Property'
        if _type == 'dict':
            prop_cls = 'DictProperty'
        elif _type == 'list':
            prop_cls = 'ListProperty'
        field_block.extend(self._indent([f':propcls: {prop_cls}'], 3))
        # field_block.append(f'.. propertyobj:: {_name} -> :class:`~pydispatch.properties.{prop_cls}`(:class:`{_type}`)')
        field_block.append('')
        field = self._format_field('', '', _desc)
        field_block.extend(self._indent(field, 3))
        field_block.append('')
        lines.extend(self._indent(field_block, 3))
    return lines

ANNO_CLS = nodes.emphasis

def build_xref(title, target, innernode=ANNO_CLS, contnode=None, env=None):
    refnode = addnodes.pending_xref('', refdomain='py', refexplicit=False, reftype='class', reftarget=target)

    refnode += contnode or innernode(title, title)
    if env:
        env.get_domain('py').process_field_xref(refnode)
    return refnode

class PropertyObjDirective(PyAttribute):
    """A directive for documenting :class:`pydispatch.properties.Property` objects

    Options
    -------

    :param str propcls: The name of the :class:`pydispatch.properties.Property`
        class or subclass (`'Property'`, `'ListProperty'`, `'DictProperty'`).
    :param str type: The data type for the property. Only useful for non-container
        Property types (for `DictProperty` and `ListProperty`,
        this would be `'list'` or `'dict'`)

    .. note::

        The values for :attr:`propcls` and :attr:`type` should be detected by
        :func:`_parse_propertyobj_section` if using napoleon
    """
    option_spec = PyAttribute.option_spec.copy()
    option_spec.update({
        'type':directives.unchanged,
        'propcls':directives.unchanged,
    })
    def run(self):
        self._build_prop_anno()
        return super().run()
    # def add_target_and_index(self, name, sig, signode):
    #     return super().add_target_and_index(name, sig, signode)
    def handle_signature(self, sig, signode):
        r = super().handle_signature(sig, signode)
        signode += self._annotation_node
        return r
    def _build_prop_anno(self):
        self.options.setdefault('type', 'None')
        prop_type = self.options['type']
        prop_cls = self.options.get('propcls')
        if prop_cls is None:
            prop_cls = 'Property'
            if prop_type == 'dict':
                prop_cls = 'DictProperty'
            elif prop_type == 'list':
                prop_cls = 'ListProperty'
        prop_cls_xr = f':class:`~pydispatch.properties.{prop_cls}`'
        prop_type_xr = f':class:`{prop_type}`'

        # self.options['annotation'] = f'{prop_cls_xr}({prop_cls})'
        anno = addnodes.desc_returns('', '')
        # anno += ANNO_CLS(' -> ', ' -> ')
        anno += build_xref(prop_cls, f'pydispatch.properties.{prop_cls}', env=self.env)
        anno += ANNO_CLS('(', '(')
        anno += build_xref(prop_type, prop_type, env=self.env)
        anno += ANNO_CLS(')', ')')
        self._annotation_node = anno

def setup(app):
    app.add_directive_to_domain('py', 'propertyobj', PropertyObjDirective)
    propertyobj_role = PyXRefRole()
    app.add_role_to_domain('py', 'propertyobj', propertyobj_role)
    return {
        'version': '0.1',
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
