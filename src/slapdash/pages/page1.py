from collections import Counter
from datetime import datetime as dt
import json
from pathlib import Path
import ast

import plotly.graph_objs as go
from dash_table import DataTable
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, State, Output

from ..app import app
from ..components import Col, Row, Card
from ..utils import to_deck_line, connect_db

import pandas as pd
import sqlalchemy as sa

from deckglplotly import LineLayer

PAGE_SIZE = 30
CURRENT_CITY = 'miraflores'

layout = html.Div([
    html.Div(
        html.Div(
            id='map-inner'
        ),
        id='map-keeper'
    ),
    html.Div([
        Card([
            ## Header
            html.Div([
                html.Div('Where is the traffic?', className='card-header-title')],
                     className='card-header'),
            
            html.Div([
                html.Div('Select a city:', className='subtitle'),
                dcc.Dropdown(
                    id='cities-dropdown',
                    options=[
                    {'label': 'Montevideo', 'value': 'montevideo'},
                    # {'label': 'São Paulo', 'value': 'sao_paulo'},
                    {'label': 'Miraflores', 'value': 'miraflores'},
                    {'label': 'Xalapa', 'value': 'xalapa'},
                    {'label': 'Quito', 'value': 'quito'},
                    ], 
                    value='montevideo'
                )
            ]),
            ## Date Picker
            html.Div([        
                html.Div('Select a date:', className='subtitle'),
                dcc.DatePickerRange(
                    id='date-picker-range',
                    start_date=dt(2018,12,20),
                    end_date=dt(2018,12,25),
                    end_date_placeholder_text='Select a date!'
                ),], className='datepicker-container'),

            html.Div('Select weekdays:', className='subtitle'),
            dcc.Checklist(
                id='dow-checklist',
                options=[
                    {'label': 'Sunday', 'value': 0},
                    {'label': 'Monday', 'value': 1},
                    {'label': 'Tuesday', 'value': 2},
                    {'label': 'Wednesday', 'value': 3},
                    {'label': 'Thursday', 'value': 4},
                    {'label': 'Friday', 'value': 5},
                    {'label': 'Saturday', 'value': 6},
                ],
                values=[1, 2, 3, 4, 5],
                labelStyle={'display': 'inline-block'}
            ),
            html.Div('Select an hour range:', className='subtitle'),
            dcc.RangeSlider(
                id='hour-range-slider',
                min=0,
                max=23,
                value=[7, 9]
            ),
            html.Div('Select a question:', className='subtitle'),
            dcc.Dropdown(
                id='problems-dropdown',
                options=[
                    {'label': 'Which segments are always congested?', 'value': 'perc'},
                    # {'label': 'Where do people lose more time?', 'value': 'time'},
                    # {'label': 'What are the longest jams?', 'value': 'size'}
                ],
                value='perc'
            ),
            html.Button(id='submit-button', n_clicks=0, children='Submit'),
            dcc.Markdown(
                id='phrase-markdown'),], 
            className='card'),
    html.Div([
        DataTable(
            id='table',
            pagination_settings={
                'current_page': 0,
                'page_size': PAGE_SIZE
            },
            filtering='be',
            filtering_settings='',
            pagination_mode='be',
            style_cell={'textAlign': 'left'},
            style_as_list_view=True,
            )],
        className='table'),
    ]),
    dcc.Store(id='signal'),
    dcc.Store(id='date_range'),
    html.Div(id='current_city', style={'display': 'none'}, children='miraflores'),
    dcc.Store(id='city_viewport')
])


    
def read_json(data):
    return pd.read_json(json.loads(data), orient='columns')

# @cache.memoize()
def process_info(start_date, end_date, hour_range, dow_checklist, city):

    con = connect_db()
    from datetime import datetime

    days = (datetime.strptime(end_date, '%Y-%m-%d') - 
            datetime.strptime(start_date, '%Y-%m-%d')).days

    query = """
        SELECT
            segment,
            street,
            avg(length_max) as segment_length,
            sum(minutes_with_jam)  as with_jam_total,   
            sum(minutes_with_jam) / (({end_hour} - {start_hour} + 1) * {days} * 0.6) as with_jam_prop           
        from waze_painel.{city}_jams_segment_per_hour
        where hour between {start_hour} and {end_hour}
        and   dtm_hour between '{start_date}' and '{end_date}'
        group by segment, street""".format(start_hour=hour_range[0],
                                           end_hour=hour_range[1],
                                           start_date=start_date,
                                           end_date=end_date,
                                           dow=','.join(map(str, dow_checklist)),
                                           city=city,
                                           days=days)
    df = pd.read_sql_query(query, con)
    
    df['segment'] = df['segment'].apply(ast.literal_eval)
    lon = lambda x: (x[0]['y'], x[1]['y'])
    lat = lambda x: (x[0]['x'], x[1]['x'])
    df['lon'] = df['segment'].apply(lon)
    df['lat'] = df['segment'].apply(lat)

    return json.dumps(df.to_json(orient='columns', date_format='iso'))


@app.callback(Output("signal", "data"),
              [Input("submit-button", "n_clicks")],
              [State("date-picker-range", 'start_date'),
               State("date-picker-range", 'end_date'),
               State("hour-range-slider", 'value'),
               State('dow-checklist', 'values'),
               State('cities-dropdown', 'value')]) 
def get_info(n_clicks, start_date, end_date, hour_range, dow_checklist,
            city):

    print('n_clicks: ', n_clicks)

    print('getting info')
    value = process_info(start_date, end_date, hour_range, dow_checklist, city)

    return value
    
@app.callback(Output("phrase-markdown", "children"),
              [Input("signal", "data")],
              [State('problems-dropdown', 'value'),
              State("hour-range-slider", 'value')])
def update_markdown(df, problem, hour_range):

    df = read_json(df)

    if problem == 'perc':
        
        markdown = """
{length}km of roads usually get jammed between {start_hour} and {end_hour} hours

There are {worst_segments} road segments that usually get jammed""".format(
                        total_segments=len(df),
                        worst_segments=len(df[df['with_jam_prop'] > 50]), 
                        length=round(df[df['with_jam_prop'] > 10]['segment_length'].sum() / 1000, 0),
                        start_hour=hour_range[0],
                        end_hour=hour_range[1])
        return markdown


def get_city_viewport(city):

    con = connect_db()

    query = """
            select initial_zoom, initial_lat, initial_lon
            from waze.cities_stats
            where city='{city}'
            """.format(city=city)

    return pd.read_sql_query(query, con).to_dict('records')[0]

@app.callback(Output('map-keeper', 'children'),
              [Input('signal', 'data')],
              [State('current_city', 'children'),
              State('cities-dropdown', 'value')])
def clean_graph(data, current_city, city):

    # if city == current_city:
    #     print('here')
    #     pass
    # else:
    if data is not None:
        print('clean')
        return html.Div(id='map-inner')

@app.callback(Output('current_city', 'children'),
              [Input('map-keeper', 'children')],
              [State('cities-dropdown', 'value')])
def update_current_city(ping, city):
    print('updating current city')
    return city

@app.callback(Output("map-inner", "children"),
                [Input('date_range', 'data')],
              [State("signal", "data"),
               State('problems-dropdown', 'value'),
               State('cities-dropdown', 'value')])
def update_graph(useless, df, problem, city):

    grey = [1,195/225,188/255]
    red = [1.0, 0.0, 0.0]

    df = read_json(df)

    data = to_deck_line(df, 'segment', 'with_jam_prop', grey, red, 
                        3, width_low=None, width_high=None,
                        legend_column='with_jam_prop', 
                        legend_title='Proportional Time Jammed (%)',
                        color_steps=4)

    viewstate = get_city_viewport(city)

    print('city: ', city)
    print('viewstate: ', viewstate)

    return LineLayer(
            id='map',
            longitude=float(viewstate['initial_lon']), 
            latitude=float(viewstate['initial_lat']),  
            zoom=float(viewstate['initial_zoom']), 
            data=data,
            mapboxtoken='pk.eyJ1IjoiYWxpc2hvYmVpcmkiLCJhIjoiY2ozYnM3YTUxMDAxeDMzcGNjbmZyMmplZiJ9.ZjmQ0C2MNs1AzEBC_Syadg',)

@app.callback(Output("table", "columns"),
              [Input("signal", "data")],
              [State('problems-dropdown', 'value')])
def update_table_columns(df, problem):
    
    df = read_json(df)

    if problem == 'perc':

        return [{"name": 'Street', "id": 'street'},
                {"name": 'Total Time Jammed (minutes)', "id": 'with_jam_total'},
                {"name": 'Proportional Time Jammed (%)', "id": 'with_jam_prop'},
         ]

@app.callback(Output("table", "data"),
              [Input("table", "columns"),
              Input('table', 'pagination_settings'),
              Input('table', "filtering_settings")],
              [State("signal", 'data'),
              State('problems-dropdown', 'value')])
def update_table_columns(columns, pagination_settings, filtering_settings,
                         df, problem):

    df = read_json(df)
    if problem == 'perc':
        df = df.sort_values(by='with_jam_total', ascending=False)
        df['with_jam_total'] = df['with_jam_total'].round(0)

    filtering_expressions = filtering_settings.split(' && ')
    dff = df
    for filter in filtering_expressions:
        if ' eq ' in filter:
            col_name = filter.split(' eq ')[0]
            filter_value = filter.split(' eq ')[1]
            dff = dff.loc[dff[col_name] == filter_value]
        if ' > ' in filter:
            col_name = filter.split(' > ')[0]
            filter_value = float(filter.split(' > ')[1])
            dff = dff.loc[dff[col_name] > filter_value]
        if ' < ' in filter:
            col_name = filter.split(' < ')[0]
            filter_value = float(filter.split(' < ')[1])
            dff = dff.loc[dff[col_name] < filter_value]

    
    return dff.iloc[
        pagination_settings['current_page'] * pagination_settings['page_size']:
        (pagination_settings['current_page'] + 1)*pagination_settings['page_size']
    ].to_dict('rows')





@app.server.before_first_request
def get_date_range():
    con = connect_db()



