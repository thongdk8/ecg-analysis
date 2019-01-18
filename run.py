# -*- coding: utf-8 -*-
from threading import Thread
from flask import Flask, render_template

from bokeh.embed import server_document
from bokeh.layouts import column
from bokeh.models import ColumnDataSource, Slider
from bokeh.plotting import figure
from bokeh.server.server import Server
from bokeh.themes import Theme
from tornado.ioloop import IOLoop

import pandas as pd
import numpy as np
import itertools
from obspy.signal.filter import bandpass
# from sklearn.preprocessing import scale
from scipy.signal import find_peaks

from bokeh.models.widgets import RadioGroup, Button, Div
from bokeh.layouts import row, widgetbox, column
from bokeh.io import reset_output

import os
from flask import flash, request, redirect, url_for
from werkzeug.utils import secure_filename
UPLOAD_FOLDER = './uploaded_data'
ALLOWED_EXTENSIONS = set(['csv'])

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['CUR_FILE'] = 'P2sRawdata135.csv'

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


fn = '/home/thongpb/works/ECG_project/P2S_121218/P2sRawdatatyu.csv'
lf, hf = 0.25, 40
df = pd.read_csv(fn)
ecg_clean = df['P02S ECG']
ecg_idx = [i for i in range(len(ecg_clean))]
ecg_filtered = bandpass(ecg_clean, lf, hf, 250, 2, False)
ecg_filtered = np.interp(
    ecg_filtered, (ecg_filtered.min(), ecg_filtered.max()), (-1, +1))
# ecg_filtered = scale(ecg_filtered, axis=0, with_mean=True,
#                      with_std=True, copy=True)

min_g = min(ecg_filtered)
max_g = max(ecg_filtered)

crr_idx = 0

def modify_doc(doc):
    reset_output(state=None)
    print("Entering modify_doc ...")
    global ecg_idx, ecg_filtered, crr_idx

    df = pd.read_csv(os.path.join(
        app.config['UPLOAD_FOLDER'], app.config['CUR_FILE']))
    ecg_clean = df['P02S ECG']
    ecg_idx = [i for i in range(len(ecg_clean))]
    ecg_filtered = bandpass(ecg_clean, lf, hf, 250, 2, False)
    ecg_filtered = np.interp(
        ecg_filtered, (ecg_filtered.min(), ecg_filtered.max()), (-1, +1))
    # ecg_filtered = scale(ecg_filtered, axis=0, with_mean=True,
    #                     with_std=True, copy=True)
    min_g = min(ecg_filtered)
    max_g = max(ecg_filtered)

    file_name_div = Div(text='Processing on file: ' +
                        app.config['CUR_FILE'].split('/')[-1])

    div = Div(text="Quality")
    radio_group = RadioGroup(
        labels=["Good", "Neutral", "Poor"], active=0)
    button_nxt_unit = Button(label="Next Unit", button_type="success")


    marker_line_st = ColumnDataSource(data=dict(x=[0, 0], y=[min_g, max_g]))
    marker_line_en = ColumnDataSource(data=dict(x=[0, 0], y=[min_g, max_g]))
    s2 = ColumnDataSource(data=dict(x=[], y=[]))

    sx = figure(width=1300, height=300, title="ecg_filtered "+str(lf) +
                "-"+str(hf)+"Hz", x_axis_label='time', y_axis_label='acc')
    sx.line(ecg_idx, ecg_filtered, legend="ecg_filtered "+str(lf) +
            "-"+str(hf)+"Hz", line_color="red", line_width=1)
    sx.line('x', 'y', source=marker_line_st,
            legend="current unit ", line_color="blue", line_width=1)
    sx.line('x', 'y', source=marker_line_en,
            legend="current unit ", line_color="blue", line_width=1)
    sx1 = figure(width=800, height=300, title="ecg_filtered "+str(lf) +
                "-"+str(hf)+"Hz", x_axis_label='time', y_axis_label='acc')
    sx1.line('x', 'y', source=s2, legend="ecg_filtered unit "+str(lf) +
            "-"+str(hf)+"Hz", line_color="red", line_width=1)

    peaks, _ = find_peaks(ecg_filtered, distance=150)

    crr_idx = 0
    def my_nxt_unit_handler():
        global crr_idx, ecg_filtered

        st = int(max(0, peaks[crr_idx] -
                     (peaks[crr_idx + 1] - peaks[crr_idx]) / 2))
        en = int(
            min(peaks[crr_idx] + (peaks[crr_idx + 1] - peaks[crr_idx]) / 2, ecg_idx[-1]))
        unit_idx = ecg_idx[st:en]
        unit_data = ecg_filtered[st:en]
        print("\nentering set unit data", "crr len(x)", len(
            s2.data['x']), "crr len(y)", len(s2.data['y']))
        s2.data['x'] = unit_idx
        print("have set x", "crr len(x)", len(
            s2.data['x']), "crr len(y)", len(s2.data['y']))
        s2.data['y'] = unit_data
        print("have set y", "crr len(x)", len(
            s2.data['x']), "crr len(y)", len(s2.data['y']))

        marker_line_st.data['x'] = [st, st]
        marker_line_en.data['x'] = [en, en]

        print("crr marked quality: ",
              radio_group.labels[radio_group.active], '\n')

        crr_idx += 1

    button_nxt_unit.on_click(my_nxt_unit_handler)
    graphs = column(
        list(itertools.chain.from_iterable([[sx, sx1, widgetbox(div)]])))

    doc.add_root(widgetbox(file_name_div))
    doc.add_root(graphs)
    doc.add_root(row(widgetbox(radio_group), widgetbox(button_nxt_unit)))
    doc.theme = Theme(filename="theme.yaml")



@app.route('/', methods=['GET'])
def bkapp_page():
    script = server_document('http://localhost:5006/bkapp')
    return render_template("embed.html", script=script, template="Flask")


def bk_worker():
    server = Server({'/bkapp': modify_doc}, io_loop=IOLoop(),
                    allow_websocket_origin=["localhost:8000"])
    server.start()
    server.io_loop.start()


Thread(target=bk_worker).start()


@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        # if user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            app.config['CUR_FILE'] = filename
            # return redirect(url_for('uploaded_file',
            #                         filename=filename))
    return redirect('/')

if __name__ == '__main__':
    # print('Opening single process Flask app with embedded Bokeh application on http://localhost:8000/')
    # print()
    app.run()
