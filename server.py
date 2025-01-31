from flask import Flask, render_template, redirect, request, flash, session, jsonify
from flask_debugtoolbar import DebugToolbarExtension
from jinja2 import StrictUndefined
from models import connect_to_db, db, Business, Rating, User
import sys
reload(sys)
sys.setdefaultencoding('UTF8')

from yelpapi import YelpAPI
import helper

import os


app = Flask(__name__)

# makes jinja throw error if requesting undefined value
app.jinja_env.undefined = StrictUndefined

# gets secret key from secrets.sh


SECRET_KEY = os.environ['HAVEN_SECRET_KEY']
app.secret_key = SECRET_KEY


# dict of api keys to be passed into every render template for google maps api




# EXAMPLE YELP QUERIES
# search_results = yelp_api.search_query(args)
# business_results = yelp_api.business_query(id=business_id, other_args)
# phone_search_results = yelp_api.phone_search_query(phone=phone_number, other_args)

def hello_world():
    return 'Hello World!'


@app.route('/')
def splash():
    """splash page"""

    # todo add map
    return render_template('splash.html',
                           keys=helper.KEYS,
                           user=session.get("user_name"))


@app.route('/local-best.json')
def best_local():
    # location = request.args.get('location')
    location = session['user_address']
    print type(request.args.get('cutoff'))
    cutoff = float(request.args.get('cutoff'))
    print location
    print 'type:', type(location)
    query = helper.best_local_business(location, cutoff)
    print jsonify(query)
    return jsonify(query)


@app.route('/login', methods=['GET'])
def login_prompt():
    """Login page"""
    return render_template('log-in.html',
                           keys=helper.KEYS,
                           user=session.get("user_name"))


@app.route('/login', methods=['POST'])
def login():
    """logs in user"""
    form_data = request.form
    # todo set up flash in base template
    results = helper.login(form_data)
    flash(results[0])
    session['user_name'] = results[1]
    session['user_id'] = results[2]
    return redirect('/')

@app.route('/logout')
def logout():
    """logs out user"""
    session['user_name'] = None
    session['user_id'] = None
    # todo fix flash
    flash("You are now logged out")
    return redirect('/')


@app.route('/create-account', methods=['GET'])
def acct_creation():
    """account creation page"""
    return render_template("user-add.html",
                           keys=helper.KEYS,
                           user=session.get("user_name"))


@app.route('/create-account', methods=['POST'])
def post_account():
    """creates user account"""
    form_data = request.form

    status = helper.add_user(form_data)

    # flash(status)

    if status == "That username already exists":
        return redirect('login')

    else:
        # todo add flash "your account has been created" & "you have been logged in"
        session['user_name'] = status[1]
        session['user_id'] = status[0]
        return redirect('/')


@app.route('/results')
def results():
    """search results page"""
    term = request.args['term']
    # location = ", ".join([helper.current_loc()['city'], helper.current_loc()['region_code']])
    location = session['user_address']
    offset = 0
    sort = int(request.args['sort'])
    print sort

    cutoff = float(request.args['haven-cutoff'])
    result = helper.build_results(term, location, offset, sort, cutoff)

    return render_template('results.html',
                           term=term,
                           location=location,
                           keys=helper.KEYS,
                           cutoff=cutoff,
                           user=session.get("user_name"),
                           businesses=result[2],
                           offset=result[1],
                           sort=sort)


# todo convert to ajax
@app.route('/business-results')
def yelp_only_results():
    term = request.args['term']
    location = session['user_address']
    # location = ", ".join([helper.current_loc()['city'], helper.current_loc()['region_code']])
    offset = 0
    cutoff = None
    result = helper.build_results(term, location, offset, 0, cutoff)
    return render_template('results.html',
                           term=term,
                           location=location,
                           keys=helper.KEYS,
                           cutoff=cutoff,
                           user=session.get("user_name"),
                           businesses=result[2],
                           offset=result[1],
                           sort=0)


@app.route('/results.json')
def more_results():
    print request.args
    term = request.args['term']
    offset = int(request.args['offset'])
    sort = int(request.args['sort'])
    if request.args['cutoff'] != 'None':
        cutoff = float(request.args['cutoff'])
    else:
        cutoff = None
    location = session['user_address']
    # location = ", ".join([helper.current_loc()['city'], helper.current_loc()['region_code']])
    result = helper.build_results(term, location, offset, sort, cutoff)
    output = {'term': result[0],
              'offset': result[1],
              'businesses': result[2],       # dictionary of objects not json serializable
              'cutoff': cutoff,
              'sort': sort
              }

    return jsonify(output)


@app.route('/<string:username>')
# fixme
def user_account(username):
    """User account page"""
    return render_template('account.html',
                           keys=helper.KEYS,
                           user=session.get("user_name"))


@app.route('/<string:username>/ratings')
def ratings(username):
    """user ratings"""
    user_id = session['user_id']
    ratings = (helper.get_ratings(user_id))

    return render_template('user-ratings.html',
                           keys=helper.KEYS,
                           user=session.get("user_name"),
                           ratings=ratings)


@app.route('/explore')
def explore():
    """explore page"""
    return render_template('construction.html',
                           keys=helper.KEYS,
                           user=session.get("user_name"))


@app.route('/info/<string:business_id>.json')
def info(business_id):
    print 'route called successfully'
    # if it exists in local db, gets object, if not, returns none.
    haven_bus_data = Business.query.filter_by(yelp_id=business_id).first()
    yelp_bus_data = helper.yelp_by_id(business_id)
    haven_ratings = [None, None]
    categories = [cat[0] for cat in yelp_bus_data['categories']]
    # updates local db with info from yelp if it is in DB
    user_rating = helper.get_user_rating(session['user_id'], business_id)
    if haven_bus_data is not None:
        helper.validate_db(yelp_bus_data, haven_bus_data)

        # gets new validated info
        haven_bus_data = Business.query.filter_by(yelp_id=business_id).first()
        haven_ratings = helper.get_aggregate_rating(haven_bus_data)
        review_info = helper.most_recent_review(haven_bus_data)

        recent_score = review_info[0]

        # condenses review if necessary
        if review_info[1]:
            if len(review_info[1]) > 100:
                recent_review = review_info[1][:100] + " ..."
                print recent_review[1]
            else:
                recent_review = review_info[1]
        else:
            recent_review = review_info[1]
    #  todo add haven review and score
    # if business doesn't exist in db, populates ratings with None

    else:
        haven_ratings = None, None
        recent_review = None
        recent_score = None
    business = {'score': haven_ratings[0],
                'categories': categories,
                'total_ratings': haven_ratings[1],
                'yelp_bus_data': yelp_bus_data,
                'recent_score': recent_score,
                'recent_review': recent_review,
                'user': session.get("user_name")}
    print user_rating
    if user_rating != []:
        business['user_rating'] = {
            'score': user_rating[0].score,
            'created_at': user_rating[0].created_at,
            'rating_id': user_rating[0].rating_id}
        try:
            user_review = user_rating[0].review
        except AttributeError:
            user_review = None

        if user_review is not None:
            business['user_rating']['review'] = user_review

    print "business:", business
    print "business json", jsonify(business)
    return jsonify(business)
    # return render_template('business.html',
    #                        score=haven_ratings[0],
    #                        total_ratings=haven_ratings[1],
    #                        yelp_bus_data=yelp_bus_data,
    #                        recent_score=recent_score,
    #                        recent_review=recent_review,
    #                        keys=helper.KEYS,
    #                        user=session.get("user_name"))




@app.route('/info/<string:business_id>/rate', methods=['GET'])
def rate(business_id):
    """presents user with form to rate business"""
    # converts id from yelp_id to business_id if applicable, then returns appropriate object
    business = helper.yelp_by_id(business_id)
    return render_template('rating-form.html',
                           yelp_id=business_id,
                           business_name=business['name'],
                           user=session.get("user_name"),
                           keys=helper.KEYS)


@app.route('/info/<string:business_id>/rate', methods=['POST'])
def submit_review(business_id):
    """submits review and redirects back to the business page"""
    # determines whether business in url is from yelp API or local only
    print 'submit review being called'
    form_data = request.form
    rating_id = form_data.get('rating_id')
    user_id = session['user_id']
    # flashes success messsage
    print business_id
    flash(helper.add_rating(form_data, business_id, user_id, rating_id))


    # todo add flash "your rating has been submitted"

    return redirect("/")


@app.route('/info/<business_id>/ratings')
def view_haven_ratings(business_id):
    rating_list = helper.get_business_ratings(business_id).reversed
    rating_date_pairs = helper.datetime_converter(rating_list)
    business = Business.query.filter_by(yelp_id=business_id).first()
    rating = helper.get_aggregate_rating(business)
    return render_template('business-ratings.html',
                           ratings=rating_date_pairs,
                           keys=helper.KEYS,
                           business=business,
                           rating=rating,
                           user=session.get("user-name"))


@app.route('/add-ratings')
def business_search_form():
    """Form for searching for yelp businesses to add ratings"""
    return render_template('business-search.html',
                           keys=helper.KEYS,
                           user=session.get("user_name"))


@app.route('/set-address', methods=['POST'])
def update_address():
    session['user_address'] = request.form.get("address")
    return redirect('/')


@app.route('/get-session.json')
def get_session():
    return jsonify(session)


# @app.route('catgeories.json')
# def serve_categorise():
#


#
# @app.route('/<string:username>/manage')
# def account_manage(username):
#     """allows update of user information. Requires new login"""
#     return render_template('construction.html',
#                            keys=helper.KEYS,
#                            user=session.get("user_name"))


# @app.route('/<string:username>/favorites')
# def favorites(username):
#     """user favorites"""
#     return render_template('construction.html',
#                            keys=helper.KEYS,
#                            user=session.get("user_name"))



if __name__ == '__main__':
    # toggles debug mode on
    # app.debug = True

    # runs debug toolbar
    DebugToolbarExtension(app)

    # connects to database
    connect_to_db(app)

    # # runs app
    app.run()
