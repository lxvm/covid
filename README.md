# covid

Interactive visualization from NYT statistics

<span style="color:blue">*New!*</span>: Visit the plotter 
[here](https://www.its.caltech.edu/~lvanmuno/covid_static.html)

![New York Times Dashboard](example.jpeg)

## Summary 

The COVID-19 pandemic has been devastating human life around the globe for over
a year now.
There is no way to express this tragedy in numerical figures, but it is important
to get the facts right so that the data allow informed decisions for the public
good.
The New York Times US county data set provides an excellent example of timely
data collection and reporting.

Interactive visualizations of large datasets can be valuable for exploring and 
sharing the data with others.
I share this project as an example of how you might make a COVID-19 dashboard in
python using the bokeh package.

[Bokeh](bokeh.org) is a python package that provides interactive plotting abilities
with modern web technology (nodejs).
Interactions can be programmed using one of several interfaces:
- Javascript callbacks: these can run independently in your web browser.
- Python callbacks: these can run in a bokeh server or in a jupyter notebook.
`covid_plotter.py` is an example of the former, and `covid_analysis.ipynb`
is an example of the latter.
The benefit of the former approach is that it can be embedded into a static html
page and published on a website rather effortlessly to be shared more easily.

Unfortunately, because the dataset only gets larger and larger I am just sharing
the code you need to create the dashboard yourself.

## Descriptions

- `covid_plotter.py` is a module with command-line-interface to create the
dashboard as static html. Run using `python3 covid_plotter.py [OPTIONS]`.
  - Requires: bokeh
- `covid_plotter.ipynb` is a jupyter notebook interface to `covid_plotter.py`.
  - Requires: bokeh, pandas, watermark (Hint: read the beginning of the notebook.)
- `covid_analysis.ipynb` was a midterm project for MS 141 (now deprecated).
