from app.db.session import SessionLocal
from app.models.models import Project

db = SessionLocal()
projects = db.query(Project).all()
for p in projects:
    print(f'id={p.id} org={p.organization_id} name={p.name} is_system={p.is_system}')
db.close() 
