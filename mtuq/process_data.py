
import csv
import obspy
import numpy as np
import warnings

from collections import defaultdict
from copy import deepcopy
from obspy import taup
from obspy.geodetics import gps2dist_azimuth
from os.path import basename, exists
from mtuq.util import AttribDict, warn
from mtuq.util.cap import taper, parse_weight_file
from mtuq.util.signal import cut, get_arrival, m_to_deg
 

class ProcessData(object):
    """ Performs filtering, windowing and other operations on seismic data

    .. rubric :: Usage

    Processing data is a two-step procedure:

    .. code::

        function_handle = process_data(filter_type=..., **filter_parameters, 
                                       pick_type=...,   **pick_parameters,
                                       window_type=..., **window_parameters,
                                       weight_type=..., **weight_parameters)

        processed_data = function_handle(data)

    In the first step, the user supplies a set of filtering, phase-picking,
    windowing, and weighting parameters.  In the second step, an obspy stream
    is given as input and a processed stream returned as output.

    See `mtuq/examples/` for a more detailed illustration of how everything
    works in practice.
    """

    def __init__(self,
                 filter_type=None,
                 pick_type=None,
                 window_type=None,
                 weight_type=None,
                 **parameters):

        #
        # check filter parameters
        #
        if filter_type is None:
            warn('No filter_type selected.')

        elif filter_type == 'Bandpass':
            # allow filter corners to be specified in terms of either period [s]
            # or frequency [Hz]
            if 'period_min' in parameters and 'period_max' in parameters:
                assert 'freq_min' not in parameters
                assert 'freq_max' not in parameters
                parameters['freq_min'] = parameters['period_max']**-1
                parameters['freq_max'] = parameters['period_min']**-1

            if 'freq_min' not in parameters: raise ValueError
            if 'freq_max' not in parameters: raise ValueError
            assert 0 < parameters['freq_min']
            assert parameters['freq_min'] < parameters['freq_max']
            assert parameters['freq_max'] < np.inf
            self.freq_min = parameters['freq_min']
            self.freq_max = parameters['freq_max']

        elif filter_type == 'Lowpass':
            if 'period' in parameters:
                assert 'freq' not in parameters
                parameters['freq'] = parameters['period']**-1

            if 'freq' not in parameters: raise ValueError
            assert 0 < parameters['freq']
            assert parameters['freq'] < np.inf
            self.freq = parameters['freq']

        elif filter_type == 'Highpass':
            if 'period' in parameters:
                assert 'freq' not in parameters
                parameters['freq'] = parameters['period']**-1

            if 'freq' not in parameters: raise ValueError
            assert 0 <= parameters['freq'] < np.inf
            self.freq = parameters['freq']

        else:
             raise ValueError('Bad parameter: filter_type')

        self.filter_type = filter_type


        #
        # check pick parameters
        #
        if pick_type is None:
            raise Exception

        elif pick_type=='from_taup_model':
            assert 'taup_model' in parameters
            self._taup_model = parameters["taup_model"]
            self._taup = taup.TauPyModel(model=parameters["taup_model"])

        elif pick_type=='from_fk_metadata':
            assert 'fk_database' in parameters
            self._fk_database = parameters['fk_database']
            self._fk_model = basename(self._fk_database)

        elif pick_type=='from_sac_metadata':
             # nothing to check now
             pass

        elif pick_type=='from_cap_weight_file':
            raise NotImplementedError

        elif pick_type=='from_pick_file':
            assert exists(parameters['pick_file'])
            self._pick_file = parameters['pick_file']

        else:
             raise ValueError('Bad parameter: pick_type')

        self._picks = defaultdict(AttribDict)
        self.pick_type = pick_type


        #
        # check window parameters
        #
        if window_type is None:
            warn('No window_type selected.')

        elif window_type == 'cap_bw':
            assert 'window_length' in parameters

        elif window_type == 'cap_sw':
            assert 'window_length' in parameters

        else:
             raise ValueError('Bad parameter: window_type')

        self.window_type = window_type
        self.window_length = parameters['window_length']
        self._windows = AttribDict()

        if 'padding_length' in parameters:
            self.padding_length = parameters['padding_length']
        else:
            self.padding_length = 0.


        #
        # check weight parameters
        #
        if weight_type is None:
            pass

        elif weight_type == 'cap_bw':
            assert 'cap_weight_file' in parameters
            assert exists(parameters['cap_weight_file'])
            self.weights = parse_weight_file(parameters['cap_weight_file'])

            if 'scaling power' in parameters:
                self.scaling_power = parameters['scaling_power']
            else:
                self.scaling_power = 1.

            if 'scaling_distance' in parameters:
                self.scaling_distance = parameters['scaling_distance']
            else:
                self.scaling_distance = 1.e5


        elif weight_type == 'cap_sw':
            assert 'cap_weight_file' in parameters
            assert exists(parameters['cap_weight_file'])
            self.weights = parse_weight_file(parameters['cap_weight_file'])

            if 'scaling power' in parameters:
                self.scaling_power = parameters['scaling_power']
            else:
                self.scaling_power = 0.5

            if 'scaling_distance' in parameters:
                self.scaling_distance = parameters['scaling_distance']
            else:
                self.scaling_distance = 1.e5


        else:
             raise ValueError('Bad parameter: weight_type')


        self.weight_type = weight_type



    def __call__(self, traces, station=None, origin=None, overwrite=False):
        ''' 
        Carries out data processing operations on obspy streams
        MTUQ GreensTensors

        input traces: all availables traces for a given station
        type traces: obspy Stream or MTUQ GreensTensor
        '''
        if station is None:
            station = getattr(traces, 'station', None)

        if origin is None:
            origin = getattr(traces, 'origin', None)

        if origin is None:
            origin = getattr(traces, 'preliminary_origin', None)
        
        # overwrite existing data?
        if overwrite:
            traces = traces
        else:
            traces = deepcopy(traces)

        if not hasattr(traces, 'id'):
            raise Exception('Missing station identifier')
        id = traces.id

        # collect location information
        distance_in_m, azimuth, _ = gps2dist_azimuth(
            origin.latitude,
            origin.longitude,
            station.latitude,
            station.longitude)

        # collect time sampling information
        nt, dt = traces[0].stats.npts, traces[0].stats.delta

        # Tags can be added through dataset.add_tag to keep track of custom
        # metadata or support other customized uses. Here we use tags to
        # distinguish data from Green's functions and displacement time series 
        # from velcoity time series
        if not hasattr(traces, 'tags'):
            raise Exception('Missing tags attribute')
        tags = traces.tags


        if 'units:cm' in tags:
            # convert to meters
            for trace in traces:
                trace.data *= 1.e-2
            index = tags.index('units:cm')
            tags[index] = 'units:m'


        #
        # part 1: filter traces
        #

        if self.filter_type == 'Bandpass':
            for trace in traces:
                trace.detrend('demean')
                trace.detrend('linear')
                trace.taper(0.05, type='hann')
                trace.filter('bandpass', zerophase=False,
                          freqmin=self.freq_min,
                          freqmax=self.freq_max)

        elif self.filter_type == 'Lowpass':
            for trace in traces:
                trace.detrend('demean')
                trace.detrend('linear')
                trace.taper(0.05, type='hann')
                trace.filter('lowpass', zerophase=False,
                          freq=self.freq)

        elif self.filter_type == 'Highpass':
            for trace in traces:
                trace.detrend('demean')
                trace.detrend('linear')
                trace.taper(0.05, type='hann')
                trace.filter('highpass', zerophase=False,
                          freq=self.freq)

        if 'type:velocity' in tags:
            # convert to displacement
            for trace in traces:
                trace.data = np.cumsum(trace.data)*dt
            index = tags.index('type:velocity')
            tags[index] = 'type:displacement'


        #
        # part 2: determine phase picks
        #

        # Phase arrival times will be stored in a dictionary indexed by 
        # id. This allows times to be reused later when process_data is
        # called on synthetics
        if not self.pick_type:
            pass


        elif id not in self._picks:
            picks = self._picks[id]

            if self.pick_type=='from_taup_model':
                with warnings.catch_warnings():
                    # supress obspy warning that gets raised even when taup is 
                    # used correctly (someone should submit an obspy fix)
                    warnings.filterwarnings('ignore')
                    arrivals = self._taup.get_travel_times(
                        origin.depth_in_m/1000., 
                        m_to_deg(distance_in_m), 
                        phase_list=['p', 's', 'P', 'S'])
                try:
                    picks.P = get_arrival(arrivals, 'p')
                except:
                    picks.P = get_arrival(arrivals, 'P')
                try:
                    picks.S = get_arrival(arrivals, 's')
                except:
                    picks.S = get_arrival(arrivals, 'S')


            elif self.pick_type=='from_fk_metadata':
                sac_headers = obspy.read('%s/%s_%s/%s.grn.0' %
                    (self._fk_database,
                     self._fk_model,
                     str(int(np.ceil(origin.depth_in_m/1000.))),
                     str(int(np.ceil(distance_in_m/1000.)))),
                    format='sac')[0].stats.sac
                picks.P = sac_headers.t1
                picks.S = sac_headers.t2


            elif self.pick_type=='from_sac_metadata':
                sac_headers = traces[0].sac
                picks.P = sac_headers.t5
                picks.S = sac_headers.t6


            elif self.pick_type=='from_cap_weight_file':
                raise NotImplementedError


            elif self.pick_type=='from_pick_file':
                with open(self._pick_file) as file:
                    reader = csv.reader(
                        filter(lambda row: row[0]!='#', file),
                        delimiter=' ',
                        skipinitialspace=True)
                    for row in reader:
                        _id = row[0]
                        self._picks[_id].P = float(row[1])
                        self._picks[_id].S = float(row[2])



        #
        # part 3a: determine window start and end times
        #

        # Start and end times will be stored in a dictionary indexed by 
        # id. This allows times to be resued later when process_data is
        # called on synthetics
        if not self.window_type:
            pass

        elif id not in self._windows:
            origin_time = float(origin.time)
            picks = self._picks[id]

            if self.window_type == 'cap_bw':
                # reproduces CAP body wave window
                t1 = picks.P - 0.4*self.window_length
                t2 = t1 + self.window_length
                t1 += origin_time
                t2 += origin_time
                self._windows[id] = [t1, t2]

            elif self.window_type == 'cap_sw':
                # reproduces CAP surface wave window
                t3 = picks.S - 0.3*self.window_length
                t4 = t3 + self.window_length
                t3 += origin_time
                t4 += origin_time
                self._windows[id] = [t3, t4]


            elif self.window_type == 'taup_bw':
                # determine body wave window from taup calculation
                raise NotImplementedError


        #
        # part 3b: pad Green's functions
        # 
        if not self.window_type:
            pass

        else:
            window = self._windows[id]

            # using a longer window for Green's functions than for data allows
            # time-shift corrections to be efficiently computed
            # in mtuq.misfit.cap
            if 'type:greens' in tags:
                starttime = window[0] - self.padding_length
                endtime = window[1] + self.padding_length

            else: 
                starttime = window[0]
                endtime = window[1]


        #
        # part 3c: cut and taper traces
        #
        if not self.window_type:
            pass

        else:
            window = self._windows[id]
            for trace in traces:
                cut(trace, starttime, endtime)

        for trace in traces:
            taper(trace.data)


        #
        # part 4: determine weights
        #

        if not self.weight_type:
            # give all traces equal weight if weight_type is false
            for trace in traces:
                trace.weight = 1.


        elif self.weight_type == 'cap_bw':
            # applies CAP body wave weighting
            for trace in traces:
                if 'type:greens' in tags:
                    break

                if trace.stats.channel:
                    component = trace.stats.channel[-1].upper()

                    if id not in self.weights: 
                        weight = 0.
                    elif component=='Z':
                        weight = self.weights[id][1]
                    elif component=='R':
                        weight = self.weights[id][2]
                    else:
                        weight = 0.

                    if weight:
                        setattr(trace, 'weight', weight)
                    else:
                        traces.remove(trace)

            for trace in traces:
                trace.data *=\
                     (distance_in_m/self.scaling_distance)**self.scaling_power

                # ad hoc factor determined by benchmark_cap_fk.py
                trace.data *= 1.


        elif self.weight_type == 'cap_sw':
            # applies CAP surface wave weighting
            for trace in traces:
                if 'type:greens' in tags:
                    break

                if trace.stats.channel:
                    component = trace.stats.channel[-1].upper()

                    if id not in self.weights: 
                        weight = 0.
                    elif component=='Z':
                        weight = self.weights[id][3]
                    elif component=='R':
                        weight = self.weights[id][4]
                    elif component=='T':
                        weight = self.weights[id][5]
                    else:
                        weight = 0.

                    if weight:
                        setattr(trace, 'weight', weight)
                    else:
                        traces.remove(trace)


            for trace in traces:
                trace.data *=\
                     (distance_in_m/self.scaling_distance)**self.scaling_power

                # ad hoc factor determined by benchmark_cap_fk.py
                trace.data *= 1.


        return traces


