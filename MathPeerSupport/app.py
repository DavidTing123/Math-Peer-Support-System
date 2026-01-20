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

          if not email.endswith('@mmu.edu.my'):
             return render_template('login.html', error="Access Restricted: MMU Email Required")

          request_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_WEB_API_KEY}"
          payload = {"email": email, "password": password, "returnSecureToken": True}

          result = requests.post(request_url, json=payload)
          data = result.json()

          if 'error' in data:
               return render_template('login.html', error="Invalid Email or Password")
          else:
               user_id = data['localId']

               user_doc = db.collection('users').document(user_id).get()
               user_role = 'student'

               if user_doc.exists:
                    user_data = user_doc.to_dict()
                    user_role = user_data.get('role', 'student')

               # save user session if login
               session['user_id'] = data['localId']
               session['email'] = data['email']
               session['role'] = user_role
               return redirect('/')
          
     return render_template('login.html')
     
# register route
@app.route('/register', methods=['GET', 'POST'])
def register():
     if request.method == 'POST':
          email = request.form['email']
          password = request.form['password']

          if not email.endswith('@mmu.edu.my'):
               return "<h1>Error: Registration is only allowed with an @mmu.edu.my emails only. <a href='/register'>Try Again</a></h1>"

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

@app.route('/delete/<question_id>')
def delete_question(question_id):
     if 'user_id' not in session:
          return redirect('/login')
     
     question_ref = db.collection('questions').document(question_id)
     question = question_ref.get()

     if question.exists:
          q_data = question.to_dict()
          if q_data['student_id'] == session['user_id']:
               question_ref.delete()

     return redirect('/')

@app.route('/edit/<question_id>', methods=['GET','POST'])
def edit_question(question_id):
     if 'user_id' not in session:
          return redirect('/login')
          
     question_ref = db.collection('questions').document(question_id)
     question = question_ref.get()

     if not question.exists:
          return "Question not found", 404
     
     q_data = question.to_dict()

     if q_data['student_id'] != session['user_id']:
          return "You are not authorized to edit this question", 403
     
     if request.method == 'POST':
          new_title = request.form['title']
          new_details = request.form['details']

          question_ref.update({
               'title': new_title,
               'details': new_details,
               'edited_at': firestore.SERVER_TIMESTAMP
          })
          return redirect('/')
     
     return render_template(
          'edit.html',
          question=q_data,
          q_id=question_id,
          user=session.get('email'))

@app.route('/question/<question_id>')
def view_question(question_id):
     if 'user_id' not in session:
          return redirect('/login')
     
     q_doc = db.collection('questions').document(question_id).get()
     if not q_doc.exists:
          return "Question not found", 404
     question_data = q_doc.to_dict()
     question_data['id'] = q_doc.id

     answers_ref = db.collection('questions').document(question_id).collection('answers')\
          .order_by('score', direction=firestore.Query.DESCENDING).stream()

     answers = []
     for a in answers_ref:
          a_data = a.to_dict()
          a_data['id'] = a.id

          if 'upvoters' not in a_data: a_data['upvoters'] = []
          if 'downvoters' not in a_data: a_data['downvoters'] = []

          answers.append(a_data)

     best_answer_id = None
     if answers:
          highest_score = max(a['score'] for a in answers)

          if highest_score > 0:
               for a in answers:
                    if a['score'] == highest_score:
                         best_answer_id = a['id']
                         break

     return render_template(
          'question_detail.html',
          question=question_data,
          answers = answers,
          user = session['email'],
          current_user_id = session['user_id'],
          best_answer_id = best_answer_id,
          current_user_role = session.get('role', 'student')
     )

@app.route('/answer/<question_id>', methods=['POST'])
def post_answer(question_id):
     if 'user_id' not in session:
          return redirect('/login')
     
     answer_text = request.form['answer_text']
     image_file = request.files.get('image')

     image_url = None

     user_role = session.get('role', 'student')
     is_verified = (user_role == 'lecturer')

     if image_file and image_file.filename != '':
          blob = bucket.blob(f"questions/{question_id}/answers/{session['user_id']}/{image_file.filename}")
          blob.upload_from_string(
               image_file.read(),
               content_type=image_file.content_type
          )
          blob.make_public()
          image_url = blob.public_url

     db.collection('questions').document(question_id).collection('answers').add({
          'answer_text': answer_text,
          'image_url': image_url,
          'student_id': session['user_id'],
          'student_email': session['email'],
          'role': user_role,
          'is_verified': is_verified,
          'timestamp': firestore.SERVER_TIMESTAMP,
          'score': 0,
          'upvoters': [],
          'downvoters': []
     })

     return redirect(f'/question/{question_id}')

@app.route('/vote/<question_id>/<answer_id>/<action>')
def vote_answer(question_id, answer_id, action):
     if 'user_id' not in session:
          return redirect('/login')
     
     user_id = session['user_id']
     ans_ref = db.collection('questions').document(question_id).collection('answers').document(answer_id)
     ans_doc = ans_ref.get()

     if ans_doc.exists:
          data = ans_doc.to_dict()

          upvoters = list(set(data.get('upvoters', [])))
          downvoters = list(set(data.get('downvoters', [])))

          if action == 'up':

               if user_id in upvoters:
                    upvoters.remove(user_id)
               
               elif user_id in downvoters:
                    downvoters.remove(user_id)
                    upvoters.append(user_id)
               
               else:
                    upvoters.append(user_id)

          elif action == 'down':
               
               if user_id in downvoters:
                    downvoters.remove(user_id)
               
               elif user_id in upvoters:
                    upvoters.remove(user_id)
                    downvoters.append(user_id)
               
               else:
                    downvoters.append(user_id)

          new_score = len(upvoters) - len(downvoters)

          ans_ref.update({
               'score': new_score,
               'upvoters': upvoters,
               'downvoters': downvoters
          })

     return redirect(f'/question/{question_id}')

@app.route('/verify-answer/<question_id>/<answer_id>')
def verify_answer(question_id, answer_id):
     if 'user_id' not in session:
          return redirect('/login')
     
     if session.get('role') != 'lecturer':
          return "Unauthorized", 403
     
     ans_ref = db.collection('questions').document(question_id).collection('answers').document(answer_id)
     ans_ref.update({
          'is_verified': True,
          'verified_by': session['email']
     })

     return redirect(f'/question/{question_id}')

@app.route('/resources')
def resources_list():
     if 'user_id' not in session:
          return redirect('/login')
     
     resources_ref = db.collection('resources').order_by('timestamp', direction=firestore.Query.DESCENDING).stream()

     all_resources = []
     for r in resources_ref:
          r_data = r.to_dict()
          r_data['id'] = r.id
          all_resources.append(r_data)

     return render_template(
          'resources.html',
          resources=all_resources,
          user_role = session.get('role', 'student')
     )

@app.route('/resource/<resource_id>')
def view_resource(resource_id):
     if 'user_id' not in session:
          return redirect('/login')
     
     res_doc = db.collection('resources').document(resource_id).get()
     if not res_doc.exists:
          return "Resource not found", 404
     
     return render_template(
          'resource_detail.html',
          resource = res_doc.to_dict(),
          user_role = session.get('role', 'student')
     )

@app.route('/upload-resource', methods=['GET', 'POST'])
def upload_resource():
     if 'user_id' not in session:
          return redirect ('/login')
     
     if session.get('role') != 'lecturer':
          return "Unauthorized", 403
     
     if request.method == 'POST':
          title = request.form['title']
          category = request.form['category']
          content = request.form['content']
          file = request.files.get('file')

          file_url = None
          file_type = None

          if file and file.filename != '':
               blob = bucket.blob(f"resources/{session['user_id']}/{file.filename}")
               blob.upload_from_string(
                    file.read(),
                    content_type = file.content_type
               )
               blob.make_public()
               file_url = blob.public_url
               file_type = file.content_type
          
          db.collection('resources').add({
               'title': title,
               'category': category,
               'content': content,
               'file_url': file_url,
               'file_type': file_type,
               'lecturer_email': session['email'],
               'timestamp': firestore.SERVER_TIMESTAMP
          })
          
          return redirect('/resources')
     
     return render_template('upload_resource.html')

@app.route('/delete-answer/<question_id>/<answer_id>')
def delete_answer(question_id, answer_id):
     if 'user_id' not in session:
          return redirect('/login')
     
     ans_ref = db.collection('questions').document(question_id).collection('answers').document(answer_id)
     ans_doc = ans_ref.get()

     if ans_doc.exists:
          data = ans_doc.to_dict()
          # SECURITY: Only allow the author to delete
          if data['student_id'] == session['user_id']:
               ans_ref.delete()
     
     return redirect(f'/question/{question_id}')

@app.route('/edit-answer/<question_id>/<answer_id>', methods=['GET', 'POST'])
def edit_answer(question_id, answer_id):
     if 'user_id' not in session:
          return redirect('/login')

     ans_ref = db.collection('questions').document(question_id).collection('answers').document(answer_id)
     ans_doc = ans_ref.get()

     if not ans_doc.exists:
          return "Answer not found", 404
     
     data = ans_doc.to_dict()

     # SECURITY: Only allow the author to edit
     if data['student_id'] != session['user_id']:
          return "Unauthorized", 403

     if request.method == 'POST':
          new_text = request.form['answer_text']
          ans_ref.update({
               'answer_text': new_text,
               'edited_at': firestore.SERVER_TIMESTAMP
          })
          return redirect(f'/question/{question_id}')

     return render_template('edit_answer.html', answer=data, question_id=question_id, answer_id=answer_id)

@app.route('/unverify-answer/<question_id>/<answer_id>')
def unverify_answer(question_id, answer_id):
     if 'user_id' not in session:
          return redirect('/login')
     
     # SECURITY: Only Lecturers
     if session.get('role') != 'lecturer':
          return "Unauthorized", 403

     ans_ref = db.collection('questions').document(question_id).collection('answers').document(answer_id)
     ans_ref.update({
          'is_verified': False,
          'verified_by': firestore.DELETE_FIELD
     })

     return redirect(f'/question/{question_id}')

@app.route('/delete-resource/<resource_id>')
def delete_resource(resource_id):
     if 'user_id' not in session:
          return redirect('/login')
     
     res_ref = db.collection('resources').document(resource_id)
     res_doc = res_ref.get()

     if res_doc.exists:
          data = res_doc.to_dict()
          # SECURITY: Only allow the UPLOADER to delete
          if data.get('lecturer_email') == session['email']:
               res_ref.delete()
               # Note: Ideally you should also delete the file from Storage bucket here
     
     return redirect('/resources')

@app.route('/edit-resource/<resource_id>', methods=['GET', 'POST'])
def edit_resource(resource_id):
     if 'user_id' not in session:
          return redirect('/login')

     res_ref = db.collection('resources').document(resource_id)
     res_doc = res_ref.get()

     if not res_doc.exists:
          return "Resource not found", 404
     
     data = res_doc.to_dict()

     # SECURITY: Only allow the UPLOADER to edit
     if data.get('lecturer_email') != session['email']:
          return "Unauthorized", 403

     if request.method == 'POST':
          new_title = request.form['title']
          new_category = request.form['category']
          new_content = request.form['content']

          res_ref.update({
               'title': new_title,
               'category': new_category,
               'content': new_content,
               'edited_at': firestore.SERVER_TIMESTAMP
          })
          return redirect('/resources')

     return render_template('edit_resource.html', resource=data, resource_id=resource_id)



if __name__ == '__main__':
        app.run(debug=True, port=8000)

