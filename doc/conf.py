import gocept.package.sphinxconf


_year_started = 2016
html_theme = 'alabaster'
html_theme_path = []
html_sidebars = {'**': ['globaltoc.html', 'searchbox.html']}
html_logo = 'zodb.png'
autosummary_generate = []

gocept.package.sphinxconf.set_defaults()

# html_sidebars['**'].pop(0)
