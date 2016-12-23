print "Loading " + __file__

import os
os.environ['ITLYST_ENVIRONMENT'] = 'local'

print "Setting environment to:", os.environ['ITLYST_ENVIRONMENT']

from app import app

if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True)