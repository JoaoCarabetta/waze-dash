from . import create_app, create_dash
from .layouts import main_layout_header, main_layout_fullpage
#from flask_caching import Cache


# The Flask instance
server = create_app()

# The Dash instance
app = create_dash(server)

# Push an application context so we can use Flask's 'current_app'
with server.app_context():
    # load the rest of our Dash app
    from . import index

    # configure the Dash instance's layout
    app.layout = main_layout_header()
    

