import sys
import os

# Change these values for your environment
# THIS FILE SHOULD NOT BE READABLE BY OTHERS,
# UPDATE THE FILE PERMISSIONS ACCORDINGLY
#
os.environ['BB_USER'] = 'USERNAME'
os.environ['BB_PASS'] = 'PASSWORD'
os.environ['PHOTOROSTER_JPG_CACHE'] = '/var/www/apps/valpo-photo-roster/cache'

sys.path.append('/var/www/apps/valpo-photo-roster')

from photoroster import app as application
