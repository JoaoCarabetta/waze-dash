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

from ..app import app, cache
from ..components import Col, Row, Card
from ..utils import to_deck_line, connect_db

import pandas as pd
import sqlalchemy as sa

from deckglplotly import line

PAGE_SIZE = 30

layout = html.Div([
    line(id='map',
         initial_longitude=-56.256744, 
         initial_latitude=-34.8749, 
         initial_zoom=13,
         data=[],
         mapboxtoken='pk.eyJ1IjoiYWxpc2hvYmVpcmkiLCJhIjoiY2ozYnM3YTUxMDAxeDMzcGNjbmZyMmplZiJ9.ZjmQ0C2MNs1AzEBC_Syadg',),
    html.Div([
        Card([
            ## Header
            html.Div([
                html.Div('Painel', className='card-header-title')],
                     className='card-header'),
            ## Date Picker
            html.Div([        
                html.Div('Select a date:', className='subtitle'),
                dcc.DatePickerRange(
                    id='date-picker-range',
                    start_date=dt(2018,9,30),
                    end_date=dt(2018,10,1),
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
                value=[0, 4]
            ),
            html.Div('Select a question:', className='subtitle'),
            dcc.Dropdown(
                id='problems-dropdown',
                options=[
                    {'label': 'Which segments are always congested?', 'value': 'perc'},
                    {'label': 'Where do people lose more time?', 'value': 'time'},
                    {'label': 'What are the longest jams?', 'value': 'size'}
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
    dcc.Store(id='date_range')
])

@app.callback(Output("date_range", "children"),
              [Input("date-picker-range", "end_date")],)
def update_graph2(end_date):
    con = connect_db()
    
def read_json(data):
    return pd.read_json(json.loads(data), orient='columns')

@cache.memoize()
def process_info(start_date, end_date, hour_range, dow_checklist):
    con = connect_db()
    query = """
        SELECT
            segment,
            street,
            max(segment_length) as segment_length,
            sum(minutes_with_jam) / (count(*) * 0.6)  as with_jam_prop,   
            sum(minutes_with_jam) / count(*) * ({end_hour} - {start_hour} + 1) as with_jam_total,   
            avg(segment_delay_sum) as lost_time_mean,  
            sum(segment_delay_sum) as lost_time_total, 
            avg(length_avg) as m_jam_mean,            
            max(length_max) as m_jam_max              
        from waze_dev.jams_segment_per_hour
        where hour between {start_hour} and {end_hour}
        and   dtm_hour between '{start_date}' and '{end_date}'
        and   dow in ({dow})
        group by segment, street""".format(start_hour=hour_range[0],
                                           end_hour=hour_range[1],
                                           start_date=start_date,
                                           end_date=end_date,
                                           dow=','.join(map(str, dow_checklist)))
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
               State('dow-checklist', 'values')]) 
def get_info(n_clicks, start_date, end_date, hour_range, dow_checklist):

    value = process_info(start_date, end_date, hour_range, dow_checklist)

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

There are {worst_segments} segments that always get jammed""".format(
                        total_segments=len(df),
                        worst_segments=len(df[df['with_jam_total'] > 90]), 
                        length=round(df['segment_length'].sum() / 1000, 0),
                        start_hour=hour_range[0],
                        end_hour=hour_range[1])
        return markdown

@app.callback(Output("map", "data"),
              [Input("signal", "data")],
              [State('problems-dropdown', 'value')])
def update_graph(df, problem):

    grey = [1,1,1]
    red = [1.0, 0.0, 0.0]

    df = read_json(df)

    data = to_deck_line(df, 'segment', 'with_jam_prop', grey, red, 
                        3, width_low=None, width_high=None,
                        legend_column='with_jam_prop', 
                        legend_title='Proportional Time Jammed (%)')
    
    return data


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



