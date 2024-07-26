This is a simple web app to process transcriptions using the Gladia API.

To start:

- Run `ngrok http 5000` to start a local server (to catch the response from Gladia)
- Run `flask --app flask-app run` or `flask --app flask-app --debug run` to start the Flask app
- Visit the `localhost` page (for me it's `http://127.0.0.1:5000`)
- Upload a file through the page, and keep the app running at least until Gladia returns a transcript.