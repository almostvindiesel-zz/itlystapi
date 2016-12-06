print "Loading " + __file__

from app import app

app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://{username}:{password}@{hostname}/{database}".format(
    username="",
    password="",
    hostname="",
    database="",
)

app.config['SQLALCHEMY_POOL_RECYCLE'] = 299
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = 'False'

app.config['FOURSQUARE_API_VERSION'] = ''
app.config['FOURSQUARE_API_CLIENT_ID'] = ''
app.config['FOURSQUARE_API_CLIENT_SECRET'] = ''

app.config['DEBUG'] = True
app.config['SECRET_KEY'] = ''

app.config['MAIL_USERNAME'] = ''
app.config['MAIL_PASSWORD'] = ''
app.config['MAIL_DEFAULT_SENDER'] = '"itlyst" <sender@host.com>'
app.config['MAIL_SERVER'] = ''
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USE_TLS'] = False
