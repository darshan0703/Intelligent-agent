from sqlalchemy import create_engine
from models import Base

engine = create_engine("postgresql://darshan@localhost/restaurant_ai")

Base.metadata.create_all(engine)

print("Tables created successfully.")