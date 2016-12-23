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
        from itlystapi import settingslocal
        from itlystapi import views
        from api import CityListAPI, VenueListAPI, PageListAPI
    elif os.environ['ITLYST_ENVIRONMENT'] == 'pythonanywhere':
        from itlystapi import settingspa
        import itlystapi.views
        from api import CityListAPI, VenueListAPI, PageListAPI
# ------------------------------------------------------------------------------------------

