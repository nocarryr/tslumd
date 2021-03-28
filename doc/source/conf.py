# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
# sys.path.insert(0, os.path.abspath('.'))
sys.path.append(os.path.abspath('./ext'))


# -- Project information -----------------------------------------------------

project = 'tslumd'
copyright = '2021, Matthew Reid'
author = 'Matthew Reid'

# The full version, including alpha/beta/rc tags
release = '0.0.1'

# <napoleon monkeypatching> --------------------------------------------------
# Hacked on Sphinx v2.2.2
# https://github.com/sphinx-doc/sphinx/tree/0c48a28ad7216ee064b0db564745d749c049bfd5

from sphinx.ext.napoleon.docstring import GoogleDocstring
from propertyobj import _parse_propertyobj_section

def _parse_attributes_section_monkeyed(self, section):
    return self._format_fields(section.title(), self._consume_fields())

GoogleDocstring._parse_attributes_section_monkeyed = _parse_attributes_section_monkeyed
GoogleDocstring._parse_propertyobj_section = _parse_propertyobj_section

def _load_custom_sections(self):
    for key in ['attributes', 'class attributes']:
        self._sections[key] = self._parse_attributes_section_monkeyed
    self._sections['properties'] = self._parse_propertyobj_section

GoogleDocstring._load_custom_sections = _load_custom_sections

# </napoleon monkeypatching> -------------------------------------------------

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    # 'sphinx_autodoc_typehints',
    'sphinx.ext.viewcode',
    'sphinx.ext.intersphinx',
    'sphinx.ext.todo',
    'propertyobj',
    'builtinproperty',
    'eventobj',
]

autodoc_member_order = 'bysource'
autodoc_default_options = {
    'show-inheritance':True,
}


# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'sphinx_rtd_theme'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']


intersphinx_mapping = {
    'python':('https://docs.python.org/', None),
    'pydispatch': ('https://python-dispatch.readthedocs.io/en/latest/', None),
}
