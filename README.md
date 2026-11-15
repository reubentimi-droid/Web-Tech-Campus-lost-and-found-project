# Campus Lost and Found

Web app for posting and finding lost items on campus. Python (Flask), MySQL on AWS RDS, deployed on Elastic Beanstalk.

## Folders
| Folder | What goes here | Who |
|---|---|---|
| `backend/` | Flask app (`main.py`): routes, login, database code | Reuben |
| `frontend/` | `templates/` (HTML) and `static/` (CSS, JS, images) | Frontend team |
| `database/` | Schema and seed SQL | Jamar |
| `tests/` | Test scripts | Areeba |
| `docs/` | Report, diagrams | Everyone |

## Run locally
```
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd backend
python main.py
```
Then open the port 5000 link.
