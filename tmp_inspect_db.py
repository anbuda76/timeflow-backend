from sqlalchemy import inspect
from app.db.session import engine
insp = inspect(engine)
print([col['name'] for col in insp.get_columns('users')])
