from . import create_app, create_dash
from .layouts import main_layout_header
from flask_caching import Cache


# The Flask instance
server = create_app()

# The Dash instance
app = create_dash(server)

CACHE_CONFIG = {
    # try 'filesystem' if you don't want to setup redis
    'CACHE_TYPE': 'filesystem',
    'CACHE_DIR': '/Users/joaoc/Documents/projects/slapdash/cache'
}
cache = Cache()
cache.init_app(app.server, config=CACHE_CONFIG)


# Push an application context so we can use Flask's 'current_app'
with server.app_context():
    # load the rest of our Dash app
    from . import index

    # configure the Dash instance's layout
    app.layout = main_layout_header()
    

