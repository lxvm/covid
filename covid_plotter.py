#!/usr/bin/env python3

# covid_plotter.py
# Written by Lorenzo Van Munoz
# Last programmed 16/02/2021

from csv import reader
from codecs import iterdecode
from datetime import datetime
from urllib.request import urlopen

from bokeh.models import ColumnDataSource, CustomJS, Select, Slider
from bokeh.models.widgets import Panel, Tabs
from bokeh.plotting import figure, show
from bokeh.layouts import row, column
from bokeh.io import output_file

def main():
    output_file('covid_static.html')
    url = "http://raw.githubusercontent.com/nytimes/covid-19-data/master/us-counties.csv"

    with urlopen(url) as html:
        html = iterdecode(html, 'utf-8')
        data = reader(html)
        
        # We have imported the rows in the csv as lists
        # and need to wrangle the columns into dictionaries
        # for use in a ColumnDataSource
        
        # First row in csv gives column names
        colnames = next(data)
        df = {col:[] for col in colnames}
        
        # Populate dataframe from csv
        for index, item in enumerate(data):
            for i, key in enumerate(df.keys()):
                if key in ['date']:
                    df[key].append(datetime(*[int(e) for e in item[i].split('-')]))
                elif key in ['cases', 'deaths']:
                    if item[i].isnumeric():
                        df[key].append(float(item[i]))
                    else: # Missing data
                        df[key].append(0.)
                else:
                    df[key].append(item[i])
        df['index'] = list(range(len(df['date'])))

    # create national aggregates
    df_national = {'index':[], 'date':[], 'metric_1':[], 'metric_2':[]}
    for i, e in enumerate(df['date']):
        if e in df_national['date']:
            pos = df_national['date'].index(e)
            df_national['metric_1'][pos] += df['cases'][i]
            df_national['metric_2'][pos] += df['deaths'][i]
        else:
            df_national['index'].append(len(df_national['index']))
            df_national['date'].append(df['date'][i])
            df_national['metric_1'].append(df['cases'][i])
            df_national['metric_2'].append(df['deaths'][i])

    # Create Column Date Source for each aggregate (which can be filtered later)
    CDS_full = ColumnDataSource(df)
    # Chose initial plot data
    CDS_plot = ColumnDataSource(df_national)

    #create plot layouts
    #linear metric 1
    p1 = figure(title='COVID-19 data', x_axis_label='date', y_axis_label='Cumulative Cases',\
               plot_width=400, plot_height=300, x_axis_type="datetime", y_axis_type='linear')
    line_p1 = p1.line(x='date', y='metric_1', source=CDS_plot)

    panel_p1 = Panel(child=p1, title='linear')

    #log metric 1
    p2 = figure(title='COVID-19 data', x_axis_label='date', y_axis_label='Cumulative Cases',\
               plot_width=400, plot_height=300, x_axis_type="datetime", y_axis_type='log')

    line_p2 = p2.line(x='date', y='metric_1', source=CDS_plot)

    panel_p2 = Panel(child=p2, title='log')

    #panel metric 1
    panels_p = [panel_p1, panel_p2]

    #linear metric 2
    q1 = figure(title='COVID-19 data', x_axis_label='date', y_axis_label='Cumulative Deaths',\
               plot_width=400, plot_height=300, x_axis_type="datetime", y_axis_type='linear')

    line_q1 = q1.line(x='date', y='metric_2', source=CDS_plot)

    panel_q1 = Panel(child=q1, title='linear')

    #log metric 2
    q2 = figure(title='COVID-19 data', x_axis_label='date', y_axis_label='Cumulative Deaths',\
               plot_width=400, plot_height=300, x_axis_type="datetime", y_axis_type='log')

    line_q2 = q2.line(x='date', y='metric_2', source=CDS_plot)

    panel_q2 = Panel(child=q2, title='log')

    #panel metric 2
    panels_q = [panel_q1, panel_q2]
        
    tabs_p = Tabs(tabs=panels_p)
    tabs_q = Tabs(tabs=panels_q)


    # Widgets
    metric_1 = Select(title="Metric 1", value='cases', options=['cases', 'deaths'], visible=False)
    metric_2 = Select(title="Metric 2", value='deaths', options=['cases', 'deaths'], visible=False)

    method_1 = Select(title="Method 1", value='cumulative', options=['cumulative', 'difference'])
    method_2 = Select(title="Method 2", value='cumulative', options=['cumulative', 'difference'])

    roll_avg = Slider(title='Rolling Average', value=1, start=1, end=14, step=1)

    scale_menu = Select(title='Scale', value='national', options=['national', 'state', 'county'])

    states = sorted(list(set(CDS_full.data['state'])))
    state_menu = Select(title='State', value='Alabama', options=states, visible=False)

    counties = sorted(list(set(CDS_full.data['county'])))
    county_menu = Select(title='County', value='Abbeville', options=counties, visible=False)

    # Callback code
    update_data = CustomJS(args=dict(CDS_plot=CDS_plot, 
                                     CDS_full=CDS_full, 
                                     m_1=metric_1,
                                     m_2=metric_2,
                                     me_1=method_1,
                                     me_2=method_2,
                                     avg=roll_avg,
                                     scale=scale_menu,
                                     state=state_menu, 
                                     county=county_menu),
                           code="""
        let full_data = CDS_full.data
        let index = []
        let dates = []
        let metric_1 = []
        let metric_2 = []
        let pos = 0
        let count = 0
        
        // Aggregate data
        for (let i = 0; i < full_data['date'].length;  i++) { //
            if (scale.value === 'national') {
                // console.log(i, full_data['state'][i], full_data['county'][i])
                update_data(i)
            }
            else if (scale.value === 'state' && full_data['state'][i] === state.value) {
                // console.log(i, full_data['county'][i])
                update_data(i)
            }
            else if (scale.value === 'county' && full_data['county'][i] === county.value) {
                // console.log(i)
                update_data(i)
            }
        }
        
        function update_data(i) {
            pos = dates.indexOf(full_data['date'][i])
            // console.log(pos, count, full_data['date'][i])
            
            if (count > pos && pos > -1) {
                // If a date is repeated, aggregate
                if (isNaN(full_data[m_1.value][i])) {}
                else {
                    metric_1[pos] += full_data[m_1.value][i]
                }
                if (isNaN(full_data[m_2.value][i])) {}
                else {
                    metric_2[pos] += full_data[m_2.value][i]
                }
            }
            else { // overwrite the old data
                index[count] = count
                dates[count] = full_data['date'][i]
                if (isNaN(full_data[m_1.value][i])) {}
                else {
                    metric_1[count] = full_data[m_1.value][i]
                }
                if (isNaN(full_data[m_2.value][i])) {}
                else {
                    metric_2[count] = full_data[m_2.value][i]
                }
                count += 1
            }
        }
        
        // Extra transformations
        if (me_1.value === 'difference') { // Assumes the input is cumulative
            for (let i=index.length-1; i > 0; i--) {
                metric_1[i] -= metric_1[i-1]
            } 
        }
        if (me_2.value === 'difference') { // Assumes the input is cumulative
            for (let i=index.length-1; i > 0; i--) {
                metric_2[i] -= metric_2[i-1]
            } 
        }
        // Rolling Average (uniform backwards window (avg over last x days))
        if (avg.value > 1) {
            for (let i=index.length-1; i > avg.value-1; i--) { // a for loop crashes :/
                metric_1[i] = metric_1.slice(i-avg.value, i+1).reduce((a, b) => a + b, 0) / (avg.value+1)
                metric_2[i] = metric_2.slice(i-avg.value, i+1).reduce((a, b) => a + b, 0) / (avg.value+1)
            } 
        }
        
        // update ColumnDataSource
        CDS_plot.data['index'] = index
        CDS_plot.data['date'] = dates
        CDS_plot.data['metric_1'] = metric_1
        CDS_plot.data['metric_2'] = metric_2
        
        CDS_plot.change.emit()
    """)

    update_menu = CustomJS(args=dict(scale=scale_menu, 
                                     state=state_menu, 
                                     county=county_menu, 
                                     CDS_full=CDS_full), 
                           code="""
        let source = CDS_full.data
        if (scale.value == 'national') {
            state.visible = false
            county.visible = false
        }  
        if (scale.value === 'state') {
            state.visible = true
            county.visible = false
        }
        if (scale.value === 'county') {
            state.visible = true
            county.visible = true
            
            // filter the state and then unique counties
            function oneState(value, index, self) {
                return source['state'][index] === state.value
            }
            
            function onlyUnique(value, index, self) {
                return self.indexOf(value) === index;
            }
            
            let counties_in_state = source['county'].filter(oneState).filter(onlyUnique).sort()
            
            if (counties_in_state.indexOf(county.value) === -1) {
                county.value = counties_in_state[0]
            }
            county.options = counties_in_state
        }
    """)

    # Callbacks
    scale_menu.js_on_change('value', update_menu)
    scale_menu.js_on_change('value', update_data)

    state_menu.js_on_change('value', update_menu)
    state_menu.js_on_change('value', update_data)

    county_menu.js_on_change('value', update_data)

    method_1.js_on_change('value', update_data) 
    method_2.js_on_change('value', update_data)

    roll_avg.js_on_change('value', update_data)


    # TODO: add widgets/callbacks for smoothing or looking at day-to day differences
    # and update plot labels

    # Display
    layout = column(row(tabs_p, tabs_q), row(metric_1, metric_2), row(method_1, method_2, roll_avg), row(scale_menu, state_menu, county_menu))

    show(layout)

if __name__=='__main__':
    main()
    raise SystemExit()
