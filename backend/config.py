"""
configuration module for application settings and database connection.

loads environment variables and provides database engine/session management.
"""

import os
from typing import Optional
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# load environment variables from .env file
load_dotenv()


class Config:
    """application configuration class."""

    # database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///vitals.db")

    # api keys (for later steps)
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    TWILIO_ACCOUNT_SID: Optional[str] = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN: Optional[str] = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_CALLER_ID: Optional[str] = os.getenv("TWILIO_CALLER_ID")
    PROVIDER_PHONE_NUMBER: Optional[str] = os.getenv("PROVIDER_PHONE_NUMBER")

    # flask settings
    FLASK_ENV: str = os.getenv("FLASK_ENV", "development")
    FLASK_DEBUG: bool = os.getenv("FLASK_DEBUG", "True").lower() == "true"


# database engine and session factory
engine = create_engine(
    Config.DATABASE_URL,
    echo=Config.FLASK_DEBUG,  # log sql queries in debug mode
    connect_args={"check_same_thread": False} if "sqlite" in Config.DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db_session() -> Session:
    """
    create and return a new database session.

    returns:
        sqlalchemy Session object

    usage:
        with get_db_session() as session:
            # use session here
            pass
    """
    return SessionLocal()
