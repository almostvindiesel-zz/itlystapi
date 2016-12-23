#!/usr/bin/env python
# -*- coding: utf-8 -*-
print "Loading " + __file__

import os
from flask import Flask
app = Flask(__name__)

# ------------------------------------------------------------------------------------------ Configuration 
if('ITLYST_ENVIRONMENT' in os.environ):
    if os.environ['ITLYST_ENVIRONMENT'] == 'heroku':
        print "-" * 50
        print "set os.environ from Heroku to app.config vars:"
        for key, value in os.environ.iteritems() :
            app.config[key] = value
            print key, value
    elif os.environ['ITLYST_ENVIRONMENT'] == 'local':
        from app import settingslocal
        from app import views
        from api import CityListAPI, VenueListAPI, PageListAPI
    elif os.environ['EXCELNINJA_ENVIRONMENT'] == 'pythonanywhere':
        from app import settingspa
        import app.views
        from api import CityListAPI, VenueListAPI, PageListAPI
# ------------------------------------------------------------------------------------------

