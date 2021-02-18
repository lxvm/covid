#!/usr/bin/env python3

# covid_plotter.py
# Written by Lorenzo Van Munoz
# Last programmed 18/02/2021

from csv import reader, writer
from codecs import iterdecode
from os.path import exists
from datetime import datetime
from urllib.request import urlopen

from bokeh.models import ColumnDataSource, CustomJS, Select, Slider, Button
from bokeh.models.widgets import Panel, Tabs
from bokeh.layouts import row, column, layout
from bokeh.plotting import figure, show
from bokeh.io import output_file

def import_data():
    output_file('covid_static.html')
    url = 'http://raw.githubusercontent.com/nytimes/covid-19-data/master/us-counties.csv'
    cache = '/home/lxvm/repos/covid/covid_data.csv'

    if not exists(cache):
        with urlopen(url) as html, open(cache, 'w', newline='') as csvfile:
            html = iterdecode(html, 'utf-8')
            data = reader(html)
            writer(csvfile).writerows(data)

    with open(cache, 'r') as csvfile:
        data = reader(csvfile)
        # We have imported the rows in the csv as lists
        # and need to wrangle the columns into dictionaries
        # for use in a ColumnDataSource

        # First row in csv gives column names
        colnames = next(data)
        filter = ['date', 'cases', 'deaths', 'state', 'county']
        df = {col:[] for col in colnames if col in filter}

        # Populate dataframe from csv
        for i, rrow in enumerate(data):

            for j, col in enumerate(rrow):
                if colnames[j] in filter:
                    key = colnames[j]
                    if key in ['date']:
                        df[colnames[j]].append(datetime(*[int(e) for e in col.split('-')]))
                    elif key in ['cases', 'deaths']:
                        if col.isnumeric():
                            df[key].append(float(col))
                        else: # Missing data as zero
                            df[key].append(0.)
                    else:
                        df[key].append(col)

    # create national aggregates
    df_national = {key:[] for key in ['date', 'cases', 'deaths']}
    for i, e in enumerate(df['date']):
        if e in df_national['date']:
            pos = df_national['date'].index(e)
            for key in ['cases', 'deaths']:
                df_national[key][pos] += df[key][i]
        else:
            for key in df_national.keys():
                df_national[key].append(df[key][i])
    return (df, df_national)


def make_plots(df, df_national):
    ### Begin Shared objects

    # Column Data Source (which can be filtered later)
    CDS_full = ColumnDataSource(df)

    # Shared options
    states = sorted(list(set(CDS_full.data['state'])))
    counties = sorted(list(set(CDS_full.data['county'])))
    metrics = ['cases', 'deaths']

    # Shared Widgets
    button = Button(label='Synchronize', button_type="success", sizing_mode='stretch_width')
    roll_avg = Slider(title='Rolling Average', value=1, start=1, end=14, step=1, sizing_mode='stretch_width')

    # Shared Callback code
    js_code_data = """
        let plot_x = []
        let plot_y = []
        let nDays = 0
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


        // Extra transformations
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

        // update ColumnDataSource
        plot.data['date'] = plot_x
        plot.data['metric'] = plot_y
        //console.log(plot_x, plot_y)
        plot.change.emit()
    """

    js_code_menu = """
        if (scale.value == 'national') {
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
        }
    """

    js_code_synchronize="""
        scale_2.value = scale_1.value
        state_2.value = state_1.value
        county_2.value = county_1.value
    """

    # Plotting size parameters

    aspect = 1
    widget_height = 100

    ### End shared objects


    ### Begin plot 1

    # Initial plot data

    CDS_plot_1 = ColumnDataSource({'date' : df_national['date'],
                                   'metric' : df_national[metrics[0]]})

    # Widgets
    menu_menu_1 = Select(title='menu 1', value='national', options=['national', 'state', 'county'], width=menu_width)
    state_menu_1 = Select(title='State 1', value='Alabama', options=states, visible=False, width=menu_width)
    county_menu_1 = Select(title='County 1', value='Abbeville', options=counties, visible=False, width=menu_width)
    metric_1 = Select(title="Metric 1", value=metrics[0], options=metrics, sizing_mode='both')
    method_1 = Select(title="Method 1", value='cumulative', options=['cumulative', 'difference'], sizing_mode='stretch_both')

    # Construct callback functions
    update_menu_1 = CustomJS(args=dict(scale=scale_menu_1,
                                       state=state_menu_1,
                                       county=county_menu_1,
                                       source=CDS_full,
                                      ),
                             code=js_code_menu,
                            )
    update_data_1 = CustomJS(args=dict(metric=metric_1,
                                       method=method_1,
                                       scale=scale_menu_1,
                                       state=state_menu_1,
                                       county=county_menu_1,
                                       plot=CDS_plot_1,
                                       source=CDS_full,
                                       avg=roll_avg,
                                      ),
                             code=js_code_data,
                            )

    # Callbacks
    scale_menu_1.js_on_change('value', update_menu_1)
    state_menu_1.js_on_change('value', update_menu_1)

    scale_menu_1.js_on_change('value', update_data_1)
    state_menu_1.js_on_change('value', update_data_1)
    county_menu_1.js_on_change('value', update_data_1)
    metric_1.js_on_change('value', update_data_1)
    method_1.js_on_change('value', update_data_1)

    # Create plot layout
    # linear metric 1
    linear_1 = figure(title='COVID-19 data_1', x_axis_label='date', y_axis_label='Cases',\
               x_axis_type="datetime", y_axis_type='linear', sizing_mode='stretch_both')
    linear_1.line(x='date', y='metric', source=CDS_plot_1)
    panel_linear_1 = Panel(child=linear_1, title='linear')
    # log metric 1
    log_1 = figure(title='COVID-19 data_1', x_axis_label='date', y_axis_label='Cases',\
               x_axis_type="datetime", y_axis_type='log', sizing_mode='stretch_both')
    log_1.line(x='date', y='metric', source=CDS_plot_1)
    panel_log_1 = Panel(child=log_1, title='log')
    # panel metric 1
    panels_1 = [panel_linear_1, panel_log_1]
    tabs_1 = Tabs(tabs=panels_1, aspect_ratio=aspect, sizing_mode='scale_both')
    column_1 = layout(tabs_1,
                      [method_1, metric_1],
                      [scale_menu_1, state_menu_1, county_menu_1],
                      sizing_mode='stretch_both',
                     )

    ### End plot 1


    ### Begin plot 2

    # Initial plot data
    CDS_plot_2 = ColumnDataSource({'date' : df_national['date'],
                                   'metric' : df_national[metrics[1]]})

    # Widgets
    scale_menu_2 = Select(title='Scale 2', value='national', options=['national', 'state', 'county'], sizing_mode='stretch_both')
    state_menu_2 = Select(title='state 2', value='Alabama', options=states, sizing_mode='stretch_both', visible=False)
    county_menu_2 = Select(title='County 2', value='Abbeville', options=counties, sizing_mode='stretch_both', visible=False)
    metric_2 = Select(title="Metric 2", value=metrics[1], options=metrics, sizing_mode='stretch_both')
    method_2 = Select(title="Method 2", value='cumulative', options=['cumulative', 'difference'], sizing_mode='stretch_both')

    # Construct callback functions
    update_menu_2 = CustomJS(args=dict(scale=scale_menu_2,
                                       state=state_menu_2,
                                       county=county_menu_2,
                                       source=CDS_full,
                                      ),
                             code=js_code_menu,
                            )
    update_data_2 = CustomJS(args=dict(metric=metric_2,
                                       method=method_2,
                                       scale=scale_menu_2,
                                       state=state_menu_2,
                                       county=county_menu_2,
                                       plot=CDS_plot_2,
                                       source=CDS_full,
                                       avg=roll_avg,
                                      ),
                             code=js_code_data,
                            )

    # Callbacks
    scale_menu_2.js_on_change('value', update_menu_2)
    state_menu_2.js_on_change('value', update_menu_2)

    scale_menu_2.js_on_change('value', update_data_2)
    state_menu_2.js_on_change('value', update_data_2)
    county_menu_2.js_on_change('value', update_data_2)
    metric_2.js_on_change('value', update_data_2)
    method_2.js_on_change('value', update_data_2)

    # Create plot layout
    # linear metric 2
    linear_2 = figure(title='COVID-19 data_2', x_axis_label='date', y_axis_label='Deaths',\
               x_axis_type="datetime", y_axis_type='linear', sizing_mode='stretch_both')
    linear_2.line(x='date', y='metric', source=CDS_plot_2)
    panel_linear_2 = Panel(child=linear_2, title='linear')
    # log metric 2
    log_2 = figure(title='COVID-19 data_2', x_axis_label='date', y_axis_label='Deaths',\
            x_axis_type="datetime", y_axis_type='log', sizing_mode='stretch_both')
    log_2.line(x='date', y='metric', source=CDS_plot_2)
    panel_log_2 = Panel(child=log_2, title='log')
    # panel metric 2
    panels_2 = [panel_linear_2, panel_log_2]
    tabs_2 = Tabs(tabs=panels_2, aspect_ratio=aspect, sizing_mode='scale_both')
    column_2 = layout(tabs_2,
                      [method_2, metric_2],
                      [scale_menu_2, state_menu_2, county_menu_2],
                      sizing_mode='stretch_both',
                     )

    ### End plot 2


    # Shared Callbacks
    roll_avg.js_on_change('value', update_data_1)
    roll_avg.js_on_change('value', update_data_2)
    button.js_on_click(CustomJS(args=dict(scale_1=scale_menu_1,
                                            state_1=state_menu_1,
                                            county_1=county_menu_1,
                                            scale_2=scale_menu_2,
                                            state_2=state_menu_2,
                                            county_2=county_menu_2,
                                           ),
                                  code=js_code_synchronize,
                                 )
                        )

    # Display
    display = layout([column_1, column_2],
                     [roll_avg, button],
                     sizing_mode='stretch_both',
                    )

    show(display)
    return


def main():
    make_plots(*import_data())
    return

if __name__=='__main__':
    main()
    raise SystemExit()
