from sqlalchemy import create_engine, Column, Integer, String, Text, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
from config import DB_PATH

DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, default="")
    preferred_language = Column(String, default="en")
    target_role = Column(String, default="sde")
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    candidate_name = Column(String, default="")
    resume_text = Column(Text, default="")
    job_description = Column(Text, default="")
    resume_analysis_json = Column(Text, default="")
    status = Column(String, default="created")  # created | ready | interviewing | deliberating | complete
    session_type = Column(String, default="full")  # full | resume | hr | technical | behavioral | coding
    consensus_score = Column(Float, nullable=True)
    consensus_verdict = Column(String, nullable=True)
    star_avg = Column(Float, nullable=True)

    user = relationship("User", back_populates="sessions")
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")
    evaluations = relationship("Evaluation", back_populates="session", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"))
    role = Column(String)
    content = Column(Text)
    persona = Column(String, nullable=True)
    star_json = Column(Text, nullable=True)
    rewritten = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("Session", back_populates="messages")


class Evaluation(Base):
    __tablename__ = "evaluations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"))
    persona = Column(String)
    score = Column(Float, nullable=True)
    feedback = Column(Text, default="")
    strengths = Column(Text, default="")
    concerns = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("Session", back_populates="evaluations")


def init_db():
    Base.metadata.create_all(bind=engine)
    # Lightweight migration for existing DBs missing new columns
    try:
        with engine.connect() as conn:
            cols = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(sessions)").fetchall()]
            if "user_id" not in cols:
                conn.exec_driver_sql("ALTER TABLE sessions ADD COLUMN user_id VARCHAR")
            if "session_type" not in cols:
                conn.exec_driver_sql("ALTER TABLE sessions ADD COLUMN session_type VARCHAR DEFAULT 'full'")
            if "consensus_score" not in cols:
                conn.exec_driver_sql("ALTER TABLE sessions ADD COLUMN consensus_score FLOAT")
            if "consensus_verdict" not in cols:
                conn.exec_driver_sql("ALTER TABLE sessions ADD COLUMN consensus_verdict VARCHAR")
            if "star_avg" not in cols:
                conn.exec_driver_sql("ALTER TABLE sessions ADD COLUMN star_avg FLOAT")
            conn.commit()
    except Exception as e:
        print(f"[db migrate] {e}")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
