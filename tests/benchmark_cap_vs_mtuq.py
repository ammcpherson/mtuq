
import os
import numpy as np

from mtuq import read, open_db, download_greens_tensors
from mtuq.graphics import plot_data_synthetics, plot_beachball
from mtuq.grid import DoubleCoupleGridRandom
from mtuq.grid_search import grid_search
from mtuq.misfit import Misfit
from mtuq.process_data import ProcessData
from mtuq.util import fullpath
from mtuq.util.cap import Trapezoid



if __name__=='__main__':
    #
    # Given seven "fundamental" moment tensors, generates MTUQ synthetics and
    # compares with corresponding CAP/FK synthetics
    #
    # Before running this script, it is necessary to unpack the CAP/FK 
    # synthetics using data/tests/unpack.bash
    #
    # This script is similar to examples/SerialGridSearch.DoubleCouple.py,
    # except here we consider only seven grid points rather than an entire
    # grid, and here the final plots are a comparison of MTUQ and CAP/FK 
    # synthetics rather than a comparison of data and synthetics
    #
    # Because of the idiosyncratic way CAP implements source-time function
    # convolution, it's not expected that CAP and MTUQ synthetics will match 
    # exactly. CAP's "conv" function results in systematic magnitude-
    # dependent shifts between origin times and arrival times. We deal with 
    # this by applying magnitude-dependent time-shifts to MTUQ synthetics 
    # (which normally lack such shifts) at the end of the benchmark. Even with
    # this correction, the match will not be exact because CAP applies the 
    # shifts before tapering and MTUQ after tapering. The resulting mismatch 
    # will usually be apparent in body-wave windows, but not in surface-wave 
    # windows
    #
    # Note that CAP works with dyne,cm and MTUQ works with N,m, so to make
    # comparisons we convert CAP output from the former to the latter
    #
    # The CAP/FK synthetics used in the comparison were generated by 
    # uafseismo/capuaf:46dd46bdc06e1336c3c4ccf4f99368fe99019c88
    # using the following commands
    #
    # source #0 (explosion):
    # cap.pl -H0.02 -P1/15/60 -p1 -S2/10/0 -T15/150 -D1/1/0.5 -C0.1/0.333/0.025/0.0625 -Y1 -Zweight_test.dat -Mscak_34 -m4.5 -I1 -R0/1.178/90/45/90 20090407201255351
    #
    # source #1 (on-diagonal)
    # cap.pl -H0.02 -P1/15/60 -p1 -S2/10/0 -T15/150 -D1/1/0.5 -C0.1/0.333/0.025/0.0625 -Y1 -Zweight_test.dat -Mscak_34 -m4.5 -I1 -R-0.333/0.972/90/45/90 20090407201255351
    #
    # source #2 (on-diagonal)
    # cap.pl -H0.02 -P1/15/60 -p1 -S2/10/0 -T15/150 -D1/1/0.5 -C0.1/0.333/0.025/0.0625 -Y1 -Zweight_test.dat -Mscak_34 -m4.5 -I1 -R-0.333/0.972/45/90/180 20090407201255351
    #
    # source #3 (on-diagonal):
    # cap.pl -H0.02 -P1/15/60 -p1 -S2/10/0 -T15/150 -D1/1/0.5 -C0.1/0.333/0.025/0.0625 -Y1 -Zweight_test.dat -Mscak_34 -m4.5 -I1 -R-0.333/0.972/45/90/0 20090407201255351
    #
    # source #4 (off-diagonal):
    # cap.pl -H0.02 -P1/15/60 -p1 -S2/10/0 -T15/150 -D1/1/0.5 -C0.1/0.333/0.025/0.0625 -Y1 -Zweight_test.dat -Mscak_34 -m4.5 -I1 -R0/0/90/90/90 20090407201255351
    #
    # source #5 (off-diagonal):
    # cap.pl -H0.02 -P1/15/60 -p1 -S2/10/0 -T15/150 -D1/1/0.5 -C0.1/0.333/0.025/0.0625 -Y1 -Zweight_test.dat -Mscak_34 -m4.5 -I1 -R0/0/90/0/0 20090407201255351
    #
    # source #6 (off-diagonal):
    # cap.pl -H0.02 -P1/15/60 -p1 -S2/10/0 -T15/150 -D1/1/0.5 -C0.1/0.333/0.025/0.0625 -Y1 -Zweight_test.dat -Mscak_34 -m4.5 -I1 -R0/0/0/90/180 20090407201255351
    #


    # by default, the script runs with figure generation and error checking
    # turned on
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--no_checks', action='store_true')
    parser.add_argument('--no_figures', action='store_true')
    args = parser.parse_args()
    run_checks = (not args.no_checks)
    run_figures = (not args.no_figures)


    from mtuq.util.cap import\
        get_synthetics_cap, get_synthetics_mtuq,\
        get_data_cap, compare_cap_mtuq


    # the following directories correspond to the moment tensors in the list 
    # "grid" below
    paths = []
    paths += [fullpath('data/tests/benchmark_cap/20090407201255351/0')]
    paths += [fullpath('data/tests/benchmark_cap/20090407201255351/1')]
    paths += [fullpath('data/tests/benchmark_cap/20090407201255351/2')]
    paths += [fullpath('data/tests/benchmark_cap/20090407201255351/3')]
    paths += [fullpath('data/tests/benchmark_cap/20090407201255351/4')]
    paths += [fullpath('data/tests/benchmark_cap/20090407201255351/5')]
    paths += [fullpath('data/tests/benchmark_cap/20090407201255351/6')]


    path_greens=  fullpath('data/tests/benchmark_cap/greens/scak')
    path_data=    fullpath('data/examples/20090407201255351/*.[zrt]')
    path_weights= fullpath('data/tests/benchmark_cap/20090407201255351/weights.dat')
    event_name=   '20090407201255351'
    model=        'scak'


    process_bw = ProcessData(
        filter_type='Bandpass',
        freq_min= 0.1,
        freq_max= 0.333,
        pick_type='from_fk_metadata',
        fk_database=path_greens,
        window_type='cap_bw',
        window_length=15.,
        padding_length=0,
        weight_type='cap_bw',
        cap_weight_file=path_weights,
        )

    process_sw = ProcessData(
        filter_type='Bandpass',
        freq_min=0.025,
        freq_max=0.0625,
        pick_type='from_fk_metadata',
        fk_database=path_greens,
        window_type='cap_sw',
        window_length=150.,
        padding_length=0,
        weight_type='cap_sw',
        cap_weight_file=path_weights,
        )


    misfit_bw = Misfit(
        time_shift_max=0.,
        time_shift_groups=['ZR'],
        )

    misfit_sw = Misfit(
        time_shift_max=0.,
        time_shift_groups=['ZR','T'],
        )


    #
    # Next we specify the source parameter grid
    #

    sources = [
       # Mrr, Mtt, Mpp, Mrt, Mrp, Mtp
       np.sqrt(1./3.)*np.array([1., 1., 1., 0., 0., 0.]), # explosion
       np.array([1., 0., 0., 0., 0., 0.]), # source 1 (on-diagonal)
       np.array([0., 1., 0., 0., 0., 0.]), # source 2 (on-diagonal)
       np.array([0., 0., 1., 0., 0., 0.]), # source 3 (on-diagonal)
       np.sqrt(1./2.)*np.array([0., 0., 0., 1., 0., 0.]), # source 4 (off-diagonal)
       np.sqrt(1./2.)*np.array([0., 0., 0., 0., 1., 0.]), # source 5 (off-diagonal)
       np.sqrt(1./2.)*np.array([0., 0., 0., 0., 0., 1.]), # source 6 (off-diagonal)
       ]

    Mw = 4.5
    M0 = 10.**(1.5*Mw + 9.1) # units: N-m
    for mt in sources:
        mt *= np.sqrt(2)*M0

    wavelet = Trapezoid(
        magnitude=Mw)


    #
    # The benchmark starts now
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
    db = open_db(path_greens, format='FK', model=model)
    greens = db.get_greens_tensors(stations, origin)

    print 'Processing Greens functions...\n'
    greens.convolve(wavelet)
    greens_bw = greens.map(process_bw)
    greens_sw = greens.map(process_sw)


    depth = int(origin.depth_in_m/1000.)+1
    name = '_'.join([model, str(depth), event_name])


    print 'Comparing waveforms...'

    for _i, mt in enumerate(sources):
        print '  %d of %d' % (_i+1, len(sources))

        cap_bw, cap_sw = get_synthetics_cap(
            data_bw, data_sw, paths[_i], name)

        mtuq_bw, mtuq_sw = get_synthetics_mtuq(
            data_bw, data_sw, greens_bw, greens_sw, mt)

        if run_figures:
            plot_data_synthetics('cap_vs_mtuq_'+str(_i)+'.png',
                cap_bw, cap_sw, mtuq_bw, mtuq_sw, 
                stations, origin, trace_labels=False)

        if run_checks:
            compare_cap_mtuq(
                cap_bw, cap_sw, mtuq_bw, mtuq_sw)

    if run_figures:
        # "bonus" figure comparing how CAP processes observed data with how
        # MTUQ processes observed data
        mtuq_sw, mtuq_bw = data_bw, data_sw

        cap_sw, cap_bw = get_data_cap(
            data_bw, data_sw, paths[0], name)

        plot_data_synthetics('cap_vs_mtuq_data.png',
            cap_bw, cap_sw, mtuq_bw, mtuq_sw, 
            stations, origin, trace_labels=False, normalize=False)

    print '\nSUCCESS\n'

