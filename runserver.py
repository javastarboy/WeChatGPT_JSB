from flask import Flask

app = Flask(__name__)

if __name__ == "__main__":
    app.run(debug=False, host='0.0.0.0', port=80, threaded=True)
