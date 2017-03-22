print "Loading " + __file__

import os
import ssl
from werkzeug.serving import run_simple
os.environ['ITLYST_ENVIRONMENT'] = 'local'

from itlystapi import app

if __name__ == '__main__':
    """
    os.environ['SSL_CRT'] = '/Users/mars/code/ssl/localhost.crt'
    os.environ['SSL_KEY'] = '/Users/mars/code/ssl/localhost.key'
    
    ctx = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    ctx.load_cert_chain(os.environ['SSL_CRT'], os.environ['SSL_KEY'])
    run_simple('localhost', 4000, app, ssl_context=ctx)
    """

    #ssl_context = (os.environ['SSL_CRT'], os.environ['SSL_KEY'])
    #run_simple('localhost', 4000, app, ssl_context, use_reloader=True)
    #app.run(host='0.0.0.0', port=5000, ssl_context=context, threaded=True, debug=True)
    app.run(host='0.0.0.0',debug=True)
