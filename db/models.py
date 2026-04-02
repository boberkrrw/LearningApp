from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from db.database import Base
from datetime import datetime, timezone
import enum


class TaskType(enum.Enum):
    HANDS_ON = "hands_on"
    QUIZ = "quiz"
    SCENARIO = "scenario"


class TaskStatus(enum.Enum):
    ACTIVE = "active"
    DONE = "done"
    SKIPPED = "skipped"


class ProgressStatus(enum.Enum):
    NOT_STARTED = "Not Started"
    LEARNING = "Learning"
    PRACTICED = "Practiced"
    CONFIDENT = "Confident"


class Topic(Base):
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False, unique=True)
    description = Column(Text)
    subtopics = relationship("Subtopic", back_populates="topic", cascade="all, delete-orphan")


class Subtopic(Base):
    __tablename__ = "subtopics"

    id = Column(Integer, primary_key=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    name = Column(String(300), nullable=False)
    description = Column(Text)
    senior_level = Column(String(10), nullable=False)
    dependencies = Column(Text)  # JSON list of subtopic IDs this depends on
    priority_score = Column(Integer, default=0)
    tier = Column(Integer, default=1)

    # Cached AI responses
    cached_explanation = Column(Text)
    cached_resources = Column(Text)
    cached_task = Column(Text)

    topic = relationship("Topic", back_populates="subtopics")
    tasks = relationship("Task", back_populates="subtopic", cascade="all, delete-orphan")
    progress = relationship("Progress", back_populates="subtopic", uselist=False, cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    subtopic_id = Column(Integer, ForeignKey("subtopics.id"), nullable=False)
    description = Column(Text, nullable=False)
    task_type = Column(SAEnum(TaskType), nullable=False)
    difficulty = Column(Integer, default=1)  # 1-5
    status = Column(SAEnum(TaskStatus), default=TaskStatus.ACTIVE)
    user_answer = Column(Text)
    ai_feedback = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime)

    subtopic = relationship("Subtopic", back_populates="tasks")


class Progress(Base):
    __tablename__ = "progress"

    id = Column(Integer, primary_key=True)
    subtopic_id = Column(Integer, ForeignKey("subtopics.id"), nullable=False, unique=True)
    status = Column(SAEnum(ProgressStatus), default=ProgressStatus.NOT_STARTED)
    weak_areas = Column(Text)
    last_session_notes = Column(Text)
    tasks_completed = Column(Integer, default=0)
    tasks_attempted = Column(Integer, default=0)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    subtopic = relationship("Subtopic", back_populates="progress")


class SessionHistory(Base):
    __tablename__ = "session_history"

    id = Column(Integer, primary_key=True)
    subtopic_id = Column(Integer, ForeignKey("subtopics.id"), nullable=False)
    activity_type = Column(String(50), nullable=False)  # learn, practice, evaluate
    content = Column(Text)
    evaluation_result = Column(Text)
    weak_spots = Column(Text)
    notes = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class EvalQuestion(Base):
    __tablename__ = "eval_questions"

    id = Column(Integer, primary_key=True)
    subtopic_id = Column(Integer, ForeignKey("subtopics.id"), nullable=False)
    question_text = Column(Text, nullable=False)
    question_type = Column(String(20), nullable=False)  # "multiple_choice" or "text"
    options = Column(Text)        # JSON: {"A": "...", "B": "...", "C": "...", "D": "..."}
    correct_answer = Column(String(5))   # "A"/"B"/"C"/"D" for MC
    model_answer = Column(Text)          # Reference answer for text questions
    explanation = Column(Text)
    position = Column(Integer, default=0)  # ordering within the test
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class EvalAttempt(Base):
    __tablename__ = "eval_attempts"

    id = Column(Integer, primary_key=True)
    subtopic_id = Column(Integer, ForeignKey("subtopics.id"), nullable=False)
    score_pct = Column(Float, default=0.0)
    total_questions = Column(Integer, default=0)
    correct_count = Column(Integer, default=0)
    answers = Column(Text)   # JSON: {question_id: {user_answer, correct, feedback}}
    weak_spots = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
