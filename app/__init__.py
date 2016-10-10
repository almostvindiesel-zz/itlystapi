print "Loading __init__.py ..."

import os
from flask import Flask
app = Flask(__name__)

# ------------------------------------------------------------------------------------------ Configuration 


if('NOMNOMTES_ENVIRONMENT' in os.environ):
    if os.environ['NOMNOMTES_ENVIRONMENT'] == 'heroku':
        print "-" * 50
        print "set os.environ from Heroku to app.config vars:"
        for key, value in os.environ.iteritems() :
            app.config[key] = value
            print key, value
        print "-" * 50
    elif os.environ['NOMNOMTES_ENVIRONMENT'] == 'local':
        from app import settingslocal

# ------------------------------------------------------------------------------------------
from app import views
from api import CityListAPI, VenueListAPI, PageListAPI




