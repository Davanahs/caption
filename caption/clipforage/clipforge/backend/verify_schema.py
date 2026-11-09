import sys
import os

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from sqlalchemy import inspect
from backend.models.database import sync_engine
from backend.models.models import Base

def verify():
    inspector = inspect(sync_engine)
    db_tables = set(inspector.get_table_names())
    model_tables = set(Base.metadata.tables.keys())
    
    missing_in_db = model_tables - db_tables
    missing_in_models = db_tables - model_tables
    
    if not missing_in_db and not missing_in_models:
        print("Schema verification passed! All model tables exist in the database.")
    else:
        if missing_in_db:
            print(f"Missing in DB: {missing_in_db}")
        if missing_in_models:
            print(f"Extra in DB: {missing_in_models}")
        print("Schema verification failed!")
        sys.exit(1)

if __name__ == "__main__":
    verify()
