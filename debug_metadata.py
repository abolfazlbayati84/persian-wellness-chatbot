from app.models.base import Base
from app.models import User, Profile, Session, Message

print(Base.metadata.tables.keys())