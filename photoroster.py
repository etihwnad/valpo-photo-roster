
import re
import csv
import os
import sys
from shutil import rmtree
from tempfile import mkdtemp
import time

import requests

from flask import Flask, request, render_template, make_response

from flask_wtf import FlaskForm, csrf
from flask_wtf.file import FileField, FileRequired

from wtforms import IntegerField, RadioField, StringField
from wtforms.validators import DataRequired, NumberRange, Optional

from werkzeug.utils import secure_filename

from werkzeug.middleware.proxy_fix import ProxyFix


app = Flask(__name__)

app.wsgi_app = ProxyFix(
    app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
)

app.secret_key = 'foo'
csrf.CSRFProtect(app)

KEEP_FILES = 'PHOTOROSTER_KEEP_FILES' in os.environ
JPG_CACHE = os.environ.get('PHOTOROSTER_JPG_CACHE', os.path.join(os.getcwd(), 'cache'))

# app.debug = True


class RosterForm(FlaskForm):
    title = StringField('Title', [DataRequired()])
    orient = RadioField('Orientation',
                        choices=[('portrait', 'Portrait'),
                                 ('landscape', 'Landscape')],
                        default='portrait')
    columns = IntegerField('# Columns',
                           [NumberRange(3, 10, 'Must be between 3 and 10')],
                           default=5)
    csvfile = FileField('CSV file', [FileRequired()])



@app.route('/', methods=['GET', 'POST'])
def photoroster():
    form = RosterForm()

    if form.validate_on_submit():
        # tmpdir = mkdtemp(prefix='photo-roster_')
        tmpdir = '/tmp/photo-roster_%i' % (int(100*time.time()),)
        os.mkdir(tmpdir, mode=0o777)
        print(tmpdir)

        csvname = os.path.join(tmpdir, secure_filename(form.csvfile.data.filename))
        form.csvfile.data.save(csvname)

        error_message = ""

        try:
            pdf = renderpdf(title=form.title.data,
                            orient=form.orient.data,
                            columns=form.columns.data,
                            csvname=csvname,
                            tmpdir=tmpdir)
            filename = form.title.data.replace(' ', '_')
            doc = make_response(pdf)
            doc.headers['Content-Disposition'] = "attachment; filename=%s.pdf" % filename
            response = doc
        except:
            # give the user *some* feedback instead of crashing
            error_message = """Something went wrong :(\n\nThis is typically an error in the input file.  Please check that it was exported with the correct setting."""
            response = render_template('roster.html', form=form, errors=[error_message])

        if not KEEP_FILES:
            print('removing %s' % tmpdir)
            # rmtree(tmpdir)
    else:
        response = render_template('roster.html', form=form, errors=None)

    return response



LATEX_SUBS = (
    (re.compile(r'\\'), r'\\textbackslash'),
    (re.compile(r'([{}_#%&$])'), r'\\\1'),
    (re.compile(r'~'), r'\~{}'),
    (re.compile(r'\^'), r'\^{}'),
    (re.compile(r'"'), r"''"),
    (re.compile(r'\.\.\.+'), r'\\ldots'),
)

def escape_tex(value):
    newval = value
    for pattern, replacement in LATEX_SUBS:
        newval = pattern.sub(replacement, newval)
    return newval

texenv = app.create_jinja_environment()
texenv.block_start_string = r'\BLOCK{'
texenv.block_end_string = '}'
texenv.line_statement_prefix = '%-'
texenv.variable_start_string = r'\VAR{'
texenv.variable_end_string = '}'
texenv.comment_start_string = r'\%{'
texenv.comment_end_string = '}'
texenv.line_comment_prefix = '%#'
texenv.filters['escape_tex'] = escape_tex



def renderpdf(title, orient, columns, csvname,
              CACHE=JPG_CACHE,
              tmpdir='tmp'):

    if orient == 'landscape':
        w = 10.0
    elif orient == 'portrait':
        w = 7.5

    width = '%fin' % (w / columns)
    height = '%fin' % ((w/columns)*4.0/3.0) # force aspect ratio

    data = {'title': title,
            'orient': orient,
            'columns': columns,
            'width': width,
            'height': height,
            }

    print(csvname)
    if sys.version_info[0] < 3:
        csvfile = open(csvname, 'rU')
    else:
        csvfile = open(csvname, 'r', newline='', encoding='utf-8')

    reader = csv.DictReader(csvfile, delimiter=',', quotechar='"')

    picUrl = 'https://apps.valpo.edu/photos/pics.php/%s'
    headers = {
        'Referer':'https://blackboard.valpo.edu/',
    }

    session = requests.Session()

    pwd = os.getcwd()
    students = []

    for row in reader:
        # skip the first row, if present (which is by default)
        if 'Points Possible' in row['Student']:
            continue

        lastfirst = row['Student']
        last, first = lastfirst.split(',')
        sid = row['SIS User ID']

        jpgname = sid + '.jpg'
        savename = os.path.join(pwd, CACHE, jpgname)
        print(savename)
        if not os.path.exists(savename):
            url = picUrl % sid
            print(url)
            r = session.get(url, headers=headers)
            if r.status_code != 200:
                print(('URL: %s' % url))
                print(r)
                print('Something went wrong retrieving the image')
            jpgdata = r.content
            # TODO: better detection of good images
            print('jpg len:', len(jpgdata))
            if len(jpgdata) > 1000:
                with open(savename, 'wb') as outjpg:
                    outjpg.write(jpgdata)
            else:
                #bad file, sub with generic image
                savename = os.path.join(pwd, CACHE, 'unknown.png')


        student = {}
        student['last'] = last
        student['first'] = first
        student['sid'] = sid
        student['filename'] = savename
        students.append(student)

    print(students)
    data['students'] = students

    texname = tmpdir + '/roster.tex'
    with open(texname, 'w') as texfile:
        tpl = texenv.get_template('roster.tex')
        texfile.write(tpl.render(data=data))

    os.chdir(tmpdir)
    cmd = 'rubber --pdf ' + texname
    os.system(cmd)
    os.chdir(pwd)

    pdfname = tmpdir + '/roster.pdf'
    with open(pdfname, 'rb') as pdffile:
        pdf = pdffile.read()

    return pdf


if __name__ == '__main__':
    app.run()

