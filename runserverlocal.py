print "Loading " + __file__

import os
os.environ['ITLYST_ENVIRONMENT'] = 'local'

from itlystapi import app

if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True)
