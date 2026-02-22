#!/bin/bash
echo "Starting StoryFlow Backend..."
cd "$(dirname "$0")/backend"
source venv/bin/activate
python manage.py runserver