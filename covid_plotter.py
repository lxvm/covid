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
from bokeh.models.formatters import FuncTickFormatter
from bokeh.models.widgets import Panel, Tabs
from bokeh.plotting import figure, show
from bokeh.layouts import layout, gridplot
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


    ### Begin plot 1

    # Initial plot data

    CDS_plot_1 = ColumnDataSource({'date' : df_national['date'],
                                   'metric' : df_national[metrics[0]],
                                   'cobweb' : [0] + df_national[metrics[0]][:-1],
                                 })

    # Widgets
    scale_menu_1 = Select(title='Scale 1', value='national', options=['national', 'state', 'county'])
    state_menu_1 = Select(title='State 1', value=states[0], options=states, visible=False)
    county_menu_1 = Select(title='County 1', value=counties[0], options=counties, visible=False)
    metric_1 = Select(title="Metric 1", value=metrics[0], options=metrics)
    method_1 = Select(title="Method 1", value='cumulative', options=['cumulative', 'difference'])
    widget_list_1 = [scale_menu_1,
                     state_menu_1,
                     county_menu_1,
                     metric_1,
                     method_1,
                    ]
    widgets_1 = layout([[method_1, metric_1],
                 [scale_menu_1, state_menu_1, county_menu_1],])

    # Create plot layout
    # linear metric 1
    linear_1 = figure(title='NYT COVID-19 data: National', x_axis_label='Date', y_axis_label='Cumulative cases',\
               x_axis_type='datetime', y_axis_type='linear')
    linear_1.yaxis.formatter = FuncTickFormatter(code="return tick.toExponential();")
    linear_1.line(x='date', y='metric', source=CDS_plot_1)
    panel_linear_1 = Panel(child=linear_1, title='linear')
    # log metric 1
    log_1 = figure(title='NYT COVID-19 data: National', x_axis_label='Date', y_axis_label='Cumulative cases',\
            x_axis_type='datetime', y_axis_type='log')
    log_1.line(x='date', y='metric', source=CDS_plot_1)
    panel_log_1 = Panel(child=log_1, title='log')
    # cobweb metric 1
    cobweb_1 = figure(title='NYT COVID-19 data: National', x_axis_label='Cumulative cases today', y_axis_label='Cumulative cases tomorrow',\
            x_axis_type='linear', y_axis_type='linear')
    cobweb_1.xaxis.formatter = FuncTickFormatter(code="return tick.toExponential();")
    cobweb_1.yaxis.formatter = FuncTickFormatter(code="return tick.toExponential();")
    cobweb_1.step(x='cobweb', y='metric', source=CDS_plot_1)
    cobweb_1.line(x='cobweb', y='cobweb', source=CDS_plot_1, line_color='red')
    panel_cobweb_1 = Panel(child=cobweb_1, title='cobweb')
    # panel metric 1
    panels_1 = [panel_linear_1, panel_log_1, panel_cobweb_1,]
    tabs_1 = Tabs(tabs=panels_1)
    plot_list_1 = [linear_1, log_1, cobweb_1,]

    # Construct callback functions
    update_menu_1 = CustomJS(args=dict(scale=scale_menu_1,
                                       state=state_menu_1,
                                       county=county_menu_1,
                                       source=CDS_full,
                                      ),
                             code=js_code_menu)
    update_data_1 = CustomJS(args=dict(metric=metric_1,
                                       method=method_1,
                                       scale=scale_menu_1,
                                       state=state_menu_1,
                                       county=county_menu_1,
                                       plot=CDS_plot_1,
                                       source=CDS_full,
                                       avg=roll_avg,
                                       linear_title=linear_1.title,
                                       linear_x=linear_1.xaxis[0],
                                       linear_y=linear_1.yaxis[0],
                                       log_title=log_1.title,
                                       log_x=log_1.xaxis[0],
                                       log_y=log_1.yaxis[0],
                                       cobweb_title=cobweb_1.title,
                                       cobweb_x=cobweb_1.xaxis[0],
                                       cobweb_y=cobweb_1.yaxis[0],
                                      ),
                             code=js_code_data+js_code_label)

    # Callbacks
    scale_menu_1.js_on_change('value', update_menu_1)
    state_menu_1.js_on_change('value', update_menu_1)

    scale_menu_1.js_on_change('value', update_data_1)
    state_menu_1.js_on_change('value', update_data_1)
    county_menu_1.js_on_change('value', update_data_1)
    metric_1.js_on_change('value', update_data_1)
    method_1.js_on_change('value', update_data_1)

    ### End plot 1


    ### Begin plot 2

    # Initial plot data
    CDS_plot_2 = ColumnDataSource({'date' : df_national['date'],
                                   'metric' : df_national[metrics[1]],
                                   'cobweb' : [0] + df_national[metrics[1]][:-1],
                                  })

    # Widgets
    scale_menu_2 = Select(title='Scale 2', value='national', options=['national', 'state', 'county'])
    state_menu_2 = Select(title='State 2', value=states[0], options=states, visible=False)
    county_menu_2 = Select(title='County 2', value=counties[0], options=counties, visible=False)
    metric_2 = Select(title="Metric 2", value=metrics[1], options=metrics)
    method_2 = Select(title="Method 2", value='cumulative', options=['cumulative', 'difference'])
    widget_list_2 = [scale_menu_2,
                     state_menu_2,
                     county_menu_2,
                     metric_2,
                     method_2,
                    ]
    widgets_2 = layout([[method_2, metric_2],
                        [scale_menu_2, state_menu_2, county_menu_2],])

    # Create plot layout
    # linear metric 2
    linear_2 = figure(title='NYT COVID-19 data: National', x_axis_label='Date', y_axis_label='Cumulative deaths',\
               x_axis_type="datetime", y_axis_type='linear')
    linear_2.yaxis.formatter = FuncTickFormatter(code="return tick.toExponential();")
    linear_2.line(x='date', y='metric', source=CDS_plot_2)
    panel_linear_2 = Panel(child=linear_2, title='linear')
    # log metric 2
    log_2 = figure(title='NYT COVID-19 data: National', x_axis_label='Date', y_axis_label='Cumulative Deaths',\
            x_axis_type="datetime", y_axis_type='log')
    log_2.line(x='date', y='metric', source=CDS_plot_2)
    panel_log_2 = Panel(child=log_2, title='log')
    # cobweb metric 2
    cobweb_2 = figure(title='NYT COVID-19 data: National', x_axis_label='Cumulative cases today', y_axis_label='Cumulative cases tomorrow',\
            x_axis_type='linear', y_axis_type='linear')
    cobweb_2.xaxis.formatter = FuncTickFormatter(code="return tick.toExponential();")
    cobweb_2.yaxis.formatter = FuncTickFormatter(code="return tick.toExponential();")
    cobweb_2.step(x='cobweb', y='metric', source=CDS_plot_2)
    cobweb_2.line(x='cobweb', y='cobweb', source=CDS_plot_2, line_color='red', )
    panel_cobweb_2 = Panel(child=cobweb_2, title='cobweb')
    # panel metric 2
    panels_2 = [panel_linear_2, panel_log_2, panel_cobweb_2,]
    tabs_2 = Tabs(tabs=panels_2)
    plot_list_2 = [linear_2, log_2, cobweb_2,]

    # Construct callback functions
    update_menu_2 = CustomJS(args=dict(scale=scale_menu_2,
                                       state=state_menu_2,
                                       county=county_menu_2,
                                       source=CDS_full,
                                      ),
                             code=js_code_menu)
    update_data_2 = CustomJS(args=dict(metric=metric_2,
                                       method=method_2,
                                       scale=scale_menu_2,
                                       state=state_menu_2,
                                       county=county_menu_2,
                                       plot=CDS_plot_2,
                                       source=CDS_full,
                                       avg=roll_avg,
                                       linear_title=linear_2.title,
                                       linear_x=linear_2.xaxis[0],
                                       linear_y=linear_2.yaxis[0],
                                       log_title=log_2.title,
                                       log_x=log_2.xaxis[0],
                                       log_y=log_2.yaxis[0],
                                       cobweb_title=cobweb_2.title,
                                       cobweb_x=cobweb_2.xaxis[0],
                                       cobweb_y=cobweb_1.yaxis[0],
                                      ),
                             code=js_code_data+js_code_label)

    # Callbacks
    scale_menu_2.js_on_change('value', update_menu_2)
    state_menu_2.js_on_change('value', update_menu_2)

    scale_menu_2.js_on_change('value', update_data_2)
    state_menu_2.js_on_change('value', update_data_2)
    county_menu_2.js_on_change('value', update_data_2)
    metric_2.js_on_change('value', update_data_2)
    method_2.js_on_change('value', update_data_2)

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
    for e in widget_list_1 + widget_list_2:
        e.height = 50
        e.width = 100
        e.sizing_mode = 'fixed'
    for e in plot_list_1 + plot_list_2:
        e.sizing_mode = 'scale_both'
        e.min_border_bottom = 80
    for e in [tabs_1, tabs_2]:
        e.aspect_ratio = 1
        e.sizing_mode = 'scale_both'
    for e in [widgets_1, widgets_2]:
        e.sizing_mode = 'stretch_both'
    for e in [button, roll_avg]:
        e.sizing_mode = 'stretch_width'
    display = gridplot([tabs_1, tabs_2,
                        button, roll_avg,
                        widgets_1, widgets_2,
                       ], ncols=2, sizing_mode='stretch_both')

    show(display)

    return


def main():
    make_plots(*import_data())
    return

if __name__=='__main__':
    main()
    raise SystemExit()
