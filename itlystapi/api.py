#!/usr/bin/env python
# -*- coding: utf-8 -*-
print "Loading " + __file__

from itlystapi import app
from flask_restful import Resource, Api

import warnings
from flask import request, jsonify
from views import *
from models import *
import jsonurl
#from flask_restful import reqparse, abort, Api, Resource

import textblob
from textblob import TextBlob

from flaskext.mysql import MySQL
import mysql

api = Api(app)


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

    def put(self, image_id):
        session['user_id'] = 2;
        print "--- USER AUTHENTICATION: Set user id to 2"

        #Get Parameters

        ui = UserImage.query.filter_by(id = image_id).first()
        server_path = 'app/tmp/';
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
    def delete(self, note_id):
        session['user_id'] = 2;
        print "--- USER AUTHENTICATION: Set user id to 2 "

        sql = 'delete from note where id = %s and user_id= %s ' % (note_id, session['user_id'])
        print "delete note sql: ", sql
        db.session.execute(sql)
        db.session.commit()

        return '', 204

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
    def get(self):

        initialize_session_vars()

        #Query Venues, apply filters
        venues_result_set = Venue.query.join(Location).join(UserVenue).outerjoin(UserImage).outerjoin(Note) \
                                .filter(UserVenue.user_id == session['page_user_id']) \
                                .order_by(UserVenue.user_rating.desc()) \

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
                print "image_large" + str(img_row.id) 
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
                 user_rating=row.user_venue.user_rating
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

# --------------------------------------------- API Endpoints
api.add_resource(EmailInviteAPI,    '/api/v1/emailinvite')
api.add_resource(TextAPI,           '/api/v1/text')
api.add_resource(NoteAPI,           '/api/v1/note/<note_id>', '/api/v1/note')
api.add_resource(ImageAPI,          '/api/v1/image/<image_id>', '/api/v1/image/')
api.add_resource(VenueAPI,          '/api/v1/venue/<venue_id>', '/api/v1/venue/search')
api.add_resource(VenueListAPI,      '/api/v1/venues')
api.add_resource(CityListAPI,       '/api/v1/cities')
api.add_resource(PageListAPI,       '/api/v1/pages')
