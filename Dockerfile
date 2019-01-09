FROM python:3.6

# Set the working directory to /app
WORKDIR /app

COPY . /app

RUN pip3 install -r requirements.txt

# RUN pip3 install dash==0.19.0
# RUN pip3 install dash-renderer==0.11.1
# RUN pip3 install dash-html-components==0.8.0
# RUN pip3 install dash-core-components==0.14.0
# RUN pip3 install plotly
# RUN pip3 install pandas
# RUN pip3 install sqlalchemy
# RUN pip3 install pyyaml
# RUN apt-get install python-importlib
# RUN apt-get update
# RUN pip3 install psycopg2

# Expose a port 
RUN pip install -e .

EXPOSE 5000

# Run app.py when the container launches
CMD gunicorn src.slapdash.wsgi -w 3 -b 0.0.0.0:5000 