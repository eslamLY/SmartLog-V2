"""
SMARTLOG — Attendance & HR Management System
Entry point — delegates to core.create_app().
"""
import os

from core import create_app

app = create_app()

if __name__ == '__main__':
    PRODUCTION = app.config.get('PRODUCTION', False)
    app.run(debug=not PRODUCTION, host='0.0.0.0',
            port=int(os.environ.get('PORT', 5000)))
