from app.database import Base, engine
from app.models import TokenTrade, PriceSurge

def create_tables():
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    create_tables()


