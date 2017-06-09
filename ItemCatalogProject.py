from flask import Flask, render_template, request, redirect, \
    jsonify, url_for, flash
from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
from database_setup import Base, User, Category, Item
from flask import session as login_session
import random
import string
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests

app = Flask(__name__)
app.secret_key = 'super_secret_key'

CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']

# Connect to the database
engine = create_engine('sqlite:///itemsdatabase.db')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
session = DBSession()


# Anti-forgery token
@app.route('/login')
def show_login():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    return render_template('login.html', STATE=state)


@app.route('/gconnect', methods=['POST'])
def gconnect():
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Get authorization code
    code = request.data
    try:
        # Get credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(json.dumps(
            'Failed to upgrade authorization code'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])

    # Abort if there is an error in access token
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID does not match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_credentials = login_session.get('credentials')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_credentials is not None and gplus_id == stored_gplus_id:
        response = make_response(
            json.dumps('Current user is already connected.'),
            200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']
    # ADD PROVIDER TO LOGIN SESSION
    login_session['provider'] = 'google'

    # see if user exists, if not, make a new one
    user_id = get_user_ID(data["email"])
    if not user_id:
        user_id = create_user(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += '" style = "width: 300px; height: 300px;border-radius: ' \
              '150px;-webkit-border-radius: 150px;-moz-border-radius: ' \
              '150px;"> '
    flash("you are now logged in as %s" % login_session['username'])
    print "done!"
    return output


# User Helper Functions
def create_user(login_session):
    new_user = User(name=login_session['username'], email=login_session[
        'email'], picture=login_session['picture'])
    session.add(new_user)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


def get_user_info(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


def get_user_ID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


# DISCONNECT - Revoke a current user's token and reset their login_session
@app.route('/gdisconnect')
def gdisconnect():
    access_token = login_session['access_token']
    print 'In gdisconnect access token is %s', access_token
    print 'User name is: '
    print login_session['username']
    if access_token is None:
        print 'Access Token is None'
        response = make_response(json.dumps('Current user not connected.'),
                                 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % \
          login_session['access_token']
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    print 'result is '
    print result
    if result['status'] == '200':
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        response = make_response(json.dumps('Successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response
    else:
        response = make_response(
            json.dumps('Failed to revoke token for given user.', 400))
        response.headers['Content-Type'] = 'application/json'
        return response


# Homepage
@app.route('/')
@app.route('/catalog')
def show_categories():
    categories = session.query(Category).order_by(asc(Category.name))
    recent_items = session.query(Item).order_by(Item.id.desc()).limit(8)
    if 'username' not in login_session:
        return render_template('publicCatalog.html', categories=categories,
                               items=recent_items)
    else:
        return render_template('catalog.html', categories=categories,
                               items=recent_items)


# Shows all the item in category
@app.route('/catalog/<int:category_id>/')
def show_category(category_id):
    category = session.query(Category).filter_by(id=category_id).one()
    items = session.query(Item).filter_by(category_id=category_id).all()
    return render_template('items.html', category=category, items=items)


# Shows chosen item
@app.route('/catalog/<int:category_id>/<int:item_id>')
def show_item(category_id, item_id):
    item = session.query(Item).filter_by(category_id=category_id,
                                         id=item_id).one()
    if 'username' not in login_session:
        return render_template('publicItem.html', item=item)
    else:
        return render_template('item.html', item=item, category_id=category_id)


# Create a new item
@app.route('/catalog/new', methods=['GET', 'POST'])
def new_item():
    if 'username' not in login_session:
        return redirect('/login')
    if request.method == 'POST':
        new_item = Item(name=request.form['name'],
                        description=request.form['description'],
                        price=request.form['price'],
                        category_id=request.form['category'],
                        user_id=login_session['user_id'])
        session.add(new_item)
        session.commit()
        return redirect(
            url_for('show_category', category_id=request.form['category']))
    else:
        categories = session.query(Category).all()
        return render_template('newItem.html', categories=categories)


# Edit item
@app.route('/catalog/<int:category_id>/<int:item_id>/edit',
           methods=['GET', 'POST'])
def edit_item(category_id, item_id):
    edited_item = session.query(Item).filter_by(id=item_id).one()
    if 'username' not in login_session:
        return redirect('/login')
    if edited_item.user_id != login_session['user_id']:
        return "<script>function myFunction(){alert('You are not authorized " \
               "to edit this item. Please create your own item " \
               "in order to edit.');}</script><body onload='myFunction()''> "
    if request.method == 'POST':
        if request.form['name']:
            edited_item.name = request.form['name']
        if request.form['description']:
            edited_item.description = request.form['description']
        if request.form['price']:
            edited_item.price = request.form['price']

        session.add(edited_item)
        session.commit()
        return redirect(url_for('show_category', category_id=category_id))
    else:
        return render_template('editItem.html', item=edited_item,
                               category_id=category_id)


@app.route('/catalog/<int:category_id>/<int:item_id>/delete',
           methods=['GET', 'POST'])
def delete_item(category_id, item_id):
    if 'username' not in login_session:
        redirect('/login')
    item_to_delete = session.query(Item).filter_by(id=item_id).one()
    if login_session['user_id'] != item_to_delete.user_id:
        return "<script>function myFunction(){alert('You are not authorized " \
               "to delete  this item. Please create your " \
               "own item in order to delete it.');}</script><body " \
               "onload='myFunction()''> "
    if request.method == 'POST':
        session.delete(item_to_delete)
        session.commit()
        return redirect(url_for('show_category', category_id=category_id))
    else:
        return render_template('deleteItem.html', item=item_to_delete,
                               category_id=category_id)


# JSON APIs

# Prints all categories
@app.route('/catalog/json')
def categories_JSON():
    categories = session.query(Category).all()
    return jsonify(categories=[r.serialize for r in categories])


# Prints all the items in given category
@app.route('/catalog/<int:category_id>/json')
def category_JSON(category_id):
    items_in_category = session.query(Item).filter_by(
        category_id=category_id).all()
    return jsonify(items_in_category=[r.serialize for r in items_in_category])


# Prints info about chosen item
@app.route('/catalog/<int:category_id>/<int:item_id>/json')
def item_JSON(category_id, item_id):
    item = session.query(Item).filter_by(id=item_id).first()
    return jsonify(item=[item.serialize])


if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
