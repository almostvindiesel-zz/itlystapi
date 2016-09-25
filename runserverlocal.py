print "Loading runserver.py ..."

import os
os.environ['NOMNOMTES_ENVIRONMENT'] = 'local'
print "Setting environment to:", os.environ['NOMNOMTES_ENVIRONMENT']

from app import app

if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True)