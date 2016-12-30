#!/usr/bin/env python
# -*- coding: utf-8 -*-
print "Loading " + __file__

from itlystapi import app
from flask_restful import Resource, Api, reqparse, abort

import warnings
from flask import request, jsonify, Flask
from views import *
from models import *
import jsonurl
from functools import wraps
#from flask_restful import reqparse, abort, Api, Resource

import textblob
from textblob import TextBlob

from flaskext.mysql import MySQL
import mysql

#api = Api(app)
api = Api(app)


# ---------------------------------------------  Authentication
def check_auth(email, password):
    #This function checks whether the username and password match
    u = User.query.filter_by(email = email).first()
    if u is not None:
        return user_manager.verify_password(password, u)
    else:
        return false

def authenticate():
    """Sends a 401 response that enables basic auth"""
    return jsonify(login_status=False)
    """
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})
    """

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        print "-"*75
        print "Checking authorization...."
        print "request: "
        print request
        print "headers: "
        print request.headers
        #print "params: "
        #print request.params

        auth = request.authorization
        print "auth.username: ", auth.username
        print "auth.password: ", auth.password
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

@app.route('/api/v1/login')
@requires_auth
def validate_login():
    return jsonify(login_status=True)

@app.route('/login')
@login_required 
def login():
    redirect("/user/sign-in", code=302)


# --------------------------------------------- API Resources

class TextAPI(Resource):
    def post(self):

        #Get Parameters
        try:
            json = jsonurl.parse_query(request.data)
            text = json['text']
        except Exception as e:
            print "Could not get parameters: ", e.message
            text = ''

        """
        text = "5 Gjusta \n Is there a better day-time eatery than Gjusta at the moment? Except for the paucity of seating, the fare coming out of the massive kitchen and ovens is impressive from beginning to end, starting with the pastries, breads, and sweets. The smoked fish is some of the best in town while the breakfast offers everything from pork sausage and eggs to flatbread pizzas. For lunch, try a prime rib, porchetta, or banh mi sandwich, which comes loaded with house-made pate."
        """

        #Replace carriage return with period, which will help identify venue names
        text = text.replace("\n"," . ")

        blob = TextBlob(text)
        btags = blob.tags
        btokens = blob.tokens

        btokens[:] = [x for x in btokens if x != '(']
        btokens[:] = [x for x in btokens if x != ')']

        #print "btags:", blob.tags
        #print "btokens:", btokens

        #Add Periods, Dashes, and Commas to the textblob
        for i in range(len(btokens)):
            if i == len(btags):
                break
            if not btokens[i] == btags[i][0]:
                btags.insert(i, (btokens[i], 'PUNT') )
                #print "logged: ", btokens[i]

        npp_count = 0;
        npps = []
        noun_phrase = ''

        for idx, pairs in enumerate(btags):
            if pairs[1] == 'NNP' or pairs[1] == 'POS':
                npp_count = npp_count + 1
            elif npp_count > 0:
                for i in range(npp_count):
                    noun_phrase = noun_phrase + btags[idx - npp_count + i][0] + ' '
                npps.append(noun_phrase.replace(" '", "'").strip().lower())
                npp_count = 0
                noun_phrase = ''
            if idx == len(btags) - 1 and npp_count > 0:
                for i in range(npp_count):
                    noun_phrase = noun_phrase + btags[idx - npp_count + i + 1][0] + ' '
                npps.append(noun_phrase.replace(" '", "'").strip().lower())

        print "-" * 50



        #Remove Duplicates
        npps_deduped = list()
        map(lambda x: not x in npps_deduped and npps_deduped.append(x), npps)

        print "NPP Venue Guesses:          ", npps_deduped

        return jsonify(potential_venues = npps_deduped)
    

class ImageAPI(Resource):

    @requires_auth
    def delete(self, image_id):
        session['user_id'] = 2;
        print "--- USER AUTHENTICATION: Set user id to 2 "

        sql = 'delete from user_image where id = %s and user_id= %s ' % (image_id, session['user_id'])
        print "delete image sql: ", sql
        db.session.execute(sql)
        db.session.commit()

        return '', 204


    def put(self, image_id):
        session['user_id'] = 2;
        print "--- USER AUTHENTICATION: Set user id to 2"

        #Get Parameters

        ui = UserImage.query.filter_by(id = image_id).first()
        server_path = 'itlystapi/tmp/';
        s3_bucket = app.config['S3_BUCKET']
        thumbnail_width = 200
        large_width = 1024


        # Add Image from Source to S3
        # --------------------------------------------------------------------
        print "\r\nProcessing image: ", ui.id
        image_original_name = ui.image_original.split('/')[::-1][0] 
        
        print " Getting image from: ", ui.image_original
        urllib.urlretrieve(ui.image_original,  server_path + image_original_name)
        print " Wrote image to disk: ", server_path + image_original_name

        filename, file_extension = os.path.splitext(image_original_name)
        s3_image_name = str(ui.id) +  file_extension

        print " Uploading to s3..."
        conn = tinys3.Connection(app.config['S3_ACCESS_KEY'], app.config['S3_SECRET_KEY'],tls=True,endpoint='s3-us-west-1.amazonaws.com')
        f = open(server_path + image_original_name,'rb')
        conn.upload(s3_image_name, f, s3_bucket)

        ui.image_url  = 'https://s3-us-west-1.amazonaws.com/%s/%s' % (s3_bucket, s3_image_name)
        print " Finished uploading original to s3, url: ", ui.image_url


        # Create Thumbnails
        # --------------------------------------------------------------------
        s3_image_large = str(ui.id) + '_large' + file_extension
        s3_image_thumb = str(ui.id) + '_thumb' + file_extension
        print "  s3_image_large: ", s3_image_large
        print "  s3_image_thumb: ", s3_image_thumb

        print "  Resizing large image... "
        resized_image = resize_image(server_path, image_original_name, s3_image_large, large_width)
        upload_to_s3(server_path, resized_image, s3_image_large, s3_bucket)
        ui.image_large = 'https://s3-us-west-1.amazonaws.com/%s/%s' % (s3_bucket, s3_image_large)

        print "  Resizing thumb image..."
        resized_image = resize_image(server_path, image_original_name, s3_image_thumb, thumbnail_width)
        upload_to_s3(server_path, resized_image, s3_image_thumb, s3_bucket)
        ui.image_thumb = 'https://s3-us-west-1.amazonaws.com/%s/%s' % (s3_bucket, s3_image_thumb)

        db.session.add(ui)
        db.session.commit()
        print "  Commited new sizes to database"

        return jsonify(image_url = ui.image_url, image_thumb = ui.image_thumb, image_large = ui.image_large)

def upload_to_s3(path, image_name, s3_name, s3_bucket):
    print "  Uploading to s3..."
    conn = tinys3.Connection(app.config['S3_ACCESS_KEY'], app.config['S3_SECRET_KEY'],tls=True,endpoint='s3-us-west-1.amazonaws.com')
    f = open(path + image_name,'rb')
    conn.upload(s3_name,f,s3_bucket)

    print "  Finished uploading to s3"

def resize_image(path, image_filename, image_filename_new, new_width):
    image_tmp_full_path = os.path.join(path, image_filename) 
    image_new_full_path = os.path.join(path, image_filename_new) 

    try:   
        fd_img = open(image_tmp_full_path, 'r')
        print "  Resizing image to width %s" % new_width
        img = Image.open(fd_img)
        img = resizeimage.resize_width(img, new_width)
        img.save(image_new_full_path, img.format)
        print "  Saved : %s" % (image_new_full_path)
        return image_filename_new
    except Exception as e:
        print "->Could not resize image since it would require enlarging it. Referencing original path\r\n", e.message, e.args
        return image_filename

class NoteAPI(Resource):

    @requires_auth
    def delete(self, note_id):
        session['user_id'] = 2;
        print "--- USER AUTHENTICATION: Set user id to 2 "

        sql = 'delete from note where id = %s and user_id= %s ' % (note_id, session['user_id'])
        print "delete note sql: ", sql
        db.session.execute(sql)
        db.session.commit()

        return '', 204

    @requires_auth
    def post(self):
        session['user_id'] = 2;
        print "--- USER AUTHENTICATION: Set user id to 2"

        #Get Parameters
        try:
            json = jsonurl.parse_query(request.data)
            venue_id = json['venue_id']
            note = json['note']
        except Exception as e:
            print "Could not get parameters: ", e.message
            note = ''
            venue_id = ''

        #Write to Database
        if venue_id and note:
            try:
                n = Note(
                    session['user_id'], 
                    note, 
                    'http://itlyst.com'
                )
                n.source = 'itlyst'
                n.venue_id = venue_id
                n.insert()
            except Exception as e:
                print "Err ", e

        return '', 204

    @requires_auth
    def put(self, note_id):
        session['user_id'] = 2;
        print "--- USER AUTHENTICATION: Set user id to 2"

        #Get Parameters
        try:
            json = jsonurl.parse_query(request.data)
            note = json['note']
        except Exception as e:
            print "Could not get note parameter: ", e.message
            note = ''

        #Write Parameters
        if note:
            try:
                sql = text('update note set note = :note where id = :note_id and user_id = :user_id')
                sql = sql.bindparams(note = note, note_id = note_id, user_id = session['user_id'])
                print "sql: ", sql
                print "params: \r\n-user_id: %s  \r\n-note_id: %s \r\n-note: %s" % (session['user_id'], note_id, note)
                db.session.execute(sql)
                db.session.commit()
            except Exception as e:
                print "Err ", e

        return '', 204

class VenueAPI(Resource):

    @requires_auth
    def delete(self, venue_id):

        session['user_id'] = 2;
        print "--- USER AUTHENTICATION: Set user id to 2 "

        sql = 'delete from user_venue where venue_id = %s and user_id= %s ' % (venue_id, session['user_id'])
        print "delete user_venue sql: ", sql
        db.session.execute(sql)
        db.session.commit()

        sql = 'delete from note where venue_id = %s and user_id= %s ' % (venue_id, session['user_id'])
        print "delete note sql: ", sql
        db.session.execute(sql)
        db.session.commit()

        sql = 'delete from user_image where venue_id = %s and user_id= %s ' % (venue_id, session['user_id'])
        print "delete user_image sql: ", sql
        db.session.execute(sql)
        db.session.commit()

        sql = 'delete from venue where id = %s ' % (venue_id)
        print "delete venue sql: ", sql
        db.session.execute(sql)
        db.session.commit()

        return '', 204

    #Searches foursquare for a venue 
    def post(self):
        session['user_id'] = 2;
        print "--- USER AUTHENTICATION: Set user id to 2"

        #Get Parameters
        try:
            json = jsonurl.parse_query(request.data)
            name = json['name']
            city = json['city']
        except Exception as e:
            print "Could not get parameters: ", e.message
            name = ''
            city = ''

        #Write to Database
        venues = []
        if name and city:
            try:
                fsvs = FoursquareVenues(name, city, None, None)
                fsvs.search()
                for venue in fsvs.venues:
                    venues.append(dict(
                            name=venue.name,
                            foursquare_reviews=venue.foursquare_reviews,
                            foursquare_rating=venue.foursquare_reviews,
                            foursquare_url=venue.foursquare_url
                            ))
                
            except Exception as e:
                print "Err ", e
                
        #!!! Returning first two foursquare results per search 
        return jsonify(venues=venues[:1])

class CityListAPI(Resource):

    def get(self):

        #Query string to search for a given city
        q = request.args.get('q', None)

        #!!! add user
        if q:
            where_filter = "where lower(city) like '%" + q.lower() + "%' and city is not null"
        else:
            where_filter = "where city is not null"
        
        sql = "select city, max(id) id from location %s group by city" % (where_filter);
        cities_result_set = db.session.execute(sql)

        cities = []
        for row in cities_result_set:
            city = {}
            city['id'] = row.id
            city['name'] = row.city
            city['tokens'] = row.city.split(" ");
            cities.append(city)

        return jsonify(cities=cities)

class VenueListAPI(Resource):

    @requires_auth
    def get(self):

        initialize_session_vars()

        #Query Venues, apply filters
        venues_result_set = Venue.query.join(Location).join(UserVenue).outerjoin(UserImage).outerjoin(Note) \
                                .filter(UserVenue.user_id == session['page_user_id']) \
                                .order_by(UserVenue.added_dt.desc()) \

        # If city is filtered, find the lat/long of the first item in that city and return all other 
        # locations within zoom miles from it
        if session['city'] != '':
            print "~~~ filtered city:", session['city']
            l = Location.query.filter_by(city = session['city']).first()
            latitude_start = l.latitude
            longitude_start = l.longitude
            zoom = session['zoom']

            sql = "SELECT id, latitude, longitude, SQRT( \
                    POW(69.1 * (latitude - %s), 2) + \
                    POW(69.1 * (%s - longitude) * COS(latitude / 57.3), 2)) AS distance \
                    FROM location \
                    GROUP BY id \
                    HAVING SQRT( \
                    POW(69.1 * (latitude - %s), 2) + \
                    POW(69.1 * (%s - longitude) * COS(latitude / 57.3), 2)) < %s" \
                    % (latitude_start, longitude_start, latitude_start, longitude_start, session['zoom'])

            locations = db.session.execute(sql)
            locationIDs = []
            for location in locations:
                locationIDs.append(location.id)
            venues_result_set = venues_result_set.filter(Location.id.in_(locationIDs))

        if session['country'] != '':
            print "~~~ filtered country:", session['country']
            venues_result_set = venues_result_set.filter(Location.country == session['country'])
        if session['parent_category'] != '':
            print "~~~ parent category:", session['parent_category']
            venues_result_set = venues_result_set.filter(Venue.parent_category == session['parent_category'])
        if session['is_hidden'] != '':
            print "~~~ is_hidden:", session['is_hidden']
            venues_result_set = venues_result_set.filter(UserVenue.is_hidden == False)
        if session['user_rating'] != '':
            print "~~~ user_rating:", session['user_rating']
            venues_result_set = venues_result_set.filter(UserVenue.user_rating == session['user_rating'])
        #print '-'*50
        venues_result_set = venues_result_set.limit(300)

        print "--- Get Venue SQL: \r\n", 
        print str(venues_result_set.statement.compile(dialect=postgresql.dialect()))

        venues =[]
        for row in venues_result_set:

            notes_array = []
            for note_row in row.notes:

                #!!! Add source back to model
                if note_row.source_url.find('tripadvisor') >= 0:
                    note_source = 'tripadvisor'
                elif note_row.source_url.find('yelp') >= 0:
                    note_source = 'yelp'
                elif note_row.source_url.find('foursquare') >= 0:
                    note_source = 'foursquare'
                else:
                    note_source = 'other'

                item = dict(
                    note = note_row.note,
                    id = note_row.id,
                    source = note_source
                    )
                notes_array.append(item)
            images_array = []

            for img_row in row.images: 
               #print "image_large" + str(img_row.id) 
                item = dict(
                    image_url = img_row.image_url,
                    image_large = img_row.image_large.replace('app',''),
                    image_thumb = img_row.image_thumb.replace('app',''),
                    id = img_row.id
                    )
                images_array.append(item)
            #!!! convert rating from string to float
            item = dict(
                 notes=notes_array, 
                 images=images_array, 
                 id=row.id,
                 name=row.name, 
                 parent_category=row.parent_category, 
                 source_url=row.source_url, 
                 latitude=row.location.latitude, 
                 longitude=row.location.longitude,
                 city=row.location.city,
                 state=row.location.state,
                 country=row.location.country,
                 source=row.source,
                 foursquare_reviews=row.foursquare_reviews,
                 foursquare_rating=str_to_float(row.foursquare_rating), 
                 foursquare_url=row.foursquare_url,
                 tripadvisor_reviews=row.tripadvisor_reviews,
                 tripadvisor_rating=str_to_float(row.tripadvisor_rating),
                 tripadvisor_url=row.tripadvisor_url,
                 yelp_reviews=row.yelp_reviews,
                 yelp_rating=str_to_float(row.yelp_rating),
                 yelp_url=row.yelp_url,
                 is_starred=row.user_venue.is_starred,
                 user_rating=row.user_venue.user_rating,
                 added_dt=row.added_dt
            )

            venues.append(item) 
                 

        #Google Maps Requires the response to have a particular format
        #!!! fix this
        if request.method == 'GET':
            format = request.args.get("format")
            if format == 'js':
                markers = dict({'markers':venues})
                return make_response("gmapfeed(" + dumps(markers) + ");")



        return jsonify(venues=venues)

class PageListAPI(Resource):
    def get(self):
        initialize_session_vars()

        #Query Venues, apply filters
        #!!! Move to model
        page_notes_result_set = Page.query.join(Location).join(UserPage).outerjoin(UserImage).outerjoin(PageNote) \
                                .filter(PageNote.user_id == session['page_user_id']) \
                                .order_by(UserPage.is_starred.desc(),Page.id.asc())

        # If city is filtered, find the lat/long of the first item in that city and return all other 
        # locations within zoom miles from it
        if session['city'] != '':
            print "current city: ", session['city']
            l = Location.query.filter_by(city = session['city']).first()
            latitude_start = l.latitude
            longitude_start = l.longitude
            zoom = session['zoom']

            sql = "SELECT id, SQRT( \
                    POW(69.1 * (latitude - %s), 2) + \
                    POW(69.1 * (%s - longitude) * COS(latitude / 57.3), 2)) AS distance \
                    FROM location \
                    GROUP BY id \
                    HAVING SQRT( \
                    POW(69.1 * (latitude - %s), 2) + \
                    POW(69.1 * (%s - longitude) * COS(latitude / 57.3), 2)) < %s" \
                    % (latitude_start, longitude_start, latitude_start, longitude_start, session['zoom'])

            locations = db.session.execute(sql)
            locationIDs = []
            for location in locations:
                locationIDs.append(location.id)
            print "--- Filtered city: ", session['city']
            print "--- Filtering locations to: ", locationIDs
            page_notes_result_set = page_notes_result_set.filter( (Location.id.in_(locationIDs)) | (Location.city == session['city']))


        if session['country'] != '':
            print "~~~ filtered country:", session['country']
            page_notes_result_set = page_notes_result_set.filter(Location.country == session['country'])
        if session['is_hidden'] != '':
            print "~~~ is_hidden:", session['is_hidden']
            page_notes_result_set = page_notes_result_set.filter(UserPage.is_hidden == False)
        #print '='*50
        #print page_notes_result_set;

        pages =[]
        for row in page_notes_result_set:
            notes_array = []
            for note_row in row.notes:
                item = dict(
                    note = note_row.note,
                    id = note_row.id
                    )
                notes_array.append(item)
            images_array = []
            for img_row in row.images:
                item = dict(
                    image_url = img_row.image_url,
                    image_large = img_row.image_large.replace('app',''),
                    image_thumb = img_row.image_thumb.replace('app',''),
                    id = img_row.id
                    )
                images_array.append(item)
            #!!! convert rating from string to float
            item = dict(
                 notes=notes_array, 
                 images=images_array, 
                 id=row.id,
                 source_url=row.source_url, 
                 source_title=row.source_title, 
                 latitude=row.location.latitude, 
                 longitude=row.location.longitude,
                 city=row.location.city,
                 country=row.location.country,
                 source=row.source,
                 is_starred=row.user_page.is_starred,
                 user_rating=row.user_page.user_rating

            )
            pages.append(item) 

            #print item['source_title']

        return jsonify(pages=pages)

class EmailInviteAPI(Resource):

    def post(self):

        #Get Parameters
        try:
            email = request.form.get('email','')
        except Exception as e:
            print "Could not get parameters: ", e.message
            email = ''

        #Write to Database
        if email:
            try:
                e = EmailInvite(email);
                e.insert()
                print "Inserted ", email
            except Exception as e:
                print "Err ", e

        return '', 204

# --------------------------------------------- Legacy Add Note Endpoint

class NewNoteAPI(Resource):

    #@requires_auth
    #@app.route('/addnote', methods=['POST', 'GET'])
    #def add_note():
    @requires_auth
    def post(self):

        """ 
        When an end user highlights a selection and saves to itlyst when not on a review page from tripadvisor, foursquare, or yelp,
        this part of the code is executed. Next step will be to save the highlight to the following:
        - page_note
        - user_page (if the page has not been saved by this user)
        - page      (if the page has not been saved before by any user)
        - location  (if the page has not been saved before by any user, we'll try to find the city or country that the page refers to)
        """
        session['user_id'] = 2;
        print "--- USER AUTHENTICATION: Set user id to 2 "

        print '=' * 80

        response_json = jsonurl.parse_query(request.data)


        action = response_json.get('action', None)
        print "action: ", action

        
        
        """
        print "Action: ", response_json.get('action')
        print "Action: ", request.args.get('action')

        print json.dumps(response_json)
        print json.dumps(request.args)
        print request.args
        print response_json
        """

        
        if action == 'new_page_note_from_home':

            pn = PageNote(
                urllib.unquote(response_json.get.get('note', None)), 
                session['user_id'], 
            )
            pn.source = 'nomnotes'
            pn.page_id = response_json.get.get('page_id', None)
            pn.insert()

            return jsonify(note_id = pn.id, page_id = pn.page_id, note = pn.note)


        elif action == 'new_venue_note_from_home':

            n = Note(
                session['user_id'], 
                urllib.unquote(response_json.get.get('note', None)), 
                'http://nomnotes'
            )
            n.source = 'nomnotes'
            n.venue_id = response_json.get.get('venue_id', None)
            n.insert()

            return jsonify(note_id = n.id, venue_id = n.venue_id, note = n.note)


        elif action == 'new_venue_note_from_venue':

            # Parameters from post request
            # ---------------------------------------------------------
            print "--- Processing parameters from the addnote/ post request for venue:"

            user_id = session['user_id']
            source_url = response_json.get('page_url', None)
            source_id = response_json.get('source_id', None)
            source = response_json.get('source', None)

            v = Venue(
                response_json.get('name', None), 
                source,
                source_url,
                response_json.get('page_title', None),
            )

            l = Location(
                'venue', 
                response_json.get('city', None),
                response_json.get('latitude', None),     
                response_json.get('longitude', None)
            )



            n = None
            ui = None
            if response_json.get('image_url'):
                ui = UserImage(
                    response_json.get('image_url'),
                    session['user_id']
                )
                #Set original image to other image locations until s3 resizes
                ui.image_original = ui.image_url
                ui.image_large = ui.image_url
                ui.image_thumb = ui.image_url
                print "--- Initialized user image object with url: ", ui.image_url

            if response_json.get('note'):
                n = Note(
                    user_id, 
                    response_json.get('note', ''), 
                    source_url
                )
                print "--- Initialized note object with note: ", n.note


            #print "categories: "
            #print response_json['categories']

            #print "before requst.form"
            #categoriesStr = response_json['categories']
            try:
                categoriesStr = response_json.get('categories')
                categories = categoriesStr.split(",")
                v.parent_category = classify_parent_category(categories, v.name.split())
            except Exception as e:
                print "Could not get categories: ", e.message, e.args
                categories = []

            
            l.address1 = None #!!!
            l.address2 = None #!!!

            # Save data depending on the review source
            # ---------------------------------------------------------
            print "--- Determining source of the note and calling respective apis to supplement data. Source: ", source

            if source == 'foursquare':

                #Venue Attributes
                if response_json.get('rating', None):
                    v.foursquare_rating = response_json.get('rating', None)
                if response_json.get('reviews', None):
                    v.foursquare_reviews = response_json.get('reviews', None)
                v.foursquare_url = source_url
                v.foursquare_id = source_id

                #Location Attributes, acquired from foursquare venue api
                #fsv = FoursquareVenue()
                #fsv.get(v.foursquare_id, l.latitude, l.longitude)
                #l.city = fsv.city               #Use city, state, and country from the api rather than from the forms for consistency
                #l.state = fsv.state
                #l.country = fsv.country

            elif source == 'tripadvisor' or source == 'yelp':

                #Set source specific properties:
                if response_json.get('rating'):
                    setattr(v, source + "_rating", response_json.get('rating', None))
                else:
                    print "No readable rating. Not inserting rating"
                if response_json.get('reviews'):
                    setattr(v, source + "_reviews", response_json.get('reviews', None))
                else:
                    print "No readable reviews. Not inserting reviews"
                setattr(v, source + "_url", source_url)
                setattr(v, source + "_id", source_id)

                #Call the Foursquare API and find the venue in the provided city
                #Use that data to supplement venue data
                fsvs = FoursquareVenues(v.name, l.city, l.latitude, l.longitude)
                fsvs.search()

                # Find a matching venue from a set of venues returned from foursquare
                # Choose the one that has the closest matching name
                fsv = None
                for fsvenue in fsvs.venues:
                    fuzzy_match_score = fuzz.token_sort_ratio(v.name, fsvenue.name)
                    print "Venue Match Ratio: %s. Source: [%s] Foursquare: [%s]" % (fuzzy_match_score, v.name, fsvenue.name)

                    if fuzzy_match_score > 80:
                        fsv = fsvenue
                        break
                
                if fsv:
                    v.name = fsv.name
                    v.foursquare_id = fsv.foursquare_id
                    v.foursquare_url = fsv.foursquare_url

                    #Call FS Venue API to Get FS Ratings/Reviews, since ratings/reviews aren't available in search
                    fsven = FoursquareVenue()
                    fsven.get(v.foursquare_id, l.latitude, l.longitude)
                    v.foursquare_rating = fsven.rating
                    v.foursquare_reviews = fsven.reviews

                    #If no category derived from source, use foursquare categories and venue categories:
                    if len(categories) == 0:
                        print "--- Using Foursquare venue api category: ", fsv.categories
                        categories = fsv.categories
                        v.parent_category = classify_parent_category(categories, v.name.split())
                    #if fsv.city:
                    #    l.city = fsv.city
                    #l.state = fsv.state
                    #l.country = fsv.country

                    # yelp pages dont show lat/long, override with foursquare api
                    if not l.latitude:
                        l.latitude = fsv.latitude       
                    if not l.longitude:
                        l.longitude = fsv.longitude

                else:
                    print "No matching foursquare venue could be found via the api."
                    
            else: 
                print "--- Source is not yelp, tripadvisor, of foursquare... "
                #Next sources to add: Google Maps and Facebook


            #Call the Google API to derive consistent city | state | country from lat long for all sources
            l.set_city_state_country_with_lat_lng_from_google_location_api()


            # Insert note and other dimensions
            # ---------------------------------------------------------
            print "--- Inserting note as well as venue and location, if applicable"

            # Search If the venue exists, just add the note


            searched_venue_in_db = Venue.get(name=v.name, foursquare_id=v.foursquare_id, tripadvisor_id=v.tripadvisor_id, yelp_id=v.yelp_id)
            if searched_venue_in_db:
                #Insert User Venue Map
                #Does a mapping already existing between existing venue and user? If not, insert it
                uv = UserVenue(user_id, searched_venue_in_db.id)
                uv.find()
                if not uv.id:
                    uv.insert()

                #Insert Note or Image:
                if n and ui:
                    print "About to insert both an image and note"

                    # !!! this is duplicative.... should create functions instead of just blindly copying and pasting
                    print "--- Checking to see if identical venue note exists in database. If not, insert it"
                    n.venue_id = uv.venue_id
                    n.find()
                    if not n.id:
                        n.insert()

                    print "--- Checking to see if user image exists. If not, insert it"
                    ui.venue_id = uv.venue_id
                    ui.find()
                    if not ui.id:
                        ui.insert()

                    response = jsonify(user_image_id = ui.id, note_id = n.id, venue_id = uv.venue_id, image_original = ui.image_original, note = n.note,  msg = "Inserted image and note" )
                elif n:
                    print "--- Checking to see if identical venue note exists in database. If not, insert it"
                    n.venue_id = uv.venue_id
                    n.find()
                    if not n.id:
                        n.insert()
                    response = jsonify(note_id = n.id, venue_id = uv.venue_id, note = n.note, msg = "Inserted note: %s" % n.note )
                elif ui:
                    print "--- Checking to see if user image exists. If not, insert it"
                    ui.venue_id = uv.venue_id
                    ui.find()
                    if not ui.id:
                        ui.insert()
                    response = jsonify(user_image_id = ui.id, venue_id = uv.venue_id, image_original = ui.image_original, msg = "Inserted image: %s" % ui.image_url )
                else:
                    print "No note or image. Returning data..."
                    response = jsonify(venue_id = uv.venue_id, msg = "...")
                return response

            # If no venue exists, add the location, then venue, then venue categories, then note
            else:
                #Add location
                l.insert()

                #Add venue
                v.location_id = l.id
                v.insert()

                #Insert User Venue Map
                uv = UserVenue(user_id, v.id)
                uv.insert()
                
                #Insert the categories for the venue
                for category in categories:
                    vc = VenueCategory(v.id, category)
                    vc.insert

                #Insert Note or Image:
                #!!! Identical to above...
                if n and ui:
                    print "About to insert both an image and note"
                    n.venue_id = uv.venue_id
                    n.find()
                    if not n.id:
                        n.insert()

                    ui.venue_id = uv.venue_id
                    ui.find()
                    if not ui.id:
                        ui.insert()
                    response = jsonify(user_image_id = ui.id, venue_id = uv.venue_id, image_url = ui.image_url, note = n.note, msg = "Inserted image and note")

                elif n:
                    print "--- Checking to see if identical page note exists in database. If not, insert it"
                    n.venue_id = uv.venue_id
                    n.find()
                    if not n.id:
                        n.insert()
                    response = jsonify(note_id = n.id, venue_id = uv.venue_id, note = n.note, msg = "Inserted note: %s" % n.note )

                elif ui:
                    print "--- Checking to see if user image exists. If not, insert it"
                    ui.venue_id = uv.venue_id
                    ui.find()
                    if not ui.id:
                        ui.insert()
                    response = jsonify(user_image_id = ui.id, venue_id = uv.venue_id, image_url = ui.image_url, msg = "Inserted image: %s" % ui.image_url )
                else:
                    response = jsonify(venue_id = uv.venue_id, msg = "...")
                return response


        elif request.method == 'POST' and (action == 'new_page_note_from_other_page'):

            print "--- Processing parameters from the addnote/ post request for other pages:"

            # Determine whether end user selected an image or a highlihted a note:
            pn = None
            ui = None
            if response_json.get('image_url'):
                ui = UserImage(
                    response_json.get('image_url'),
                    session['user_id']
                )
                #Set original image to other image locations until s3 resizes
                ui.image_original = ui.image_url
                ui.image_large = ui.image_url
                ui.image_thumb = ui.image_url

            elif response_json.get('note'):
                pn = PageNote(
                    urllib.unquote(response_json.get('note', '')), 
                    session['user_id']
                )
                
            p = Page(
                response_json.get('source', None),
                response_json.get('page_url', None),
                response_json.get('page_title', None)
            )

            print "--- Checking to see if page exists. If not, insert it"
            p.find()
            if not p.id:
                print "--- Attempting to derive location of the page from the title."

                #Attempt to detect the location without user input by tokenizing the page title and matching it against existing cities:
                print "--- Page title: ", p.source_title
                title_tokens = p.source_title.split(" ");

                cities = db.session.execute("select distinct city, country from location where city is not null and country is not null")

                location_note_city = None
                location_note_country = None
                found_city = False
                for row in cities:
                    for token in title_tokens:
                        match_score = fuzz.token_sort_ratio(token.lower(), row['city'].lower())
                        if(match_score >= 90):
                            location_note_city = row['city']
                            location_note_country = row['country']
                            print "Found city in title: %s, %s" % (location_note_city, location_note_country)
                            found_city = True
                            break
                    if found_city:
                        break


                #Find google location based on the city/country. Then insert it
                if location_note_city and location_note_country:
                    l = Location(
                        'page', 
                        location_note_city, 
                        None, 
                        None
                    )
                    l.country = location_note_country
                    l.set_lat_lng_state_from_city_country()

                    print "--- Inserting location "
                    l.insert()

                    if l.id:
                        p.location_id = l.id
                        "--- Associating new location to page"

                print "--- Inserting page: "
                p.insert()

            if pn:
                print "--- Checking to see if identical page note exists in database. If not, insert it"
                pn.page_id = p.id
                pn.find()
                if not pn.id:
                    pn.insert()

                print "--- Checking if user_page mapping exists in database. If not, insert it"
                up = UserPage(session['user_id'], pn.page_id)
                up.find()
                if not up.id:
                    up.insert()
                response = jsonify(page_note_id = pn.id, page_id = p.id, note = pn.note, msg = "Inserted note: %s" % pn.note )

            elif ui:
                print "--- Checking to see if user image exists. If not, insert it"
                ui.page_id = p.id
                ui.find()
                if not ui.id:
                    ui.insert()
                    #ui.save_locally()
                response = jsonify(user_image_id = ui.id, page_id = p.id, image_url = ui.image_url, msg = "Inserted image: %s" % ui.image_url )

                """
                image_url =  response_json.get('image_url', None)
                image_name = 'abc.jpg' 
                path = 'img/'
                full_path = os.path.join(path, image_name)       

                f = open(full_path,'wb')
                f.write(urllib.urlopen(image_url).read())
                f.close()
                print "Saved image"
                """
            
            return response


        #!!! return json instead
        return "No Note Added =("

def classify_parent_category(category_list, name_tokens):

    print "--- Classifying venue.parent_category. Using existing categories (%s) and venue name %s" % (category_list, name_tokens)
    places = ['theater', 'park', 'museum', 'garden', 'club', 'plaza', 'beach', \
              'palace', 'cove','bay','cave', 'lookout', 'boat', 'fortress']
    coffees = ['coffee', 'caf']
    foods = ['breakfast', 'italian', 'restaurant', 'mediterranean', 'european', 'seafood' \
             'bakery', 'bakeries', 'pizza', 'ice cream', 'bar', 'pub', 'cocktail' \
             'donut', 'food', 'ice cream', 'dessert', 'sandwich','souvlaki']

    parent_category = None

    #Try to classify the category based on the categories scraped from the page
    for category in category_list:
        for food in foods:
            if category.lower().find(food) >= 0:
                return 'food'
        for place in places:
            if category.lower().find(place) >= 0:
                return 'place'
        for coffee in coffees:
            if category.lower().find(coffee) >= 0:
                return 'coffee'

    #If unsuccessful, try to classify the category based on the venue name, examining each token for a match
    for token in name_tokens:
        for food in foods:
            if token.lower().find(food) >= 0:
                return 'food'
        for place in places:
            if token.lower().find(place) >= 0:
                return 'place'
        for coffee in coffees:
            if token.lower().find(coffee) >= 0:
                return 'coffee'

    return 'unknown'

def initialize_session_vars():

    #Necessary?
    app.secret_key = app.config['APP_SECRET_KEY']

    #!!! hardcoded for simplier api access
    session['user_id'] = 2;
    session['username'] = 'almostvindiesel';


    if request.args.get('zoom'):
        session['zoom'] = request.args.get('zoom')
        print "--- Changed zoom to: ", request.args.get('zoom')
    if not ('zoom' in session):
        session['zoom'] = 5
    session['zoom_options'] = ['1', '3', '5','10','25','50']


    session['user_rating_options'] = [0, 1, 2, 3, 4]
    session['user_rating_display'] = ["fa fa-circle-o", "fa fa-thumb-tack", "fa fa-meh-o",  "fa fa-frown-o",  "fa fa-smile-o"]
    if request.args.get('user_rating'):
        if request.args.get('user_rating') == session['user_rating']:
            session['user_rating'] = ''
        else:
            session['user_rating'] = request.args.get('user_rating')
            print "--- Changed user_rating filter to: ", session['user_rating']
    if  not ('user_rating' in session) or session['user_rating'] == 'reset' or session['user_rating'] == '':
        session['user_rating'] = ''


    """
    The following statements process the location and category filters.
    For a given filter, first set the session variable based on the form.
    If the form says reset, set the session variable to empty set.
    Then create a where statement
    """


    #!!! Controls whether a user can edit a page based on whether they are logged inner
    #!!! This is probably not the right way to do this...
    if 'user_id' in session:
        if not 'username' in session:
            u = User.query.filter_by(user_id = session['user_id']).first()
            session['username'] = u.username
            session['can_edit'] = 1
            session['page_user_id'] = session['user_id']
        else: 
            u = User.query.filter_by(username = session['username']).first()
            session['page_user_id'] = session['user_id']
            if u.id == int(session['user_id']):
                session['can_edit'] = 1
            else:
                session['can_edit'] = 0
    else:
        session['can_edit'] = 0
        if 'username' in session:
            u = User.query.filter_by(username = session['username']).first()

            if u.id:
                session['page_user_id'] = u.id
            else:
                #!!! Future iteration: redirect to localhost
                session['page_user_id'] = 'almostvindiesel'

    #if username and the user_id is the same, then 

    #If user

    #print "is hidden get before: ", request.args.get('is_hidden')
    #print "is hidden session before: ", session['is_hidden'] 

    if request.args.get('lystvisibility'):
        if request.args.get('lystvisibility') == 'showhidden':
            session['is_hidden'] = ''
        elif request.args.get('lystvisibility') == 'hidehidden':
            session['is_hidden'] = False
    elif 'is_hidden' not in session:
        session['is_hidden'] = ''
    #print "is hidden session after: ", session['is_hidden'] 

    if request.args.get('parent_category'):
        session['parent_category'] = request.args.get('parent_category')
        print "--- Changed parent_category filter to: ", session['parent_category']
    if  not ('parent_category' in session) or session['parent_category'] == 'reset' or session['parent_category'] == '':
        session['parent_category'] = ''

    if request.args.get('city'):
        session['city'] = request.args.get('city')
        session['country'] = ''
        print "--- Changed city filter to: ", session['city']
    if not 'city' in session or session['city'] == 'reset' or session['city'] == '':
        session['city'] = ''
    
    if request.args.get('country'):
        session['country'] = request.args.get('country')
        session['city'] = ''
    if not 'country' in session or session['country'] == 'reset' or session['country'] == '':
        session['country'] = ''

def str_to_float(str):
    if not str:
        str = 0
        str = float(str)
        str = None;
    else:
        str = float(str.strip())

    return str

# --------------------------------------------- API Endpoints

api.add_resource(NewNoteAPI,        '/addnote')

api.add_resource(EmailInviteAPI,    '/api/v1/emailinvite')
api.add_resource(TextAPI,           '/api/v1/text')
api.add_resource(NoteAPI,           '/api/v1/note/<note_id>', '/api/v1/note')
api.add_resource(ImageAPI,          '/api/v1/image/<image_id>', '/api/v1/image/')
api.add_resource(VenueAPI,          '/api/v1/venue/<venue_id>', '/api/v1/venue/search')
api.add_resource(VenueListAPI,      '/api/v1/venues')
api.add_resource(CityListAPI,       '/api/v1/cities')
api.add_resource(PageListAPI,       '/api/v1/pages')
