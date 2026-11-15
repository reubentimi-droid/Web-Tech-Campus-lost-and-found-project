# Campus Lost and Found

Web app for posting and finding lost items on campus. Python (Flask), MySQL on AWS RDS, deployed on Elastic Beanstalk.

## Folders
| Folder | What goes here |
|---|---|---|
| `backend/` | Flask app (`main.py`): routes, login, database code |
| `frontend/` | `templates/` (HTML) and `static/` (CSS, JS, images) | 
| `database/` | Schema and seed SQL |


## Run locally
```
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd backend
python main.py
```
Then open the port 5000 link.
