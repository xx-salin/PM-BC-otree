import os
from os import environ



# pip install xlrd
# import xlrd

# to activate sentry
SENTRY_DSN = 'http://dc47b6d4cd0e4f57bdf965286e6f629a:c04b645ccd5b458da917b5aa9c2d49bd@sentry.otree.org/295'

# if you set a property in SESSION_CONFIG_DEFAULTS, it will be inherited by all configs
# in SESSION_CONFIGS, except those that explicitly override it.
# the session config can be accessed from methods in your apps as self.session.config,
# e.g. self.session.config['participation_fee']

SESSION_CONFIG_DEFAULTS = {
    'real_world_currency_per_point': 1.00,
    'participation_fee': 3.50, 
    'doc': "",
    'testing': False, 
}


SESSION_CONFIGS = [
        #{
        #'name': 'SMP1',
        #'display_name': 'SMP1',
        #'num_demo_participants': 40,
        #'app_sequence': ['SMP1']
        #}#,
        # {
        # 'name': 'MRE2',
        # 'display_name': 'MRE2',
        # 'num_demo_participants': 32,
        # 'app_sequence': ['MRE2']
        # },
        # {
        # 'name': 'RFIH',
        # 'display_name': 'RFIH',
        # 'num_demo_participants': 320,
        # 'app_sequence': ['RFIH'],
        # 'testing': True,
        # },
        # {
        #  'name': 'RF2',
        #  'display_name': 'RF2',
        #  'num_demo_participants': 16,
        #  'app_sequence': ['RF2'],
        #  'testing': False,
        #  },
          {
         'name': 'ME',
         'display_name': 'ME',
         'num_demo_participants': 32,
         'app_sequence': ['ME'],
         'testing': True,
         },
        #    {
        #  'name': 'HB',
        #  'display_name': 'HB',
        #  'num_demo_participants': 32,
        #  'app_sequence': ['HB'],
        #  'testing': True,
        #  },

      
     
        
        #{
        #'name': 'CRB1a',
        #'display_name': 'CRB1a',
        #'num_demo_participants': 16,
        #'app_sequence': ['CRB1a'],
        #'participation_fee' : 2.00 #changes the participation fee to 3.00 instead of the standard 2.50
        #},
        #{
        #'name': 'CRB2a',
        #'display_namea': 'CRB2a',
        #'num_demo_participants': 32,
        #'app_sequence': ['CRB2a'],
        #'participation_fee' : 2.00 #changes the participation fee to 3.00 instead of the standard 2.50
        #}#,
        #{
        #'name': 'PRE3',
        #'display_name': 'PRE3',
        #'num_demo_participants': 16,
        #'app_sequence': ['PRE3'],
        #'participation_fee' : 1.00 #changes the participation fee
        #},
        #{
        #'name': 'PRE4',
        #'display_name': 'PRE4',
        #'num_demo_participants': 16,
        #'app_sequence': ['PRE4'],
        #'participation_fee' : 1.00 #changes the participation fee
        #}
]
# see the end of this file for the inactive session configs


# ISO-639 code
# '''
# LANGUAGE_CODE = 'de' # for example: de, fr, ja, ko, zh-hans
# REAL_WORLD_CURRENCY_CODE = 'EUR' # e.g. EUR, GBP, CNY, JPY
# USE_POINTS = False
# '''
LANGUAGE_CODE = 'en'
REAL_WORLD_CURRENCY_CODE = 'GBP' # e.g. EUR, GBP, CNY, JPY
USE_POINTS = False


ROOM_DEFAULTS = {}

ROOMS = [
     dict(
     name='Study',
     display_name='Study'
    # participant_label_file='_rooms/econ101.txt',
    )
]


# AUTH_LEVEL:
# this setting controls which parts of your site are freely accessible,
# and which are password protected:
# - If it's not set (the default), then the whole site is freely accessible.
# - If you are launching a study and want visitors to only be able to
#   play your app if you provided them with a start link, set it to STUDY.
# - If you would like to put your site online in public demo mode where
#   anybody can play a demo version of your game, but not access the rest
#   of the admin interface, set it to DEMO.

# for flexibility, you can set it in the environment variable OTREE_AUTH_LEVEL
AUTH_LEVEL = environ.get('OTREE_AUTH_LEVEL')

ADMIN_USERNAME = 'admin'
# for security, best to set admin password in an environment variable
ADMIN_PASSWORD = environ.get('OTREE_ADMIN_PASSWORD')


# Consider '', None, and '0' to be empty/false
#DEBUG = (environ.get('OTREE_PRODUCTION') in {None, '', '1'}) # to turn debug info on
DEBUG = (environ.get('OTREE_PRODUCTION') in {None, '', '0'}) # to turn debug info off

DEMO_PAGE_INTRO_HTML = """
<ul>
    <li>
        <a href="https://github.com/oTree-org/otree" target="_blank">
            oTree on GitHub
        </a>.
    </li>
    <li>
        <a href="http://www.otree.org/" target="_blank">
            oTree homepage
        </a>.
    </li>
</ul>
<p>
    Here are various games implemented with oTree. These games are all open
    source, and you can modify them as you wish.
</p>
"""

# don't share this with anybody.
SECRET_KEY = 'f6j&u9ui=cewq3j_#gtyccc=sv)(06gfg$1(oxi5cr^4s$q@^c'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  

STATIC_URL = '/static/'




STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'ME/static'),
]
  


# if an app is included in SESSION_CONFIGS, you don't need to list it here
INSTALLED_APPS = ['otree', 'django.contrib.staticfiles', 'ME']


if not DEBUG:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


# Middleware settings
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',  # Manages sessions across requests
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',  # Enables CSRF protection
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

