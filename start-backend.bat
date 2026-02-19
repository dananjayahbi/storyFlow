@echo off
echo Starting StoryFlow Backend...
cd /d %~dp0backend
call venv\Scripts\activate
python manage.py runserver
