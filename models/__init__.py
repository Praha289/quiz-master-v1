from database import db
# Import models in the correct order
from models.subject import Subject  # Subject has no dependencies, safe to import first
from models.chapter import Chapter  # Chapter depends on Subject
from models.quiz import Quiz        # Quiz depends on Chapter
from models.question import Question  # Question depends on Quiz
from models.score import Score      # Score depends on Quiz
from models.user import User        # User is independent, safe to import last
from models.answer import Answer
from models.user_answer import UserAnswer