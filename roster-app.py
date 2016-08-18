
import re
import csv
import os
import sys
from shutil import rmtree
from tempfile import mkdtemp

import requests

from flask import Flask, request, render_template, make_response

from flask_wtf import Form, csrf
from flask_wtf.file import FileField, FileRequired

from wtforms import IntegerField, RadioField, StringField
from wtforms.validators import DataRequired, NumberRange, Optional

from werkzeug.utils import secure_filename


app = Flask(__name__)

app.secret_key = 'foo'
csrf.CsrfProtect(app)

KEEP_FILES = True

JPG_CACHE = os.path.join(os.getcwd(), 'cache')

# app.debug = True


class RosterForm(Form):
    title = StringField('Title', [DataRequired()])
    orient = RadioField('Orientation',
                        choices=[('landscape', 'Landscape'),
                                 ('portrait', 'Portrait')],
                        default='landscape')
    columns = IntegerField('# Columns',
                           [NumberRange(3, 10, 'Between 3 and 10')])
    csvfile = FileField('CSV file', [FileRequired()])



@app.route('/photoroster', methods=['GET', 'POST'])
def roster():
    form = RosterForm()

    if form.validate_on_submit():
        tmpdir = mkdtemp(prefix='photo-roster_')
        print tmpdir

        csvname = os.path.join(tmpdir, secure_filename(form.csvfile.data.filename))
        form.csvfile.data.save(csvname)
        pdf = renderpdf(title=form.title.data,
                        orient=form.orient.data,
                        columns=form.columns.data,
                        csvname=csvname,
                        tmpdir=tmpdir)

        filename = form.title.data.replace(' ', '_')
        doc = make_response(pdf)
        doc.headers['Content-Disposition'] = "attachment; filename=%s.pdf" % filename
        response = doc
        if not KEEP_FILES:
            rmtree(tmpdir)
    else:
        response = render_template('roster.html', form=form)

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
texenv.block_start_string = '\BLOCK{'
texenv.block_end_string = '}'
texenv.line_statement_prefix = '%-'
texenv.variable_start_string = '\VAR{'
texenv.variable_end_string = '}'
texenv.comment_start_string = '\%{'
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

    print csvname
    if sys.version_info[0] < 3:
        csvfile = open(csvname, 'rU')
    else:
        csvfile = open(csvname, 'r', newline='', encoding='iso8859-1')

    # the first 3 bytes of Blackboard CSV files are a
    # UTF-8 byte-order-mark "0xEF BB BF"
    # HACK: just throw them out!
    csvfile.read(3)
    reader = csv.DictReader(csvfile, delimiter=',', quotechar='"')

    picUrl = 'https://www.intra.valpo.edu/bb_pics/pics/auto/pics.php/%s'
    BB_USER = os.environ['BB_USER']
    BB_PASS = os.environ['BB_PASS']

    pwd = os.getcwd()
    students = []
    for row in reader:

        last = row['Last Name']
        first = row['First Name']
        sid = row['Student ID']

        jpgname = sid + '.jpg'
        savename = os.path.join(pwd, CACHE, jpgname)
        if not os.path.exists(savename):
            url = picUrl % sid
            r = requests.get(url, auth=(BB_USER, BB_PASS))
            if r.status_code != 200:
                print('URL: %s' % url)
                print('Something went wrong retrieving the image')
            jpgdata = r.content
            print 'jpg len:', len(jpgdata)
            if len(jpgdata) > 10000:
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
    with open(pdfname, 'r') as pdffile:
        pdf = pdffile.read()

    return pdf


if __name__ == '__main__':
    app.run()

