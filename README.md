Flask app to generate photo rosters.

# Dependencies
* python3
* flask
* flask-WTF
* rubber for compiling latex

`sudo apt install python3-flask python3-flaskext.wtf rubber`



```bash
export BB_USER=username
export BB_PASS=pass
export PHOTOROSTER_JPG_CACHE=/path/to/jpg/cache
export FLASK_APP=roster-app.py

# uncomment to keep uploaded files and temp files for debugging
#export PHOTOROSTER_KEEP_FILES=1

flask run
```

With Apache's mod_wsgi, start with `roster-app.wsgi` and `roster-app.conf`.

