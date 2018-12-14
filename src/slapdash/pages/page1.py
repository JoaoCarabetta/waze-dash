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
from ..components import Col, Row

import pandas as pd
import sqlalchemy as sa

PAGE_SIZE = 30

layout = html.Div([
    dcc.Markdown("""
# Jams

This demo counts the number of characters in the text box and updates a bar
chart with their frequency as you type."""),
    html.Div('Select a date:'),
    dcc.DatePickerRange(
        id='date-picker-range',
        start_date=dt(2018,9,30),
        end_date=dt(2018,10,1),
        end_date_placeholder_text='Select a date!'
    ),
    html.Div('Select weekdays:'),
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
    html.Div('Select an hour range:'),
    dcc.RangeSlider(
        id='hour-range-slider',
        marks={i: 'Hour {}'.format(i) for i in range(0, 24)},
        min=0,
        max=23,
        value=[0, 4]
    ),
    html.Div('Select a question:'),
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
        id='phrase-markdown'),
    dcc.Graph(id='map-graph'),
    DataTable(
        id='table',
        pagination_settings={
        'current_page': 0,
        'page_size': PAGE_SIZE
        },
        pagination_mode='be',
        style_cell={'textAlign': 'left'},
        style_as_list_view=True,
    ),
    html.Div(id='signal', style={'display': 'none'}),
    html.Div(id='date_range', style={'display': 'none'})
])

@app.callback(Output("date_range", "children"),
              [Input("date-picker-range", "end_date")],)
def update_graph(end_date):
    con = sa.create_engine(open(Path(__file__).parent / 'redshift_key.txt', 'r').read())
    

def read_json(data):
    return pd.read_json(json.loads(data), orient='columns')

@cache.memoize()
def process_info(start_date, end_date, hour_range, dow_checklist):
    con = sa.create_engine(open(Path(__file__).parent / 'redshift_key.txt', 'r').read())
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


@app.callback(Output("signal", "children"),
              [Input("submit-button", "n_clicks")],
              [State("date-picker-range", 'start_date'),
               State("date-picker-range", 'end_date'),
               State("hour-range-slider", 'value'),
               State('dow-checklist', 'values')]) 
def get_info(n_clicks, start_date, end_date, hour_range, dow_checklist):

    value = process_info(start_date, end_date, hour_range, dow_checklist)

    return value

@app.callback(Output("phrase-markdown", "children"),
              [Input("signal", "children")],
              [State('problems-dropdown', 'value'),
              State("hour-range-slider", 'value')])
def update_markdown(df, problem, hour_range):

    df = read_json(df)

    if problem == 'perc':
        
        markdown = """
### {length}km of roads were jammed between {start_hour} and {end_hour} hours.
### From {total_segments} road segments that were jammed, {worst_segments} segments were always totally jammed""".format(
                        total_segments=len(df),
                        worst_segments=len(df[df['with_jam_total'] > 90]), 
                        length=round(df['segment_length'].sum() / 1000, 0),
                        start_hour=hour_range[0],
                        end_hour=hour_range[1])
        return markdown

@app.callback(Output("map-graph", "figure"),
              [Input("signal", "children")],
              [State('problems-dropdown', 'value')])
def update_graph(df, problem):

    df = read_json(df)

    mapbox_access_token = 'pk.eyJ1IjoiYWxpc2hvYmVpcmkiLCJhIjoiY2ozYnM3YTUxMDAxeDMzcGNjbmZyMmplZiJ9.ZjmQ0C2MNs1AzEBC_Syadg'

    zoom = 12.0
    latInitial = -34.874314
    lonInitial = -56.252405
    bearing = 0

    if problem == 'perc':
        df = df.sort_values(by='with_jam_total', ascending=False)
    data = []
    for i, row in df[:100].iterrows():
        
        data.append(
            go.Scattermapbox(
                lat=row['lon'],
                lon=row['lat'],
                mode='lines',
                hoverinfo="lat+lon",
                line=dict(
                    color='red',
                    width=2),
        ))

    return go.Figure(
        data=data,
        layout=go.Layout(
            autosize=True,
            height=750,
            margin=dict(l=0, r=0, t=0, b=0),
            showlegend=False,
            mapbox=dict(
                accesstoken=mapbox_access_token,
                center=dict(
                    lat=latInitial,
                    lon=lonInitial 
                ),
                bearing=bearing,
                zoom=zoom
            ),
        ),
    )

@app.callback(Output("table", "columns"),
              [Input("signal", "children")],
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
              Input('table', 'pagination_settings')],
              [State("signal", 'children'),
              State('problems-dropdown', 'value')])
def update_table_columns(columns, pagination_settings, df, problem):

    df = read_json(df)
    if problem == 'perc':
        df = df.sort_values(by='with_jam_total', ascending=False)
    
    return df.iloc[
        pagination_settings['current_page']*pagination_settings['page_size']:
        (pagination_settings['current_page'] + 1)*pagination_settings['page_size']
    ].to_dict('rows')




@app.server.before_first_request
def get_date_range():
    con = sa.create_engine(open(Path(__file__).parent / 'redshift_key.txt', 'r').read())



