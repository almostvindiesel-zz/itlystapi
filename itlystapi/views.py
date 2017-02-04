#!/usr/bin/env python
# -*- coding: utf-8 -*-
print "Loading " + __file__

from itlystapi import app
import warnings
from flask.exthook import ExtDeprecationWarning
warnings.simplefilter('ignore', ExtDeprecationWarning)
#import sqlite3
import urllib
import os
import sys
import random
import requests
import requests.packages.urllib3
import re
import urllib
from fuzzywuzzy import fuzz
from datetime import datetime
import json
from json import dumps, loads
from flask_user import login_required, UserManager, UserMixin, SQLAlchemyAdapter, current_user
from flask_mail import Mail
#from contextlib import closing #from werkzeug.utils import secure_filename #requests.packages.urllib3.disable_warnings()
from sqlalchemy import UniqueConstraint, distinct, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import text
from flask import Flask, request, session, g, redirect, url_for, abort, render_template, render_template_string, flash, jsonify, make_response
from sqlalchemy.dialects import postgresql
from flask_restful import Resource, Api
from werkzeug.datastructures import ImmutableMultiDict

from flaskext.mysql import MySQL
import mysql


from PIL import Image
from resizeimage import resizeimage
import imghdr

from models import db, User, Note, Venue, Location, VenueCategory, FoursquareVenue, FoursquareVenues
from models import UserVenue, UserPage, Page, PageNote, UserImage, EmailInvite, Zdummy

reload(sys)
sys.setdefaultencoding('utf-8')
app.secret_key = app.config['APP_SECRET_KEY']

db_adapter = SQLAlchemyAdapter(db, User)        # Register the User model
user_manager = UserManager(db_adapter, app)     # Initialize Flask-User
mail = Mail(app)  



import boto
import urllib
import tinys3
from boto.s3.key import Key



# ----------------------------------------------------------------------------
# Landing Page



@app.route('/', methods=['GET'])
@app.route('/lp', methods=['GET'])
def show_landing_page():
    return render_template('lp.html')


# ----------------------------------------------------------------------------
# Admin and Database 

@app.route('/admin/', methods=['GET'])
#  @login_required 
def show_admin():

    msg = request.args.get('msg', '')
    print '*' * 50, msg

    table_classes = app.config['TABLE_CLASSES']
    table_names = app.config['TABLE_NAMES']

    return render_template('show_admin.html', table_classes=table_classes, table_names=table_names, msg=msg)

@app.route('/admin/api/v1/createtable/<table>', methods=['GET'])
def create_table(table):

    print '-' * 50
    print "About to create table: ", table

    import models
    klass = getattr(models, table)
    #t = klass()

    try: 
        klass.__table__.create(db.session.bind, checkfirst=True)
        msg = "Created table: %s" % (table)

    except Exception as e:
        print "Exception ", e.message, e.args
        msg = "ERROR. Could NOT create table: %s" % (table)
            
    return redirect(url_for('show_admin', msg = msg ))


@app.route('/admin/api/v1/droptable/<table>', methods=['GET'])
def drop_table(table):

    print '-' * 50
    print "About to drop table: ", table

    import models
    klass = getattr(models, table)
    #t = klass()

    try: 
        klass.__table__.drop(db.session.bind, checkfirst=True)
        msg = "Dropped table: %s" % (table)

    except Exception as e:
        print "Error ", e.message, e.args
        msg = "ERROR. Could NOT drop table: %s" % (table)
        
    return redirect(url_for('show_admin', msg = msg ))


@app.route('/admin/api/v1/truncatetable/<table>', methods=['GET'])
def truncate_table(table):

    print '-' * 50
    print "About to truncate table: ", table

    try: 
        db.session.execute("delete from %s where id >= 1" % (table))
        db.session.commit()
        msg = "Truncated table: %s" % (table)

    except Exception as e:
        print "Error ", e.message, e.args
        msg = "ERROR. Could NOT truncate table: %s" % (table)
        
    return redirect(url_for('show_admin', msg = msg ))


#I think this is only for postgres--not relevant for mysql
@app.route('/admin/api/updatesequencekeys', methods=['GET'])
def update_sequence_keys():

    all_tables = app.config['TABLE_NAMES']

    for table in all_tables:
        print "table: ", table
        sql = "select setval('%s_id_seq', (select max(id) FROM %s)+1)" % (table, table)

        print sql
        db.session.execute(sql)
        db.session.commit()

    msg = "done"

    return redirect(url_for('show_admin', msg = msg ))

@app.route('/admin/migrateimagestos3')
def migrate_images_to_s3():

    starting_id = 226
    images = UserImage.query.filter(id > starting_id).all()
    server_path = 'app/tmp/';
    s3_bucket = 'itlyst'

    for i in images:

        print "\r\nProcessing image: ", i.id
        image_original_name = i.image_original.split('/')[::-1][0] 
        """
        i.image_original = i.image_url
        db.session.add(i)
        db.session.commit()
        """
        
        print "Getting image from: ", i.image_original
        urllib.urlretrieve(i.image_original,  server_path + image_original_name)
        print "Wrote image to disk: ", server_path + image_original_name

        filename, file_extension = os.path.splitext(server_path + image_original_name)
        s3_name = str(i.id) +  file_extension

        print "Uploading to s3..."
        conn = tinys3.Connection(app.config['S3_ACCESS_KEY'], app.config['S3_SECRET_KEY'],tls=True,endpoint='s3-us-west-1.amazonaws.com')
        f = open(server_path + image_original_name,'rb')
        conn.upload(s3_name,f,s3_bucket)

        i.image_url  = 'https://s3-us-west-1.amazonaws.com/%s/%s' % (s3_bucket, s3_name)
        db.session.add(i)
        db.session.commit()

        print "Finished uploading to s3, url: ", s3_name

    return 'done'

@app.route('/admin/creates3imagethumbs')
def create_s3_image_thumbnails():

    starting_id = 0
    images = UserImage.query.filter(id > starting_id)
    server_path = 'app/tmp/';
    s3_bucket = 'itlyst'

    thumbnail_width = 200
    large_width = 1024

    for i in images:

        print "\r\nProcessing image: ", i.id

        s3_image_name = i.image_url.split('/')[::-1][0] 

        print "  Getting image from s3: ", i.image_url, s3_image_name
        urllib.urlretrieve(i.image_url,  server_path + s3_image_name)
        print "  Wrote image to disk: ", server_path + s3_image_name

        filename, file_extension = os.path.splitext(s3_image_name)
        s3_image_large = filename + '_large' + file_extension
        s3_image_thumb = filename + '_thumb' + file_extension
        print "  s3_image_large: ", s3_image_large
        print "  s3_image_thumb: ", s3_image_thumb

        print "  Resizing large image... "
        resized_image = resize_image(server_path, s3_image_name, s3_image_large, large_width)
        upload_to_s3(server_path, resized_image, s3_image_large, s3_bucket)
        i.image_large = 'https://s3-us-west-1.amazonaws.com/%s/%s' % (s3_bucket, s3_image_large)

        print "  Resizing thumb image..."
        resized_image = resize_image(server_path, s3_image_name, s3_image_thumb, thumbnail_width)
        upload_to_s3(server_path, resized_image, s3_image_thumb, s3_bucket)
        i.image_thumb = 'https://s3-us-west-1.amazonaws.com/%s/%s' % (s3_bucket, s3_image_thumb)

        db.session.add(i)
        db.session.commit()
        print "  Commited new sizes to database"

    return 'done'


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


       



    """
    image_tmp_dir = 'img/'
    print "Getting image and saving to directory (%s) from url: \r\n %s" % (image_tmp_dir + image_tmp_name, image_url)
    image_tmp_full_path = os.path.join(image_tmp_dir, image_tmp_name) 

    try:   


        i.image_type = imghdr.what(image_tmp_full_path)
        print "Detected image type: %s" % (i.image_type)

        image_id = '5'
        image_dir = image_tmp_dir
        image_original_path = os.path.join(image_dir, image_id + '.' + i.image_type) 
        image_large_path = os.path.join(image_dir, image_id + '_large.' + i.image_type) 
        image_thumb_path = os.path.join(image_dir, image_id + '_thumb.' + i.image_type) 

        print "Resizing image..."
        thumbnail_width = 200
        large_width = 1024

        fd_img = open(image_tmp_full_path, 'r')

        

        try:   
            print "Resizing image to width %s" % thumbnail_width
            img = Image.open(fd_img)
            img = resizeimage.resize_width(img, thumbnail_width)
            img.save(image_thumb_path, img.format)
            print "Saved thumb img: %s " % (image_thumb_path)
        except Exception as e:
            print "Could resize image since it would require enlarging it. Referencing original path\r\n", e.message, e.args
            image_thumb_path = image_original_path
            print "Saved thumb img: %s " % (image_thumb_path)

    except Exception as e:
        print "Could not save tmp image ", e.message, e.args
        print "Exception ", e.message, e.args

    return 'a'
    """

#!!! Need to validate if this still works...
@app.route('/admin/updatevenuecategories', methods=['GET'])
def update_venue_categories():
    initialize_session_vars()

    sql = "update venue \
    set parent_category = 'place' \
    where parent_category = 'unknown' \
      and tripadvisor_url like '%sAttraction_Review%s'" % ('%','%')
    db.session.execute(sql)
    db.session.commit()

    sql = "update venue \
    set parent_category = 'food' \
    where parent_category = 'unknown' \
      and tripadvisor_url like '%sRestaurant_Review%s'" % ('%','%')
    db.session.execute(sql)
    db.session.commit()

    sql = "update venue \
    set parent_category = 'food' \
    where parent_category = 'coffee'"
    db.session.execute(sql)
    db.session.commit()

    #Get all locations
    venues = Venue.query

    return redirect(url_for('show_notes', username=session['username']))


# ----------------------------------------------------------------------------
# Page Note

@app.route('/ratepage/id/<int:page_id>/<int:user_rating>', methods=['GET'])
@login_required 
def rate_page(page_id, user_rating):
    initialize_session_vars()

    sql = 'update user_page set user_rating = %s where page_id=%s and user_id=%s' % (user_rating, page_id, session['user_id'])
    db.session.execute(sql)
    db.session.commit()

    return redirect(url_for('show_notes', username=session['username']))

@app.route('/deletepagenote/id/<int:id>', methods=['GET'])
@login_required 
def delete_page_note(id):
    sql = 'delete from page_note where id = %s' % (id)
    db.session.execute(sql)
    db.session.commit()

    initialize_session_vars()
    return redirect(url_for('show_notes', username=session['username']))

@app.route('/editpagenote', methods=['POST'])
@login_required 
def edit_page_note():
    if request.method == 'POST':
        #note = urllib.unquote_plus(request.form.get('note'))
        note = request.form.get('note')
        note_id = request.form.get('note_id')
        page_id = request.form.get('page_id')
        #print note

        sql = text('update page_note set note = :note where id = :note_id')
        sql = sql.bindparams(note=note, note_id=note_id)
        db.session.execute(sql)
        db.session.commit()

        return jsonify(note_id = note_id, page_id = page_id, note = note)
    else:
        return jsonify(note_id = '', page_id = '', note = '')

#This function is used to update a location on a page note 
@app.route('/updatepagelocation', methods=['POST'])
@login_required 
def update_page_location():

    initialize_session_vars()

    location_id = request.form.get('location_id', None)
    page_id = request.form.get('page_id', None)
    print "--- Updating Page Location for page_id %s and location_id %s" % (page_id, location_id)

    #Find Existing Location and Attributes using city and country
    searched_location = Location.query.filter_by(id = location_id).first()
    print "--- Found city: %s" % (searched_location.city)

    new_location = Location ('page', searched_location.city, None, None)
    new_location.country  = searched_location.country

    #Now set the lat long and insert the location
    new_location.set_lat_lng_state_from_city_country()
    new_location.insert()

    #Associate the new location with the page_note
    sql = 'update page set location_id = %s where id = %s' % (new_location.id, page_id)




    db.session.execute(sql)
    db.session.commit()

    return redirect(url_for('show_notes', username=session['username']))

# ----------------------------------------------------------------------------
# Image

@app.route('/deleteimage/id/<int:id>', methods=['GET'])
@login_required 
def delete_image(id):
    sql = 'delete from user_image where id = %s' % (id)
    db.session.execute(sql)
    db.session.commit()

    initialize_session_vars()
    return redirect(url_for('show_notes', username=session['username']))

# ----------------------------------------------------------------------------
# Page

@app.route('/deletepage/id/<int:id>', methods=['GET'])
@login_required 
def delete_page(id):

    sql = 'delete from page_note where page_id = %s' % (id)
    db.session.execute(sql)
    db.session.commit()

    sql = 'delete from user_page where page_id = %s and user_id= %s ' % (id, session['user_id'])
    db.session.execute(sql)
    db.session.commit()

    initialize_session_vars()
    return redirect(url_for('show_notes', username=session['username']))

@app.route('/unstarpage/id/<int:id>', methods=['GET'])
@login_required  
def unstar_page(id):
    initialize_session_vars()

    sql = 'update user_page set is_starred = False where page_id = %s and user_id=%s' % (id, session['user_id'])
    db.session.execute(sql)
    db.session.commit()
    return redirect(url_for('show_notes', username=session['username']))

@app.route('/starpage/id/<int:id>', methods=['GET'])
@login_required 
def star_page(id):
    initialize_session_vars()

    sql = 'update user_page set is_starred = True where page_id = %s and user_id=%s' % (id, session['user_id'])
    db.session.execute(sql)
    db.session.commit()
    return redirect(url_for('show_notes', username=session['username']))

@app.route('/hidepage/id/<int:id>', methods=['GET'])
@login_required 
def hide_page(id):
    initialize_session_vars()

    sql = 'update user_page set is_hidden = True where page_id = %s and user_id=%s' % (id, session['user_id'])
    db.session.execute(sql)
    db.session.commit()
    return redirect(url_for('show_notes', username=session['username']))

#!!! showvenue working?
@app.route('/showpage/id/<int:id>', methods=['GET'])
@login_required 
def show_page(id):
    initialize_session_vars()

    sql = 'update user_page set is_hidden = False where page_id = %s and user_id=%s' % (id, session['user_id'])
    db.session.execute(sql)
    db.session.commit()
    
    return redirect(url_for('show_notes', username=session['username']))

# ----------------------------------------------------------------------------
# Venue

@app.route('/deletevenue/id/<int:id>', methods=['GET'])
@login_required 
def delete_venue(id):

    sql = 'delete from note where venue_id = %s' % (id)
    db.session.execute(sql)
    db.session.commit()

    sql = 'delete from user_venue where venue_id = %s and user_id= %s ' % (id, session['user_id'])
    db.session.execute(sql)
    db.session.commit()

    initialize_session_vars()
    return redirect(url_for('show_notes', username=session['username']))

@app.route('/ratevenue/id/<int:venue_id>/<int:user_rating>', methods=['GET'])
@login_required 
def rate_venue(venue_id, user_rating):
    initialize_session_vars()

    sql = 'update user_venue set user_rating = %s where venue_id=%s and user_id=%s' % (user_rating, venue_id, session['user_id'])
    db.session.execute(sql)
    db.session.commit()

    return redirect(url_for('show_notes', username=session['username']))

@app.route('/unstarvenue/id/<int:id>', methods=['GET'])
@login_required 
def unstar_venue(id):
    initialize_session_vars()

    sql = 'update user_venue set is_starred = false where venue_id = %s and user_id=%s' % (id, session['user_id'])
    db.session.execute(sql)
    db.session.commit()
    return redirect(url_for('show_notes', username=session['username']))

@app.route('/starvenue/id/<int:id>', methods=['GET'])
@login_required 
def star_venue(id):
    initialize_session_vars()

    sql = 'update user_venue set is_starred = true where venue_id = %s and user_id=%s' % (id, session['user_id'])
    db.session.execute(sql)
    db.session.commit()
    return redirect(url_for('show_notes', username=session['username']))

@app.route('/hidevenue/id/<int:id>', methods=['GET'])
@login_required 
def hide_venue(id):
    initialize_session_vars()

    sql = 'update user_venue set is_hidden = True where venue_id = %s and user_id=%s' % (id, session['user_id'])
    db.session.execute(sql)
    db.session.commit()
    return redirect(url_for('show_notes', username=session['username']))

#!!! showvenue working?
@app.route('/showvenue/id/<int:id>', methods=['GET'])
@login_required 
def show_venues(id):
    initialize_session_vars()

    sql = 'update user_venue set is_hidden = False where venue_id = %s and user_id=%s' % (id, session['user_id'])
    db.session.execute(sql)
    db.session.commit()
    
    return redirect(url_for('show_notes', username=session['username']))




@app.teardown_appcontext
def shutdown_session(exception=None):
    db.session.remove()



