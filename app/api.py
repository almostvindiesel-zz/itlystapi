#!/usr/bin/env python
# -*- coding: utf-8 -*-

print "Loading api.py ..."

from app import app
from flask_restful import Resource, Api

import warnings
from flask import request, jsonify
from views import *

api = Api(app)



# --------------------------------------------- API Resources

class CityAPI(Resource):
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

class VenueAPI(Resource):
    def get(self):

        initialize_session_vars()

        #Query Venues, apply filters
        venues_result_set = Venue.query.join(Location).join(UserVenue).outerjoin(UserImage).outerjoin(Note) \
                                .filter(UserVenue.user_id == session['page_user_id']) \
                                .order_by(UserVenue.user_rating.desc()) \


        # If city is filtered, find the lat/long of the first item in that city and return all other 
        # locations within zoom miles from it
        if session['city'] != '':
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

class PageAPI(Resource):
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

# --------------------------------------------- API Endpoints

api.add_resource(CityAPI, '/api/v1/city')
api.add_resource(VenueAPI, '/api/v1/venue')
api.add_resource(PageAPI, '/api/v1/page')

