from flask import current_app as server
import dash_core_components as dcc
import dash_html_components as html

from .utils import component, get_url

def _merge(a, b):
    return dict(a, **b)


def _omit(omitted_keys, d):
    return {k: v for k, v in d.items() if k not in omitted_keys}


@component
def Row(children=None, **kwargs):
    """A convenience component that makes a Bootstrap row"""
    return html.Div(children=children, className='row', **kwargs)


@component  
def Col(children=None, bp=None, size=None, **kwargs):
    """A convenience component that makes a Bootstrap column"""
    if size is None and bp is None:
        col_class = 'col'
    elif bp is None:
        col_class = 'col-{}'.format(size)
    else:        
        col_class = 'col-{}-{}'.format(bp, size)
    return html.Div(children=children, className=col_class, **kwargs)


def Card(children, **kwargs):
    return html.Section(
        children,
        style=_merge({
            'padding': 20,
            'margin': 5,
            'borderRadius': 5,
            'border': 'thin lightgrey solid',

            # Remove possibility to select the text for better UX
            'user-select': 'none',
            '-moz-user-select': 'none',
            '-webkit-user-select': 'none',
            '-ms-user-select': 'none'
        }, kwargs.get('style', {})),
        **_omit(['style'], kwargs)
    )

@component
def Header(children=None, **kwargs):
    return html.Header(html.H1(
        children=[
            Fa('bar-chart'), 
            dcc.Link(
                server.config['TITLE'],
                href=server.config['ROUTES_PATHNAME_PREFIX']
            )
        ],
        **kwargs
    ))


def Fa(name):
    """A convenience component for adding Font Awesome icons"""
    return html.I(className="fa fa-{}".format(name))


@component
def Navbar(
        children=None,
        items=None,
        current_path=None,
        first_root_nav=True,
        **kwargs):

    items = items if items is not None else []
    nav_items = []
    route_prefix = server.config['ROUTES_PATHNAME_PREFIX']
    
    for i, (path, text) in enumerate(items):
        href = get_url(path)
        # bool indicating if: on the root url and this is the first nav item       
        is_first_root_nav = (current_path == route_prefix) and (i == 0)
        # active if we are on the path of this nav item, or if first_root_nav is
        # enabled and applies for this path
        is_active = (current_path == href) or (first_root_nav and is_first_root_nav) 
        className = 'nav-item active' if is_active else 'nav-item'
        nav_items.append(html.Li(
            className=className,
            children=dcc.Link(text, href=href, className='nav-link')
        ))

    return html.Nav(
        className=f'navbar',
        children=[
            html.Ul(
                className=f'nav',
                children=nav_items
            ),
        ],
        **kwargs,
    )
