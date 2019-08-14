#!/usr/bin/env python

import os
import numpy as np

from mtuq import read, open_db, download_greens_tensors
from mtuq.graphics import plot_data_greens, plot_beachball
from mtuq.grid import DoubleCoupleGridRandom
from mtuq.grid_search import grid_search
from mtuq.misfit import Misfit
from mtuq.process_data import ProcessData
from mtuq.util import fullpath
from mtuq.util.cap import Trapezoid



if __name__=='__main__':
    #
    # Double-couple inversion example
    # 
    # Carries out grid search over 50,000 randomly chosen double-couple 
    # moment tensors
    #
    # USAGE
    #   python SerialGridSearch.DoubleCouple.py
    #
    # A typical runtime is about 10 minutes. For faster results try 
    # GridSearch.DoubleCouple.py, which runs the same inversion in parallel
    #


    #
    # Here we specify the data used for the inversion. The event is an 
    # Mw~4 Alaska earthquake
    #

    path_data=    fullpath('data/examples/20090407201255351/*.[zrt]')
    path_weights= fullpath('data/examples/20090407201255351/weights.dat')
    event_name=   '20090407201255351'
    model=        'ak135'


    #
    # Body- and surface-wave data are processed separately and held separately 
    # in memory
    #

    process_bw = ProcessData(
        filter_type='Bandpass',
        freq_min= 0.1,
        freq_max= 0.333,
        pick_type='from_taup_model',
        taup_model=model,
        window_type='cap_bw',
        window_length=15.,
        padding_length=2.,
        weight_type='cap_bw',
        cap_weight_file=path_weights,
        )

    process_sw = ProcessData(
        filter_type='Bandpass',
        freq_min=0.025,
        freq_max=0.0625,
        pick_type='from_taup_model',
        taup_model=model,
        window_type='cap_sw',
        window_length=150.,
        padding_length=10.,
        weight_type='cap_sw',
        cap_weight_file=path_weights,
        )


    #
    # We define misfit as a sum of indepedent body- and surface-wave 
    # contributions
    #

    misfit_bw = Misfit(
        time_shift_max=2.,
        time_shift_groups=['ZR'],
        )

    misfit_sw = Misfit(
        time_shift_max=10.,
        time_shift_groups=['ZR','T'],
        )


    #
    # Following obspy, we use the variable name "source" for the mechanism of
    # an event and "origin" for the location of an event
    #

    sources = DoubleCoupleGridRandom(
        npts=50000,
        magnitude=4.5)

    wavelet = Trapezoid(
        magnitude=4.5)


    #
    # The main I/O work starts now
    #

    print 'Reading data...\n'
    data = read(path_data, format='sac',
        event_id=event_name,
        tags=['units:cm', 'type:velocity']) 

    data.sort_by_distance()

    stations = data.get_stations()
    origin = data.get_origins()[0]


    print 'Processing data...\n'
    data_bw = data.map(process_bw)
    data_sw = data.map(process_sw)

    print 'Reading Green''s functions...\n'
    greens = download_greens_tensors(stations, origin, model)

    print 'Processing Greens functions...\n'
    greens.convolve(wavelet)
    greens_bw = greens.map(process_bw)
    greens_sw = greens.map(process_sw)


    #
    # The main computational work starts nows
    #

    print 'Evaluating body wave misfit...\n'

    results_bw = grid_search(
        data_bw, greens_bw, misfit_bw, origin, sources)

    print 'Evaluating surface wave misfit...\n'

    results_sw = grid_search(
        data_sw, greens_sw, misfit_sw, origin, sources)

    best_misfit = (results_bw + results_sw).min()
    best_source = sources.get((results_bw + results_sw).argmin())


    #
    # Saving results
    #

    print 'Saving results...\n'

    plot_data_greens(event_name+'.png', 
        data_bw, data_sw, greens_bw, greens_sw, process_bw, process_sw, 
        misfit_bw, misfit_sw, stations, origin, best_source)

    plot_beachball(event_name+'_beachball.png', best_source)

    #grid.save(event_name+'.h5', {'misfit': results})

    print 'Finished\n'

