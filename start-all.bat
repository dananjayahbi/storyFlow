@echo off
echo Starting StoryFlow...
start "StoryFlow Backend" cmd /k "cd /d %~dp0backend && call venv\Scripts\activate && python manage.py runserver 8765"
start "StoryFlow Frontend" cmd /k "cd /d %~dp0frontend && npm run dev -- -p 3847"
echo Backend: http://localhost:8765
echo Frontend: http://localhost:3847
