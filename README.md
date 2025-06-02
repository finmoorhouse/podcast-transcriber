This is a simple web app to process transcriptions using the Deepgram API.

To start. just run `./start_app.sh`. This runs the following commands, which you can also run separately:

- Run `source transcription/bin/activate` to activate the venv
- Run `python start_ngrok.py` to start a local server
- Run `flask --app flask_app run` or `flask --app flask_app --debug run` to start the Flask app (or simply `flask run`)

To use the site:

- Visit the `localhost` page (for me it's `http://127.0.0.1:5000`)
- Upload a file through the page, and keep the app running at least until the API returns a transcript.