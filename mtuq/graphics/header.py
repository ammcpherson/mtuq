
#
# graphics/header.py - figure headers and text
#


import numpy as np
import os
from matplotlib import pyplot
from matplotlib.font_manager import FontProperties
from mtuq.event import MomentTensor
from mtuq.graphics.beachball import gray, plot_beachball
from mtuq.util.math import to_delta_gamma
from obspy.core import AttribDict


class Base(object):
    """ Base class for storing and writing text to a matplotlib figure
    """
    def __init__(self):
        raise NotImplementedError("Must be implemented by subclass")


    def _get_axis(self, height, fig=None):
        """ Returns matplotlib axes of given height along top of figure
        """
        if fig is None:
            fig = pyplot.gcf()
        width, figure_height = fig.get_size_inches()

        assert height < figure_height, Exception(
             "Header height exceeds entire figure height. Please double check "
             "input arguments.")
               
        x0 = 0.
        y0 = 1.-height/figure_height

        ax = fig.add_axes([x0, y0, 1., height/figure_height])
        ax.set_xlim([0., width])
        ax.set_ylim([0., height])

        # hides axes lines, ticks, and labels
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.get_xaxis().set_ticks([])
        ax.get_yaxis().set_ticks([])

        return ax


    def write(self, *args, **kwargs):
        raise NotImplementedError("Must be implemented by subclass")



class TextHeader(Base):
    """ Prints header text from a list ((xp, yp, text), ...)
    """
    def __init__(self, items):
        # validates items
        for item in items:
            assert len(item) >= 3
            xp, yp, text  = item[0], item[1], item[2]
            assert 0. <= xp <= 1.
            assert 0. <= yp <= 1.

        self.items = items


    def write(self, height, width, margin_left, margin_top):
        ax = self._get_axis(height)

        for item in self.items:
            xp, yp, text = item[0], item[1], item[2]
            kwargs = {}
            if len(item) > 3:
                kwargs = item[3]

            _write_text(text, xp, yp, ax, **kwargs)



class MomentTensorHeader(Base):
    """ Stores information from a moment tensor inversion and writes UAF-style
    text to the top of a matplotlib figure
    """
    def __init__(self, event_name, process_bw, process_sw, misfit_bw, misfit_sw,
        model, solver, mt, lune_dict, origin, best_misfit_bw, best_misfit_sw):

        self.event_name = event_name
        self.magnitude = mt.magnitude()
        self.depth_in_m = origin.depth_in_m
        self.depth_in_km = origin.depth_in_m/1000.
        self.model = model
        self.solver = solver
        self.mt = mt
        self.lune_dict = lune_dict
        self.origin = origin
        self.best_misfit_bw = best_misfit_bw[0]*1.e10
        self.best_misfit_sw = best_misfit_sw[0]*1.e10
        self.best_misfit = self.best_misfit_bw + self.best_misfit_sw

        self.process_bw = process_bw
        self.process_sw = process_sw
        self.misfit_bw = process_bw
        self.misfit_sw = process_sw
        self.norm = misfit_bw.norm

        if self.process_bw:
            self.bw_T_min = process_bw.freq_max**-1
            self.bw_T_max = process_bw.freq_min**-1
            self.bw_win_len = process_bw.window_length

        if self.process_sw:
            self.sw_T_min = process_sw.freq_max**-1
            self.sw_T_max = process_sw.freq_min**-1
            self.sw_win_len = process_sw.window_length


    def display_source(self, ax, height, offset):

        #
        # If ObsPy plotted focal mechanisms correctly we could do the following
        #

        #from obspy.imaging.beachball import beach
        ## beachball size
        #diameter = 0.75*height
        #xp = 0.50*diameter + offset
        #yp = 0.45*height
        #ax.add_collection(
        #    beach(self.mt, xy=(xp, yp), width=diameter,
        #    linewidth=0.5, facecolor=gray))


        #
        # Instead, we must use this workaround
        #

        # beachball size
        diameter = 0.75*height

        # beachball placement
        xp = offset
        yp = 0.075*height

        plot_beachball('tmp.png', self.mt)
        img = pyplot.imread('tmp.png')

        try:
            os.remove('tmp.png')
            os.remove('tmp.ps')
        except:
            pass

        ax.imshow(img, extent=(xp,xp+diameter,yp,yp+diameter))


    def write(self, height, width, margin_left, margin_top):
        """ Writes header text to current figure
        """
        ax = self._get_axis(height)

        px0 = (margin_left + 0.75*height)/width + 0.05
        py0 = 0.8 - margin_top/height

        self.display_source(ax, height, margin_left)


        # write text line #1
        px = px0
        py = py0
        line = '%s  $M_w$ %.2f  Depth %d km  %s' % (
            self.event_name, self.magnitude, self.depth_in_km, _lat_lon(self.origin))
        _write_bold(line, px, py, ax, fontsize=16)


        # write text line #2
        px = px0
        py -= 0.175
        line = u'Model %s   Solver %s   %s norm %.1e' % \
                (self.model, self.solver, self.norm, self.best_misfit)
        _write_text(line, px, py, ax, fontsize=14)


        # write text line #3
        px = px0
        py -= 0.175

        if self.process_bw and self.process_bw:
            line = ('body waves:  %.1f - %.1f s passband, %.1f s window ;  ' +\
                    'surface waves: %.1f - %.1f s passband, %.1f s window ') %\
                    (self.bw_T_min, self.bw_T_max, self.bw_win_len,
                     self.sw_T_min, self.sw_T_max, self.sw_win_len)

        elif self.process_sw:
            line = 'passband %.1f - %.1f s,  window length %.1f s ' %\
                    (self.sw_T_min, self.sw_T_max, self.sw_win_len)

        _write_text(line, px, py, ax, fontsize=14)


        # write text line #4
        px = px0
        py -= 0.175
        line = _focal_mechanism(self.lune_dict)
        line +=  _delta_gamma(self.lune_dict)
        _write_text(line, px, py, ax, fontsize=14)


class ForceHeader(Base):
    """ Stores information from a force inversion and writes UAF-style to the 
    top of a matplotlib figure
    """

    def __init__(self, event_name, process_bw, process_sw, misfit_bw, misfit_sw,
        model, solver, force, force_dict, origin, best_misfit_bw, best_misfit_sw):

        self.event_name = event_name
        self.depth_in_m = origin.depth_in_m
        self.depth_in_km = origin.depth_in_m/1000.
        self.model = model
        self.solver = solver
        self.force = force
        self.force_dict = force_dict
        self.origin = origin
        self.best_misfit_bw = best_misfit_bw[0]*1.e10
        self.best_misfit_sw = best_misfit_sw[0]*1.e10
        self.best_misfit = self.best_misfit_bw + self.best_misfit_sw

        self.process_bw = process_bw
        self.process_sw = process_sw
        self.misfit_bw = process_bw
        self.misfit_sw = process_sw
        self.norm = misfit_bw.norm

        if self.process_bw:
            self.bw_T_min = process_bw.freq_max**-1
            self.bw_T_max = process_bw.freq_min**-1
            self.bw_win_len = process_bw.window_length

        if self.process_sw:
            self.sw_T_min = process_sw.freq_max**-1
            self.sw_T_max = process_sw.freq_min**-1
            self.sw_win_len = process_sw.window_length


    def write(self, height, width, margin_left, margin_top):

        ax = self._get_axis(height)

        px0 = (margin_left + 0.75*height)/width + 0.05
        py0 = 0.8 - margin_top/height


        # write text line #1
        px = px0
        py = py0
        line = '%s   $F$ %.2e Newtons   Depth %d km   %s' % (
            self.event_name, self.force_dict['F0'], self.depth_in_km, _lat_lon(self.origin))
        _write_bold(line, px, py, ax, fontsize=16)


        # write text line #2
        px = px0
        py -= 0.175
        line = u'Model %s   Solver %s   %s norm %.1e' % \
                (self.model, self.solver, self.norm, self.best_misfit)
        _write_text(line, px, py, ax, fontsize=14)


        # write text line #3
        px = px0
        py -= 0.175

        if self.process_bw and self.process_bw:
            line = ('body waves:  %.1f - %.1f s passband, %.1f s window ;  ' +\
                    'surface waves: %.1f - %.1f s passband, %.1f s window ') %\
                    (self.bw_T_min, self.bw_T_max, self.bw_win_len,
                     self.sw_T_min, self.sw_T_max, self.sw_win_len)

        elif self.process_sw:
            line = '%.1f - %.1f s passband, %.1f s window ' %\
                    (self.sw_T_min, self.sw_T_max, self.sw_win_len)

        _write_text(line, px, py, ax, fontsize=14)


        # write text line #4
        px = px0
        py -= 0.175
        line = _phi_theta(self.force_dict)
        _write_text(line, px, py, ax, fontsize=14)


    def display_source(self):
        raise NotImplementedError



def _lat_lon(origin):
    if origin.latitude >= 0:
        latlon = '%.1f%s%s' % (+origin.latitude, u'\N{DEGREE SIGN}', 'N')
    else:
        latlon = '%.1f%s%s' % (-origin.latitude, u'\N{DEGREE SIGN}', 'S')

    if origin.longitude > 0:
        latlon += '% .1f%s%s' % (+origin.longitude, u'\N{DEGREE SIGN}', 'E')
    else:
        latlon += '% .1f%s%s' % (-origin.longitude, u'\N{DEGREE SIGN}', 'W')

    return latlon


def _focal_mechanism(lune_dict):
    strike = lune_dict['kappa']

    try:
        dip = np.degrees(np.arccos(lune_dict['h']))
    except:
        dip = lune_dict['theta']

    slip = lune_dict['sigma']

    return ("strike  dip  slip:  %d  %d  %d;  " %
        (strike, dip, slip))


def _delta_gamma(lune_dict):
    try:
        v, w = lune_dict['v'], lune_dict['w']
        delta, gamma = to_delta_gamma(v, w)
    except:
        delta, gamma = lune_dict['delta'], lune_dict['gamma']

    return '  %s  %s:  %d  %d' % (u'\u03B3', u'\u03B4', delta, gamma)


def _phi_theta(force_dict):
    try:
        phi, theta = force_dict['phi'], force_dict['theta']
    except:
        phi, h = force_dict['phi'], force_dict['h']
        theta = np.degrees(np.arccos(h))

    return '%s  %s:  %d  %d' % (u'\u03C6', u'\u03B8', phi, theta)


def _write_text(text, x, y, ax, fontsize=12, **kwargs):
    pyplot.text(x, y, text, fontsize=fontsize, transform=ax.transAxes,  **kwargs)


def _write_bold(text, x, y, ax, fontsize=14):
    font = FontProperties()
    #font.set_weight('bold')
    pyplot.text(x, y, text, fontproperties=font, fontsize=fontsize,
        transform=ax.transAxes)


def _write_italic(text, x, y, ax, fontsize=12):
    font = FontProperties()
    font.set_style('italic')
    pyplot.text(x, y, text, fontproperties=font, fontsize=fontsize,
        transform=ax.transAxes)


