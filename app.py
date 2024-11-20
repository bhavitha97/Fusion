from flask import Flask, redirect, jsonify, request, render_template, url_for, session
from math import radians, sin, cos, sqrt, atan2
from datetime import datetime
import time
import os
import googlemaps
from google.cloud import vision
from google.oauth2 import service_account
from dotenv import load_dotenv
from flask_session import Session
from authlib.integrations.flask_client import OAuth
import secrets
from functools import wraps
import requests
from flask_cors import CORS

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'path_to_your_google_api_key'

app = Flask(__name__)
CORS(app)

load_dotenv()

credentials = service_account.Credentials.from_service_account_file('path_to_your_google_api_key')
vision_client = vision.ImageAnnotatorClient(credentials=credentials)

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False

Session(app)

wishlist_items = []

oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    access_token_url='https://oauth2.googleapis.com/token',
    userinfo_endpoint='https://openidconnect.googleapis.com/v1/userinfo',
    client_kwargs={
        'scope': 'openid email profile',
        'token_endpoint_auth_method': 'client_secret_post'
    }
)

GEMINI_API_KEY = os.getenv('your_gemini_api_key')
GOOGLE_MAPS_API_KEY = os.getenv('your_maps_api_key')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login')
def login():
    if 'user' in session:
        return redirect(url_for('fusion'))
    return render_template('login.html')
    
    nonce = secrets.token_urlsafe(16)
    session['nonce'] = nonce
    session['state'] = secrets.token_urlsafe(16)  
    

    redirect_uri = url_for('authorize', _external=True)
    return google.authorize_redirect(redirect_uri, nonce=nonce, state=session['state'])

@app.route('/authorize')
def authorize():
    try:
        nonce = secrets.token_urlsafe(16)
        session['nonce'] = nonce
        session['state'] = secrets.token_urlsafe(16)
        redirect_uri = url_for('authorize_callback', _external=True)
        return google.authorize_redirect(redirect_uri, nonce=nonce, state=session['state'])
    except Exception as e:
        print(f"Exception during authorization: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/authorize_callback')
def authorize_callback():
    try:
        token = google.authorize_access_token()
        nonce = session.pop('nonce', None)
        if nonce is None:
            return jsonify({'error': 'Nonce not found in session'}), 400
        user_info = google.parse_id_token(token, nonce=nonce)
        session['user'] = user_info  
        return redirect(url_for('fusion'))  
    except Exception as e:
        print(f"Exception during authorization: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/fusion')
@login_required
def fusion():
    return render_template('fusion.html')


@app.route('/search', methods=['POST'])
@login_required
def search():
    data = request.json
    lat = float(data.get('lat'))
    lng = float(data.get('lng'))
    category = data.get('category')
    radius_str = data.get('radius', 1000)

    if not lat or not lng:
        return jsonify({'error': 'Invalid location data provided.'}), 400
    
    try:
        radius_miles = float(radius_str)
    except ValueError:
        return jsonify({'error': 'Invalid radius value provided.'}), 400

    radius_meters = max(radius_miles * 1609.34, 1000)

    category_type_map = {
        "Things To Do": "Things To Do",
        "ATM": "atm",
        "Bakery": "bakery",
        "Furniture Stores": "furniture_store",
        "Electronic Stores": "electronics_store",
        "Electricians": "electrician",
        "Plumbers": "plumber",
        "Interior Designers": "interior_designer",
        "Beauty Salon": "beauty_salon",
        "Bar": "bar",
        "Bicycle Store": "bicycle_store",
        "Book Store": "book_store",
        "Bowling Alley": "bowling_alley",
        "Cafe": "cafe",
        "Airports": "airport",
        "Campground": "campground",
        "Car Dealer": "car_dealer",
        "Car Rental": "car_rental",
        "Car Repair": "car_repair",
        "Car Wash": "car_wash",
        "Casino": "casino",
        "Cemetery": "cemetery",
        "Church": "church",
        "City Hall": "city_hall",
        "Clothing Store": "clothing_store",
        "Convenience Store": "convenience_store",
        "Courthouse": "courthouse",
        "Dentist": "dentist",
        "Department Store": "department_store",
        "Doctor": "doctor",
        "Embassy": "embassy",
        "Gym": "gym",
        "Fire Station": "fire_station",
        "Florist": "florist",
        "Hair Care": "hair_care",
        "Hardware Store": "hardware_store",
        "Temples": "hindu_temple",
        "Home Goods Store": "home_goods_store",
        "Insurance Agency": "insurance_agency",
        "Jewelry Store": "jewelry_store",
        "Laundry": "laundry",
        "Local Government Office": "local_government_office",
        "Lawyer": "lawyer",
        "Library": "library",
        "Mosque": "mosque",
        "Movie Rental": "movie_rental",
        "Moving Company": "moving_company",
        "Museum": "museum",
        "Parking": "parking",
        "Pet Store": "pet_store",
        "Physiotherapist": "physiotherapist",
        "Police": "police",
        "Post Office": "post_office",
        "Primary School": "primary_school",
        "Restaurants": "restaurant",
        "RV Park": "rv_park",
        "Secondary School": "secondary_school",
        "Shoe Store": "shoe_store",
        "Shopping Malls": "shopping_mall",
        "Spa": "spa",
        "Stadium": "stadium",
        "Store": "store",
        "Subway Station": "subway_station",
        "Supermarket": "supermarket",
        "Taxi Stand": "taxi_stand",
        "Tourist Attraction": "tourist_attraction",
        "Transit Station": "transit_station",
        "Travel Agency": "travel_agency",
        "University": "university",
        "Veterinary Care": "veterinary_care",
        "Zoo": "zoo",
        "Busstops": "bus_station",
        "Train Station": "train_station",
        "Bank": "bank",
        "Gas Stations": "gas_station",
        "Hospitals": "hospital",
        "Pharmacy Stores": "pharmacy",
        "Grocery Stores": "grocery_or_supermarket",
        "Indian Grocery Stores": "grocery_or_supermarket",  
        "Asian Grocery Stores": "grocery_or_supermarket",
        "School": "school",
        "Colleges": "university",
        "Parks": "park",
        "Movie Theatres": "movie_theater"
    }

    types = category_type_map.get(category, None)
    keyword = None

    if category == "Indian Grocery Stores":
        keyword = "Indian"
    elif category == "Asian Grocery Stores":
        keyword = "Asian"

    if not types:
        return jsonify({'error': 'Invalid category selected.'}), 400

    places_url = (
        f"https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        f"?location={lat},{lng}&radius={int(radius_meters)}&type={types}&key={'your_maps_api_key'}"
    )

    if keyword:
        places_url += f"&keyword={keyword}"

    response = requests.get(places_url)
    places = response.json()
    
    if 'results' in places and len(places['results']) > 0:
        results = []
        for place in places['results']:
            open_now_status = "Unknown"

            if 'opening_hours' in place:
                open_now_value = place['opening_hours'].get('open_now')
                if open_now_value is True:
                    open_now_status = "Open"
                elif open_now_value is False:
                    open_now_status = "Closed"

            result = {
                'name': place['name'],
                'address': place.get('vicinity', 'N/A'),
                'rating': place.get('rating', 'N/A'),
                'open_now': open_now_status,
                'lat': place['geometry']['location']['lat'],
                'lng': place['geometry']['location']['lng']
            }
            results.append(result)

        return jsonify({'results': results})
    else:
        return jsonify({'results': [], 'message': f'No {category} found in the selected location.'})
    

def calculate_distance(lat1, lng1, lat2, lng2):  
    lat1, lng1, lat2, lng2 = map(float, [lat1, lng1, lat2, lng2])
    lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])

    dlat = lat2 - lat1
    dlng = lng2 - lng1

    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlng / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    radius = 6371.0
    distance = radius * c

    return distance * 0.621371

@app.route('/add_to_wishlist', methods=['POST'])
@login_required
def add_to_wishlist():
    data = request.json
    required_fields = ['name', 'rating', 'address', 'lat', 'lng']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Invalid data provided, missing fields'}), 400
    
    wishlist_item = {
        'name': data['name'],
        'rating': data['rating'],
        'address': data['address'],
        'lat': data['lat'],
        'lng': data['lng']
    }
    wishlist_items.append(wishlist_item)
    return jsonify({'message': 'Item added to wishlist'}), 200

@app.route('/remove_from_wishlist', methods=['POST'])
@login_required
def remove_from_wishlist():
    data = request.json
    if 'name' not in data:
        return jsonify({'error': 'Invalid data provided'}), 400

    global wishlist_items
    wishlist_items = [item for item in wishlist_items if item['name'] != data['name']]
    return jsonify({'message': 'Item removed from wishlist'}), 200

@app.route('/wishlist')
@login_required
def wishlist():
    return render_template('wishlist.html', wishlist_items=wishlist_items)

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
