# Copyright 2024 Robert Eckelmann
# SPDX-License-Identifier: GPL-3.0-or-later
# Configuration file for the Sphinx documentation builder.

import datetime
import os
import sys

sys.path.insert(0, os.path.abspath(".."))  # Allow modules to be found

project = "pmbootstrap"
copyright = str(datetime.date.today().year) + ", postmarketOS contributors"
extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.doctest",
    "sphinxcontrib.autoprogram",
    "sphinxcontrib.jquery",
]
exclude_patterns = ["_build", "_out", "Thumbs.db", ".DS_Store", ".venv", "README.md"]

html_theme = "pmos"
html_theme_options = {
    "source_edit_link": "https://gitlab.postmarketos.org/postmarketOS/pmbootstrap/-/blob/main/docs/{filename}",
}

# Output file base name for HTML help builder.
htmlhelp_basename = "pmbootstrapdoc"

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    ("index", "pmbootstrap", "pmbootstrap Documentation", ["postmarketOS Contributors"], 1)
]
