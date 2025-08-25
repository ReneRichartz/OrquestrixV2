import os
from app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    # use_reloader=False um ImportError (watchdog EVENT_TYPE_OPENED) zu vermeiden
    app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False)