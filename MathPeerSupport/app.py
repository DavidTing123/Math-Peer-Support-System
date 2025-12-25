import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask

# setup firebase connection
# use try-except block to catch errors if the key file is missing or invalid.

try:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase connected Successfully!")
except Exception as e:
    print(f"Error connecting to Firebase: {e}")
    print("Make sure 'serviceAccountKey.json' is in the same folder as app.py")

app = Flask(__name__)

# home page route
@app.route('/')
def home():
    return """
    <h1>Math Peer Support System (Firebase)</h1>
    <p>System Status: Online</p>
    <a href='/test-connection'>Click here to Test Database Write</a>
    """

# test route
# this simulates a student signing up to see if the db works
@app.route('/test-connection')
def test_db():
    try:
        #create a reference to a new document in the 'users' collection
        #we will use 'leader_id' as the document name
        doc_ref = db.collection('users').document('leader_id')

        #write data to it
        doc_ref.set({
            'username': 'Chong',
            'role': 'Programming Leader',
            'email': 'chongyouwei0521@gmail.com',
            'system_status': 'Active'
        })

        return "SUCCESS! Data written to Firebase. Check your Firestore console"
    except Exception as e:
        return f"FAILED : {e}"
    
if __name__ == '__main__':
        app.run(debug=True, port=8000)

