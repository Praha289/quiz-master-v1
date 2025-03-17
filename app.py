from flask import Flask, render_template, redirect, url_for, request, session,flash
from werkzeug.security import generate_password_hash, check_password_hash
from database import db
from models.user import User
from models.subject import Subject
from datetime import datetime,timedelta
from models.chapter import Chapter
from sqlalchemy.sql import text
from flask_migrate import Migrate
from flask import request, redirect
from collections import defaultdict

import sqlite3
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///quiz.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key_here'

db.init_app(app)
with app.app_context():
    db.create_all()
migrate = Migrate(app, db)  

from models import*
# Home Page
@app.route('/')
def index():
    return render_template('indexprev.html')

@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username").strip()
        password = request.form.get("password").strip()

        print(f"Received username: '{username}'")  # Check if there are spaces
        print(f"Received password: '{password}'")

        correct_username = "admin"
        correct_password = "admin@123"

        print(f"Comparing with username: '{correct_username}'")
        print(f"Comparing with password: '{correct_password}'")

        if username == correct_username and password == correct_password:
            print("Admin login successful!")
            session["user_id"] = "admin"
            session["role"] = "admin"
            return redirect(url_for("admin_dashboard"))
        else:
            print("Login failed!")
            return "Invalid admin credentials!"

    return render_template("admin_login.html")



# User Registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('fullname')
        qualification = request.form.get('qualification')
        dob_str = request.form.get('dob')
        dob = datetime.strptime(dob_str, '%Y-%m-%d').date() if dob_str else None
        hashed_password = generate_password_hash(password)

        if User.query.filter_by(email=email).first():
            return 'Email already registered! Please use a different email.'
        if User.query.filter_by(username=username).first():
            return 'Username already taken! Choose a different one.'

        new_user = User(username=username, email=email, password=hashed_password,
                        full_name=full_name, qualification=qualification, dob=dob, role="user")

        try:
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            return f"Error: {str(e)}"

    return render_template('register.html')

# User Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session["user_id"] = user.id
            session["role"] = user.role
            return redirect(url_for("admin_dashboard" if user.role == "admin" else "user_dashboard"))
        else:
            return "Invalid username or password!"
    return render_template("login.html")

# Admin Dashboard
@app.route("/admin_dashboard")
def admin_dashboard():
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("admin_login"))
    subjects = Subject.query.all()
    return render_template("admin_dashboard.html", subjects=subjects)

# Add Subject
@app.route("/add_subject", methods=["POST"])
def add_subject():
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("admin_login"))
    subject_name = request.form.get("subject_name")
    if subject_name:
        new_subject = Subject(name=subject_name)
        db.session.add(new_subject)
        db.session.commit()
    return redirect(url_for("admin_dashboard"))

# Delete Subject
@app.route("/delete_subject/<int:subject_id>", methods=["POST"])
def delete_subject(subject_id):
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("admin_login"))
    subject = Subject.query.get(subject_id)
    if subject:
        db.session.delete(subject)
        db.session.commit()
    return redirect(url_for("admin_dashboard"))

@app.route('/user_dashboard')
def user_dashboard():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    from models.db_utils import get_user_subjects, get_user_chapters, get_user_quizzes

    subjects = get_user_subjects(user_id)
    chapters = get_user_chapters(user_id)
    quizzes = get_user_quizzes(user_id)

    # Structure Data: Each subject contains chapters, each chapter contains quizzes
    subjects_data = []
    for subject in subjects:
        subject_chapters = [ch for ch in chapters if ch.subject_id == subject.id]
        for chapter in subject_chapters:
            chapter.quizzes = [q for q in quizzes if q.chapter_id == chapter.id]
        subjects_data.append({'id': subject.id, 'name': subject.name, 'chapters': subject_chapters})

    print("Structured Data:", subjects_data)  # Debugging

    return render_template('user_dashboard.html', subjects=subjects_data)

# Logout
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))
from flask import Flask, render_template, request, redirect, url_for, session
from datetime import datetime, timedelta

@app.route('/attempt_quiz/<int:quiz_id>', methods=['GET', 'POST'])
def attempt_quiz(quiz_id):
    quiz = Quiz.query.get(quiz_id)
    if not quiz:
        return "Quiz not found!"

    # Fetch all questions related to this quiz
    questions = Question.query.filter_by(quiz_id=quiz_id).all()
    if not questions:
        return "No questions found for this quiz!"

    # Store quiz start time in session
    if "quiz_start_time" not in session:
        session["quiz_start_time"] = datetime.now().isoformat()

    # Calculate remaining time
    start_time = datetime.fromisoformat(session["quiz_start_time"])
    end_time = start_time + timedelta(minutes=quiz.time_duration)
    current_time = datetime.now()

    # If time is over, auto-submit
    if current_time >= end_time:
        return redirect(url_for('submit_quiz', quiz_id=quiz_id))  

    return render_template("attempt_quiz.html", quiz=quiz, questions=questions, end_time=end_time)

@app.route("/add_chapter", methods=["POST"])
def add_chapter():
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("admin_login"))

    chapter_name = request.form.get("chapter_name")
    subject_id = request.form.get("subject_id")

    if chapter_name and subject_id:
        new_chapter = Chapter(name=chapter_name, subject_id=subject_id)
        db.session.add(new_chapter)
        db.session.commit()
    
    return redirect(url_for("admin_dashboard"))
@app.route('/manage_questions/<int:chapter_id>/<int:quiz_id>', methods=['GET', 'POST'])
def manage_questions(chapter_id, quiz_id):
    """Handles adding and displaying questions for a quiz."""
    
    if request.method == 'POST':
        question_text = request.form['question_text']
        option1 = request.form['option1']
        option2 = request.form['option2']
        option3 = request.form['option3']
        option4 = request.form['option4']
        correct_answer = request.form['correct_answer']

        new_question = Question(
            quiz_id=quiz_id,
            question_text=question_text,
            option1=option1,
            option2=option2,
            option3=option3,
            option4=option4,
            correct_answer=correct_answer
        )

        db.session.add(new_question)
        db.session.commit()
        flash('Question added successfully!', 'success')

    questions = Question.query.filter_by(quiz_id=quiz_id).all()
    
    return render_template('manage_questions.html', chapter_id=chapter_id, quiz_id=quiz_id, questions=questions)

@app.route("/add_question", methods=["POST"])
def add_question():
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("admin_login"))

    quiz_id = request.form.get("quiz_id")
    question_text = request.form.get("question_text")

    # Ensure session has the correct chapter_id
    chapter_id = session.get("chapter_id")
    if not chapter_id:
        flash("Chapter ID is missing!", "error")
        return redirect(url_for("admin_dashboard"))

    if not quiz_id or not question_text:
        flash("Missing quiz ID or question text", "error")
        return redirect(url_for("admin_dashboard"))

    new_question = Question(
        quiz_id=quiz_id,
        question_text=question_text,
        option1=request.form.get("option1"),
        option2=request.form.get("option2"),
        option3=request.form.get("option3"),
        option4=request.form.get("option4"),
        correct_answer=request.form.get("correct_answer"),
    )
    db.session.add(new_question)
    db.session.commit()
    
    flash("Question added successfully!", "success")
    return redirect(url_for("manage_questions", chapter_id=chapter_id, quiz_id=quiz_id))


@app.route('/delete_question/<int:question_id>', methods=['POST'])
def delete_question(question_id):
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("admin_login"))

    question = Question.query.get(question_id)
    if question:
        db.session.delete(question)
        db.session.commit()
        flash("Question deleted successfully!", "success")

    return redirect(request.referrer or url_for("admin_dashboard"))


@app.route("/delete_chapter/<int:chapter_id>", methods=["POST"])
def delete_chapter(chapter_id):
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("admin_login"))

    chapter = db.session.get(Chapter, chapter_id)  # Corrected session handling

    if chapter:
        db.session.delete(chapter)
        db.session.commit()

    return redirect(url_for("admin_dashboard"))

@app.route('/quiz/<int:quiz_id>', methods=['GET'])
def start_quiz(quiz_id):
    db.session.expire_all()  # Force refresh from DB
    quiz = Quiz.query.get_or_404(quiz_id)
    questions = Question.query.filter_by(quiz_id=quiz_id).all()

    print(f"Quiz ID: {quiz_id} - Retrieved Questions: {len(questions)}")
    for q in questions:
        print(f"Question: {q.id} - {q.question_text} (Quiz ID: {q.quiz_id})")

    return render_template('attempt_quiz.html', quiz=quiz, questions=questions)
def store_score(user_id, quiz_id, score_data, score):
    print("DEBUG: score_data =", score_data, "Type:", type(score_data))  # Check data format

    if isinstance(score_data, list):  
        for item in score_data:  # Iterate over list items
            if isinstance(item, dict) and 'user_answer' in item:
                user_answer = item.get('user_answer')
                correct_answer = item.get('correct_answer', None)

                # Save each answer in the database
                new_score = Score(
                    user_id=user_id,
                    quiz_id=quiz_id,
                    user_answer=user_answer,
                    correct_answer=correct_answer,
                    score=score
                )
                db.session.add(new_score)
                print(f"Stored Score - User Answer: {user_answer}, Correct Answer: {correct_answer}")

    elif isinstance(score_data, dict):  
        user_answer = score_data.get('user_answer', None)
        correct_answer = score_data.get('correct_answer', None)

        # Save single answer in the database
        new_score = Score(
            user_id=user_id,
            quiz_id=quiz_id,
            user_answer=user_answer,
            correct_answer=correct_answer,
            score=score
        )
        db.session.add(new_score)
        print(f"Stored Score - User Answer: {user_answer}, Correct Answer: {correct_answer}")

    else:
        print("ERROR: Unexpected format for score_data!")

    db.session.commit()  # Ensure all changes are saved

    
@app.route('/submit_quiz/<int:quiz_id>', methods=['GET', 'POST'])
def submit_quiz(quiz_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    quiz = Quiz.query.get_or_404(quiz_id)
    questions = Question.query.filter_by(quiz_id=quiz_id).all()

    if request.method == 'POST':
        score = 0
        score_data = []

        # Delete old scores before storing new ones
        Score.query.filter_by(user_id=user_id, quiz_id=quiz_id).delete()
        db.session.commit()

        for question in questions:
            user_answer = request.form.get(f'answer_{question.id}', '').strip()
            correct_answer = question.correct_answer.strip()
            is_correct = user_answer.lower() == correct_answer.lower()

            if is_correct:
                score += 1

            score_data.append({
                'question': question.question_text,
                'user_answer': user_answer,
                'correct_answer': correct_answer
            })

        # Store score
        store_score(user_id, quiz_id, score_data, score)

        flash(f'Quiz submitted! Your score: {score}/{len(questions)}', 'success')
        return redirect(url_for('view_scores'))

    return render_template('quiz.html', quiz=quiz, questions=questions)

@app.route('/add_quiz', methods=['POST'])
def add_quiz():
    print("=== Form Data Received ===")
    print(request.form)  # This will show what Flask is getting
    print("==========================")

    subject_id = request.form.get('subject_id')
    chapter_id = request.form.get('chapter_id')
    quiz_title = request.form.get('quiz_name')  
    time_duration = request.form.get('time_duration')

    if not subject_id or not chapter_id or not quiz_title or not time_duration:
        flash("All fields are required!", "error")
        return redirect(url_for('admin_dashboard'))

    try:
        new_quiz = Quiz(
            subject_id=int(subject_id),
            chapter_id=int(chapter_id),
            title=quiz_title,
            time_duration=int(time_duration)
        )
        db.session.add(new_quiz)
        db.session.commit()
        flash("Quiz added successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error adding quiz: {str(e)}", "error")

    return redirect(url_for('admin_dashboard'))

@app.route('/view_scores')
def view_scores():
    user_id = session.get('user_id')  # Ensure user is logged in
    if not user_id:
        return redirect(url_for('login'))

    # Fetch all scores for the user
    raw_scores = Score.query.filter_by(user_id=user_id).all()

    quiz_scores = {}  # Dictionary to store latest score per quiz

    for score in raw_scores:
        quiz_title = score.quiz.title  # Ensure quiz title exists in your model
        if quiz_title not in quiz_scores or score.date_attempted > quiz_scores[quiz_title]['date_attempted']:
            quiz_scores[quiz_title] = {
                'quiz_title': quiz_title,
                'score': score.score,  
                'date_attempted': score.date_attempted  # Keep original datetime
            }

    return render_template("view_scores.html", scores=list(quiz_scores.values()))


@app.route('/delete_quiz/<int:quiz_id>', methods=['POST'])
def delete_quiz(quiz_id):
    conn = sqlite3.connect("quiz.db")
    cursor = conn.cursor()

    # Delete quiz from database
    cursor.execute("DELETE FROM quiz WHERE id = ?", (quiz_id,))
    conn.commit()
    conn.close()

    flash("Quiz deleted successfully!", "success")
    return redirect(url_for("admin_dashboard"))
@app.route('/view_scores/<int:quiz_id>')
def view_quiz_scores(quiz_id):  
    from models.db_utils import get_user_scores

    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    scores = get_user_scores( quiz_id, user_id)

    # Instead of redirecting, render the scores page
    return render_template('view_scores.html', scores=scores, quiz_id=quiz_id)




if __name__ == '__main__':
     
    
    app.run(debug=True)