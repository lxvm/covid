#!/usr/bin/env python3
"""
Uses Bokeh to make an interactive, static html
document displaying the latest NYT covid-19 data.

Written by Lorenzo Van Muñoz
Last updated 16/03/2021
"""

COMMAND_LINE_USAGE = """
python3 covid_plotter.py [OPTIONS]

DESCRIPTION:
    Uses Bokeh to make a covid-19 dashboard from latest NYT data.

OPTIONS:
    update      updates cached dataset if older than 1 day, then dashboard
    -v          verbose output
    -h, help    show this message and exit
"""


import os
import sys
import csv
import time
import json
import logging
from codecs import iterdecode
from datetime import datetime
from urllib.request import urlopen

from bokeh.models import ColumnDataSource, CustomJS, Select, Slider, Button
from bokeh.models.formatters import FuncTickFormatter
from bokeh.models.widgets import Panel, Tabs
from bokeh.plotting import figure, save
from bokeh.layouts import grid, gridplot
from bokeh.io import output_file


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(SCRIPT_DIR, 'covid_static.html')
CACHE_FILE = os.path.join(SCRIPT_DIR, 'covid_data.csv')
DATA_URL = 'http://raw.githubusercontent.com/nytimes/covid-19-data/master/us-counties.csv'


def download_data(data_url=DATA_URL, cache_file=CACHE_FILE):
    """Downloads the csv file from DATA_URL to CACHE_FILE.

    Keyword arguments:
    data_url -- str -- the url to the NYT covid-19 data repo (default DATA_URL)
    cache_file -- str -- a path to save the cache (default CACHE_FILE)
    """

    with urlopen(data_url) as html, open(cache_file, 'w', newline='') as csvfile:
        html = iterdecode(html, 'utf-8')
        data = csv.reader(html)
        csv.writer(csvfile).writerows(data)
    return


def import_data(update=None, data_url=DATA_URL, cache_file=CACHE_FILE):
    """Creates or updates the cached dataset.

    By default uses an existing cache.

    Keyword arguments:
    update -- bool -- only replaces cache if older than 1 day (default: None)
    data_url -- str -- the url to the NYT covid-19 data repo (default DATA_URL)
    cache_file -- str -- a path to save the cache (default: CACHE_FILE)
    """

    # Save dataset to cache because it is large
    if os.path.exists(cache_file):
        # Don't import new data unless 1 day/86400 seconds have passed
        # Since COVID numbers are only update daily
        logging.info('Cache found')
        if update and ((time.time() - os.path.getmtime(cache_file)) > 86400):
            logging.info('Updating cache')
            download_data()
        elif update:
            logging.info('Data already up to date')
        logging.info('Using cached data')
    else:
        if os.access(os.path.basename(cache_file), os.W_OK):
            logging.info('Saving data to cache located at ' + cache_file)
            download_data()
        else:
            logging.info('Please edit the cache directory in the script')
            raise PermissionError('%s is not writeable', os.path.basename(cache_file))
    return


def import_cache(cache_file=CACHE_FILE):
    """Reads cached NYT covid-19 dataset into a tuple of dictionaries.

    The pandas equivalent of this function is:
    df_full = pd.read_csv(CACHE_FILE)
    df_full['date'] = pd.to_datetime(df_full['date'])
    df_plot = df_full.loc[:, ['date', 'cases', 'deaths']].groupby('date').agg('sum').reset_index()
    df_plot = df_plot.join(df_plot[['cases', 'deaths']].shift(fill_value=0).add_prefix('cobweb_'))

    The first dictionary contains the entire dataset.
    Its key/value pairs are:
    date : list -- datetime
    state : list -- str
    county : list -- str
    cases : list -- float
    deaths : list -- float
    Note: all lists must have equal length and elements of the given type.

    The second dictionary contains a plottable subset (default: national aggregates).
    Its key/value pairs are:
    date : list -- datetime
    cases : list -- float
    deaths : list -- float
    cobweb_cases: list -- float
    cobweb_deaths: list -- float
    Note: in a plottable subset, each date appears once in the time-series data.
    Note: all lists must have equal length and elements of the given type.

    Keyword arguments:
    cache_file -- str -- a path to read the cache (default: CACHE_FILE)

    Returns:
    tuple -- (dict, dict) -- the full and plottable datasets, respectively
    """

    logging.info('Reading cache')
    # Read in dataset from cache
    with open(cache_file, 'r') as csvfile:
        data = csv.reader(csvfile)
        # We have imported the rows in the csv as lists
        # and need to wrangle the columns into dictionaries
        # for use in a ColumnDataSource

        # First row in csv gives column names
        colnames = next(data)
        filter = ['date', 'cases', 'deaths', 'state', 'county']
        df_full = {col:[] for col in colnames if col in filter}

        # Populate dataframe from csv
        for i, rrow in enumerate(data):
            for j, col in enumerate(rrow):
                if colnames[j] in filter:
                    key = colnames[j]
                    if key in ['date']:
                        df_full[colnames[j]].append(datetime(*[int(e) for e in col.split('-')]))
                    elif key in ['cases', 'deaths']:
                        if col.isnumeric():
                            df_full[key].append(float(col))
                        else: # Missing data as zero
                            df_full[key].append(0.)
                    else:
                        df_full[key].append(col)

    # create national aggregates
    df_plot = {key:[] for key in ['date', 'cases', 'deaths']}
    for i, e in enumerate(df_full['date']):
        if e in df_plot['date']:
            pos = df_plot['date'].index(e)
            for key in ['cases', 'deaths']:
                df_plot[key][pos] += df_full[key][i]
        else:
            for key in df_plot.keys():
                df_plot[key].append(df_full[key][i])
    df_plot['cobweb_cases'] = [0] + df_plot['cases'][:-1]
    df_plot['cobweb_deaths'] = [0] + df_plot['deaths'][:-1]

    return (df_full, df_plot)


def make_plots(df_full, df_plot):
    """Builds the Bokeh plot dashboard.

    Uses the Bokeh package to create the plots in the dashboard.
    Client-side html interactivity is provided by Bokeh's Javascript callbacks.

    Required arguments:
    df_full -- dict or pd.dataframe -- containing the whole NYT dataset
    df_plot -- dict or pd.dataframe -- contains a plottable subset of dataset
    Both objects will be passed as inputs to ColumnDataSources
    The expected keys/columns of df_full are:
    date, state, county, cases, deaths
    The expected keys/columns in each element of df_plot are:
    date, cases, deaths, cobweb_cases, cobweb_deaths

    Returns:
    bokeh.layouts.grid -- can be saved or used in jupyter notebook
    """
    ### Begin Shared objects

    # Column Data Source (which can be filtered later)
    CDS_full = ColumnDataSource(df_full)

    # Shared options
    states = sorted(list(set(CDS_full.data['state'])))
    counties = sorted(list(set(CDS_full.data['county'])))
    metrics = ['cases', 'deaths']

    # Shared Widgets
    button = Button(label='Synchronize', button_type="success", sizing_mode='stretch_width')
    roll_avg = Slider(title='Rolling Average', value=1, start=1, end=14, step=1, sizing_mode='stretch_width')

    # Shared Callback code
    js_code_menu = """
        if (scale.value === 'national') {
            state.visible = false
            county.visible = false
        }

        else if (scale.value === 'state') {
            state.visible = true
            county.visible = false
        }

        else if (scale.value === 'county') {
            state.visible = true
            county.visible = true

            // filter the state and then unique counties
            function oneState(value, index, self) {
                return source.data['state'][index] === state.value
            }

            function onlyUnique(value, index, self) {
                return self.indexOf(value) === index;
            }

            let counties_in_state = source.data['county'].filter(oneState).filter(onlyUnique).sort()

            if (counties_in_state.indexOf(county.value) === -1) {
                county.value = counties_in_state[0]
            }
            county.options = counties_in_state
        };
    """

    js_code_data = """
        let plot_x = []
        let plot_y = []
        let plot_z = []
        let nDays = -1
        let yesterdate = 0

        function mask (x) {
            if (scale.value === 'national') {
                return true
            }
            else if (scale.value === 'state') {
                return source.data['state'][x] === state.value
            }
            else { // if (scale.value === 'county') {
                return source.data['county'][x] === county.value
            }
        }

        // this works because it knows the dates are in increasing order
        for (let i=0; i < source.data['date'].length; i++) {
            if (mask(i)) { // filter by scale
                if (yesterdate < source.data['date'][i]) {
                    plot_x.push(source.data['date'][i])
                    plot_y.push(source.data[metric.value][i])
                    yesterdate = source.data['date'][i]
                    nDays += 1
                }
                else { // aggregate values with the same date
                    plot_y[nDays] += source.data[metric.value][i]
                }
            }
        }


        // Extra transformations (edge cases are the first few days)
        // Except for edge cases, you can show that the order of
        // difference and average doesn't matter
        if (method.value === 'difference') {
            // Converts from raw cumulative data
            for (let i=plot_x.length-1; i > 0; i--) {
                plot_y[i] -= plot_y[i-1]
            }
        }
        // Rolling Average (uniform backwards window (avg over last x days))
        if (avg.value > 1) {
            for (let i=plot_x.length-1; i > avg.value-1; i--) {
                plot_y[i] = plot_y.slice(i-avg.value, i+1).reduce((a, b) => a + b, 0) / (avg.value+1)
            }
        }

        // cobweb plotting
        plot_z = plot_y.slice()
        plot_z.pop()
        plot_z.unshift(0)

        // update ColumnDataSource
        plot.data['date'] = plot_x
        plot.data['metric'] = plot_y
        plot.data['cobweb'] = plot_z
        plot.change.emit();
    """

    js_code_label="""
    if (scale.value === 'national') {
        linear_title.text = 'NYT COVID-19 data: National'
        log_title.text = 'NYT COVID-19 data: National'
        cobweb_title.text = 'NYT COVID-19 data: National'
    }
    else if (scale.value === 'state') {
        linear_title.text = 'NYT COVID-19 data: State: '+ state.value
        log_title.text = 'NYT COVID-19 data: State: ' + state.value
        cobweb_title.text = 'NYT COVID-19 data: State: ' + state.value
    }
    else { // if (scale.value === 'county') {
        linear_title.text = 'NYT COVID-19 data: County: ' + county.value
        log_title.text = 'NYT COVID-19 data: County: ' + county.value
        cobweb_title.text = 'NYT COVID-19 data: County: ' + state.value
    }

    let method_name =''
    if (method.value === 'difference') {
        method_name = 'New '
    }
    else { // if (method.value === 'cumulative')
        method_name = 'Cumulative '
    }
    linear_y.axis_label = method_name + metric.value
    log_y.axis_label = method_name + metric.value
    cobweb_x.axis_label = method_name + metric.value + ' today'
    cobweb_y.axis_label = method_name + metric.value + ' tomorrow'
    ;
    """

    js_code_synchronize="""
        scale_2.value = scale_1.value
        state_2.value = state_1.value
        county_2.value = county_1.value
    ;
    """

    ### End shared objects


    ### Begin combined plots

    # Create lists indexed by plot

    CDS_plots = []

    scale_menus = []
    state_menus = []
    county_menus = []
    metric_menus = []
    method_menus = []
    widget_lists = []
    widget_layouts = []

    linear_plots = []
    log_plots = []
    cobweb_plots = []
    linear_panels = []
    log_panels = []
    cobweb_panels = []
    plot_lists = []
    panel_lists = []
    tab_lists = []

    update_menus = []
    update_datas = []

    # Create a plot for the desired number of plots
    N = 2
    # If N > 2, the following items are affected:
    # metrics
    # js_code_synchronize
    for i in range(N):

        # Initial plot data

        CDS_plots.append(
            ColumnDataSource(
                {
                'date' : df_plot['date'],
                'metric' : df_plot[metrics[i]],
                'cobweb' : df_plot['cobweb_' + metrics[i]],
                }
            )
        )

        # Widgets

        scale_menus.append(
            Select(
                title='Scale ' + str(i + 1),
                value='national',
                options=['national', 'state', 'county'],
            )
        )
        state_menus.append(
            Select(
                title='State ' + str(i + 1),
                value=states[0],
                options=states,
                visible=False,
            )
        )
        county_menus.append(
            Select(
                title='County ' + str(i + 1),
                value=counties[0],
                options=counties,
                visible=False,
            )
        )
        metric_menus.append(
            Select(
                title="Metric " + str(i + 1),
                value=metrics[i],
                options=metrics,
            )
        )
        method_menus.append(
            Select(
                title="Method " + str(i + 1),
                value='cumulative',
                options=['cumulative', 'difference'],
            )
        )
        widget_lists.append(
            [
            scale_menus[i],
            state_menus[i],
            county_menus[i],
            metric_menus[i],
            method_menus[i],
            ]
        )
        widget_layouts.append(
            [
            [method_menus[i], metric_menus[i]],
            [scale_menus[i], state_menus[i], county_menus[i]],
            ]
        )

        # Create plot layout
        # linear plot
        linear_plots.append(
            figure(
                title='NYT COVID-19 data: National',
                x_axis_label='Date',
                y_axis_label='Cumulative cases',
                x_axis_type='datetime',
                y_axis_type='linear',
            )
        )
        linear_plots[i].yaxis.formatter = FuncTickFormatter(code="return tick.toExponential();")
        linear_plots[i].line(x='date', y='metric', source=CDS_plots[i])
        linear_panels.append(
            Panel(
                child=linear_plots[i],
                title='linear',
            )
        )
        # log plot
        log_plots.append(
            figure(
                title='NYT COVID-19 data: National',
                x_axis_label='Date',
                y_axis_label='Cumulative cases',
                x_axis_type='datetime',
                y_axis_type='log',
            )
        )
        log_plots[i].line(x='date', y='metric', source=CDS_plots[i])
        log_panels.append(
            Panel(
                child=log_plots[i],
                title='log',
            )
        )
        # cobweb plot
        cobweb_plots.append(
            figure(
                title='NYT COVID-19 data: National',
                x_axis_label='Cumulative cases today',
                y_axis_label='Cumulative cases tomorrow',
                x_axis_type='linear',
                y_axis_type='linear',
            )
        )
        cobweb_plots[i].xaxis.formatter = FuncTickFormatter(code="return tick.toExponential();")
        cobweb_plots[i].yaxis.formatter = FuncTickFormatter(code="return tick.toExponential();")
        cobweb_plots[i].step(x='cobweb', y='metric', source=CDS_plots[i])
        cobweb_plots[i].line(x='cobweb', y='cobweb', source=CDS_plots[i], line_color='red')
        cobweb_panels.append(
            Panel(
                child=cobweb_plots[i],
                title='cobweb',
            )
        )
        # collect plots, panels, tabs
        plot_lists.append(
            [
            linear_plots[i],
            log_plots[i],
            cobweb_plots[i],
            ]
        )
        panel_lists.append(
            [
            linear_panels[i],
            log_panels[i],
            cobweb_panels[i],
            ]
        )
        tab_lists.append(
            Tabs(tabs=panel_lists[i])
        )

        # Construct callback functions
        update_menus.append(
            CustomJS(
                args=dict(
                    scale=scale_menus[i],
                    state=state_menus[i],
                    county=county_menus[i],
                    source=CDS_full,
                ),
                code=js_code_menu
            )
        )
        update_datas.append(
            CustomJS(
                args=dict(
                    metric=metric_menus[i],
                    method=method_menus[i],
                    scale=scale_menus[i],
                    state=state_menus[i],
                    county=county_menus[i],
                    plot=CDS_plots[i],
                    source=CDS_full,
                    avg=roll_avg,
                    linear_title=linear_plots[i].title,
                    linear_x=linear_plots[i].xaxis[0],
                    linear_y=linear_plots[i].yaxis[0],
                    log_title=log_plots[i].title,
                    log_x=log_plots[i].xaxis[0],
                    log_y=log_plots[i].yaxis[0],
                    cobweb_title=cobweb_plots[i].title,
                    cobweb_x=cobweb_plots[i].xaxis[0],
                    cobweb_y=cobweb_plots[i].yaxis[0],
                ),
                code=js_code_data+js_code_label
            )
        )

        # Callbacks
        scale_menus[i].js_on_change('value', update_menus[i])
        state_menus[i].js_on_change('value', update_menus[i])

        scale_menus[i].js_on_change('value', update_datas[i])
        state_menus[i].js_on_change('value', update_datas[i])
        county_menus[i].js_on_change('value', update_datas[i])
        metric_menus[i].js_on_change('value', update_datas[i])
        method_menus[i].js_on_change('value', update_datas[i])


    ### End combined plots


    # Shared Callbacks
    menu_dict = {}
    for i in range(N):
        roll_avg.js_on_change('value', update_datas[i])
        # store all menus to later be synchronized
        menu_dict['scale_' + str(i + 1)] = scale_menus[i]
        menu_dict['state_' + str(i + 1)] = state_menus[i]
        menu_dict['county_' + str(i + 1)] = county_menus[i]
    button.js_on_click(
        CustomJS(
            args=menu_dict,
            code=js_code_synchronize,
        )
    )

    # Display options
    for i in range(N):
        for e in widget_lists[i]:
            e.height = 50
            e.width = 100
            e.sizing_mode = 'fixed'
        for e in plot_lists[i]:
            e.sizing_mode = 'scale_both'
            e.min_border_bottom = 80
    for e in tab_lists:
        e.aspect_ratio = 1
        e.sizing_mode = 'scale_height'
    for e in [button, roll_avg]:
        e.sizing_mode = 'stretch_width'
    # Display arrangement
    display = grid(
        [
        gridplot([tab_lists]),
        [button, roll_avg],
        widget_layouts,
        ],
        sizing_mode='stretch_both',
    )
    return(display)


def main(update=None):
    """Imports dataset and builds dashboard."""

    # Command line options
    if len(sys.argv) > 1:
        if 'help' in sys.argv or '-h' in sys.argv:
            print(COMMAND_LINE_USAGE)
            return
        if 'update' in sys.argv:
            update = True
        if '-v' in sys.argv:
            logging.basicConfig(level=logging.INFO)

    global CACHE_FILE, OUTPUT_FILE, DATA_URL

    # Import optional JSON configuration
    if os.path.exists(os.path.join(SCRIPT_DIR, 'covid_plotter.json')):
        dirs = json.load(open(os.path.join(SCRIPT_DIR, 'covid_plotter.json'), 'r'))
        if 'cache' in dirs.keys():
            CACHE_FILE = dirs['cache']
        if 'output' in dirs.keys():
            OUTPUT_FILE = dirs['output']
        if 'data' in dirs.keys():
            DATA_URL = dirs['data']

    logging.info('DATA_URL: %s', DATA_URL)
    logging.info('CACHE_FILE: %s', CACHE_FILE)
    logging.info('OUTPUT_FILE: %s', OUTPUT_FILE)

    import_data(update, DATA_URL, CACHE_FILE)
    cache = import_cache(CACHE_FILE)
    logging.info('Building plots')
    display = make_plots(*cache)
    logging.info('Saving output')
    output_file(OUTPUT_FILE)
    save(display)
    return

if __name__=='__main__':
    main()
    raise SystemExit()
