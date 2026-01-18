import firebase_admin
from firebase_admin import credentials, firestore, auth
from flask import Flask, render_template, request, redirect, url_for, session
import requests #for verify passwords
import json
from firebase_admin import storage

#configuration
FIREBASE_WEB_API_KEY = "AIzaSyA2tfxr1I8xmxnxsDTXhWCOaMcPZif4aiQ"
# setup firebase connection
# use try-except block to catch errors if the key file is missing or invalid.

if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred,{
         'storageBucket': 'mathpeersupport.firebasestorage.app'
    })
    db = firestore.client()
    bucket = storage.bucket()


app = Flask(__name__)
app.secret_key = "secret_math_key"

# home page route
@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect('/login')

    questions_ref = db.collection('questions').order_by('timestamp', direction=firestore.Query.DESCENDING).stream()

    all_questions = []
    for q in questions_ref:
         q_data = q.to_dict()
         q_data['id'] = q.id
         all_questions.append(q_data)

    return render_template(
         'dashboard.html', 
         questions=all_questions, 
         user=session['email'],
         current_user_id=session['user_id'])


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



@app.route('/ask', methods=['GET','POST'])
def ask_question():
     if 'user_id' not in session:
          return redirect('/login')
     
     if request.method == 'POST':
          title = request.form['title']
          details = request.form['details']
          image_file = request.files['image']

          image_url = None

          if image_file and image_file.filename!= '':

               blob = bucket.blob(f"questions/{session['user_id']}/{image_file.filename}")
               blob.upload_from_string(
                    image_file.read(),
                    content_type=image_file.content_type
               )
               blob.make_public()
               image_url = blob.public_url

          db.collection('questions').add({
               'student_id': session['user_id'],
               'student_email': session['email'],
               'title': title,
               'details': details,
               'image_url': image_url,
               'timestamp': firestore.SERVER_TIMESTAMP
          })

          return redirect('/')
          
     
     return render_template(
          'ask.html',
          user=session['email'],
     )
                            

if __name__ == '__main__':
        app.run(debug=True, port=8000)

