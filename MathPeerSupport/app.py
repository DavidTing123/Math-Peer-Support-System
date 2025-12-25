import firebase_admin
from firebase_admin import credentials, firestore, auth
from flask import Flask, render_template, request, redirect, url_for, session
import requests #for verify passwords
import json

#configuration
FIREBASE_WEB_API_KEY = "AIzaSyA2tfxr1I8xmxnxsDTXhWCOaMcPZif4aiQ"
# setup firebase connection
# use try-except block to catch errors if the key file is missing or invalid.

try:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
    db = firestore.client()
except Exception:
   pass #initialized

app = Flask(__name__)
app.secret_key = "secret_math_key"

# home page route
@app.route('/')
def home():
    if 'user_id' in session:
        return f"<h1>Welcome, {session['email']}!</h1><a href='/logout'</a>"
    return redirect('/login')

# login route
@app.route('/login', methods=['GET', 'POST'])
def login():
     if request.method == 'POST':
          email = request.form['email']
          password = request.form['password']

          request_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_WEB_API_KEY}"
          payload = {"email": email, "password": password, "returnSecureToken": True}

          result = requests.post(request_url, json=payload)
          data = result.json()

          if 'error' in data:
               return render_template('login.html', error="Invalid Email or Password")
          else:
               # save user session if login
               session['user_id'] = data['localId']
               session['email'] = data['email']
               return redirect('/')
          
     return render_template('login.html')
     
# register route
@app.route('/register', methods=['GET', 'POST'])
def register():
     if request.method == 'POST':
          email = request.form['email']
          password = request.form['password']

          try:
               # create user in firebase auth
               user = auth.create_user(email=email, password=password)

               # create user profile in firestore
               db.collection('users').document(user.uid).set({
                    'email': email,
                    'role' : 'student',
                    'created_at': firestore.SERVER_TIMESTAMP
               })

               return "<h1>Account Created! <a href='/login'>Go to Login</a></h1>"
          except Exception as e:
               return f"Error: {e}"
          
     return """
          <form method='POST'>
               <h2>Register</h2>
               <input type="email" name="email" placeholder="Email" required><br>
               <input type="password" name="password" placeholder="Password" required><br>
               <button type="submit">Sign Up</button>
          </form>

     """

# logout route
@app.route('/logout')
def logout():
     session.clear()
     return redirect('/login')   

if __name__ == '__main__':
        app.run(debug=True, port=8000)

