from flask import current_app as server
from functools import wraps
from colour import Color
import ast


def get_url(path):
    """Expands an internal URL to include prefix the app is mounted at"""
    return f"{server.config['ROUTES_PATHNAME_PREFIX']}{path}"


def component(func):
    """Decorator to help vanilla functions as pseudo Dash Components"""
    @wraps(func)
    def function_wrapper(children=None, **kwargs):
        # remove className and style args from input kwargs so the component
        # function does not have to worry about clobbering them.
        className = kwargs.pop('className', None)
        style = kwargs.pop('className', None)
        
        # call the component function and get the result
        result = func(children=children, **kwargs)

        # now restore the initial classes and styles by adding them
        # to any values the component introduced

        if className is not None:
            if hasattr(result, 'className'):
                result.className = f'{className} {result.className}'
            else:
                result.className = className

        if style is not None:
            if hasattr(result, 'style'):
                result.style = style.update(result.style)
            else:
                result.style = style                

        return result
    return function_wrapper


def to_deck_line(df, segment_column,
                 color_column, color_low, color_high, 
                 width_column, width_low, width_high,
                 legend_column, legend_title,
                 color_opacity=1, color_steps=10):
    
    if isinstance(color_column, str):
        color_true = True
        color_max_value = df[color_column].max()
        print(df[color_column].mean())
        color_range = list(Color(rgb=color_low).range_to(Color(rgb=color_high), color_steps))
        color_range = list(map(lambda hues: list(map(lambda x: x * 255, hues.rgb)), color_range))

    elif isinstance(color_column, tuple) and len(color_column) == 3:
        color_true = False
    else:
        raise TypeError('color_column should be a rbg tuple or a column name string')
        
    if isinstance(width_column, str):
        width_true = True
        width_max_value = df[width_column].max()
    elif isinstance(width_column, int):
        width_true = False
    else:
        raise TypeError('width_column should be a int or a column name string')
        
    if isinstance(legend_column, str):
        legend_true = True
    elif isinstance(legend_column, None):
        width_true = False
    else:
        raise TypeError('width_column should be a int or None')
    
    try:
        df[segment_column] = df[segment_column].apply(ast.literal_eval)
    except ValueError:
        pass
    
    columns = [i for i in [segment_column, color_column, width_column] if isinstance(i, str)]
    column_map =  dict(zip(columns, [i for i in range(len(columns))]))
    
    records = df[columns].to_dict(orient='list')
    records = list(zip(*records.values()))
    
    def to_color_range(value, color_low, color_high, color_opacity=225, color_steps=10):
    
        to_range = lambda x: int(round(x / color_max_value * (color_steps - 1))) 

        return color_range[to_range(value)] + [color_opacity]
    
    def to_width_range(value):
        
        return round(value / width_max_value * (width_high - width_low) + width_low)

    def to_legend_data(value):

        if isinstance(value, float):
            return round(value)

    def inside(record, column_map):

        segment = record[column_map[segment_column]]
        result = {'sourcePosition': [segment[0]['x'], segment[0]['y']], 
             'targetPosition': [segment[1]['x'], segment[1]['y']], 
             'color': to_color_range(record[column_map[color_column]], color_low, color_high) if color_true else color_column,
             'width': to_width_range(record[column_map[width_column]]) if width_true else width_column,
             'legend_title': legend_title,
             'legend_data': to_legend_data(record[column_map[legend_column]]) if legend_true else legend_column}     
        return result
    
    return list(map(lambda x: inside(x, column_map), records))
