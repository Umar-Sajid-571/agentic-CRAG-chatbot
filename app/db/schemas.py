import uuid
from sqlalchemy import Column, String, Text, ForeignKey, LargeBinary
from sqlalchemy.orm import declarative_base
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

# Define Base for declarative models
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)

class LongTermMemory(Base):
    __tablename__ = 'long_term_memory'

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    fact_content = Column(Text, nullable=False)
    # Placeholder for vector embedding. Requires a vector database extension or library for actual vector operations.
    embedding = Column(LargeBinary, nullable=True)

class ChatTitle(Base):
    __tablename__ = 'chat_titles'

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    title = Column(String, nullable=False)
    thread_id = Column(String, nullable=False) # Assuming thread_id is a string
